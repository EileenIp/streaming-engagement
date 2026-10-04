"""Netflix titles -> IMDb tconst.

The hard direction. Netflix publishes a name; IMDb has 2.8M candidate titles of
the right kinds and 11.2M alternate names for them, and shares no identifier
with Netflix at all.

Shape of the solution:

  * Keys are built in SQL, over 11M rows, because doing it in Python would mean
    pulling the whole akas table into memory. test_normalise_sql_matches_python
    holds the SQL and the Python normaliser to the same output.
  * A Netflix TV title matches a *series* tconst; IMDb has no season entity, so
    the season number is validated separately against title.episode.
  * Exact matches on a name that hits more than one tconst are resolved in a
    fixed order - a matching year, then vote count - and every tie-break is
    counted, because "the popular one" is a judgement, not a fact.
  * The residue is fuzzy-matched inside a block of candidates that share a rare
    token with it. Without blocking this is 20k x 2.8M comparisons.

Run: python -m src.match_imdb
"""
from __future__ import annotations

import argparse

import duckdb
import pandas as pd
from rapidfuzz import fuzz, process

from src import config, ingest_engagement, match, normalise

TV_TYPES = ("tvSeries", "tvMiniSeries")
FILM_TYPES = ("movie", "tvMovie", "video", "tvSpecial", "tvShort", "short")

# The rungs of the exact ladder, strongest first. Each is reported separately.
#   name              the published name, normalised
#   alternate_name    the other name in 'English // Original'
#   spacing           both sides with spaces removed: 'S.W.A.T.' <-> 'swat'
#   qualifier_dropped 'Shameless (U.S.)' as 'Shameless' - merges versions, so weak
#   prefix            the series name before a named arc - loses which arc, so weakest
RUNGS = ["name", "alternate_name", "spacing", "qualifier_dropped", "prefix"]

# Mirrors src.normalise.normalise. Kept in SQL so 11M alternate titles never
# leave the database; a test pins the two together.
NORM_SQL = r"""
CREATE OR REPLACE MACRO norm(s) AS trim(regexp_replace(regexp_replace(
    lower(strip_accents(replace(replace(replace(s, '&', ' and '), '+', ' and '), '×', ' x '))),
    '[^\p{L}\p{N}]+', ' ', 'g'), '\s+', ' ', 'g'));
"""

KEYS_SQL = f"""
CREATE OR REPLACE TABLE imdb_keys AS
WITH candidates AS (
    SELECT tconst, titleType, startYear,
           titleType IN {TV_TYPES} AS is_series,
           primaryTitle, originalTitle
    FROM title_basics
    WHERE titleType IN {TV_TYPES + FILM_TYPES}
),
named AS (
    SELECT tconst, titleType, startYear, is_series, norm(primaryTitle) AS key, 'primary' AS source FROM candidates
    UNION ALL
    SELECT tconst, titleType, startYear, is_series, norm(originalTitle), 'original' FROM candidates
    UNION ALL
    SELECT c.tconst, c.titleType, c.startYear, c.is_series, norm(a.title), 'aka'
    FROM title_akas a JOIN candidates c ON a.titleId = c.tconst
)
SELECT DISTINCT tconst, titleType, startYear, is_series, key, min(source) AS source
FROM named WHERE key <> '' GROUP BY ALL;
"""

TOKENS_SQL = """
CREATE OR REPLACE TABLE imdb_tokens AS
SELECT token, tconst, key, is_series FROM (
    SELECT unnest(string_split(key, ' ')) AS token, tconst, key, is_series FROM imdb_keys
) WHERE length(token) > 1;
CREATE OR REPLACE TABLE token_freq AS
SELECT token, count(DISTINCT tconst) AS df FROM imdb_tokens GROUP BY 1;
"""


