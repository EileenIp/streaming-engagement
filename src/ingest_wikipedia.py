"""Wikipedia pageviews: external demand for a title, outside Netflix. Replaced Google
Trends at Checkpoint 0 (see data/validation/checkpoint0-sources.md).

Two steps, both keyed on IMDb ids, so this source can only run for titles
Phase 2 has already resolved:

1. Wikidata: IMDb id (property P345) -> English Wikipedia article.
2. Wikimedia REST API: daily user pageviews for that article.

Responses are saved raw, one JSON file per request, before anything is parsed.
One IMDb id can map to more than one Wikidata item and one item can carry more
than one IMDb id. Both are kept as found; choosing between them is Phase 2's.

Run: python -m src.ingest_wikipedia [IMDB_ID ...]
"""
import argparse
import json
import re
import time
from urllib.parse import quote

import pandas as pd
import requests

from src import config, manifest
from src.schema import SchemaError, profile

RAW = config.RAW / "wikipedia"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = config.API_UA

IMDB_ID = re.compile(r"tt\d{7,}")


def _get(url, params=None, max_tries=4, **kw):
    """GET with a bounded, Retry-After-respecting back-off. Never loops forever into a rate limit."""
    for attempt in range(max_tries):
        r = SESSION.get(url, params=params, timeout=90, **kw)
        if r.status_code not in (429, 503):
            return r
        time.sleep(float(r.headers.get("Retry-After", 5 * 2 ** attempt)))
    r.raise_for_status()
    return r


def _safe_name(article):
    return re.sub(r"[^\w.-]", lambda m: f"%{ord(m.group()):02X}", article)


def fetch_articles(imdb_ids):
    ids = sorted(set(imdb_ids))
    bad = [i for i in ids if not IMDB_ID.fullmatch(i)]
    if bad:
        raise ValueError(f"not IMDb title ids: {bad[:5]}")
    out = RAW / "wikidata"
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for b in range(0, len(ids), config.WIKIDATA_BATCH):
        batch = ids[b:b + config.WIKIDATA_BATCH]
        values = " ".join(f'"{i}"' for i in batch)
        query = ("SELECT ?imdb ?item ?article WHERE { VALUES ?imdb { " + values + " } "
                 "?item wdt:P345 ?imdb. "
                 "OPTIONAL { ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. } }")
        r = _get(config.WIKIDATA_SPARQL, params={"query": query},
                 headers={"Accept": "application/sparql-results+json"})
        r.raise_for_status()
        path = out / f"imdb_{batch[0]}_{batch[-1]}.json"
        path.write_text(json.dumps({"imdb_ids": batch, "response": r.json()}, ensure_ascii=False), encoding="utf-8")
        manifest.record(path, "wikidata", config.WIKIDATA_SPARQL, imdb_ids=len(batch))
        paths.append(path)
    return paths


def load_articles(paths) -> pd.DataFrame:
    rows = []
    for path in paths:
        manifest.verify(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        found = set()
        for b in payload["response"]["results"]["bindings"]:
            article = b.get("article", {}).get("value")
            rows.append({"imdb_id": b["imdb"]["value"],
                         "wikidata_item": b["item"]["value"].rsplit("/", 1)[1],
                         "article": article.rsplit("/wiki/", 1)[1] if article else None})
            found.add(b["imdb"]["value"])
        rows += [{"imdb_id": i, "wikidata_item": None, "article": None}
                 for i in payload["imdb_ids"] if i not in found]
    return pd.DataFrame(rows, columns=["imdb_id", "wikidata_item", "article"]).drop_duplicates()


def fetch_pageviews(article, start=config.PAGEVIEWS_START, end=config.PAGEVIEWS_END):
    url = config.PAGEVIEWS_URL.format(article=quote(article, safe=""),
                                      start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    r = _get(url)
    if r.status_code == 404:
        # The API's answer when an article has no views in range (e.g. created later). Kept, not skipped.
        body = {"items": [], "status": 404, "detail": r.json().get("detail")}
    else:
        r.raise_for_status()
        body = r.json()
    path = RAW / "pageviews" / f"{_safe_name(article)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"article": article, "start": str(start), "end": str(end), "response": body},
                               ensure_ascii=False), encoding="utf-8")
    manifest.record(path, "wikimedia_pageviews", url)
    return path


def load_pageviews(paths) -> pd.DataFrame:
    rows = []
    for path in paths:
        manifest.verify(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload["response"]["items"]:
            if item.get("granularity") != "daily" or item.get("agent") != "user":
                raise SchemaError(f"{path.name}: expected daily user pageviews, got {item}")
            rows.append({"article": payload["article"],
                         "date": pd.to_datetime(item["timestamp"][:8], format="%Y%m%d").date(),
                         "views": int(item["views"])})
    return pd.DataFrame(rows, columns=["article", "date", "views"])


def main():
    ap = argparse.ArgumentParser()
    # Default smoke id: Wednesday, the one mapping checked by hand at Phase 0.
    ap.add_argument("imdb_ids", nargs="*", default=["tt13443470"])
    args = ap.parse_args()
    articles = load_articles(fetch_articles(args.imdb_ids))
    profile(articles, "Wikidata IMDb -> English Wikipedia", "n/a (current mapping)")
    print(f"  ids with an article: {articles.dropna(subset=['article']).imdb_id.nunique()} of {len(set(args.imdb_ids))}")
    paths = [fetch_pageviews(a) for a in sorted(articles.article.dropna().unique())]
    views = load_pageviews(paths)
    profile(views, "Wikipedia daily pageviews", f"{views.date.min()} to {views.date.max()}" if len(views) else "empty")


if __name__ == "__main__":
    main()
