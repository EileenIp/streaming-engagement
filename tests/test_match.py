"""Phase 2: the normalisation ladder, the rungs, and the checks on the result.

Three kinds of test here:

  * pure unit tests on parsing and normalisation;
  * tests against a tiny hand-built IMDb database, including a regression test for
    the bug that matched 'Despicable Me 3' to the 2010 original;
  * tests against the real data, skipped when the raw files are not downloaded.
    The one that matters most is free ground truth: the Top 10 file publishes
    show_title and season_title as separate columns, so Netflix itself says where
    the season suffix ends on 1,660 titles.
"""
from __future__ import annotations

import json

import duckdb
import pandas as pd
import pytest

from src import config, ingest_engagement, ingest_top10, match, match_imdb, normalise

RAW_PRESENT = (config.RAW / "top10" / "all-weeks-global.tsv").exists() and \
              all(match_imdb.__dict__ and (config.RAW / "engagement" / f"engagement_{p.label}.xlsx").exists()
                  for p in config.ENGAGEMENT_PERIODS)
DB_PRESENT = config.IMDB_DB.exists()
needs_raw = pytest.mark.skipif(not RAW_PRESENT, reason="raw Netflix files not downloaded")
needs_db = pytest.mark.skipif(not DB_PRESENT, reason="IMDb DuckDB not built")


# --- parsing -------------------------------------------------------------------------

@pytest.mark.parametrize("title, base, kind, number, year", [
    ("Wednesday: Season 2", "Wednesday", "season", 2, None),
    ("Suits (2011): Season 1", "Suits", "season", 1, 2011),
    ("Dear Child: Limited Series", "Dear Child", "limited", None, None),
    ("Lupin: Part 3", "Lupin", "part", 3, None),
    ("Downton Abbey: Series 1", "Downton Abbey", "series", 1, None),
    ("Aquí no hay quien viva (2003): Temporada 4", "Aquí no hay quien viva", "season", 4, 2003),
    ("Law & Order: Special Victims Unit: The Sixth Year",
     "Law & Order: Special Victims Unit", "season", 6, None),
    ("Miraculous: Season 2: Part 2", "Miraculous", "season", 2, None),
    ("Love Is Blind: S10: Ohio", "Love Is Blind", "season", 10, None),
    ("Our Planet: II", "Our Planet", "season", 2, None),
    ("Furies: Season 1:", "Furies", "season", 1, None),
    ("Raw: June 15, 2025", "Raw", "episode_date", None, None),
    ("Knives Out", "Knives Out", None, None, None),
    # A two-part film is not part 2 of anything.
    ("Sailor Moon Cosmos: Part 1 / Part 2", "Sailor Moon Cosmos: Part 1 / Part 2", None, None, None),
])
def test_season_suffixes_are_parsed_not_guessed(title, base, kind, number, year):
    p = normalise.parse(title)
    assert (p.base, p.season_kind, p.season_number, p.year) == (base, kind, number, year)


def test_bilingual_titles_keep_both_names():
    p = normalise.parse("Dear Child: Limited Series // Liebes Kind: Miniserie")
    assert p.primary == "Dear Child: Limited Series"
    assert p.alternates == ("Liebes Kind: Miniserie",)
    assert p.alternate_keys == ("dear child", "liebes kind")


def test_a_trailing_number_is_flagged_because_it_is_ambiguous():
    """'Stranger Things 4' is a season; 'Extraction 2' is a sequel. Same shape."""
    for title in ("Stranger Things 4", "Extraction 2"):
        p = normalise.parse(title)
        assert p.season_number == 2 or p.season_number == 4
        assert p.season_from_bare_number is True
    assert normalise.parse("Wednesday: Season 2").season_from_bare_number is False


@pytest.mark.parametrize("text, key", [
    ("Shameless (U.S.)", "shameless us"),          # IMDb writes this 'Shameless US'
    ("E.T. the Extra-Terrestrial", "et the extra terrestrial"),
    ("Café & Bar", "cafe and bar"),
    ("I Am Legend", "i am legend"),                # single words must survive untouched
    ("A Man Called Otto", "a man called otto"),
    ("鬼滅の刃", "鬼滅の刃"),                         # non-Latin scripts must survive
])
def test_normalisation_is_for_comparison_only(text, key):
    assert normalise.normalise(text) == key