def build_indexes(con, rebuild=False):
    """Build the key and token indexes. Two minutes over 11M alternate titles, so
    an existing index is reused unless a rebuild is asked for."""
    existing = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if not rebuild and {"imdb_keys", "imdb_tokens", "token_freq"} <= existing:
        return {"keys": con.execute("SELECT count(*) FROM imdb_keys").fetchone()[0],
                "titles": con.execute("SELECT count(DISTINCT tconst) FROM imdb_keys").fetchone()[0],
                "tokens": con.execute("SELECT count(*) FROM token_freq").fetchone()[0],
                "reused": True}
    con.execute(NORM_SQL)
    con.execute(KEYS_SQL)
    for statement in TOKENS_SQL.strip().split(";"):
        if statement.strip():
            con.execute(statement)
    return {"keys": con.execute("SELECT count(*) FROM imdb_keys").fetchone()[0],
            "titles": con.execute("SELECT count(DISTINCT tconst) FROM imdb_keys").fetchone()[0],
            "tokens": con.execute("SELECT count(*) FROM token_freq").fetchone()[0]}


def entity_of(kind: str, title: str, release_date=None) -> tuple:
    """The (kind, key, year) an engagement row belongs to. The one place that rule lives."""
    p = normalise.parse(title)
    if kind == "film":
        key = normalise.normalise(normalise.YEAR_IN_TITLE.sub("", p.primary).strip())
    else:
        key = p.key
    year = p.year or (release_date.year if release_date else None)
    return (kind, key, year)


def netflix_entities(engagement=None, with_rows=False):
    """One row per thing Netflix reported on, pooled over periods.

    A TV entity is a base name (its seasons are listed); a film entity is a name
    plus, where published, a year. A film's trailing number is part of its name
    ('Extraction 2'), so for films the season parse is deliberately ignored.

    with_rows=True also returns, for each engagement row, the entity it belongs to -
    which is what the star schema needs, since a fact row is one season in one period
    while an entity is the whole series.
    """
    e = ingest_engagement.load() if engagement is None else engagement
    e = e[~e.is_catch_all]
    rows = {}
    row_entity = {}
    for r in e.itertuples():
        p = normalise.parse(r.title)
        if r.kind == "film":
            # Keep the sequel number - it is part of the name - and drop only a
            # disambiguating year. The season-stripped base is deliberately NOT a
            # key here: it is what made 'Despicable Me 3' match the 2010 original.
            name = normalise.YEAR_IN_TITLE.sub("", p.primary).strip()
            key = normalise.normalise(name)
            alternates = tuple(normalise.normalise(normalise.YEAR_IN_TITLE.sub("", a).strip())
                               for a in p.alternates)
        else:
            key, alternates = p.key, p.alternate_keys[1:]
        year = p.year or (r.release_date.year if r.release_date else None)
        ent = rows.setdefault((r.kind, key, year), {
            "kind": r.kind, "key": key, "year": year, "example_title": r.title,
            # The rungs, strongest first. A rung is only tried when every rung
            # above it found nothing, and each one is reported separately so the
            # weaker ones can be inspected - or rejected - on their own.
            "name": {key}, "alternate_name": set(), "spacing": set(),
            "qualifier_dropped": set(), "prefix": set(),
            "seasons": set(), "periods": set(), "hours_viewed": 0, "views": 0,
        })
        ent["alternate_name"].update(a for a in alternates if a and a != key)
        # 'S.W.A.T.' is 's w a t' in IMDb and 'swat' here; compacting both sides matches them.
        ent["spacing"].add(normalise.compact(key))
        if p.qualifier and (r.kind == "tv" or year or " " in p.key_without_qualifier):
            # Films carry the qualifier too - 153 of them, almost all Indian-language
            # versions: 'Leo (Hindi) (2023)', 'Tughlaq Durbar (Telugu)'. Eileen's
            # hand-labelled pairs called that last one a match, and it was reaching
            # fuzzy instead of this rung because the rung was TV-only.
            #
            # The guard is what keeps it safe: a film qualifies only when it has a
            # published year or a multi-word name. Without it, 'Bro (Hindi)' becomes
            # the key 'bro' and the vote tie-break picks whichever film called Bro has
            # the most votes.
            ent["qualifier_dropped"].add(p.key_without_qualifier)
        if r.kind == "tv" and ": " in p.base:
            # 'ONE PIECE: East Blue' and 'Demon Slayer: ...: Hashira Training Arc' are
            # named arcs of a series IMDb lists under the series name alone. This rung
            # gives up knowing which arc, so it is the last one and counted apart.
            ent["prefix"].add(normalise.normalise(p.base.rsplit(": ", 1)[0]))
        if r.kind == "tv" and p.season_number:
            ent["seasons"].add(p.season_number)
        ent["periods"].add(r.period)
        ent["hours_viewed"] += r.hours_viewed
        ent["views"] += int(r.views) if pd.notna(r.views) else 0
        row_entity[r.Index] = (r.kind, key, year)
    order = {k: i for i, k in enumerate(rows)}
    df = pd.DataFrame(rows.values())
    for tier in RUNGS:
        # A key already tried on a stronger rung is dropped from the weaker one - but
        # only among rungs that compare against the same IMDb column. 'spacing'
        # compares compacted keys, so 'swat' there is a different comparison from
        # 'swat' on the name rung and has to be kept.
        if tier == "spacing":
            df[tier] = df[tier].apply(lambda s: tuple(sorted(k for k in s if k)))
            continue
        earlier_rungs = [r for r in RUNGS[:RUNGS.index(tier)] if r != "spacing"]
        df[tier] = [tuple(sorted(k for k in row[tier] if k and k not in set().union(
            *(row[earlier] for earlier in earlier_rungs), set())))
            for _, row in df.iterrows()]
    df["seasons"] = df["seasons"].apply(lambda s: tuple(sorted(s)))
    df["periods"] = df["periods"].apply(lambda s: tuple(sorted(s)))
    df = df.reset_index(drop=True)
    if not with_rows:
        return df
    return df, pd.Series({row: order[ent] for row, ent in row_entity.items()}, dtype="int64")


