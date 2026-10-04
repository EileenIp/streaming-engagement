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

## Still outstanding at the time

The 30-pair fixture was unlabelled when this was written, so 88 rested on the
band-by-band reading above rather than on pair-by-pair ground truth. That was
settled on 2026-10-04 — see the section below, which is what moved the threshold
to 87.

---

## The hand-labelled fixture — Eileen, 2026-10-04

Eileen labelled 29 of the 30 sampled pairs in `label.html` (p12, *When Cousins
Marry* against *my swedish cousins*, was left unanswered). The page showed two
names and the source each came from — never the score, never what the pipeline
had decided — so the labels are independent of the threshold they are used to
judge. 19 same, 10 different.

**Threshold moved from 88 to 87.** Disagreements with her labels, counted over
the 29 she judged:

| threshold | accepted but different | rejected but same | total |
|---|---|---|---|
| 83 | 4 | 1 | 5 |
| 85 | 3 | 2 | 5 |
| **87** | **2** | **1** | **3** |
| 88 | 2 | 2 | 4 |
| 90 | 1 | 5 | 6 |
| 95 | 0 | 10 | 10 |

87 is where her answers put it, and `test_the_threshold_matches_eileens_hand_labelled_pairs`
now holds the constant there: it fails if any threshold between 70 and 100 would
disagree with her less often. It also fails if any pair scoring 95 or above turns
out not to be a match — whatever the error rate is, the confident end has to be clean.

### What the audit found that the threshold could not fix

**One disagreement was a missing rung, not a bad threshold.** She called
`Tughlaq Durbar (Telugu)` and `tughlaq durbar` the same film; it scored 80.0 and
was rejected. The `qualifier_dropped` rung exists for exactly that shape, but it
was restricted to TV, so 153 film titles carrying a language qualifier — almost
all Indian-language versions — could never reach it. The rung now applies to a
film when it has a published year or a multi-word name, which keeps
`Leo (Hindi) (2023)` and blocks `Bro (Hindi)` from becoming the key `bro`.
**82 titles newly matched**, among them *Kalki 2898 AD (Hindi)*,
*Baahubali 2: The Conclusion (Hindi Version)* and *Spider-Man: No Way Home
(Extended Version)*. Overall matching went from 92.2% to 92.7%.

**Two pairs the pipeline accepts are not matches, and no threshold excludes them:**

| score | Netflix | IMDb |
|---|---|---|
| 90.9 | `Project Mc²: Part 2` | `project c24` |
| 88.4 | `The Secret World of Lego` | `the secret world of` |

Both are recorded rather than ruled out. A rule to catch them — one name being a
truncation or near-prefix of the other — would also reject `Broken Hearts Gallery`
against `the broken hearts gallery`, which she labelled a match. **So the fuzzy
rung's measured error rate is about 2 in 29 audited pairs, and that is stated
rather than engineered away.**

**Two remaining rejections are translation variants**, which string distance
cannot reach: `Crayon Shin-chan the Movie: Action Kamen vs. Leotard Devil`
against `crayon shin chan action mask vs leotard devil` (83.2 — *Kamen* and
*mask* are the same word in two languages), and the Doraemon film at 87.5, which
87 now accepts.

**On the audit itself:** the recorded scores in `label-pairs.json` are the ones
the pairs had when she judged them. The Tughlaq pair now matches on a rung
instead of through fuzzy, so that score is history rather than current state —
which is what an audit snapshot is. `match_report.py` refuses to re-sample the
fixture once `pair-labels.json` exists, because the labels are keyed by pair id
and re-sampling would silently point them at different pairs.
