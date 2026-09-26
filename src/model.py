"""Phase 3: the unified model — a small star schema in DuckDB.

    dim_title      one row per film or series, carrying the resolved IMDb id
    dim_period     one row per published report, with the file it came from
    fact_engagement_halfyear   one row per season per report period
    fact_top10_weekly          one row per Top 10 slot per week
    fact_pageviews             one row per title per day of English Wikipedia views

Three decisions the shape encodes:

* **A fact row is a season in a period; a dim row is the whole title.** Netflix
  reports 'Wednesday: Season 2' for Jan-Jun 2026; the season belongs on the fact,
  because IMDb has no season entity to hang it on.
* **The period is data, not schema.** `dim_period` has a start and end date, so the
  annual report Netflix starts publishing in 2027 is a row, not a migration.
* **Unmatched titles are kept.** Checkpoint 2: a title with no IMDb id still gets a
  `title_id` and its facts, with `matched = false`. Nothing disappears quietly.

`title_id` is a hash of (kind, name key, published year), so it is stable across
rebuilds and does not shift when Netflix publishes another report.

Run: python -m src.model [--rebuild-imdb-index]
"""
from __future__ import annotations

import argparse
import hashlib
import json

import duckdb
import pandas as pd

from src import config, ingest_engagement, ingest_top10, match_imdb, match_netflix, normalise

MODEL_DB = config.PROCESSED / "streaming.duckdb"

SCHEMA = """
DROP VIEW IF EXISTS v_earning_its_place;
DROP VIEW IF EXISTS v_title_period;
DROP VIEW IF EXISTS v_top10_longevity;
DROP VIEW IF EXISTS v_weekly_demand;
DROP TABLE IF EXISTS fact_pageviews;
DROP TABLE IF EXISTS fact_top10_weekly;
DROP TABLE IF EXISTS fact_engagement_halfyear;
DROP TABLE IF EXISTS dim_period;
DROP TABLE IF EXISTS dim_title;

CREATE TABLE dim_title (
    title_id           VARCHAR PRIMARY KEY,
    kind               VARCHAR NOT NULL,   -- tv | film, as Netflix classifies it
    name_key           VARCHAR NOT NULL,   -- normalised name the match was made on
    canonical_title    VARCHAR NOT NULL,   -- as Netflix published it, most recent period
    published_year     INTEGER,            -- the (2011) in 'Suits (2011)', or the release year
    imdb_tconst        VARCHAR,            -- null when unmatched: kept, not dropped
    imdb_type          VARCHAR,
    imdb_start_year    INTEGER,
    imdb_genres        VARCHAR,
    imdb_rating        DOUBLE,
    imdb_votes         INTEGER,
    imdb_max_season    INTEGER,
    rejected_candidate VARCHAR,            -- the near miss: a candidate the threshold turned down
    match_rung         VARCHAR,            -- which rung of the ladder matched it
    match_tie_break    VARCHAR,            -- how several candidate ids were narrowed to one
    match_score        DOUBLE,
    matched            BOOLEAN NOT NULL,
    seasons_reported   VARCHAR,            -- seasons Netflix reported, as a list
    seasons_present    BOOLEAN,            -- does IMDb list them
    wikipedia_article  VARCHAR
);

CREATE TABLE dim_period (
    period        VARCHAR PRIMARY KEY,
    period_start  DATE NOT NULL,
    period_end    DATE NOT NULL,
    source_file   VARCHAR,
    source_sha256 VARCHAR
);

CREATE TABLE fact_engagement_halfyear (
    title_id           VARCHAR NOT NULL REFERENCES dim_title(title_id),
    period             VARCHAR NOT NULL REFERENCES dim_period(period),
    published_title    VARCHAR NOT NULL,
    season_kind        VARCHAR,
    season_number      INTEGER,
    part_number        INTEGER,
    available_globally BOOLEAN,
    release_date       DATE,
    hours_viewed       BIGINT NOT NULL,
    views              BIGINT,
    runtime_hours      DOUBLE,
    runtime_withheld   BOOLEAN NOT NULL,
    runtime_starred    BOOLEAN NOT NULL,
    source_row         VARCHAR NOT NULL
);

CREATE TABLE fact_top10_weekly (
    title_id                   VARCHAR REFERENCES dim_title(title_id),  -- null: charted but unmatchable
    title_match_scope          VARCHAR,   -- period: matched inside its own report period
                                          -- name_only: matched by name against any period,
                                          -- for weeks before July 2023 and for titles
                                          -- Netflix later renamed
    week                       DATE NOT NULL,
    category                   VARCHAR NOT NULL,
    kind                       VARCHAR NOT NULL,
    language                   VARCHAR NOT NULL,
    weekly_rank                INTEGER NOT NULL,
    charting_title             VARCHAR NOT NULL,
    season_number              INTEGER,
    weekly_hours_viewed        BIGINT NOT NULL,
    weekly_views               BIGINT,
    runtime                    DOUBLE,
    cumulative_weeks_in_top_10 INTEGER NOT NULL
);

CREATE TABLE fact_pageviews (
    title_id VARCHAR NOT NULL REFERENCES dim_title(title_id),
    article  VARCHAR NOT NULL,
    date     DATE NOT NULL,
    views    BIGINT NOT NULL
);
"""