def exact_stage(con, entities: pd.DataFrame) -> pd.DataFrame:
    """Join Netflix keys to IMDb keys, then resolve one tconst per entity in a fixed order."""
    pairs = pd.DataFrame([{"entity": i, "key": k, "tier": tier, "rung": RUNGS[tier - 1],
                           "is_series": r.kind == "tv", "year": r.year}
                          for i, r in entities.iterrows()
                          for tier, rung in enumerate(RUNGS, start=1) for k in r[rung]])
    con.register("netflix_keys", pairs)
    # Two joins, not one with a CASE: the spacing rung compares compacted keys on
    # both sides, every other rung compares the keys as normalised.
    hits = con.execute("""
        SELECT n.entity, n.tier, n.rung, n.year AS netflix_year, k.tconst, k.titleType,
               k.startYear, k.source, coalesce(r.numVotes, 0) AS votes
        FROM netflix_keys n
        JOIN imdb_keys k ON k.key = n.key AND k.is_series = n.is_series
        LEFT JOIN title_ratings r ON r.tconst = k.tconst
        WHERE n.rung <> 'spacing'
        UNION ALL
        SELECT n.entity, n.tier, n.rung, n.year, k.tconst, k.titleType,
               k.startYear, k.source, coalesce(r.numVotes, 0)
        FROM netflix_keys n
        JOIN imdb_keys k ON replace(k.key, ' ', '') = n.key AND k.is_series = n.is_series
        LEFT JOIN title_ratings r ON r.tconst = k.tconst
        WHERE n.rung = 'spacing'
    """).fetchdf()
    # Deterministic order before any tie-break: equal votes must resolve the same way
    # in every run, or the same data produces a different model.
    hits = hits.sort_values(["entity", "tier", "tconst"]).reset_index(drop=True)
    resolved = []
    for entity, g in hits.groupby("entity"):
        # Strongest rung that found anything wins; rungs are never pooled.
        g = g[g.tier == g.tier.min()]
        rung = g.rung.iloc[0]
        candidates = g.drop_duplicates("tconst")
        stage, chosen, tie_break = f"imdb_{rung}", candidates, "none"
        if len(candidates) > 1:
            year = candidates.netflix_year.iloc[0]
            same_year = candidates[candidates.startYear.notna() & (candidates.startYear == year)] if pd.notna(year) else candidates.iloc[0:0]
            near_year = candidates[candidates.startYear.notna() & (abs(candidates.startYear - year) <= 1)] if pd.notna(year) else candidates.iloc[0:0]
            if len(same_year) == 1:
                chosen, tie_break = same_year, "year"
            elif len(near_year) == 1:
                chosen, tie_break = near_year, "year_within_one"
            else:
                pool = same_year if len(same_year) > 1 else (near_year if len(near_year) > 1 else candidates)
                chosen = pool.sort_values(["votes", "tconst"], ascending=[False, True]).head(1)
                tie_break = "votes"
        row = chosen.iloc[0]
        resolved.append({"entity": entity, "stage": stage, "rung": rung, "tie_break": tie_break,
                         "tconst": row.tconst,
                         "imdb_type": row.titleType, "imdb_year": row.startYear,
                         "key_source": row.source, "votes": int(row.votes),
                         "tconst_candidates": len(candidates), "score": 100.0,
                         "runner_up_votes": int(candidates.sort_values(
                             ["votes", "tconst"], ascending=[False, True]).votes.iloc[1])
                                            if len(candidates) > 1 else None})
    return pd.DataFrame(resolved)


