# Match report — Phase 2

Built 2026-09-25 at fuzzy threshold **88**, which is the value Checkpoint 2 exists to set. Every figure here comes from `python -m src.match_report`.

## The two joins

| join | rows | matched | rate |
|---|---|---|---|
| Netflix Top 10 → engagement report (same half) | 2,764 | 2,751 | 99.5% |
| Netflix engagement titles → IMDb id | 24,902 | 22,963 | 92.2% |

Exact string matching with no normalisation at all managed 57.0% and 54.0% on the first join (Phase 0). The difference is what the normalisation ladder is worth.

## Netflix Top 10 → engagement report

| rung | pairs |
|---|---|
| exact | 2,733 |
| alternate | 0 |
| year | 1 |
| season_equiv | 16 |
| fuzzy | 1 |
| near_miss | 13 |
| unmatched | 0 |

By period and kind:

| period | matched | of | rate |
|---|---|---|---|
| 2023H2 | 466 | 469 | 99.4% |
| 2024H1 | 436 | 442 | 98.6% |
| 2024H2 | 441 | 442 | 99.8% |
| 2025H1 | 461 | 462 | 99.8% |
| 2025H2 | 459 | 460 | 99.8% |
| 2026H1 | 488 | 489 | 99.8% |
| all periods, film | 1,526 | 1,530 | 99.7% |
| all periods, tv | 1,225 | 1,234 | 99.3% |

## Netflix → IMDb

The IMDb index holds 4,959,624 names for 2,851,090 candidate titles, including alternate titles.

| rung | matched | share of all entities |
|---|---|---|
| name | 21,450 | 86.1% |
| alternate_name | 450 | 1.8% |
| spacing | 133 | 0.5% |
| qualifier_dropped | 12 | 0.0% |
| prefix | 660 | 2.7% |
| fuzzy (≥ 88) | 258 | 1.0% |
| near miss (best score below threshold) | 1,867 | 7.5% |
| no candidate at all | 72 | 0.3% |

**98.7% of all reported viewing hours** sit on a title that reached an IMDb id — the unmatched residue is mostly small titles.

| kind | matched | of | rate |
|---|---|---|---|
| film | 15,538 | 16,154 | 96.2% |
| tv | 7,425 | 8,748 | 84.9% |

### Where a name hit more than one IMDb id

One name can match several ids. They are resolved in a fixed order — a matching year, a year within one, then vote count — and the last of those is a judgement, not a fact.

| tie-break | entities |
|---|---|
| none | 14,149 |
| votes | 5,799 |
| year | 2,520 |
| year_within_one | 237 |

Of the 5,799 resolved by votes, 2,388 had a runner-up with under 100 votes — those are not really contests. **2,140 are genuinely close** (runner-up within 10% and at least 100 votes); they are the ones worth a look:

| Netflix title | chosen | votes | runner-up votes |
|---|---|---|---|
| Rosario Tijeras (Mexico): Season 1 | tt6340304 (2016) | 783 | 638 |
| Destined with You: Limited Series // 이 연애는 불가항력: 리미티드 시리즈 | tt27974068 (2023) | 9,684 | 2,680 |
| Leo | tt15654328 (2023) | 75,034 | 47,301 |
| Carrossel | tt0170885 (1989) | 904 | 697 |
| ONE PIECE: Season 2 | tt0388629 (1999) | 366,950 | 211,015 |
| Lift | tt14371878 (2024) | 53,724 | 8,764 |
| Love of my life: Season 1 // Devuélveme la vida: Temporada 1 | tt27517632 (2024) | 736 | 601 |
| Carinha de Anjo: Season 1 | tt0247859 (2000) | 616 | 207 |
| ONE PIECE: East Blue // ワンピース: イーストブルー編 | tt0388629 (1999) | 366,950 | 211,015 |
| La Reina del Sur: Season 3 | tt1064899 (2016) | 38,470 | 3,953 |
| Rosario Tijeras (Mexico): Season 4 | tt6340304 (2016) | 783 | 638 |
| Trolls | tt1679335 (2016) | 102,375 | 36,681 |

### Two checks on the result