VIEWS = """
-- One row per title per report period: the engagement facts with the title's attributes.
CREATE OR REPLACE VIEW v_title_period AS
SELECT t.title_id, t.canonical_title, t.kind, t.imdb_tconst, t.imdb_genres, t.imdb_rating,
       t.imdb_votes, t.matched, f.period, p.period_start, p.period_end,
       count(*)                       AS seasons_reported_in_period,
       sum(f.hours_viewed)            AS hours_viewed,
       sum(f.views)                   AS views,
       min(f.release_date)            AS first_release_date,
       bool_or(f.available_globally)  AS available_globally
FROM fact_engagement_halfyear f
JOIN dim_title t USING (title_id)
JOIN dim_period p USING (period)
GROUP BY ALL;

-- Top 10 longevity: the supporting metric candidate from the spec.
CREATE OR REPLACE VIEW v_top10_longevity AS
SELECT title_id,
       -- One title can chart under two names: Netflix renamed Berlin's first season
       -- when its second arrived, and the Top 10 file shows the new name for the old
       -- weeks. Grouping by name as well as id would split the run in two.
       string_agg(DISTINCT charting_title, ' | ') AS charting_titles,
       count(DISTINCT week)            AS weeks_charted,
       min(weekly_rank)                AS best_rank,
       min(week)                       AS first_week,
       max(week)                       AS last_week,
       sum(weekly_hours_viewed)        AS top10_hours,
       count(DISTINCT category)        AS categories
FROM fact_top10_weekly
WHERE title_id IS NOT NULL
GROUP BY ALL;

-- On-platform hours beside off-platform interest, by week, for the lead/lag question.
CREATE OR REPLACE VIEW v_weekly_demand AS
WITH pv AS (
    SELECT title_id, date_trunc('week', date) + INTERVAL 6 DAY AS week_ending, sum(views) AS pageviews
    FROM fact_pageviews GROUP BY ALL
),
top10 AS (
    SELECT title_id, week, sum(weekly_hours_viewed) AS hours, min(weekly_rank) AS best_rank
    FROM fact_top10_weekly WHERE title_id IS NOT NULL GROUP BY ALL
)
SELECT coalesce(t.title_id, p.title_id)        AS title_id,
       coalesce(t.week, p.week_ending::DATE)   AS week,
       t.hours, t.best_rank, p.pageviews
FROM top10 t FULL OUTER JOIN pv p
  ON p.title_id = t.title_id AND p.week_ending::DATE = t.week;

-- The three candidate headline metrics, side by side, for Checkpoint 3.
CREATE OR REPLACE VIEW v_earning_its_place AS
WITH engagement AS (
    SELECT title_id, sum(hours_viewed) AS hours, sum(views) AS views,
           min(release_date) AS release_date, max(runtime_hours) AS runtime_hours,
           count(DISTINCT period) AS periods_reported
    FROM fact_engagement_halfyear GROUP BY 1
),
-- 'Hours per available week since release' needs a release date, and Netflix
-- publishes one for only a third of titles. Three sources, best first, and which one
-- was used is reported - because for an old catalogue title like Suits (2011) the
-- answer changes the metric by an order of magnitude.
available_from AS (
    SELECT e.title_id,
           coalesce(e.release_date,
                    CASE WHEN t.imdb_start_year IS NOT NULL
                         THEN make_date(t.imdb_start_year, 1, 1) END,
                    (SELECT min(p.period_start) FROM dim_period p
                      WHERE p.period = (SELECT min(f.period) FROM fact_engagement_halfyear f
                                         WHERE f.title_id = e.title_id))) AS available_from,
           CASE WHEN e.release_date IS NOT NULL THEN 'netflix_release_date'
                WHEN t.imdb_start_year IS NOT NULL THEN 'imdb_start_year'
                ELSE 'first_period_reported' END AS available_from_source
    FROM engagement e JOIN dim_title t USING (title_id)
),
weeks_available AS (
    SELECT a.title_id, a.available_from, a.available_from_source,
           greatest(1, date_diff('week', a.available_from,
                                 (SELECT max(period_end) FROM dim_period))) AS weeks_available
    FROM available_from a
),
-- Pageviews only over the days inside the periods the title was actually reported in.
-- Article windows differ - 'Berlin and the Lady with an Ermine' has an English article
-- 170 days old against three years for 'Stranger Things' - so unaligned totals are not
-- comparable between titles. pageview_days keeps that coverage visible rather than
-- letting a short window look like low interest.
demand AS (
    SELECT p.title_id, sum(p.views) AS pageviews, count(DISTINCT p.date) AS pageview_days
    FROM fact_pageviews p
    JOIN (SELECT DISTINCT title_id, period FROM fact_engagement_halfyear) r
      ON r.title_id = p.title_id
    JOIN dim_period d ON d.period = r.period AND p.date BETWEEN d.period_start AND d.period_end
    GROUP BY 1
)
SELECT t.title_id, t.canonical_title, t.kind, t.imdb_genres, t.imdb_rating, t.imdb_votes,
       e.hours, e.views, e.release_date, w.available_from, w.available_from_source,
       w.weeks_available,
       e.hours / w.weeks_available                       AS hours_per_week_available,
       l.weeks_charted, l.best_rank,
       d.pageviews, d.pageview_days,
       CASE WHEN d.pageviews > 0 THEN e.hours / (d.pageviews / 1000.0) END AS hours_per_1k_pageviews
FROM dim_title t
JOIN engagement e USING (title_id)
JOIN weeks_available w USING (title_id)
LEFT JOIN v_top10_longevity l USING (title_id)
LEFT JOIN demand d USING (title_id);
"""


