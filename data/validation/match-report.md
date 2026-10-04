# Match report — Phase 2

Built 2026-10-04 at fuzzy threshold **87**, which is the value Checkpoint 2 exists to set. Every figure here comes from `python -m src.match_report`.

## The two joins

| join | rows | matched | rate |
|---|---|---|---|
| Netflix Top 10 → engagement report (same half) | 2,764 | 2,751 | 99.5% |
| Netflix engagement titles → IMDb id | 24,902 | 23,072 | 92.7% |

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
| qualifier_dropped | 95 | 0.4% |
| prefix | 660 | 2.7% |
| fuzzy (≥ 87) | 284 | 1.1% |
| near miss (best score below threshold) | 1,758 | 7.1% |
| no candidate at all | 72 | 0.3% |

**98.8% of all reported viewing hours** sit on a title that reached an IMDb id — the unmatched residue is mostly small titles.

| kind | matched | of | rate |
|---|---|---|---|
| film | 15,633 | 16,154 | 96.8% |
| tv | 7,439 | 8,748 | 85.0% |

### Where a name hit more than one IMDb id

One name can match several ids. They are resolved in a fixed order — a matching year, a year within one, then vote count — and the last of those is a judgement, not a fact.

| tie-break | entities |
|---|---|
| none | 14,183 |
| votes | 5,830 |
| year | 2,538 |
| year_within_one | 237 |

Of the 5,830 resolved by votes, 2,395 had a runner-up with under 100 votes — those are not really contests. **2,160 are genuinely close** (runner-up within 10% and at least 100 votes); they are the ones worth a look:

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

* **Films sharing an id:** 642 ids carry more than one film entity (1,357 entities). Most are the same film published twice by Netflix under different names — `The Godfather` and `The Godfather (1972)`, `Vertigo // 버티고` and `Vertigo (1958)` — which is the join doing its job. The rest are wrong, and they are the reason a Phase 3 fact table must be keyed on the resolved id rather than the published name.
* **Seasons IMDb does not list:** 218 of 6,051 matched TV entities report a season number IMDb has no episodes for. That is either a wrong match or IMDb being behind, and it is a cheap ongoing check on match quality.

## The fuzzy rung, and the threshold

2,056 pairs reached the fuzzy rung. Their best-score distribution:

| score band | pairs |
|---|---|
| 98–100 | 11 |
| 95–98 | 51 |
| 92–95 | 66 |
| 90–92 | 58 |
| 85–90 | 147 |
| 80–85 | 182 |
| 70–80 | 472 |
| 0–70 | 1,069 |

What each threshold would accept:

| threshold | fuzzy pairs accepted | left as near misses |
|---|---|---|
| 80 | 515 | 1,541 |
| 85 | 333 | 1,723 |
| 88 | 256 | 1,800 |
| 90 | 186 | 1,870 |
| 92 | 128 | 1,928 |
| 95 | 62 | 1,994 |
| 98 | 11 | 2,045 |

The full list is in `near-misses.csv`, worst score first. The pairs just below the current threshold are the ones to read: they decide whether the threshold moves.

### The 20 highest-scoring pairs the threshold currently rejects

| score | left | right |
|---|---|---|
| 87.0 | Hansan: Rising Dragon - REDUX // 한산 리덕스 | hansan rising dragon |
| 87.0 | Inssa Family: Season 2 // 인싸가족: 시즌2 | family ness |
| 87.0 | Story of…Tea | a tea story |
| 87.0 | My (K)night // MY (K)NIGHT マイ・ナイト | make my night |
| 87.0 | The Fisherman and the City: Season 5 // 나만 믿고 따라와, 도시어부: 시즌5 | the man and the city |
| 87.0 | Dragon Ball Episode of Bardock: Season 1 // ドラゴンボール エピソードオブバーダック: シーズン1 | dragon ball episode of bardock |
| 87.0 | The Great Chinese Beans // فول الصين العظيم | the great chinese boxer |
| 86.8 | Doraemon the Movie: Nobita's Dorabian Nights // 映画ドラえもん のび太のドラビアンナイト | doraemon nobita s dorabian nights |
| 86.8 | Detective Conan the  Movie: Zero the Enforcer // 劇場版 名探偵コナン ゼロの執行人 | detective conan zero the enforcer |
| 86.8 | The Ancient Magus' Bride Season 2 // 魔法使いの嫁: The Ancient Magus' Bride シーズン2 | the ancient magus bride |
| 86.8 | Motu Patlu in the City of Gold | motu patlu in gold city |
| 86.7 | Mobile Suit Gundam Unicorn RE:0096: Season 1 // 機動戦士ガンダムユニコーン RE:0096: 第1期 | mobile suit gundam unicorn |
| 86.7 | Tales of Africa: Season 1 // Tales of Africa : Papa Nzenu conte l'Afrique: Season 1 | tales of azaria |
| 86.6 | BORDERLESS Ae! group's Debut Tour: Season 1 // BORDERLESS Aぇ! group デビューツアーの裏側: シーズン1 | borderless ae group s debut journey |
| 86.6 | Mobile Suit Gundam The Origin: Season 1 // 機動戦士ガンダムTHE ORIGIN: シーズン1 | mobile suit gundam the origin |
| 86.5 | Matsuko in Real Life // 「マツコ、リアルする」ディレクターズカット版 | matt in real life |
| 86.5 | My Neighbor, Chikara: Season 1 // となりのチカラ: シーズン1 | my neighbor chacha |
| 86.5 | Long March to Freedom | march to freedom |
| 86.4 | White Christmas Fireplace | christmas fireplace |
| 86.4 | Inside Men: The Original // 내부자들: 디 오리지널 | insiders the original |

---

## What Checkpoint 2 has to decide

1. **The fuzzy threshold**, from the table and the near-miss list above. Record it with three example pairs it correctly rejects — that is the interview answer.
2. **What happens to unmatched titles.** Dropping them biases the result towards titles that resolve (the long tail vanishes); keeping them breaks the joins. Either is defensible, stated plainly. The unmatched residue is 7.3% of entities but only 1.2% of hours.
3. **Whether the weak rungs stay.** `qualifier_dropped` merges `Shameless (U.S.)` with `Shameless`; `prefix` matches `ONE PIECE: East Blue` to the series and gives up knowing which arc. Their counts are above, and either can be switched off on its own.