def test_qualifier_is_kept_but_reachable_without():
    p = normalise.parse("Shameless (U.S.): Season 1")
    assert p.qualifier == "U.S."
    assert p.key == "shameless us"
    assert p.key_without_qualifier == "shameless"   # weaker: it also matches the UK show


# --- Netflix's own columns as ground truth -------------------------------------------

@needs_raw
def test_parser_agrees_with_netflix_own_season_column():
    """The Top 10 file gives show_title and season_title separately. The parsed base
    must never contradict the show name Netflix itself published."""
    t = ingest_top10.load()
    pairs = t.dropna(subset=["season_title"])[["show_title", "season_title"]].drop_duplicates()
    assert len(pairs) > 1000
    exact = contradictions = 0
    for r in pairs.itertuples():
        base = normalise.parse(r.season_title).base
        if base == r.show_title:
            exact += 1
        elif not (base.startswith(r.show_title) or r.show_title.startswith(base)):
            contradictions += 1
    # Bases longer than show_title are correct - named arcs like
    # 'Demon Slayer: Kimetsu no Yaiba: Swordsmith Village Arc'.
    assert contradictions == 0
    assert exact / len(pairs) > 0.97


# --- the rungs -----------------------------------------------------------------------

def candidate(raw, block=("2026H1", "tv")):
    df = pd.DataFrame([{"title": raw, "period": block[0], "kind": block[1]}])
    return match.candidates(df, "title", ["period", "kind"])


def test_season_equivalence_only_fires_when_it_cannot_choose_wrongly():
    """Netflix calls one thing 'Season 1' in the Top 10 and 'Limited Series' in the
    report. That is matchable. But if the report lists both, it is not."""
    left = candidate("Sean Combs: The Reckoning: Season 1")
    one = candidate("Sean Combs: The Reckoning: Limited Series")
    assert match.match(left, one).stage.item() == "season_equiv"

    both = candidate("Sean Combs: The Reckoning: Limited Series") + \
        candidate("Sean Combs: The Reckoning")
    assert match.match(left, both).stage.item() in ("near_miss", "unmatched")


def test_a_different_season_never_matches():
    left = candidate("Wednesday: Season 2")
    right = candidate("Wednesday: Season 1")
    assert match.match(left, right).stage.item() in ("near_miss", "unmatched")


# --- a tiny IMDb database ------------------------------------------------------------

BASICS = [
    # tconst, titleType, primaryTitle, originalTitle, startYear
    ("tt1323594", "movie", "Despicable Me", "Despicable Me", 2010),
    ("tt1690953", "movie", "Despicable Me 2", "Despicable Me 2", 2013),
    ("tt3469046", "movie", "Despicable Me 3", "Despicable Me 3", 2017),
    ("tt0413573", "tvSeries", "Grey's Anatomy", "Grey's Anatomy", 2005),
    ("tt9999991", "tvSeries", "Grey's Anatomy", "Grey's Anatomy", 2019),   # a namesake, no votes
    ("tt4574334", "tvSeries", "Stranger Things", "Stranger Things", 2016),
    ("tt2527424", "tvSeries", "S.W.A.T.", "S.W.A.T.", 2017),
    ("tt0364845", "tvSeries", "ONE PIECE", "ONE PIECE", 1999),
    ("tt0292421", "tvSeries", "Shameless", "Shameless", 2004),             # the UK original
]
AKAS = [("tt0413573", 1, "Grey's Anatomy", None, 1), ("tt0292421", 1, "Shameless", None, 1)]
RATINGS = [("tt1323594", 7.6, 640959), ("tt1690953", 7.3, 465636), ("tt3469046", 6.2, 186168),
           ("tt0413573", 7.6, 377844), ("tt9999991", 5.0, 0), ("tt4574334", 8.6, 1738796),
           ("tt2527424", 6.9, 24000), ("tt0364845", 9.0, 180000), ("tt0292421", 8.4, 60000)]
