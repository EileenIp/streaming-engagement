"""Checkpoint 3: the three candidate headline metrics, measured side by side.

"Earning its place" needs an operational form. The spec names three candidates and
leaves the choice to Eileen. This puts numbers on each one: how many titles it can
be computed for, what it ranks at the top, how much it agrees with the others, and
where it breaks.

Writes data/validation/checkpoint3-metrics.md.

Run: python -m src.metric_options
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src import config, model

OUT = config.ROOT / "data" / "validation" / "checkpoint3-metrics.md"

# Only titles with enough of a footprint to rank; a title reported in one period with
# 100k hours is noise in any of these metrics.
FLOOR = "hours >= 1000000"


def table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def build(con) -> str:
    coverage = con.execute(f"""
        SELECT count(*) AS titles,
               count(hours_per_week_available) AS can_do_hours_per_week,
               count(weeks_charted) AS can_do_longevity,
               count(hours_per_1k_pageviews) AS can_do_demand
        FROM v_earning_its_place WHERE {FLOOR}
    """).fetchdf()
    sources = con.execute(f"""
        SELECT available_from_source, count(*) AS titles, round(median(weeks_available)) AS median_weeks
        FROM v_earning_its_place WHERE {FLOOR} GROUP BY 1 ORDER BY 2 DESC
    """).fetchdf()

    def top(metric, extra=""):
        return con.execute(f"""
            SELECT canonical_title AS title, kind,
                   round(hours / 1e6, 1) AS hours_m,
                   round(hours_per_week_available / 1e6, 2) AS hours_per_week_m,
                   weeks_available, weeks_charted, best_rank,
                   round(hours_per_1k_pageviews / 1e6, 2) AS hours_m_per_1k_views,
                   pageview_days
            FROM v_earning_its_place
            WHERE {FLOOR} {extra} AND {metric} IS NOT NULL
            ORDER BY {metric} DESC LIMIT 10
        """).fetchdf()

    agreement = con.execute(f"""
        SELECT round(corr(hours_per_week_available, weeks_charted), 2) AS hours_week_vs_longevity,
               round(corr(hours, weeks_charted), 2) AS hours_vs_longevity,
               round(corr(hours_per_week_available, hours_per_1k_pageviews), 2) AS hours_week_vs_demand,
               round(corr(weeks_charted, pageviews), 2) AS longevity_vs_pageviews
        FROM v_earning_its_place WHERE {FLOOR}
    """).fetchdf()

    old = con.execute(f"""
        SELECT e.canonical_title AS title, t.imdb_start_year AS imdb_year,
               round(e.hours / 1e6, 1) AS hours_m, e.weeks_available,
               round(e.hours_per_week_available / 1e6, 3) AS hours_per_week_m
        FROM v_earning_its_place e JOIN dim_title t USING (title_id)
        WHERE e.hours >= 1000000 AND e.weeks_available > 500
        ORDER BY e.hours DESC LIMIT 6
    """).fetchdf()

    demand_n = int(coverage.can_do_demand.iloc[0])
    young = con.execute(f"""
        SELECT canonical_title AS title, round(hours / 1e6, 1) AS hours_m, weeks_available,
               round(hours_per_week_available / 1e6, 1) AS hours_per_week_m
        FROM v_earning_its_place WHERE {FLOOR} AND weeks_available <= 3
        ORDER BY hours_per_week_available DESC LIMIT 5
    """).fetchdf()
    lines = [
        "# Checkpoint 3 — what does \"earning its place\" mean?",
        "",
        f"Built {pd.Timestamp.now():%Y-%m-%d} from `v_earning_its_place`, over the "
        f"{int(coverage.titles.iloc[0]):,} titles with at least 1M reported hours. "
        "Every figure is from `python -m src.metric_options`.",
        "",
        "The spec names three candidates and leaves the choice here. What each one can "
        "actually be computed for:",
        "",
        table(coverage),
        "",
        "## Candidate 1 — hours per week available since release",
        "",
        "Total reported hours divided by the weeks between release and the end of the last "
        "report. Rewards titles that pull a lot of viewing quickly.",
        "",
        "**The catch is the denominator.** Netflix publishes a release date for about a "
        "quarter of titles; the rest fall back to IMDb's start year, then to the first "
        "period the title was reported in. Which source was used is a column, "
        "`available_from_source`, because it changes the answer by an order of magnitude:",
        "",
        table(sources),
        "",
        "It also punishes old catalogue titles by construction. These are real, large "
        "titles whose hours are spread over a denominator of decades:",
        "",
        table(old),
        "",
        "**And it explodes at the other end.** A title released days before the report "
        "closes has a denominator of one or two weeks, so its rate is meaningless:",
        "",
        table(young),
        "",
        "Ranked with a floor of eight weeks available, which is the smallest window that "
        "stops that happening:",
        "",
        table(top("hours_per_week_available", "AND weeks_available >= 8")),
        "",
        "## Candidate 2 — Top 10 longevity (weeks charted)",
        "",
        "Weeks the title spent in the global Top 10. Netflix's own measure of staying power, "
        "and it needs no release date at all.",
        "",
        f"**The catch is coverage.** Only {int(coverage.can_do_longevity.iloc[0]):,} of "
        f"{int(coverage.titles.iloc[0]):,} titles ever charted, so for the rest the metric "
        "is not low, it is absent. It is also capped and lumpy: ten slots per category per "
        "week, so a title either charts or it does not, and a huge catalogue title that "
        "never charts scores zero.",
        "",
        "Top 10 by this metric:",
        "",
        table(top("weeks_charted")),
        "",
        "## Candidate 3 — hours per 1,000 Wikipedia pageviews",
        "",
        "On-platform viewing against off-platform interest: how much watching Netflix got "
        "out of the attention a title had. High means it over-delivered against its public "
        "profile; low means people looked it up and did not watch it.",
        "",
        "Pageviews are counted only over days inside the periods a title was reported in, "
        "because English articles differ wildly in age - 170 days for *Berlin and the Lady "
        "with an Ermine*, three years for *Stranger Things* - and unaligned totals would "
        "make a young article look like public indifference. `pageview_days` is in the "
        "output so that coverage stays visible.",
        "",
        f"**The catch is coverage again, and language.** It can be computed for {demand_n:,} "
        "titles — the ones that charted at least five weeks and have an English Wikipedia "
        "article (see `fetch_demand.py` for why that scope, and it is partly a rate limit). "
        "English Wikipedia also under-represents non-English titles, which are half the "
        "Top 10 by construction.",
        "",
        "It needs a floor of its own: *Unfamiliar: Season 1* has nine days of article "
        "history, which is not a measure of public interest. Ranked over titles with at "
        "least 60 days of pageviews:",
        "",
        table(top("hours_per_1k_pageviews", "AND pageview_days >= 60")),
        "",
        "**One caveat that applies to any pairing of these metrics.** Hours stop at the "
        "last report (30 June 2026); the Top 10 file runs to 13 September 2026 and "
        "pageviews to yesterday. So a title can show more weeks charted than weeks "
        "available - *Swapped* charts 13 weeks against 8 weeks available - because the two "
        "numbers end on different days. Any headline built on both needs one cut-off, "
        "stated.",
        "",
        "## How much do they agree?",
        "",
        table(agreement),
        "",
        "## What to decide",
        "",
        "One headline metric and one supporting metric, with the reason written down. The "
        "shape of the trade-off:",
        "",
        "| | computable for | needs | biased against |",
        "|---|---|---|---|",
        f"| hours per week available | {int(coverage.can_do_hours_per_week.iloc[0]):,} titles | a release date, mostly inferred | old catalogue titles |",
        f"| Top 10 longevity | {int(coverage.can_do_longevity.iloc[0]):,} titles | nothing | anything that never charted |",
        f"| hours per 1k pageviews | {demand_n:,} titles | Wikipedia + a chart run | non-English titles |",
        "",
    ]
    return "\n".join(lines) + "\n"


def main():
    con = duckdb.connect(str(model.MODEL_DB), read_only=True)
    report = build(con)
    OUT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