def fuzzy_stage(con, entities: pd.DataFrame, residue, threshold=match.FUZZY_THRESHOLD,
                max_df=20000, pool_cap=4000) -> pd.DataFrame:
    """Fuzzy match the residue against candidates sharing its rarest token.

    max_df keeps a common word ('the', 'love') from pulling a pool of a million;
    an entity whose every token is that common gets no pool and stays unmatched,
    which the report counts rather than hides.
    """
    # One query for the whole residue, not one per title: the pools are picked in
    # SQL and the string comparison happens in Python.
    wanted = pd.DataFrame([
        {"entity": i, "token": tok, "is_series": entities.at[i, "kind"] == "tv"}
        for i in residue for tok in set(entities.at[i, "key"].split()) if len(tok) > 1])
    rows = [{"entity": i, "stage": "unmatched", "pool": 0}
            for i in residue if not [t for t in entities.at[i, "key"].split() if len(t) > 1]]
    if wanted.empty:
        return pd.DataFrame(rows)
    con.register("residue_tokens", wanted)
    pools = con.execute(f"""
        WITH ranked AS (
            SELECT r.entity, r.token, r.is_series, f.df,
                   row_number() OVER (PARTITION BY r.entity ORDER BY f.df) AS rarity
            FROM residue_tokens r JOIN token_freq f USING (token)
            WHERE f.df <= {max_df}
        ),
        rare AS (SELECT * FROM ranked WHERE rarity <= 2),
        hits AS (
            SELECT DISTINCT rare.entity, t.tconst, t.key
            FROM rare JOIN imdb_tokens t ON t.token = rare.token AND t.is_series = rare.is_series
        ),
        capped AS (
            -- ORDER BY is not decoration: without it the cap keeps an arbitrary
            -- subset, so two runs over the same data can match different titles.
            SELECT *, row_number() OVER (PARTITION BY entity ORDER BY tconst, key) AS n FROM hits
        )
        SELECT c.entity, c.tconst, c.key, k.titleType, k.startYear
        FROM capped c JOIN imdb_keys k ON k.tconst = c.tconst AND k.key = c.key
        WHERE c.n <= {pool_cap}
        ORDER BY c.entity, c.tconst, c.key
    """).fetchdf()
    by_entity = dict(tuple(pools.groupby("entity")))
    for i in residue:
        ent = entities.loc[i]
        pool = by_entity.get(i)
        if pool is None or pool.empty:
            if not any(r["entity"] == i for r in rows):
                rows.append({"entity": i, "stage": "unmatched", "pool": 0})
            continue
        pool = pool.reset_index(drop=True)
        best = process.extract(ent.key, pool.key.to_dict(), scorer=fuzz.token_sort_ratio, limit=3)
        _, score, idx = best[0]
        hit = pool.loc[idx]
        rows.append({"entity": i, "stage": "imdb_fuzzy" if score >= threshold else "near_miss",
                     "tconst": hit.tconst, "imdb_type": hit.titleType, "imdb_year": hit.startYear,
                     "imdb_key": hit.key, "score": score, "pool": len(pool),
                     "other_candidates": "; ".join(f"{pool.loc[j, 'key']} ({s:.0f})" for _, s, j in best[1:])})
    return pd.DataFrame(rows)


