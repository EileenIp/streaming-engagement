# Phase 4 — findings

Built 2026-09-27 from the star schema. Intervals are 95% bootstrap intervals over 2,000 resamples **of titles**, not of rows: a title contributes several seasons and periods, and resampling rows would treat those as independent evidence.

Three limits apply to everything below, so they are stated once. The engagement reports are half-yearly, so the finest grain available for hours is six months. Hours are rounded to the nearest 100,000 and the smallest published value is 100,000, so the long tail is cut off. And the Top 10 is capped at ten slots per category per week, so chart presence is zero-sum in a way hours are not.

## 1. Which genres over-deliver hours against their chart presence?

Share of reported hours divided by share of Top 10 slots. Above 1 means a genre gets watched more than its chart presence would suggest; below 1 means it charts more than it is watched. Genres with fewer than 25 titles are dropped. Genres come from IMDb, not Netflix, and a title with three genres counts in all three.

| genre       |   titles |   charting |   hours_share |   slots_share |   delivery | ci        |
|:------------|---------:|-----------:|--------------:|--------------:|-----------:|:----------|
| Family      |     1427 |         82 |           2.3 |           1.4 |       1.65 | 1.23–2.32 |
| Western     |       92 |         12 |           0.2 |           0.2 |       1.36 | 0.93–2.07 |
| Animation   |     2751 |        212 |           6.1 |           4.6 |       1.32 | 1.1–1.61  |
| Fantasy     |     1301 |        118 |           2.9 |           2.4 |       1.23 | 1.01–1.51 |
| Music       |      577 |         40 |           0.5 |           0.5 |       1.21 | 0.77–1.88 |
| Adventure   |     3332 |        381 |           8.5 |           7.2 |       1.18 | 1.04–1.36 |
| Drama       |    11069 |       1158 |          22.8 |          20.9 |       1.09 | 1.03–1.15 |
| Comedy      |     8217 |        680 |          13.1 |          12.3 |       1.07 | 0.97–1.18 |
| Romance     |     3513 |        337 |           6.3 |           6.3 |       1.01 | 0.89–1.17 |
| Musical     |      176 |          7 |           0.2 |           0.2 |       0.99 | 0.42–4.15 |
| Action      |     4560 |        604 |          10.6 |          10.7 |       0.98 | 0.89–1.08 |
| Mystery     |     1877 |        219 |           3.8 |           4.1 |       0.94 | 0.8–1.11  |
| Game-Show   |      209 |         36 |           0.5 |           0.5 |       0.93 | 0.76–1.25 |
| Crime       |     3784 |        576 |           9.4 |          10.2 |       0.93 | 0.84–1.02 |
| Sci-Fi      |      679 |         58 |           0.9 |           1   |       0.91 | 0.66–1.32 |
| War         |      235 |         12 |           0.1 |           0.2 |       0.83 | 0.57–1.57 |
| Biography   |     1134 |        105 |           1.3 |           1.6 |       0.83 | 0.68–1.03 |
| Short       |      218 |          7 |           0.1 |           0.1 |       0.8  | 0.44–3.08 |
| Horror      |     1626 |        138 |           2   |           2.5 |       0.8  | 0.56–1.17 |
| Reality-TV  |      683 |        101 |           1.1 |           1.4 |       0.8  | 0.7–0.93  |
| History     |      820 |         91 |           1.2 |           1.5 |       0.78 | 0.66–0.95 |
| Thriller    |     2643 |        346 |           3.9 |           5.8 |       0.67 | 0.58–0.77 |
| Sport       |      597 |         71 |           0.6 |           0.9 |       0.66 | 0.53–0.84 |
| Talk-Show   |      123 |          2 |           0   |           0.1 |       0.44 | 0.27–nan  |
| Documentary |     1710 |        247 |           1.4 |           3.2 |       0.44 | 0.4–0.48  |

## 2. Do higher-rated titles hold the chart longer?

Among the 2,282 titles that charted inside a report period and have an IMDb rating. Spearman correlation between rating and weeks charted: **0.118** (p = 1.48e-08).

