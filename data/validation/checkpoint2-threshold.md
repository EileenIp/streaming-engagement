# Checkpoint 2 — the threshold, the residue, and the weak rungs

Decided by Eileen, 2026-09-25, from `match-report.md` and `near-misses.csv`.
The numbers below are at the decided settings.

## 1. Fuzzy threshold: 88

Read the near-miss list by score band before choosing. What each band actually
contains is the whole argument:

| band | pairs | what they look like |
|---|---|---|
| 88–90 | 76 | **mostly true matches.** Whole film families where the two sources phrase a name differently: Netflix writes `Detective Conan the Movie: The Scarlet Bullet`, IMDb writes `detective conan the scarlet bullet`; same for the Doraemon films. Also plain suffix differences: `Ray Winstone's Sicily: Season 1` / `ray winstone in sicily`. |
| 85–88 | 90 | **genuinely mixed.** `Railroad Man // 鉄道員` → `the railroad man` is right; `Sir (Hindi) (2023)` → `jai hind sir` is a different film. |
| 80–85 | 213 | **mostly wrong.** `Louis C.K.: Ridiculous` → `ridiculous cakes`. |
| below 80 | 1,563 | wrong, with occasional exceptions that only a person would spot. |

88 is where the band above is mostly right and the band below is not. It is not
a round number chosen for looking principled: it is the edge of the Conan and
Doraemon families, which are the largest group of real matches the fuzzy rung
finds at all.

**Three pairs 88 correctly rejects** — the interview answer:

| score | Netflix | IMDb | why rejecting it is right |
|---|---|---|---|
| 85.7 | `Sir (Hindi) (2023)` | `jai hind sir` | Different films. The short name makes any small edit look large. |
| 85.1 | `Matsumoto Seicho's Kao // 松本清張 顔` | `matsumoto seicho no ekiro` | Same author's name, different work — the part that differs is the title. |
| 80.0 | `Louis C.K.: Ridiculous` | `ridiculous cakes` | Shares one word, nothing else. The kind of pair a lower threshold would let in. |

What moving it costs, from the same run: at 88 the fuzzy rung accepts 258 pairs;
at 90 it accepts 181; at 85, 348.

## 2. Unmatched titles: kept, and flagged

Kept in the data with no IMDb id rather than dropped, so nothing disappears
quietly. They fall out only of results that need IMDb columns, and any figure
computed on matched titles alone says so.

The residue after the decisions: **1,939 of 24,902 entities (7.8%)**, carrying
**1.3% of reported viewing hours**. It is small titles, and the honest reason to
keep them is that dropping them would bias every "which titles earn their place"
result towards titles that happen to resolve.

## 3. Both weak rungs stay

- **`prefix` (660 matches).** `ONE PIECE: East Blue` matches the One Piece
  series. It gains the title and gives up knowing which arc, which is most of
  the reason TV went from 77% to 85%. Kept, with the arc name still in the raw
  title, so a later phase can decide what to do with it.
- **`qualifier_dropped` (12 matches).** `Shameless (U.S.)` reaching `Shameless`.
  Twelve titles, and the risk is real — it can merge the UK and US versions of a
  show — so it is the weakest rung, tried last, and counted on its own.

Both can be switched off individually in `match_imdb.RUNGS`.

## Result at these settings

| join | rows | matched | rate |
|---|---|---|---|
| Netflix Top 10 → engagement report | 2,764 | 2,751 | 99.5% |
| Netflix engagement titles → IMDb id | 24,902 | 22,963 | 92.2% |
| — film | 16,154 | 15,538 | 96.2% |
| — TV | 8,748 | 7,425 | 84.9% |
| share of reported hours matched | | | 98.7% |

## Still outstanding

The 30-pair fixture in `label.html` has not been labelled yet. Until it is,
`test_threshold_agrees_with_the_hand_labelled_pairs` skips, and 88 rests on the
band-by-band reading above rather than on pair-by-pair ground truth. The pairs
were sampled across score bands and the page does not show the score or what the
pipeline decided, so the labels stay independent of it.
