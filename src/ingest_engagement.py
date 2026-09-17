"""Netflix engagement reports ("What We Watched"): download, then load to one tidy table.

Titles are loaded exactly as published. Splitting off ' // ' alternate names,
season suffixes and the rest is Phase 2's job, and doing any of it here would
hide from the match report what the raw string was.

Run: python -m src.ingest_engagement [--download]
"""
import argparse
import re

import openpyxl
import pandas as pd
import requests

from src import config, manifest
from src.schema import SchemaError, expect_columns, expect_not_html, profile

OUT_COLUMNS = ["period", "period_start", "period_end", "kind", "title", "available_globally",
               "release_date", "hours_viewed", "runtime_hours", "runtime_withheld", "runtime_starred",
               "views", "is_catch_all", "source_row"]


def raw_path(period: config.Period):
    return config.RAW / "engagement" / f"engagement_{period.label}.xlsx"


def download(period: config.Period):
    page_url = config.NETFLIX_NEWS_URL.format(slug=period.news_slug)
    page = requests.get(page_url, headers={"User-Agent": config.BROWSER_UA}, timeout=60)
    page.raise_for_status()
    links = sorted(set(re.findall(r"https://[^\"' ]+\.xlsx", page.text)))
    if len(links) != 1:
        raise SchemaError(f"{period.label}: expected one xlsx link on {page_url}, found {links}")
    r = requests.get(links[0], headers={"User-Agent": config.BROWSER_UA}, timeout=120)
    r.raise_for_status()
    expect_not_html(r, links[0])
    dest = raw_path(period)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return manifest.record(dest, "netflix_engagement", links[0], period=period.label, page=page_url)


def parse_runtime(value):
    """Runtime text -> (hours, withheld, starred). Three forms occur, all on the Shows/TV sheet:

    'H:MM'   the normal case; hours can run past 100 for long-running series.
    '*'      no runtime published: 171-193 rows per report. Views are still given.
    'H:MM*'  a runtime with an asterisk: 3 rows in 2024 H2 rising to 117 in 2026 H1,
             including live events (WWE Raw episodes, Jake Paul vs. Mike Tyson).

    Netflix explains neither asterisk in the files or on the report pages, so
    both are kept as flags and no meaning is assumed. Anything else is a schema error.
    """
    if value is None:
        return None, False, False
    text = str(value).strip()
    if text == "*":
        return None, True, False
    m = re.fullmatch(r"(\d+):([0-5]\d)(\*?)", text)
    if not m:
        raise SchemaError(f"runtime {value!r} is not H:MM, H:MM* or *")
    return int(m.group(1)) + int(m.group(2)) / 60, False, m.group(3) == "*"


def read_workbook(path, period: config.Period) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True)
    names = [ws.title for ws in wb.worksheets]
    unknown = [n for n in names if n not in config.ENGAGEMENT_SHEET_KIND]
    kinds = sorted(config.ENGAGEMENT_SHEET_KIND[n] for n in names if n in config.ENGAGEMENT_SHEET_KIND)
    if unknown or kinds != ["film", "tv"]:
        raise SchemaError(f"{path.name}: expected one TV and one film sheet, found {names}")

    rows = []
    first, width = config.ENGAGEMENT_FIRST_COL - 1, len(config.ENGAGEMENT_COLUMNS)
    for ws in wb.worksheets:
        kind = config.ENGAGEMENT_SHEET_KIND[ws.title]
        for n, r in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = list(r[first:first + width]) + [None] * max(0, width - len(r[first:]))
            if n < config.ENGAGEMENT_HEADER_ROW:
                continue
            if n == config.ENGAGEMENT_HEADER_ROW:
                expect_columns(cells, config.ENGAGEMENT_COLUMNS, f"{path.name}/{ws.title}")
                continue
            title, glob, released, hours, runtime, views = cells
            if title is None and hours is None:
                continue
            if not isinstance(hours, (int, float)):
                if isinstance(title, str) and title.startswith("*"):
                    continue  # footnote
                raise SchemaError(f"{path.name}/{ws.title} row {n}: hours {hours!r} is not a number")
            title = str(title)
            if title in config.ENGAGEMENT_CATCH_ALL:
                # '*' in every field except hours; parsing them as a title's values would fail or mislead.
                glob = released = runtime = views = None
            runtime_hours, runtime_withheld, runtime_starred = parse_runtime(runtime)
            if views is not None and not isinstance(views, (int, float)):
                raise SchemaError(f"{path.name}/{ws.title} row {n}: views {views!r} is not a number")
            if glob not in ("Yes", "No", None):
                raise SchemaError(f"{path.name}/{ws.title} row {n}: Available Globally? is {glob!r}")
            rows.append({
                "period": period.label, "period_start": period.start, "period_end": period.end,
                "kind": kind, "title": title,
                "available_globally": {"Yes": True, "No": False}.get(glob),
                "release_date": pd.to_datetime(released).date() if released else None,
                "hours_viewed": int(hours), "runtime_hours": runtime_hours,
                "runtime_withheld": runtime_withheld, "runtime_starred": runtime_starred,
                "views": int(views) if views is not None else None,
                "is_catch_all": title in config.ENGAGEMENT_CATCH_ALL,
                "source_row": f"{ws.title}!{n}",
            })
    df = pd.DataFrame(rows, columns=OUT_COLUMNS)
    df["views"] = df["views"].astype("Int64")
    return df


def load(periods=config.ENGAGEMENT_PERIODS, check_manifest=True) -> pd.DataFrame:
    frames = []
    for p in periods:
        path = raw_path(p)
        if check_manifest:
            manifest.verify(path)
        frames.append(read_workbook(path, p))
    return pd.concat(frames, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="fetch the reports before loading")
    args = ap.parse_args()
    if args.download:
        for p in config.ENGAGEMENT_PERIODS:
            e = download(p)
            print(f"downloaded {p.label}: {e['bytes']:,} bytes, sha256 {e['sha256'][:16]}")
    df = load()
    periods = f"{df.period_start.min()} to {df.period_end.max()} ({df.period.nunique()} reports)"
    profile(df, "Netflix engagement reports", periods)
    titles = df[~df.is_catch_all]
    print("  titles per report:")
    for (period, kind), n in titles.groupby(["period", "kind"]).size().items():
        print(f"    {period} {kind:<4} {n:>6,}")
    print(f"  catch-all rows (excluded from title-level work): {int(df.is_catch_all.sum())}")
    flags = titles.groupby("period")[["runtime_withheld", "runtime_starred"]].sum()
    print("  runtime markers (withheld = '*', starred = 'H:MM*'):")
    for period, row in flags.iterrows():
        print(f"    {period} withheld {row.runtime_withheld:>4}  starred {row.runtime_starred:>4}")


if __name__ == "__main__":
    main()