EPISODES = [("tt00e1", "tt4574334", 1, 1), ("tt00e2", "tt4574334", 2, 1), ("tt00e3", "tt4574334", 3, 1),
            ("tt00e4", "tt4574334", 4, 1), ("tt00e5", "tt0413573", 1, 1)]


@pytest.fixture
def tiny_imdb(tmp_path):
    con = duckdb.connect(str(tmp_path / "imdb.duckdb"))
    con.execute("CREATE TABLE title_basics (tconst VARCHAR, titleType VARCHAR, primaryTitle VARCHAR,"
                " originalTitle VARCHAR, startYear INTEGER)")
    con.executemany("INSERT INTO title_basics VALUES (?,?,?,?,?)", BASICS)
    con.execute("CREATE TABLE title_akas (titleId VARCHAR, ordering INTEGER, title VARCHAR,"
                " region VARCHAR, isOriginalTitle BOOLEAN)")
    con.executemany("INSERT INTO title_akas VALUES (?,?,?,?,?)", AKAS)
    con.execute("CREATE TABLE title_ratings (tconst VARCHAR, averageRating DOUBLE, numVotes INTEGER)")
    con.executemany("INSERT INTO title_ratings VALUES (?,?,?)", RATINGS)
    con.execute("CREATE TABLE title_episode (tconst VARCHAR, parentTconst VARCHAR,"
                " seasonNumber INTEGER, episodeNumber INTEGER)")
    con.executemany("INSERT INTO title_episode VALUES (?,?,?,?)", EPISODES)
    match_imdb.build_indexes(con, rebuild=True)
    return con


def entities_from(titles):
    """Build entities the way the pipeline does, from engagement-shaped rows."""
    rows = [{"period": "2026H1", "period_start": None, "period_end": None, "kind": kind,
             "title": title, "available_globally": True, "release_date": None,
             "hours_viewed": 1_000_000, "runtime_hours": 1.0, "runtime_withheld": False,
             "runtime_starred": False, "views": 1000, "is_catch_all": False, "source_row": "x!1"}
            for title, kind in titles]
    return match_imdb.netflix_entities(pd.DataFrame(rows))


def test_a_sequel_does_not_match_the_original(tiny_imdb):
    """The regression test: pooling the season-stripped key with the published name
    let 'Despicable Me 3' match 'Despicable Me' (2010), which had the most votes."""
    ents = entities_from([("Despicable Me 3", "film"), ("Despicable Me 2", "film"),
                          ("Despicable Me", "film")])
    got = match_imdb.exact_stage(tiny_imdb, ents).set_index("entity")
    by_title = {ents.at[i, "example_title"]: r.tconst for i, r in got.iterrows()}
    assert by_title == {"Despicable Me 3": "tt3469046", "Despicable Me 2": "tt1690953",
                        "Despicable Me": "tt1323594"}


def test_every_entity_resolves_to_exactly_one_imdb_id(tiny_imdb):
    ents = entities_from([("Grey's Anatomy: Season 1", "tv"), ("Stranger Things 4", "tv"),
                          ("S.W.A.T. (2017): Season 1", "tv"), ("ONE PIECE: East Blue", "tv")])
    got = match_imdb.exact_stage(tiny_imdb, ents)
    assert got.entity.is_unique
    assert got.tconst.notna().all()


def test_each_rung_is_recorded_so_it_can_be_switched_off(tiny_imdb):
    ents = entities_from([("Grey's Anatomy: Season 1", "tv"),        # name
                          ("S.W.A.T. (2017): Season 1", "tv"),      # spacing: 's w a t' vs 'swat'
                          ("ONE PIECE: East Blue", "tv")])          # prefix: a named arc
    got = match_imdb.exact_stage(tiny_imdb, ents).set_index("entity")
    rungs = {ents.at[i, "example_title"]: r.rung for i, r in got.iterrows()}
    assert rungs["Grey's Anatomy: Season 1"] == "name"
    assert rungs["S.W.A.T. (2017): Season 1"] == "spacing"
    assert rungs["ONE PIECE: East Blue"] == "prefix"