def title_id(kind: str, key: str, year) -> str:
    """Stable surrogate key: same inputs, same id, in any run and after new data arrives."""
    raw = f"{kind}|{key}|{'' if year is None or pd.isna(year) else int(year)}"
    return "t_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def build_dim_title(entities: pd.DataFrame, con_imdb) -> pd.DataFrame:
    dim = pd.DataFrame({
        "title_id": [title_id(r.kind, r.key, r.year) for r in entities.itertuples()],
        "kind": entities.kind,
        "name_key": entities.key,
        "canonical_title": entities.example_title,
        "published_year": entities.year,
        # A near miss carries the best candidate it found. That candidate was rejected,
        # so it must not sit in imdb_tconst where every query would treat it as the
        # answer; it is kept beside the score that rejected it instead.
        "imdb_tconst": entities.tconst.where(entities.matched),
        "imdb_type": entities.imdb_type.where(entities.matched),
        "imdb_start_year": entities.imdb_year.where(entities.matched),
        "rejected_candidate": entities.tconst.where(~entities.matched),
        "imdb_max_season": entities.imdb_max_season,
        "match_rung": entities.rung,
        "match_tie_break": entities.tie_break,
        "match_score": entities.score,
        "matched": entities.matched,
        "seasons_reported": entities.seasons.apply(lambda s: json.dumps(list(s))),
        "seasons_present": entities.seasons_present,
    })
    # Genres and ratings come from IMDb, for matched titles only.
    ids = dim.imdb_tconst.dropna().unique().tolist()
    con_imdb.register("wanted_ids", pd.DataFrame({"tconst": ids}))
    attrs = con_imdb.execute("""
        SELECT b.tconst AS imdb_tconst, b.genres AS imdb_genres,
               r.averageRating AS imdb_rating, r.numVotes AS imdb_votes
        FROM wanted_ids w JOIN title_basics b ON b.tconst = w.tconst
        LEFT JOIN title_ratings r ON r.tconst = b.tconst
    """).fetchdf()
    dim = dim.merge(attrs, on="imdb_tconst", how="left")
    dim["wikipedia_article"] = None
    if dim.title_id.duplicated().any():
        dupes = dim[dim.title_id.duplicated(keep=False)].canonical_title.head(5).tolist()
        raise ValueError(f"title_id is not unique; collisions near {dupes}")
    return dim


