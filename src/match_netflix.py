"""Netflix Top 10 -> Netflix engagement report, within the same half.

The easiest join in the project — two files from the same company — and the
first honest measure of how much work normalisation is doing: exact string
matching alone got 54-57% (see data/validation/checkpoint0-sources.md).

A Top 10 row's charting title is season_title where there is one, otherwise
show_title, which is what the engagement report publishes as its Title.

Run: python -m src.match_netflix
"""
from __future__ import annotations

import pandas as pd

from src import config, ingest_engagement, ingest_top10, match


def charting_titles(top10=None, periods=config.ENGAGEMENT_PERIODS) -> pd.DataFrame:
    """Distinct (period, kind, title) that appeared in the Top 10 during each period."""
    t = ingest_top10.load() if top10 is None else top10
    t = t.assign(charting_title=t.season_title.where(t.season_title.notna(), t.show_title))
    rows = []
    for p in periods:
        window = t[(t.week >= p.start) & (t.week <= p.end)]
        for (kind, title), g in window.groupby(["kind", "charting_title"]):
            rows.append({"period": p.label, "kind": kind, "title": title,
                         "weeks_charted": g.week.nunique(),
                         "best_rank": int(g.weekly_rank.min()),
                         "top10_hours": int(g.weekly_hours_viewed.sum())})
    return pd.DataFrame(rows)


def run(threshold=match.FUZZY_THRESHOLD):
    top10 = charting_titles()
    engagement = ingest_engagement.load()
    engagement = engagement[~engagement.is_catch_all]
    left = match.candidates(top10, "title", ["period", "kind"],
                            payload_columns=["weeks_charted", "best_rank", "top10_hours"])
    right = match.candidates(engagement, "title", ["period", "kind"],
                             payload_columns=["hours_viewed", "views", "release_date"])
    return match.match(left, right, threshold=threshold)


def main():
    matched = run()
    stats = match.rate(matched)
    print(f"Top 10 -> engagement report: {stats['matched']:,} of {stats['rows']:,} "
          f"charting title-periods matched ({stats['match_rate']:.1%})")
    for stage in match.STAGES + ["near_miss", "unmatched"]:
        print(f"  {stage:<10} {stats[stage]:>6,}")
    print("\nby period:")
    for period, g in matched.groupby(matched.block.str[0]):
        print(f"  {period}  {g.matched.sum():>4} / {len(g):<4} ({g.matched.mean():.1%})")
    print("\nby kind:")
    for kind, g in matched.groupby(matched.block.str[1]):
        print(f"  {kind:<5} {g.matched.sum():>4} / {len(g):<4} ({g.matched.mean():.1%})")
    near = matched[matched.stage == "near_miss"].sort_values("score", ascending=False)
    print(f"\nnear misses (best fuzzy score below {match.FUZZY_THRESHOLD}): {len(near)}")
    for r in near.head(15).itertuples():
        print(f"  {r.score:5.1f}  {r.left_raw[:52]:<52} -> {str(r.right_raw)[:52]}")
    unmatched = matched[matched.stage == "unmatched"]
    print(f"\nno candidate in block at all: {len(unmatched)}")
    for r in unmatched.head(10).itertuples():
        print(f"    {r.left_raw[:60]:<60} season={r.season_kind} {r.season_number}")


if __name__ == "__main__":
    main()
