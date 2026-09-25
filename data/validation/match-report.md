# Match report — Phase 2

Built 2026-09-25 at fuzzy threshold **90**, which is the value Checkpoint 2 exists to set. Every figure here comes from `python -m src.match_report`.

## The two joins

| join | rows | matched | rate |
|---|---|---|---|
| Netflix Top 10 → engagement report (same half) | 2,764 | 2,751 | 99.5% |
| Netflix engagement titles → IMDb id | 24,902 | 22,886 | 91.9% |

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
| fuzzy (≥ 90) | 181 | 0.7% |
| near miss (best score below threshold) | 1,944 | 7.8% |
| no candidate at all | 72 | 0.3% |

**98.7% of all reported viewing hours** sit on a title that reached an IMDb id — the unmatched residue is mostly small titles.

| kind | matched | of | rate |
|---|---|---|---|
| film | 15,485 | 16,154 | 95.9% |
| tv | 7,401 | 8,748 | 84.6% |

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

* **Films sharing an id:** 630 ids carry more than one film entity (1,322 entities). Most are the same film published twice by Netflix under different names — `The Godfather` and `The Godfather (1972)`, `Vertigo // 버티고` and `Vertigo (1958)` — which is the join doing its job. The rest are wrong, and they are the reason a Phase 3 fact table must be keyed on the resolved id rather than the published name.
* **Seasons IMDb does not list:** 214 of 6,049 matched TV entities report a season number IMDb has no episodes for. That is either a wrong match or IMDb being behind, and it is a cheap ongoing check on match quality.

## The fuzzy rung, and the threshold

2,139 pairs reached the fuzzy rung. Their best-score distribution:

| score band | pairs |
|---|---|
| 98–100 | 11 |
| 95–98 | 54 |
| 92–95 | 64 |
| 90–92 | 53 |
| 85–90 | 166 |
| 80–85 | 213 |
| 70–80 | 504 |
| 0–70 | 1,074 |

What each threshold would accept:

| threshold | fuzzy pairs accepted | left as near misses |
|---|---|---|
| 80 | 561 | 1,578 |
| 85 | 348 | 1,791 |
| 88 | 258 | 1,881 |
| 90 | 182 | 1,957 |
| 92 | 129 | 2,010 |
| 95 | 65 | 2,074 |
| 98 | 11 | 2,128 |

The full list is in `near-misses.csv`, worst score first. The pairs just below the current threshold are the ones to read: they decide whether the threshold moves.

### The 20 highest-scoring pairs the threshold currently rejects

| score | left | right |
|---|---|---|
| 89.9 | GODZILLA Planet of the Monsters: Part 1 // GODZILLA 怪獣惑星: パート1 | godzilla planet of the monsters |
| 89.8 | Doraemon the Movie: Nobita and the Galaxy Super-express // 映画ドラえもん のび太と銀河超特急 | doraemon nobita and the galaxy super express |
| 89.8 | Doraemon the Movie: Nobita and the Knights on Dinosaurs // 映画ドラえもん のび太と竜の騎士 | doraemon nobita and the knights on dinosaurs |
| 89.7 | Natsume Yuujinchou: Ishi Okoshi to Ayashiki Raihousha: Film Series // 夏目友人帳 石起こしと怪しき来訪者: 映画シリーズ | natsume yuujinchou ishi okoshi to ayashiki raihousha |
| 89.7 | Doraemon the Movie: Nobita and The Giant's Legend of Green Planet // 映画ドラえもん のび太と緑の巨人伝 | doraemon the movie nobita and the green giant legend |
| 89.7 | Giants the Movie // Giants the Movie ～頂点への挑戦～ | ant the movie |
| 89.7 | A Paedophile in My Family: Surviving Dad: Season 1 | a paedophile in my family surviving dad |
| 89.7 | Death of a Son | death of a soul |
| 89.6 | Detective Conan the Movie: The Phantom of Baker Street // 劇場版 名探偵コナン ベイカー街の亡霊 | detective conan the phantom of baker street |
| 89.6 | Doraemon the Movie: Nobita's Three Visionary Swordsmen // 映画ドラえもん のび太と夢幻三剣士 | doraemon nobita s three visionary swordsmen |
| 89.6 | WWE St. Valentine's Day Massacre: 1999 | waw st valentine s day massacre |
| 89.6 | Sampradayani Suppini Sudhapoosani // Sampradayini Suppini Suddapoosani | sampradayaini suppini suddapusaani |
| 89.5 | Monks in the Kitchen: Season 1 // 공양간의 셰프들: 시즌 1 | men in the kitchen |
| 89.5 | Rise of the Krays | the rise of the krays |
| 89.5 | Fall of the Krays | the fall of the krays |
| 89.4 | CoComelon Animal Time: Season 1 | cocomelon jj s animal time |
| 89.4 | Detective Conan the Movie: The Time-Bombed Skyscraper // 劇場版 名探偵コナン 時計じかけの摩天楼 | detective conan the time bombed skyscraper |
| 89.4 | Detective Conan the Movie: Magician of the Silver Sky // 劇場版 名探偵コナン 銀翼の奇術師 | detective conan magician of the silver sky |
| 89.4 | Playing with children // اللعب مع العيال | children playing with fish |
| 89.3 | Haikyu!! Movie 3: Genius and Sense // 劇場版総集編 青葉城西高校戦『ハイキュー!! 才能とセンス』 | haikyu 3 genius and sense |

---

## What Checkpoint 2 has to decide

1. **The fuzzy threshold**, from the table and the near-miss list above. Record it with three example pairs it correctly rejects — that is the interview answer.
2. **What happens to unmatched titles.** Dropping them biases the result towards titles that resolve (the long tail vanishes); keeping them breaks the joins. Either is defensible, stated plainly. The unmatched residue is 8.1% of entities but only 1.3% of hours.
3. **Whether the weak rungs stay.** `qualifier_dropped` merges `Shameless (U.S.)` with `Shameless`; `prefix` matches `ONE PIECE: East Blue` to the series and gives up knowing which arc. Their counts are above, and either can be switched off on its own.

