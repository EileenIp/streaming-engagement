"""Loaders refuse a file whose columns changed rather than guess at what moved."""
import requests


class SchemaError(ValueError):
    pass


def expect_columns(found, expected, where):
    found = [str(c).strip() if c is not None else None for c in found]
    if found != list(expected):
        missing = [c for c in expected if c not in found]
        extra = [c for c in found if c not in expected]
        raise SchemaError(f"{where}: columns changed. expected {list(expected)}, found {found}"
                          f" (missing {missing}, unexpected {extra})")


def expect_not_html(response: requests.Response, url: str):
    """Netflix serves its 'unsupported browser' page as HTTP 200, so status alone proves nothing."""
    ctype = response.headers.get("Content-Type", "")
    if "text/html" in ctype or response.content[:15].lstrip().lower().startswith((b"<!doctype", b"<html")):
        raise SchemaError(f"{url} returned an HTML page, not data (Content-Type {ctype!r})")


def profile(df, name, period):
    """The Phase 1 acceptance print: rows, columns, nulls, period covered."""
    print(f"\n{name}")
    print(f"  rows: {len(df):,}   columns: {len(df.columns)}   period: {period}")
    nulls = df.isna().sum()
    for col in df.columns:
        print(f"    {col:<28} nulls {nulls[col]:>9,}")
