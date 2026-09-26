"""Phase 3: the star schema keeps every row it was given, and says what it could not resolve.

The spec's test for this phase is that the join loses no more rows than the match
report predicts. That is what most of these check: the facts carry exactly the rows
the loaders produced, the hours still add up to the published totals, and a title
with no IMDb id still has its facts.

They run against the built database and skip without it, because building it takes
several minutes; `python -m src.model` builds it.
"""
from __future__ import annotations

import duckdb
import pytest

from src import config, ingest_engagement, ingest_top10, model

needs_model = pytest.mark.skipif(not model.MODEL_DB.exists(),
                                 reason="model not built - run python -m src.model")


@pytest.fixture(scope="module")
def con():
    return duckdb.connect(str(model.MODEL_DB), read_only=True)


def one(con, sql):
    return con.execute(sql).fetchone()[0]


# --- the surrogate key -----------------------------------------------------------------

def test_title_id_is_stable_across_runs_and_distinguishes_years():
    """A positional id would shift the moment Netflix publishes another report."""
    assert model.title_id("tv", "wednesday", 2022) == model.title_id("tv", "wednesday", 2022)
    assert model.title_id("tv", "wednesday", 2022) != model.title_id("tv", "wednesday", None)
    assert model.title_id("tv", "shameless", 2011) != model.title_id("tv", "shameless", 2004)
    assert model.title_id("film", "wednesday", 2022) != model.title_id("tv", "wednesday", 2022)
    assert model.title_id("tv", "wednesday", 2022).startswith("t_")


def test_title_id_ignores_how_a_missing_year_is_spelled():
    import numpy as np
    assert model.title_id("film", "leo", None) == model.title_id("film", "leo", np.nan)


# --- nothing is lost -------------------------------------------------------------------

@needs_model
def test_engagement_facts_carry_every_published_row(con):
    source = ingest_engagement.load()
    source = source[~source.is_catch_all]
    assert one(con, "SELECT count(*) FROM fact_engagement_halfyear") == len(source)
    assert one(con, "SELECT sum(hours_viewed) FROM fact_engagement_halfyear") == int(source.hours_viewed.sum())
    assert one(con, "SELECT sum(views) FROM fact_engagement_halfyear") == int(source.views.sum())


@needs_model
def test_top10_facts_keep_every_slot_including_the_ones_with_no_title(con):
    source = ingest_top10.load()
    assert one(con, "SELECT count(*) FROM fact_top10_weekly") == len(source)
    # Still ten rows per week and category, as in the file.
    assert one(con, """SELECT count(*) FROM (
        SELECT week, category, count(*) n FROM fact_top10_weekly GROUP BY 1, 2) WHERE n <> 10""") == 0
    assert one(con, "SELECT sum(weekly_hours_viewed) FROM fact_top10_weekly") == int(source.weekly_hours_viewed.sum())


@needs_model
def test_no_fact_points_at_a_title_that_is_not_there(con):
    assert one(con, """SELECT count(*) FROM fact_engagement_halfyear f
                       LEFT JOIN dim_title t USING (title_id) WHERE t.title_id IS NULL""") == 0
    assert one(con, """SELECT count(*) FROM fact_top10_weekly f
                       LEFT JOIN dim_title t USING (title_id)
                       WHERE f.title_id IS NOT NULL AND t.title_id IS NULL""") == 0
    assert one(con, """SELECT count(*) FROM fact_pageviews f
                       LEFT JOIN dim_title t USING (title_id) WHERE t.title_id IS NULL""") == 0


@needs_model
def test_unmatched_titles_are_kept_with_their_facts(con):
    """Checkpoint 2: unmatched titles stay in the data, flagged. This is that decision,
    written as a test, so dropping them later cannot happen quietly."""
    unmatched = one(con, "SELECT count(*) FROM dim_title WHERE NOT matched")
    assert unmatched > 0
    assert one(con, """SELECT count(*) FROM dim_title WHERE NOT matched AND imdb_tconst IS NOT NULL""") == 0
    # A rejected near-miss candidate is kept, but never where a query would read it as the answer.
    assert one(con, "SELECT count(*) FROM dim_title WHERE rejected_candidate IS NOT NULL") > 0
    assert one(con, """SELECT count(*) FROM dim_title
                       WHERE matched AND rejected_candidate IS NOT NULL""") == 0
    with_facts = one(con, """SELECT count(DISTINCT t.title_id) FROM dim_title t
                             JOIN fact_engagement_halfyear f USING (title_id) WHERE NOT t.matched""")
    assert with_facts == unmatched


@needs_model
def test_every_title_is_unique_and_every_matched_one_has_an_id(con):
    assert one(con, "SELECT count(*) - count(DISTINCT title_id) FROM dim_title") == 0
    assert one(con, "SELECT count(*) FROM dim_title WHERE matched AND imdb_tconst IS NULL") == 0
    # One IMDb id may legitimately carry several titles - the seasons of a series - but
    # a title must never carry two ids.
    assert one(con, """SELECT count(*) FROM (SELECT title_id, count(DISTINCT imdb_tconst) n
                       FROM dim_title WHERE imdb_tconst IS NOT NULL GROUP BY 1) WHERE n > 1""") == 0