* **Films sharing an id:** 629 ids carry more than one film entity (1,320 entities). Most are the same film published twice by Netflix under different names — `The Godfather` and `The Godfather (1972)`, `Vertigo // 버티고` and `Vertigo (1958)` — which is the join doing its job. The rest are wrong, and they are the reason a Phase 3 fact table must be keyed on the resolved id rather than the published name.
* **Seasons IMDb does not list:** 217 of 6,049 matched TV entities report a season number IMDb has no episodes for. That is either a wrong match or IMDb being behind, and it is a cheap ongoing check on match quality.

## The fuzzy rung, and the threshold

2,139 pairs reached the fuzzy rung. Their best-score distribution:

| score band | pairs |
|---|---|
| 98–100 | 11 |
| 95–98 | 55 |
| 92–95 | 63 |
| 90–92 | 56 |
| 85–90 | 162 |
| 80–85 | 209 |
| 70–80 | 509 |
| 0–70 | 1,074 |

What each threshold would accept:

| threshold | fuzzy pairs accepted | left as near misses |
|---|---|---|
| 80 | 556 | 1,583 |
| 85 | 347 | 1,792 |
| 88 | 259 | 1,880 |
| 90 | 185 | 1,954 |
| 92 | 129 | 2,010 |
| 95 | 66 | 2,073 |
| 98 | 11 | 2,128 |

The full list is in `near-misses.csv`, worst score first. The pairs just below the current threshold are the ones to read: they decide whether the threshold moves.

### The 20 highest-scoring pairs the threshold currently rejects

| score | left | right |
|---|---|---|
| 87.8 | Detective Conan the Movie: Captured in Her Eyes // 劇場版 名探偵コナン 瞳の中の暗殺者 | detective conan captured in her eyes |
| 87.8 | Pokémon The Movie: Arceus and the Jewel of Life // 극장판 포켓몬스터 DP: 아르세우스 초극의 시공으로 | pokemon arceus and the jewel of life |
| 87.8 | Merry Christmas (Telugu) (2023) | the merry christmas |
| 87.8 | Doraemon the Movie: Nobita and the Space Heroes // 映画ドラえもん のび太の宇宙英雄記 (スペースヒーローズ) | doraemon nobita and the space heroes |
| 87.8 | Merry Christmas (Hindi) // मेरी क्रिसमस (हिंदी) | merry christmas dick |
| 87.7 | Baby Einstein Ocean Explorers: Season 1 | baby einstein farm explorers |
| 87.5 | The Grand Family: Season 1 // 華麗なる一族: シーズン1 | the giant family |
| 87.5 | Qarmat In trouble // قرمط بيتمرمط | lara in trouble |
| 87.5 | Ejakulasi Dini: Season 1 | edi ejakulasi dini |
| 87.5 | Detective Conan the Movie: Countdown to Heaven // 劇場版 名探偵コナン 天国へのカウントダウン | detective conan countdown to heaven |
| 87.5 | Our Diary // 우리들의 일기 | our day |
| 87.5 | The Dublin Murders: Season 1 | dublin murders |
| 87.5 | Just Wanna Say I Love U: Season 1 | just wanna say i love you |
| 87.5 | Didi & Friends: Season 1 | bigi and friends |
| 87.5 | Her Divorce Lawyer // محامي خلع | divorce lawyer |
| 87.5 | The 101st Proposal: Season 1 // 101回目のプロポーズ: シーズン1 | 101st proposal |
| 87.5 | Ordinary Glory // 平凡的榮耀 // 平凡的荣耀 | the ordinary glory |
| 87.5 | Emergency Interrogation Room Special // 緊急取調室: ドラマスペシャル 緊急取調室 | emergency interrogation room |
| 87.5 | Doraemon the Movie: Nobita and the Spiral City // 映画ドラえもん のび太のねじ巻き都市冒険記 | doraemon nobita and the spiral city |
| 87.5 | Burn the Witch: #0.8 | burn the witch |

---

## What Checkpoint 2 has to decide

1. **The fuzzy threshold**, from the table and the near-miss list above. Record it with three example pairs it correctly rejects — that is the interview answer.
2. **What happens to unmatched titles.** Dropping them biases the result towards titles that resolve (the long tail vanishes); keeping them breaks the joins. Either is defensible, stated plainly. The unmatched residue is 7.8% of entities but only 1.3% of hours.
3. **Whether the weak rungs stay.** `qualifier_dropped` merges `Shameless (U.S.)` with `Shameless`; `prefix` matches `ONE PIECE: East Blue` to the series and gives up knowing which arc. Their counts are above, and either can be switched off on its own.

