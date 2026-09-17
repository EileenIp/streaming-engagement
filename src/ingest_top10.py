"""Netflix Global Top 10, weekly. One file holds every week since 2021-07-04 and is
replaced in place each Tuesday, so every download is a new manifest entry.

Run: python -m src.ingest_top10 [--download]
"""
import argparse
import io

import pandas as pd
import requests

from src import config, manifest
from src.schema import SchemaError, expect_columns, expect_not_html, profile

RAW = config.RAW / "top10" / "all-weeks-global.tsv"


def download():
    r = requests.get(config.TOP10_URL, headers={"User-Agent": config.BROWSER_UA}, timeout=120)
    r.raise_for_status()
    expect_not_html(r, config.TOP10_URL)
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_bytes(r.content)
    return manifest.record(RAW, "netflix_top10", config.TOP10_URL,
                           last_modified=r.headers.get("Last-Modified"))


def read_tsv(text: str) -> pd.DataFrame:
    header = text.split("\n", 1)[0].rstrip("\r").split("\t")
    expect_columns(header, config.TOP10_COLUMNS, "all-weeks-global.tsv")
    # keep_default_na=False: a title can legitimately be "NA" or "None".
    df = pd.read_csv(io.StringIO(text), sep="\t", dtype=str, keep_default_na=False)
    for col in ["season_title", "runtime", "weekly_views"]:
        df[col] = df[col].replace({"N/A": None, "": None})
    df["week"] = pd.to_datetime(df["week"], format="%Y-%m-%d").dt.date
    for col in ["weekly_rank", "weekly_hours_viewed", "cumulative_weeks_in_top_10"]:
        df[col] = pd.to_numeric(df[col], errors="raise").astype("int64")
    df["weekly_views"] = pd.to_numeric(df["weekly_views"]).astype("Int64")
    df["runtime"] = pd.to_numeric(df["runtime"]).astype("Float64")
    df["kind"] = df["category"].str.startswith("TV").map({True: "tv", False: "film"})
    df["language"] = df["category"].str.contains("Non-English").map({True: "non-english", False: "english"})

    per_week = df.groupby(["week", "category"]).size()
    if not (per_week == 10).all():
        raise SchemaError(f"expected 10 rows per week and category; off in {list(per_week[per_week != 10].index[:5])}")
    return df


def load(check_manifest=True) -> pd.DataFrame:
    if check_manifest:
        manifest.verify(RAW)
    return read_tsv(RAW.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    if args.download:
        e = download()
        print(f"downloaded: {e['bytes']:,} bytes, last modified {e['last_modified']}, sha256 {e['sha256'][:16]}")
    df = load()
    profile(df, "Netflix Global Top 10", f"weeks ending {df.week.min()} to {df.week.max()} ({df.week.nunique()} weeks)")
    print(f"  views reported from week {df.loc[df.weekly_views.notna(), 'week'].min()}")


if __name__ == "__main__":
    main()