def build_facts(dim: pd.DataFrame, row_entity: pd.Series, entities: pd.DataFrame):
    engagement = ingest_engagement.load()
    engagement = engagement[~engagement.is_catch_all]
    ids = [title_id(r.kind, r.key, r.year) for r in entities.itertuples()]
    fact_e = pd.DataFrame({
        "title_id": [ids[row_entity[i]] for i in engagement.index],
        "period": engagement.period,
        "published_title": engagement.title,
        "season_kind": [normalise.parse(t).season_kind for t in engagement.title],
        "season_number": [normalise.parse(t).season_number for t in engagement.title],
        "part_number": [normalise.parse(t).part_number for t in engagement.title],
        "available_globally": engagement.available_globally,
        "release_date": engagement.release_date,
        "hours_viewed": engagement.hours_viewed,
        "views": engagement.views,
        "runtime_hours": engagement.runtime_hours,
        "runtime_withheld": engagement.runtime_withheld,
        "runtime_starred": engagement.runtime_starred,
        "source_row": engagement.source_row,
    })
    fact_e["season_number"] = fact_e.season_number.astype("Int64")
    fact_e["part_number"] = fact_e.part_number.astype("Int64")

    # Top 10 weeks reach a title through the Phase 2 match: charting title in a period
    # -> the engagement row it matched -> that row's entity.
    charting = match_netflix.charting_titles()
    matched = match_netflix.run()
    lookup, any_period = {}, {}
    for r in matched[matched.matched].itertuples():
        left = charting.loc[r.left_row]
        lookup[(left.period, left.kind, left.title)] = ids[row_entity[r.right_row]]
        # The Top 10 file goes back to July 2021, three half-years before the first
        # engagement report, and a week inside a period can still fail to match there -
        # Berlin's 2023 weeks carry the name the show was given in 2026. Both cases fall
        # back to matching the name against any period, which is weaker and is labelled.
        any_period.setdefault((left.kind, left.title), ids[row_entity[r.right_row]])

    t = ingest_top10.load()
    t = t.assign(charting_title=t.season_title.where(t.season_title.notna(), t.show_title))
    period_of = {}
    for p in config.ENGAGEMENT_PERIODS:
        for week in t.week.unique():
            if p.start <= week <= p.end:
                period_of[week] = p.label
    resolved = [(lookup.get((period_of.get(r.week), r.kind, r.charting_title)), "period")
                if (period_of.get(r.week), r.kind, r.charting_title) in lookup
                else (any_period.get((r.kind, r.charting_title)), "name_only")
                for r in t.itertuples()]
    fact_t = pd.DataFrame({
        "title_id": [tid for tid, _ in resolved],
        "title_match_scope": [scope if tid else None for tid, scope in resolved],
        "week": t.week, "category": t.category, "kind": t.kind, "language": t.language,
        "weekly_rank": t.weekly_rank, "charting_title": t.charting_title,
        "season_number": [normalise.parse(x).season_number for x in t.charting_title],
        "weekly_hours_viewed": t.weekly_hours_viewed, "weekly_views": t.weekly_views,
        "runtime": t.runtime, "cumulative_weeks_in_top_10": t.cumulative_weeks_in_top_10,
    })
    fact_t["season_number"] = fact_t.season_number.astype("Int64")

    manifest = json.loads(config.MANIFEST.read_text(encoding="utf-8"))
    dim_period = pd.DataFrame([{
        "period": p.label, "period_start": p.start, "period_end": p.end,
        "source_file": f"engagement_{p.label}.xlsx",
        "source_sha256": manifest.get(f"data/raw/engagement/engagement_{p.label}.xlsx", {}).get("sha256"),
    } for p in config.ENGAGEMENT_PERIODS])
    return dim_period, fact_e, fact_t


def load_pageviews(dim: pd.DataFrame) -> pd.DataFrame:
    """Whatever Wikipedia data has been fetched so far, for titles in the model."""
    from src import ingest_wikipedia
    article_dir = config.RAW / "wikipedia" / "pageviews"
    mapping = config.ROOT / "data" / "validation" / "wikipedia-articles.json"
    if not article_dir.exists() or not mapping.exists():
        return pd.DataFrame(columns=["title_id", "article", "date", "views"])
    by_article = {a: t for t, a in json.loads(mapping.read_text(encoding="utf-8")).items()}
    paths = [p for p in sorted(article_dir.glob("*.json"))]
    views = ingest_wikipedia.load_pageviews(paths)
    views["title_id"] = views.article.map(by_article)
    known = set(dim.title_id)
    return views[views.title_id.notna() & views.title_id.isin(known)][
        ["title_id", "article", "date", "views"]]


def refresh_views(db_path=MODEL_DB):
    """Recreate the views without rebuilding the tables. The tables take eight minutes
    (matching runs inside); a view definition should not cost that to change."""
    con = duckdb.connect(str(db_path))
    for statement in VIEWS.split(";"):
        if statement.strip():
            con.execute(statement)
    return con


