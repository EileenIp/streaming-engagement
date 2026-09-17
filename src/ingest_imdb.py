"""IMDb non-commercial datasets: download the gzipped TSVs, load them untouched into DuckDB.

The dumps are 0.8 GB compressed and title.akas alone is tens of millions of
rows, so they go straight from gzip into DuckDB rather than through pandas.
Nothing is filtered here. Which title types can match a Netflix row is an
entity-resolution decision and belongs to Phase 2, where it can be seen.

IMDb data is licensed for personal, non-commercial use: raw files and the
database stay local (gitignored); only aggregates are ever published.

Run: python -m src.ingest_imdb [--download]
"""
import argparse
import gzip
import shutil

import duckdb
import requests

from src import config, manifest
from src.schema import expect_columns

# IMDb writes no quoting at all: titles contain bare double quotes. Parsing
# with CSV quote rules on would merge rows silently.
READ_OPTS = "delim='\t', header=true, quote='', escape='', nullstr='\\N', all_varchar=true"

CASTS = {
    "title.basics": "tconst, titleType, primaryTitle, originalTitle, isAdult::BOOLEAN AS isAdult, "
                    "startYear::INTEGER AS startYear, endYear::INTEGER AS endYear, "
                    "runtimeMinutes::INTEGER AS runtimeMinutes, genres",
    "title.ratings": "tconst, averageRating::DOUBLE AS averageRating, numVotes::INTEGER AS numVotes",
    "title.akas": "titleId, ordering::INTEGER AS ordering, title, region, language, types, attributes, "
                  "isOriginalTitle::BOOLEAN AS isOriginalTitle",
    "title.episode": "tconst, parentTconst, seasonNumber::INTEGER AS seasonNumber, "
                     "episodeNumber::INTEGER AS episodeNumber",
}


def raw_path(name):
    return config.RAW / "imdb" / f"{name}.tsv.gz"


def table_name(name):
    return name.replace(".", "_")


def download(name):
    url = config.IMDB_URL.format(name=name)
    dest = raw_path(name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        last_modified = r.headers.get("Last-Modified")
        with open(dest, "wb") as f:
            shutil.copyfileobj(r.raw, f, length=1 << 20)
    return manifest.record(dest, "imdb", url, last_modified=last_modified)


def check_header(path, name):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
    expect_columns(header, config.IMDB_COLUMNS[name], path.name)


def build(names=tuple(config.IMDB_COLUMNS), db_path=config.IMDB_DB, check_manifest=True):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    for name in names:
        path = raw_path(name)
        if check_manifest:
            manifest.verify(path)
        check_header(path, name)
        rows_in_file = sum(1 for _ in gzip.open(path, "rb")) - 1
        con.execute(f"CREATE OR REPLACE TABLE {table_name(name)} AS "
                    f"SELECT {CASTS[name]} FROM read_csv('{path.as_posix()}', {READ_OPTS})")
        loaded = con.execute(f"SELECT count(*) FROM {table_name(name)}").fetchone()[0]
        if loaded != rows_in_file:
            # A row count that differs from the line count means a delimiter or quote was misread.
            raise ValueError(f"{name}: {rows_in_file:,} data lines in the file but {loaded:,} rows loaded")
    return con


def profile(con, names=tuple(config.IMDB_COLUMNS)):
    for name in names:
        t = table_name(name)
        cols = [c[0] for c in con.execute(f"DESCRIBE {t}").fetchall()]
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        entry = manifest.verify(raw_path(name))
        print(f"\nIMDb {name}")
        print(f"  rows: {n:,}   columns: {len(cols)}   period: snapshot, last modified {entry['last_modified']}")
        nulls = con.execute("SELECT " + ", ".join(f'count(*) - count("{c}")' for c in cols) + f" FROM {t}").fetchone()
        for c, k in zip(cols, nulls):
            print(f"    {c:<28} nulls {k:>12,}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    if args.download:
        for name in config.IMDB_COLUMNS:
            e = download(name)
            print(f"downloaded {name}: {e['bytes'] / 1e6:,.0f} MB, sha256 {e['sha256'][:16]}")
    con = build()
    profile(con)
    types = con.execute("SELECT titleType, count(*) FROM title_basics GROUP BY 1 ORDER BY 2 DESC").fetchall()
    print("\n  title.basics by titleType:", ", ".join(f"{t} {n:,}" for t, n in types))


if __name__ == "__main__":
    main()
