"""Fetch the external-demand source for titles that actually charted.

Wikipedia pageviews replaced Google Trends at Checkpoint 0. Scope, stated plainly,
and it is a rate limit as much as a judgement: **titles that charted in the Top 10
for at least five weeks inside the six report periods, and resolved to an IMDb id**
- 278 of 24,902 titles, carrying 53.3B of the 102.5B Top 10 hours in those periods.

Two reasons, in order of honesty:

1. The Wikimedia REST API answers an anonymous client with HTTP 429 and
   `Retry-After: 22` after a handful of requests, so every article costs about 22
   seconds. All 2,297 charting titles would take some eleven hours of continuous
   polling of a free API, which is not a reasonable thing to do to it.
2. The question the demand series answers - does outside interest lead or lag
   on-platform viewing - needs a title with several weeks of on-platform signal to
   correlate against. A single week in the chart has no shape.

The cut is a flag, not a constant, so widening it is one argument and a longer wait.

Two steps, both resumable: an article already fetched is skipped, so an
interrupted run costs nothing.

    IMDb id --(Wikidata P345)--> English Wikipedia article --> daily pageviews

Run: python -m src.fetch_demand [--limit N]
"""
from __future__ import annotations

import argparse
import json
import time

import duckdb
import pandas as pd
from rapidfuzz import fuzz

from src import config, ingest_wikipedia, model, normalise

ARTICLE_MAP = config.ROOT / "data" / "validation" / "wikipedia-articles.json"
AMBIGUOUS = config.ROOT / "data" / "validation" / "wikipedia-ambiguous.json"


def charting_titles(db_path=model.MODEL_DB, min_weeks=5) -> pd.DataFrame:
    """Titles with at least min_weeks in the Top 10 inside the report periods."""
    con = duckdb.connect(str(db_path), read_only=True)
    return con.execute("""
        SELECT t.title_id, t.imdb_tconst, t.canonical_title,
               count(DISTINCT f.week) AS weeks_charted,
               sum(f.weekly_hours_viewed) AS top10_hours
        FROM fact_top10_weekly f
        JOIN dim_period p ON f.week BETWEEN p.period_start AND p.period_end
        JOIN dim_title t USING (title_id)
        WHERE t.matched AND t.imdb_tconst IS NOT NULL
        GROUP BY 1, 2, 3
        HAVING count(DISTINCT f.week) >= ?
        ORDER BY sum(f.weekly_hours_viewed) DESC
    """, [min_weeks]).fetchdf()


def pick_article(title: str, found: list[str]) -> str:
    """Closest article name to the title Netflix published.

    One IMDb id can carry several articles: tt13207736 is the Monster anthology, and
    Wikidata offers the series article plus one per season. Alphabetical order picked
    'Monster: The Ed Gein Story' for every one of them. Matching the name instead sends
    each Netflix title to its own season's article.
    """
    if len(found) == 1:
        return found[0]
    target = normalise.normalise(normalise.parse(title).base)
    return max(found, key=lambda a: fuzz.token_sort_ratio(
        target, normalise.normalise(a.replace("_", " "))))


def resolve_articles(titles: pd.DataFrame) -> tuple[dict, dict]:
    """IMDb id -> English Wikipedia article, via Wikidata. Ambiguity is recorded, not hidden."""
    paths = ingest_wikipedia.fetch_articles(titles.imdb_tconst.tolist())
    mapping = ingest_wikipedia.load_articles(paths).dropna(subset=["article"])
    candidates, ambiguous = {}, {}
    for imdb_id, g in mapping.groupby("imdb_id"):
        found = sorted(set(g.article))
        candidates[imdb_id] = found
        if len(found) > 1:
            ambiguous[imdb_id] = found

    articles = {r.title_id: pick_article(r.canonical_title, candidates[r.imdb_tconst])
                for r in titles.itertuples() if r.imdb_tconst in candidates}
    ARTICLE_MAP.write_text(json.dumps(articles, ensure_ascii=False, indent=1), encoding="utf-8")
    AMBIGUOUS.write_text(json.dumps(ambiguous, ensure_ascii=False, indent=1), encoding="utf-8")
    return articles, ambiguous


def fetch_all(articles: dict, limit=None, pause=0.05):
    done = skipped = missing = 0
    # Biggest titles first: an interrupted run then still covers the ones any analysis
    # would reach for. sorted() would have gone alphabetically.
    targets = list(dict.fromkeys(articles.values()))
    if limit:
        targets = targets[:limit]
    for i, article in enumerate(targets, start=1):
        path = config.RAW / "wikipedia" / "pageviews" / f"{ingest_wikipedia.safe_name(article)}.json"
        if path.exists():
            skipped += 1
            continue
        payload = json.loads(ingest_wikipedia.fetch_pageviews(article).read_text(encoding="utf-8"))
        if not payload["response"]["items"]:
            missing += 1
        done += 1
        time.sleep(pause)
        if i % 250 == 0:
            print(f"  {i}/{len(targets)} articles: {done} fetched, {skipped} already had, "
                  f"{missing} with no data", flush=True)
    return {"articles": len(targets), "fetched": done, "already_had": skipped, "no_data": missing}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="stop after N articles (for a smoke run)")
    ap.add_argument("--min-weeks", type=int, default=5,
                    help="weeks in the Top 10 inside a report period a title needs to qualify")
    args = ap.parse_args()
    titles = charting_titles(min_weeks=args.min_weeks)
    print(f"{len(titles):,} titles charted >= {args.min_weeks} weeks in a report period, "
          f"with an IMDb id")
    articles, ambiguous = resolve_articles(titles)
    print(f"resolved {len(articles):,} to an English Wikipedia article "
          f"({len(titles) - len(articles):,} have none); {len(ambiguous)} IMDb ids matched "
          f"more than one article, recorded in {AMBIGUOUS.name}")
    stats = fetch_all(articles, limit=args.limit)
    print(f"pageviews: {stats}")
    print("run `python -m src.model` to load them into fact_pageviews")


if __name__ == "__main__":
    main()