def test_a_namesake_is_resolved_by_votes_and_says_so(tiny_imdb):
    ents = entities_from([("Grey's Anatomy: Season 1", "tv")])
    got = match_imdb.exact_stage(tiny_imdb, ents).iloc[0]
    assert got.tconst == "tt0413573" and got.tie_break == "votes"
    assert got.tconst_candidates == 2 and got.runner_up_votes == 0


def test_season_validation_flags_a_season_imdb_does_not_have(tiny_imdb):
    ents = entities_from([("Stranger Things 4", "tv"), ("Grey's Anatomy: Season 1", "tv")])
    matched = ents.join(match_imdb.exact_stage(tiny_imdb, ents).set_index("entity"))
    checked = match_imdb.validate_seasons(tiny_imdb, matched).set_index("example_title")
    assert bool(checked.loc["Stranger Things 4", "seasons_present"]) is True   # IMDb lists 4 seasons
    ents2 = entities_from([("Stranger Things 5", "tv")])
    m2 = ents2.join(match_imdb.exact_stage(tiny_imdb, ents2).set_index("entity"))
    assert bool(match_imdb.validate_seasons(tiny_imdb, m2).seasons_present.item()) is False


@needs_db
def test_normalise_sql_matches_python():
    """The IMDb keys are built in SQL over 11M rows; the Netflix keys in Python. If the
    two normalisers drift, matches silently disappear."""
    # Attached read-only into an in-memory database, so the macro can be created
    # without taking a write lock on the real file.
    con = duckdb.connect()
    con.execute(f"ATTACH '{config.IMDB_DB.as_posix()}' AS imdb (READ_ONLY)")
    con.execute(match_imdb.NORM_SQL)
    sample = con.execute("""
        SELECT primaryTitle FROM imdb.title_basics
        WHERE titleType IN ('movie','tvSeries','tvMiniSeries') USING SAMPLE 4000 ROWS (reservoir, 7)
    """).fetchdf().primaryTitle.tolist()
    rows = con.execute("SELECT title, norm(title) FROM (SELECT unnest(?::VARCHAR[]) AS title)",
                       [sample]).fetchall()
    drift = [(t, sql, normalise.normalise(t, collapse_acronyms=False))
             for t, sql in rows if sql != normalise.normalise(t, collapse_acronyms=False)]
    assert not drift[:10], f"{len(drift)} of {len(rows)} titles normalise differently: {drift[:5]}"


# --- Eileen's hand-labelled fixture --------------------------------------------------

LABELS = config.ROOT / "data" / "validation" / "pair-labels.json"
PAIRS = config.ROOT / "data" / "validation" / "label-pairs.json"


@pytest.mark.skipif(not LABELS.exists(),
                    reason="Checkpoint 2: Eileen has not labelled the 30 pairs yet (open label.html)")
def test_threshold_agrees_with_the_hand_labelled_pairs():
    """The fixture the spec asks for: 30 pairs Eileen judged by eye, used to hold the
    threshold to a standard set by a person rather than by the pipeline."""
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["labels"]
    pairs = {p["id"]: p for p in json.loads(PAIRS.read_text(encoding="utf-8"))["pairs"]}
    judged = [(pairs[i], v) for i, v in labels.items() if v in ("same", "different")]
    assert len(judged) >= 20, f"only {len(judged)} pairs judged same/different"
    wrong = [(p["left"], p["right"], p["score"], verdict)
             for p, verdict in judged
             if p["score"] is not None and
             ((verdict == "same") != (p["score"] >= match.FUZZY_THRESHOLD))]
    assert not wrong, (f"threshold {match.FUZZY_THRESHOLD} disagrees with Eileen on "
                       f"{len(wrong)} of {len(judged)} pairs: {wrong[:5]}")