# --- the shape the spec asked for ------------------------------------------------------

@needs_model
def test_the_period_is_data_not_schema(con):
    """Netflix goes annual in 2027. A period is a row with a start and an end, so that
    report is an insert, not a migration."""
    periods = con.execute("SELECT period, period_start, period_end, source_sha256 FROM dim_period "
                          "ORDER BY period_start").fetchdf()
    assert len(periods) == len(config.ENGAGEMENT_PERIODS)
    assert (periods.period_end > periods.period_start).all()
    assert periods.source_sha256.notna().all(), "every period should name the file it came from"
    # No gaps and no overlaps between consecutive periods.
    gaps = [(b.period_start - a.period_end).days for a, b in zip(periods.itertuples(), periods.iloc[1:].itertuples())]
    assert set(gaps) == {1}, f"periods should be contiguous, found gaps of {sorted(set(gaps))} days"


@needs_model
def test_top10_scope_is_recorded_wherever_a_title_was_resolved(con):
    """A week outside the report periods can only be matched by name. That is weaker, and
    the Berlin retitling is why: the file's current name for a 2021 week may be a name the
    title acquired years later."""
    assert one(con, """SELECT count(*) FROM fact_top10_weekly
                       WHERE (title_id IS NULL) <> (title_match_scope IS NULL)""") == 0
    scopes = set(con.execute("SELECT DISTINCT title_match_scope FROM fact_top10_weekly").fetchdf()
                 .title_match_scope.dropna())
    assert scopes <= {"period", "name_only"}
    # A handful of weeks inside a report period still fall back to name_only, and every
    # one of them must have a real reason: the name the Top 10 file shows was not
    # published in that period's report at all. Berlin is the case this catches - it
    # charted in December 2023 under a name it was only given in 2026.
    unexplained = one(con, """
        SELECT count(*) FROM fact_top10_weekly f
        JOIN dim_period p ON f.week BETWEEN p.period_start AND p.period_end
        WHERE f.title_match_scope = 'name_only'
          AND EXISTS (SELECT 1 FROM fact_engagement_halfyear e
                      WHERE e.period = p.period AND e.published_title = f.charting_title)""")
    assert unexplained == 0, "an in-period fallback is only defensible when that period never published the name"


@needs_model
def test_each_view_answers_a_dashboard_question(con):
    for view in ["v_title_period", "v_top10_longevity", "v_weekly_demand", "v_earning_its_place"]:
        assert one(con, f"SELECT count(*) FROM {view}") >= 0
    # Every title with engagement appears once in the metric view, with its hours intact.
    assert one(con, "SELECT count(*) FROM v_earning_its_place") == one(con, "SELECT count(*) FROM dim_title")
    assert one(con, "SELECT sum(hours) FROM v_earning_its_place") == \
           one(con, "SELECT sum(hours_viewed) FROM fact_engagement_halfyear")
    assert one(con, """SELECT count(*) FROM v_earning_its_place WHERE weeks_available < 1""") == 0
    assert one(con, """SELECT count(*) FROM v_earning_its_place
                       WHERE available_from_source NOT IN
                       ('netflix_release_date','imdb_start_year','first_period_reported')""") == 0


@needs_model
def test_pageviews_are_one_article_per_title(con):
    n = one(con, "SELECT count(*) FROM fact_pageviews")
    if n == 0:
        pytest.skip("Wikipedia pageviews not fetched yet - run python -m src.fetch_demand")
    assert one(con, """SELECT count(*) FROM (SELECT title_id, count(DISTINCT article) a
                       FROM fact_pageviews GROUP BY 1) WHERE a > 1""") == 0
    assert one(con, "SELECT count(*) FROM fact_pageviews WHERE views < 0") == 0
    assert one(con, """SELECT count(*) FROM dim_title
                       WHERE wikipedia_article IS NOT NULL AND NOT matched""") == 0


# --- the demand source -----------------------------------------------------------------

def test_one_imdb_id_with_several_wikipedia_articles_picks_the_matching_one():
    """tt13207736 is the Monster anthology: Wikidata offers the series article and one
    per season, so taking the first alphabetically sent every season to Ed Gein."""
    from src import fetch_demand
    found = ["Monster:_The_Ed_Gein_Story", "Monster:_The_Jeffrey_Dahmer_Story",
             "Monster_(American_TV_series)"]
    assert fetch_demand.pick_article("Monster: The Ed Gein Story: Season 1", found) == \
        "Monster:_The_Ed_Gein_Story"
    assert fetch_demand.pick_article("Monster: The Jeffrey Dahmer Story: Limited Series", found) == \
        "Monster:_The_Jeffrey_Dahmer_Story"
    assert fetch_demand.pick_article("Wednesday: Season 2", ["Wednesday_(TV_series)"]) == \
        "Wednesday_(TV_series)"