def build(db_path=MODEL_DB, rebuild_imdb_index=False):
    con_imdb = duckdb.connect(str(config.IMDB_DB))
    match_imdb.build_indexes(con_imdb, rebuild=rebuild_imdb_index)
    entities, row_entity = match_imdb.netflix_entities(with_rows=True)
    exact = match_imdb.exact_stage(con_imdb, entities)
    residue = [i for i in entities.index if i not in set(exact.entity)]
    fuzzy = match_imdb.fuzzy_stage(con_imdb, entities, residue)
    stages = pd.concat([exact, fuzzy], ignore_index=True)
    matched = entities.join(stages.set_index("entity"))
    matched["stage"] = matched.stage.fillna("unmatched")
    matched["matched"] = matched.stage.str.startswith("imdb_")
    matched = match_imdb.validate_seasons(con_imdb, matched)

    dim = build_dim_title(matched, con_imdb)
    dim_period, fact_e, fact_t = build_facts(dim, row_entity, matched)
    pageviews = load_pageviews(dim)
    if not pageviews.empty:
        articles = pageviews[["title_id", "article"]].drop_duplicates().set_index("title_id").article
        dim["wikipedia_article"] = dim.title_id.map(articles)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    for statement in SCHEMA.split(";"):
        if statement.strip():
            con.execute(statement)
    for table, frame in [("dim_title", dim), ("dim_period", dim_period),
                         ("fact_engagement_halfyear", fact_e), ("fact_top10_weekly", fact_t),
                         ("fact_pageviews", pageviews)]:
        con.register(f"src_{table}", frame)
        cols = [c[0] for c in con.execute(f"DESCRIBE {table}").fetchall()]
        con.execute(f"INSERT INTO {table} SELECT {', '.join(cols)} FROM src_{table}")
    for statement in VIEWS.split(";"):
        if statement.strip():
            con.execute(statement)
    return con


def summarise(con):
    print("\ntables")
    for table in ["dim_title", "dim_period", "fact_engagement_halfyear",
                  "fact_top10_weekly", "fact_pageviews"]:
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table:<26} {n:>10,}")
    checks = con.execute("""
        SELECT
          (SELECT count(*) FROM fact_engagement_halfyear f
             LEFT JOIN dim_title t USING (title_id) WHERE t.title_id IS NULL)     AS engagement_orphans,
          (SELECT count(*) FROM fact_top10_weekly f
             LEFT JOIN dim_title t USING (title_id)
            WHERE f.title_id IS NOT NULL AND t.title_id IS NULL)                  AS top10_orphans,
          (SELECT sum(hours_viewed) FROM fact_engagement_halfyear)                AS engagement_hours,
          (SELECT count(*) FROM fact_top10_weekly WHERE title_id IS NULL)         AS top10_unresolved,
          (SELECT count(*) FROM dim_title WHERE matched)                          AS titles_matched,
          (SELECT count(*) FROM dim_title)                                        AS titles
    """).fetchdf().iloc[0]
    print("\nintegrity")
    print(f"  fact rows pointing at a missing title: {int(checks.engagement_orphans)} engagement, "
          f"{int(checks.top10_orphans)} top 10")
    print(f"  Top 10 slots with no resolved title:   {int(checks.top10_unresolved):,} "
          f"of {con.execute('SELECT count(*) FROM fact_top10_weekly').fetchone()[0]:,}")
    print(f"  titles with an IMDb id:                {int(checks.titles_matched):,} of {int(checks.titles):,}")
    print(f"  hours in fact_engagement_halfyear:     {int(checks.engagement_hours):,}")
    print("\nthe three candidate headline metrics, top 8 by hours per week available:")
    print(con.execute("""
        SELECT canonical_title, kind, round(hours / 1e6, 1) AS hours_m,
               round(hours_per_week_available / 1e6, 2) AS hours_per_week_m,
               weeks_charted, best_rank
        FROM v_earning_its_place
        WHERE weeks_available >= 4
        ORDER BY hours_per_week_available DESC LIMIT 8
    """).fetchdf().to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild-imdb-index", action="store_true")
    ap.add_argument("--views-only", action="store_true",
                    help="recreate the views over the existing tables")
    args = ap.parse_args()
    if args.views_only:
        con = refresh_views()
        print(f"refreshed views in {MODEL_DB}")
        summarise(con)
        return
    con = build(rebuild_imdb_index=args.rebuild_imdb_index)
    print(f"built {MODEL_DB}")
    summarise(con)


if __name__ == "__main__":
    main()