def validate_seasons(con, matched: pd.DataFrame) -> pd.DataFrame:
    """Does IMDb list the seasons Netflix reported? A tconst whose seasons stop short is a wrong match."""
    tv = matched[(matched.kind == "tv") & matched.tconst.notna()]
    if tv.empty:
        return matched.assign(imdb_max_season=pd.NA, seasons_present=pd.NA)
    con.register("tv_matches", tv[["tconst"]].drop_duplicates())
    seasons = con.execute("""
        SELECT parentTconst AS tconst, max(seasonNumber) AS imdb_max_season
        FROM title_episode WHERE parentTconst IN (SELECT tconst FROM tv_matches) GROUP BY 1
    """).fetchdf()
    out = matched.merge(seasons, on="tconst", how="left")
    out["seasons_present"] = [
        None if r.kind != "tv" or not r.seasons or pd.isna(r.imdb_max_season)
        else bool(max(r.seasons) <= r.imdb_max_season)
        for r in out.itertuples()]
    return out


def run(threshold=match.FUZZY_THRESHOLD, db_path=config.IMDB_DB, rebuild=False):
    con = duckdb.connect(str(db_path))
    index_stats = build_indexes(con, rebuild=rebuild)
    entities = netflix_entities()
    exact = exact_stage(con, entities)
    residue = [i for i in entities.index if i not in set(exact.entity)]
    fuzzy = fuzzy_stage(con, entities, residue, threshold=threshold)
    stages = pd.concat([exact, fuzzy], ignore_index=True)
    matched = entities.join(stages.set_index("entity"))
    matched["stage"] = matched.stage.fillna("unmatched")
    matched["matched"] = matched.stage.str.startswith("imdb_")
    return validate_seasons(con, matched), index_stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="rebuild the IMDb name and token indexes")
    matched, index_stats = run(rebuild=ap.parse_args().rebuild)
    print(f"IMDb index: {index_stats['keys']:,} name keys over {index_stats['titles']:,} titles, "
          f"{index_stats['tokens']:,} distinct tokens")
    print(f"\nNetflix entities: {len(matched):,} ({(matched.kind == 'tv').sum():,} TV, "
          f"{(matched.kind == 'film').sum():,} film)")
    print(f"matched to an IMDb id: {matched.matched.sum():,} ({matched.matched.mean():.1%})")
    for stage, n in matched.stage.value_counts().items():
        print(f"  {stage:<22} {n:>6,}")
    print("\nby kind:")
    for kind, g in matched.groupby("kind"):
        print(f"  {kind:<5} {g.matched.sum():>6,} / {len(g):<6,} ({g.matched.mean():.1%})")
    hours = matched.groupby("matched").hours_viewed.sum()
    print(f"\nshare of reported hours on a matched title: {hours.get(True, 0) / hours.sum():.1%}")
    tv = matched[(matched.kind == "tv") & matched.seasons_present.notna()]
    print(f"season check: {int((~tv.seasons_present.astype(bool)).sum()):,} of {len(tv):,} matched TV entities "
          f"report a season IMDb does not list")
    print("\nwhich rung did the work, and how was a tie broken:")
    hit = matched[matched.matched]
    print(pd.crosstab(hit.rung, hit.tie_break).reindex(RUNGS).fillna(0).astype(int).to_string())
    amb = matched[matched.tie_break == "votes"]
    print(f"\nresolved by vote count (a judgement, not a fact): {len(amb):,}")
    for r in amb.sort_values("hours_viewed", ascending=False).head(8).itertuples():
        print(f"  {r.example_title[:44]:<44} -> {r.tconst} {r.imdb_year} ({r.votes:,} votes, "
              f"runner-up {r.runner_up_votes:,}), {r.tconst_candidates} candidates")


if __name__ == "__main__":
    main()
