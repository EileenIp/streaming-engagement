"""Phase 0: check that each source is live, and report what it actually contains.

Nothing here is kept as project data. Netflix files land in data/raw/phase0/
(gitignored) so the figures in data/validation/checkpoint0-sources.md can be
re-derived; IMDb is probed by headers and first rows only, because the full
dumps are 0.8 GB. Google Trends is deliberately not probed from code: the
unofficial endpoint answered 429 to the first request, and a script that
retries into a rate limit is how an IP gets blocked for the day.

Run: python src/phase0_probe.py
"""
import gzip
import hashlib
import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "phase0"

# Netflix serves an "unsupported browser" HTML page, with status 200, to an
# outdated user agent. Checking the content type is what catches it.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
API_UA = "EileenIp-portfolio-streaming-engagement/0.1 (github.com/EileenIp)"

TOP10_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-global.tsv"

REPORT_PAGES = {
    "2023H1": "what-we-watched-a-netflix-engagement-report",
    "2023H2": "what-we-watched-the-second-half-of-2023",
    "2024H1": "what-we-watched-the-first-half-of-2024",
    "2024H2": "what-we-watched-the-second-half-of-2024",
    "2025H1": "what-we-watched-the-first-half-of-2025",
    "2025H2": "what-we-watched-the-second-half-of-2025",
    "2026H1": "what-we-watched-the-first-half-of-2026",
}

IMDB_FILES = ["title.basics", "title.ratings", "title.akas", "title.episode"]


def fetch(url, dest, ua=BROWSER_UA):
    r = requests.get(url, headers={"User-Agent": ua}, timeout=120)
    r.raise_for_status()
    if "text/html" in r.headers.get("Content-Type", "") and not url.endswith("/"):
        if dest.suffix in {".tsv", ".xlsx"}:
            sys.exit(f"{url} returned HTML, not data - user agent rejected?")
    dest.write_bytes(r.content)
    return r


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe_top10():
    dest = RAW / "all-weeks-global.tsv"
    r = fetch(TOP10_URL, dest)
    d = pd.read_csv(dest, sep="\t", keep_default_na=False)
    print("\n## Netflix Global Top 10")
    print(f"url: {TOP10_URL}")
    print(f"last-modified: {r.headers.get('Last-Modified')}  bytes: {dest.stat().st_size:,}  sha256: {sha256(dest)[:16]}")
    print(f"rows: {len(d):,}  columns: {list(d.columns)}")
    print(f"weeks: {d.week.nunique()} ({d.week.min()} to {d.week.max()})")
    print(f"categories: {dict(d.category.value_counts())}")
    has_views = ~d.weekly_views.astype(str).isin(["", "N/A"])
    print(f"weekly_views/runtime missing: {(~has_views).sum():,} rows; first week with views: {d.loc[has_views, 'week'].min()}")
    print(f"distinct show_title: {d.show_title.nunique():,}  distinct (show, season): {len(d[['show_title', 'season_title']].drop_duplicates()):,}")
    return d


def report_rows(path):
    """Title rows from every sheet. Layout: 5 preamble rows, header on row 6, data in columns B onwards."""
    wb = openpyxl.load_workbook(path, read_only=True)
    sheets = {}
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        header = [v for v in rows[5] if v is not None]
        body = [r[1:1 + len(header)] for r in rows[6:]]
        data = [r for r in body if r[0] is not None and isinstance(r[3], (int, float))]
        notes = [str(v) for r in rows[6:] for v in r if isinstance(v, str) and v.startswith("*")]
        sheets[ws.title] = (header, data, notes)
    return sheets


def probe_reports():
    print("\n## Netflix engagement reports (What We Watched)")
    out = {}
    for period, slug in REPORT_PAGES.items():
        page = requests.get(f"https://about.netflix.com/en/news/{slug}",
                            headers={"User-Agent": BROWSER_UA}, timeout=60).text
        links = sorted(set(re.findall(r"https://[^\"' ]+\.xlsx", page)))
        if len(links) != 1:
            sys.exit(f"{period}: expected one xlsx link on the page, found {len(links)}")
        dest = RAW / f"engagement_{period}.xlsx"
        fetch(links[0], dest)
        sheets = report_rows(dest)
        print(f"\n{period}: {links[0].rsplit('/', 1)[1]}  bytes: {dest.stat().st_size:,}  sha256: {sha256(dest)[:16]}")
        for name, (header, data, notes) in sheets.items():
            dated = sum(r[2] is not None for r in data)
            date_type = {type(r[2]).__name__ for r in data if r[2] is not None}
            # Exact names: a prefix test also catches real titles like "Other People (2016)".
            other = [(r[0], r[3]) for r in data if r[0] in {"Other Shows", "Other Movies"}]
            print(f"  sheet {name!r}: {len(data):,} titles; columns {header}; release date on {dated:,} ({'/'.join(date_type)}); min hours {min(r[3] for r in data if r[0] not in {'Other Shows', 'Other Movies'}):,}; catch-all rows (title, hours) {other}")
            for n in sorted(set(notes)):
                print(f"    footnote: {n}")
        out[period] = sheets
    return out


def probe_imdb():
    print("\n## IMDb non-commercial datasets")
    for name in IMDB_FILES:
        url = f"https://datasets.imdbws.com/{name}.tsv.gz"
        head = requests.head(url, timeout=60)
        with requests.get(url, stream=True, timeout=60) as r:
            first = gzip.GzipFile(fileobj=r.raw).readline().decode().rstrip("\n")
        print(f"{name}: {int(head.headers['Content-Length']) / 1e6:,.0f} MB gz, last-modified {head.headers['Last-Modified']}; columns {first.split(chr(9))}")


def probe_wikipedia():
    print("\n## Wikipedia pageviews (candidate replacement for Google Trends)")
    q = ('SELECT ?article WHERE { ?item wdt:P345 "tt13443470". '
         '?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }')
    r = requests.get("https://query.wikidata.org/sparql", params={"query": q},
                     headers={"User-Agent": API_UA, "Accept": "application/sparql-results+json"}, timeout=60)
    article = r.json()["results"]["bindings"][0]["article"]["value"]
    print(f"Wikidata: IMDb tt13443470 -> {article}")
    title = article.rsplit("/", 1)[1]
    r = requests.get("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                     f"en.wikipedia/all-access/user/{title}/daily/20260901/20260916",
                     headers={"User-Agent": API_UA}, timeout=60)
    items = r.json()["items"]
    print(f"pageviews: {len(items)} daily points, latest {items[-1]['timestamp']} = {items[-1]['views']:,}")


def naive_match(top10, reports):
    """Exact string match, no normalisation at all: the floor Phase 2 has to beat."""
    print("\n## Naive exact title match, Top 10 -> engagement report of the same half")
    top10 = top10.assign(key=top10.season_title.where(top10.season_title != "N/A", top10.show_title))
    for period, start, end in [("2025H2", "2025-07-01", "2025-12-31"), ("2026H1", "2026-01-01", "2026-06-30")]:
        titles = {r[0] for _, data, _ in reports[period].values() for r in data}
        keys = top10[(top10.week >= start) & (top10.week <= end)].key.unique()
        hit = sum(k in titles for k in keys)
        dual = sum(" // " in t for t in titles)
        print(f"{period}: {hit}/{len(keys)} distinct charting titles match exactly ({hit / len(keys):.1%}); "
              f"{dual:,} report titles carry an alternate-language name after ' // '")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    RAW.mkdir(parents=True, exist_ok=True)
    t10 = probe_top10()
    reps = probe_reports()
    probe_imdb()
    probe_wikipedia()
    naive_match(t10, reps)