Rating on its own is confounded — big titles get watched, rated and charted together — so the same question with size held constant:

| term        |   estimate |   ci_low |   ci_high |
|:------------|-----------:|---------:|----------:|
| intercept   |    -24.419 |  -28.039 |   -21.375 |
| rating      |      0.062 |   -0.034 |     0.165 |
| log_hours   |      3.581 |    3.151 |     4.089 |
| log_votes   |     -0.25  |   -0.452 |    -0.079 |
| is_tv       |     -1.074 |   -1.5   |    -0.739 |
| non_english |      1.076 |    0.889 |     1.268 |

R² = 0.384. The response is weeks charted, so an estimate of 0.5 on `rating` would mean half a week more chart time per rating point.

**Censoring:** 37 titles were still in the chart in the file's last week, so their runs are cut short by the data ending, not by the title falling out.

## 3. Does outside interest lead or lag on-platform viewing?

Weekly Wikipedia pageviews against weekly Top 10 hours, for the 63 titles with at least 8 overlapping weeks. Both series are turned into week-on-week changes first: in levels they both spike at release and decay, so they correlate whatever the timing. A negative lag means pageviews moved first, and a lag is only tried when at least 6 weeks survive the shift.

**The hours series only exists while a title is charting.** Weekly hours come from the Top 10 file, so the on-platform series stops when the title leaves the chart while pageviews carry on. Any tail beyond the chart run is missing from one side and present on the other.

| best lag (weeks) | titles |
|---|---|
| -4 | 1 |
| -3 | 1 |
| -2 | 2 |
| -1 | 4 |
| +0 | 47 |
| +1 | 3 |
| +3 | 4 |
| +4 | 1 |

Median best lag **+0 weeks**, median correlation at that lag 0.83. Of the 16 titles with a non-zero best lag, 8 lead and 8 lag (sign test p = 1); 47 move in the same week.

**Is the same-week co-movement about the title at all?** Both series rise at release and decay, so any two of them share that shape. Pairing each title's hours with a *different* title's pageviews gives a median correlation of **0.23** against **0.82** for the real pairings, and 28 of 63 titles beat the placebo's 95th percentile (0.83). So the correlation is mostly title-specific, not just the shared shape.

**What this can and cannot say.** The estimate is the best-fitting lag per title, picked from nine candidates, so some of the spread is the search itself. Coverage is the bigger limit: English Wikipedia only, on titles that charted at least five weeks, which excludes most non-English titles even though they are half the chart by construction.

Titles where the relationship is strongest, in either direction:

| title                                                                            | kind   |   weeks |   best_lag |    r |
|:---------------------------------------------------------------------------------|:-------|--------:|-----------:|-----:|
| The Witcher: Season 3                                                            | tv     |       8 |          0 | 0.99 |
| The Crown: Season 6                                                              | tv     |       8 |          0 | 0.99 |
| Baby Reindeer: Limited Series                                                    | tv     |       8 |          0 | 0.99 |
| Bon Appétit, Your Majesty: Limited Series // 폭군의 셰프: 리미티드 시리즈        | tv     |      10 |          0 | 0.98 |
| When Life Gives You Tangerines: Limited Series // 폭싹 속았수다: 리미티드 시리즈 | tv     |       9 |          0 | 0.98 |
| Bridgerton: Season 2                                                             | tv     |       8 |         -1 | 0.97 |
| Sirens: Limited Series                                                           | tv     |       8 |          0 | 0.97 |
| My Royal Nemesis: Limited Series // 멋진 신세계: 리미티드 시리즈                 | tv     |       8 |          0 | 0.97 |
| Cobra Kai: Season 6                                                              | tv     |       9 |          0 | 0.97 |
| Outer Banks: Season 4                                                            | tv     |       8 |          0 | 0.96 |

---

## What Checkpoint 4 has to decide

Interpretation, and the renewal-shaped recommendation. The findings above are measurements; what a content team should *do* about them is Eileen's, because it is the part an interviewer will push on.

