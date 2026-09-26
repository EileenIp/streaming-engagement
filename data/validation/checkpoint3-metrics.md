# Checkpoint 3 — what does "earning its place" mean?

Built 2026-09-27 from `v_earning_its_place`, over the 16,313 titles with at least 1M reported hours. Every figure is from `python -m src.metric_options`.

The spec names three candidates and leaves the choice here. What each one can actually be computed for:

|   titles |   can_do_hours_per_week |   can_do_longevity |   can_do_demand |
|---------:|------------------------:|-------------------:|----------------:|
|    16313 |                   16313 |               2386 |             229 |

## Candidate 1 — hours per week available since release

Total reported hours divided by the weeks between release and the end of the last report. Rewards titles that pull a lot of viewing quickly.

**The catch is the denominator.** Netflix publishes a release date for about a quarter of titles; the rest fall back to IMDb's start year, then to the first period the title was reported in. Which source was used is a column, `available_from_source`, because it changes the answer by an order of magnitude:

| available_from_source   |   titles |   median_weeks |
|:------------------------|---------:|---------------:|
| imdb_start_year         |     9929 |            495 |
| netflix_release_date    |     5802 |            215 |
| first_period_reported   |      582 |            130 |

It also punishes old catalogue titles by construction. These are real, large titles whose hours are spread over a denominator of decades:

| title                        |   imdb_year |   hours_m |   weeks_available |   hours_per_week_m |
|:-----------------------------|------------:|----------:|------------------:|-------------------:|
| Suits (2011): Season 1       |        2011 |    4661.2 |               808 |              5.769 |
| Grey's Anatomy: Season 1     |        2005 |    3520.4 |              1121 |              3.14  |
| Gilmore Girls: Season 1      |        2000 |    3496.3 |              1382 |              2.53  |
| The Walking Dead: Season 1   |        2010 |    2864.2 |               860 |              3.33  |
| Shameless (U.S.): Season 1   |        2011 |    2805.4 |               808 |              3.472 |
| Gossip Girl (2007): Season 1 |        2007 |    2380.8 |              1017 |              2.341 |

**And it explodes at the other end.** A title released days before the report closes has a denominator of one or two weeks, so its rate is meaningless:

| title                                                         |   hours_m |   weeks_available |   hours_per_week_m |
|:--------------------------------------------------------------|----------:|------------------:|-------------------:|
| I Will Find You: Limited Series                               |     350.5 |                 1 |              350.5 |
| Teach You a Lesson: Limited Series // 참교육: 리미티드 시리즈 |     514.7 |                 3 |              171.6 |
| Voicemails for Isabelle                                       |     104.8 |                 1 |              104.8 |
| Avatar: The Last Airbender: Season 2                          |      90   |                 1 |               90   |
| Rosario Tijeras (Mexico): Season 5                            |     167.8 |                 2 |               83.9 |

Ranked with a floor of eight weeks available, which is the smallest window that stops that happening:

| title                                       | kind   |   hours_m |   hours_per_week_m |   weeks_available |   weeks_charted |   best_rank |   hours_m_per_1k_views | pageview_days   |
|:--------------------------------------------|:-------|----------:|-------------------:|------------------:|----------------:|------------:|-----------------------:|:----------------|
| Stranger Things 5                           | tv     |    1458.1 |              48.6  |                30 |              10 |           1 |                 nan    | <NA>            |
| Bridgerton: Season 4                        | tv     |     889.8 |              42.37 |                21 |               9 |           1 |                 nan    | <NA>            |
| Man on Fire: Season 1                       | tv     |     224.3 |              28.04 |                 8 |               5 |           1 |                   0.31 | 173             |
| Swapped                                     | film   |     222.4 |              27.8  |                 8 |              13 |           1 |                   0.2  | 166             |
| ONE PIECE: Season 2                         | tv     |     383.5 |              23.97 |                16 |               5 |           1 |                   0.7  | 181             |
| Apex                                        | film   |     204.2 |              22.69 |                 9 |               6 |           1 |                   0.06 | 181             |
| Wednesday: Season 2                         | tv     |    1035.4 |              22.51 |                46 |              11 |           1 |                 nan    | <NA>            |
| Squid Game: Season 2 // 오징어 게임: 시즌 2 | tv     |    1614.6 |              20.7  |                78 |              14 |           1 |                 nan    | <NA>            |
| KPop Demon Hunters                          | film   |    1081   |              20.4  |                53 |              64 |           1 |                   0.07 | 433             |
| His & Hers: Limited Series                  | tv     |     454.3 |              18.93 |                24 |               7 |           1 |                   0.14 | 181             |

## Candidate 2 — Top 10 longevity (weeks charted)

Weeks the title spent in the global Top 10. Netflix's own measure of staying power, and it needs no release date at all.

**The catch is coverage.** Only 2,386 of 16,313 titles ever charted, so for the rest the metric is not low, it is absent. It is also capped and lumpy: ten slots per category per week, so a title either charts or it does not, and a huge catalogue title that never charts scores zero.

Top 10 by this metric:

| title                                       | kind   |   hours_m |   hours_per_week_m |   weeks_available |   weeks_charted |   best_rank |   hours_m_per_1k_views | pageview_days   |
|:--------------------------------------------|:-------|----------:|-------------------:|------------------:|----------------:|------------:|-----------------------:|:----------------|
| KPop Demon Hunters                          | film   |    1081   |              20.4  |                53 |              64 |           1 |                   0.07 | 433             |
| Raw: January 6, 2025                        | tv     |     348.2 |               4.52 |                77 |              47 |           4 |                 nan    | <NA>            |
| Squid Game: Season 1 // 오징어 게임: 시즌 1 | tv     |     845.3 |               3.39 |               249 |              32 |           1 |                   0.07 | 1096            |
| Stranger Things 4                           | tv     |    1318.1 |               6.19 |               213 |              29 |           1 |                 nan    | <NA>            |
| Wednesday: Season 1                         | tv     |     847.7 |               4.53 |               187 |              28 |           1 |                   0.08 | 1096            |
| The Boss Baby                               | film   |     433.4 |               0.88 |               495 |              27 |           2 |                   0.33 | 1096            |
| Ms. Rachel: Season 1                        | tv     |     591.7 |               7.68 |                77 |              27 |           5 |                 nan    | <NA>            |
| The Super Mario Bros. Movie                 | film   |     416.6 |               2.29 |               182 |              24 |           4 |                   0.05 | 1096            |
| Raw: April 20, 2026                         | tv     |     150.8 |               6.03 |                25 |              23 |           4 |                 nan    | <NA>            |
| DAN DA DAN // ダンダダン                    | tv     |     271.7 |               2.09 |               130 |              23 |           2 |                   4.42 | 123             |

## Candidate 3 — hours per 1,000 Wikipedia pageviews

On-platform viewing against off-platform interest: how much watching Netflix got out of the attention a title had. High means it over-delivered against its public profile; low means people looked it up and did not watch it.

Pageviews are counted only over days inside the periods a title was reported in, because English articles differ wildly in age - 170 days for *Berlin and the Lady with an Ermine*, three years for *Stranger Things* - and unaligned totals would make a young article look like public indifference. `pageview_days` is in the output so that coverage stays visible.

**The catch is coverage again, and language.** It can be computed for 229 titles — the ones that charted at least five weeks and have an English Wikipedia article (see `fetch_demand.py` for why that scope, and it is partly a rate limit). English Wikipedia also under-represents non-English titles, which are half the Top 10 by construction.

It needs a floor of its own: *Unfamiliar: Season 1* has nine days of article history, which is not a measure of public interest. Ranked over titles with at least 60 days of pageviews:

| title                                                                                        | kind   |   hours_m |   hours_per_week_m |   weeks_available |   weeks_charted |   best_rank |   hours_m_per_1k_views |   pageview_days |
|:---------------------------------------------------------------------------------------------|:-------|----------:|-------------------:|------------------:|----------------:|------------:|-----------------------:|----------------:|
| Berlin and the Lady with an Ermine: Limited Series // Berlín y la dama del armiño: Miniserie | tv     |     204.4 |              34.07 |                 6 |               5 |           1 |                 834.29 |              80 |
| Rulers of Fortune: Season 1 // Os Donos do Jogo: Temporada 1                                 | tv     |     198   |               5.82 |                34 |               6 |           1 |                  19.05 |             208 |
| Destined with You: Limited Series // 이 연애는 불가항력: 리미티드 시리즈                     | tv     |     445.8 |               3.01 |               148 |               8 |           3 |                  11.45 |            1050 |
| CoComelon Lane: Season 1                                                                     | tv     |     299.3 |               2.2  |               136 |               6 |           3 |                   6.19 |             781 |
| The Accident: Season 1 // Accidente: Temporada 1                                             | tv     |     407.7 |               4.25 |                96 |               7 |           1 |                   5.57 |             403 |
| The Wages of Fear // Le salaire de la peur                                                   | film   |     141.5 |               1.21 |               117 |               8 |           1 |                   4.5  |             309 |
| Caramelo                                                                                     | film   |     105.3 |               2.85 |                37 |               8 |           1 |                   4.44 |             259 |
| DAN DA DAN // ダンダダン                                                                     | tv     |     271.7 |               2.09 |               130 |              23 |           2 |                   4.42 |             123 |
| Beckham: Limited Series                                                                      | tv     |     253.1 |               1.78 |               142 |               6 |           1 |                   3.49 |             705 |
| Counterattack // Contraataque                                                                | film   |     135.6 |               1.97 |                69 |              12 |           1 |                   3.34 |             440 |

**One caveat that applies to any pairing of these metrics.** Hours stop at the last report (30 June 2026); the Top 10 file runs to 13 September 2026 and pageviews to yesterday. So a title can show more weeks charted than weeks available - *Swapped* charts 13 weeks against 8 weeks available - because the two numbers end on different days. Any headline built on both needs one cut-off, stated.

## How much do they agree?

|   hours_week_vs_longevity |   hours_vs_longevity |   hours_week_vs_demand |   longevity_vs_pageviews |
|--------------------------:|---------------------:|-----------------------:|-------------------------:|
|                      0.18 |                 0.47 |                   0.31 |                     0.43 |

## What to decide

One headline metric and one supporting metric, with the reason written down. The shape of the trade-off:

| | computable for | needs | biased against |
|---|---|---|---|
| hours per week available | 16,313 titles | a release date, mostly inferred | old catalogue titles |
| Top 10 longevity | 2,386 titles | nothing | anything that never charted |
| hours per 1k pageviews | 229 titles | Wikipedia + a chart run | non-English titles |

