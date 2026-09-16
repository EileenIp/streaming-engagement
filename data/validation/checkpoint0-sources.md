# Checkpoint 0 — are the four sources still what the spec says?

Checked 2026-09-17. Every figure below comes from `src/phase0_probe.py`, which
downloads the Netflix files to `data/raw/phase0/` (gitignored) and re-derives
them. Google Trends is the exception: it was checked by hand, for the reason
given in its section.

**Short version:** three of the four are live and usable as described. Google
Trends isn't, in any way a pipeline can depend on. Netflix has also announced
that the engagement report is going annual. Three decisions for Eileen are at
the bottom.

---

## 1. Netflix engagement report ("What We Watched") — live, with caveats

Seven half-year reports, one xlsx each, linked from its About Netflix news post:

| Period | File | Bytes | Sheets | Titles |
|---|---|---|---|---|
| 2023 H1 | `What_We_Watched_A_Netflix_Engagement_Report_2023Jan-Jun.xlsx` | 695,975 | Engagement | 18,214 |
| 2023 H2 | `…_2023Jul-Dec.xlsx` | 881,985 | TV / Film | 6,599 / 9,395 |
| 2024 H1 | `…_2024Jan-Jun.xlsx` | 896,503 | TV / Film | 6,801 / 9,360 |
| 2024 H2 | `…_2024Jul-Dec.xlsx` | 872,691 | TV / Film | 6,883 / 8,680 |
| 2025 H1 | `…_2025Jan-Jun.xlsx` | 913,605 | Shows / Movies | 7,508 / 8,674 |
| 2025 H2 | `…_2025Jul-Dec__6_.xlsx` | 931,483 | Shows / Movies | 7,746 / 8,724 |
| 2026 H1 | `Netflix-s_What_We_Watched_Report_2026Jan-Jun__1_.xlsx` | 988,392 | Shows / Movies | 8,194 / 9,178 |

Every file has five preamble rows, a header on row 6, and data starting in
column B. The layout hasn't changed. The contents have, and each change breaks
a naive loader:

- **Three layouts in seven files.** 2023 H1 is a single sheet with TV and film
  mixed together and only `Title, Available Globally?, Release Date, Hours
  Viewed`. `Runtime` and `Views` start in 2023 H2. The sheets are named
  `TV`/`Film` until 2024 H2, then `Shows`/`Movies`.
- **Release date changes type.** It's a real Excel date in 2023 H1 and a text
  string after that. It's blank for most titles in every file (for example,
  1,906 of 9,178 movies in 2026 H1 have one).
- **Catch-all rows appear in 2025 H2.** `Other Shows` and `Other Movies` hold
  all viewing of titles under 50k views: 659.0M and 98.2M hours in 2025 H2,
  757.0M and 102.9M in 2026 H1. Earlier reports don't have them. If they get
  loaded as titles, they become the biggest "shows" in the dataset.
- **The catch-all changes meaning in 2026 H1.** That report's footnote adds that
  *all video podcasts* are counted under `Other Shows`. So `Other Shows` can't be
  compared from one half to the next.
- **Rounding floor:** the smallest value in every file is 100,000 hours, so the
  long tail is cut off and rounded.
- **Alternate-language names** follow ` // ` in the title: 6,433 titles in
  2026 H1 (e.g. `The Girls at the Back: Limited Series // Las de la última fila:
  Miniserie`).

**Cadence change, announced July 2026:** after the 2026 H1 report, Netflix is
moving to one report a year, published in Q1, starting 2027. The next file is
therefore a full calendar year, not a half. This is the risk the spec's
readiness notes had in mind ("Netflix has changed report cadence before"), and
it now has a concrete answer: the period needs to be a column in the model,
not built into its structure. Sources:
[Deadline](https://deadline.com/2026/07/netflix-viewership-data-reports-change-to-annual-1236982322/),
[About Netflix, H1 2026](https://about.netflix.com/en/news/what-we-watched-the-first-half-of-2026).

## 2. Netflix Global Top 10 weekly — live

`https://www.netflix.com/tudum/top10/data/all-weeks-global.tsv` (also `.xlsx`).
893,380 bytes, last modified 2026-09-15.

- 10,880 rows, 272 weeks from 2021-07-04 to 2026-09-13, four categories × top 10.
- Columns: `week, category, weekly_rank, show_title, season_title,
  weekly_hours_viewed, runtime, weekly_views, cumulative_weeks_in_top_10`.
- `runtime` and `weekly_views` are `N/A` on 4,080 rows. Views start on
  2023-06-18, which lines up with the engagement report adding Views in 2023 H2.
- 3,465 distinct `show_title`; 3,947 distinct show+season pairs.
- **Download quirk:** Netflix answers an out-of-date browser user agent with an
  "unsupported browser" HTML page and HTTP 200, not an error. The probe checks
  the content type. The Phase 1 loader has to do the same, or it will quietly
  save a web page as `.tsv`.

## 3. IMDb non-commercial datasets — live

`https://datasets.imdbws.com/`, refreshed daily (last modified 2026-09-16).

| File | Size (gz) | Columns |
|---|---|---|
| `title.basics` | 227 MB | tconst, titleType, primaryTitle, originalTitle, isAdult, startYear, endYear, runtimeMinutes, genres |
| `title.ratings` | 9 MB | tconst, averageRating, numVotes |
| `title.akas` | 514 MB | titleId, ordering, title, region, language, types, attributes, isOriginalTitle |
| `title.episode` | 55 MB | tconst, parentTconst, seasonNumber, episodeNumber |

`title.episode` isn't in the spec. It's worth adding, because the Netflix sources
report by season and IMDb's `tconst` is for the whole series. The data is for
personal and non-commercial use only, so the raw dumps and any bulk extract
stay out of the public repo. Only aggregates get published.

## 4. Google Trends — not reliably available

- `pytrends`, the library the spec names, was archived on GitHub; its last
  PyPI release is 4.9.2 from 2023-04-13.
- The unofficial endpoint returned **HTTP 429 on the first request** from this
  machine. The Trends website then showed a 429 page in a normal browser too.
  I stopped there rather than retry into the limit.
- Google's official Trends API is still an alpha you have to apply for
  ([announcement](https://developers.google.com/search/blog/2025/07/trends-api)),
  with no self-serve key.
- The structural problem remains even if a manual export works: Trends values
  are relative (0–100 within a single query of at most five terms), so
  comparing hundreds of titles means chaining queries through an anchor term.
  That adds noise and is hard to reproduce.

**Candidate swap: Wikipedia pageviews.** Checked and working:

- The Wikimedia REST API gives daily or monthly **absolute** view counts per
  article, free, no key, current to yesterday.
- Wikidata maps an IMDb ID to its Wikipedia article directly (property P345):
  `tt13443470` → `Wikipedia: Wednesday_(TV_series)`.
- The trade-offs: English Wikipedia skews toward English-speaking audiences,
  which matters for the half of Top 10 categories that are non-English. And people
  looking a title up aren't the same as people searching for it. The spec's
  Phase 4 lead/lag question still works.

---

## How hard Phase 2 will be

A baseline for Phase 2 to beat: exact string match with no normalisation,
Top 10 titles against the engagement report for the same half.

| Half | Distinct charting titles | Exact match |
|---|---|---|
| 2025 H2 | 460 | 262 (57.0%) |
| 2026 H1 | 489 | 264 (54.0%) |

This is the match rate between two files from the *same company*, before IMDb
is involved at all. Some of the misses you can see straight away: bilingual
` // ` titles, and `: Season 1` in one file where the other says
`: Limited Series`. The spec was right that entity resolution is the project.

---

## Eileen decides

1. **Confirm the three live sources** (engagement report, Top 10, IMDb), with
   `title.episode` added to the IMDb files.
2. **Google Trends: swap or keep?**
   - *Swap to Wikipedia pageviews* (recommended): reproducible, absolute counts,
     and a pipeline can actually run it. The title still reads "Four Sources".
   - *Keep Trends* as a small manual export for a handful of headline titles
     only, stated as a limitation. It can't be a source the pipeline depends on.
3. **Which halves count.** Recommended: **2023 H2 to 2026 H1** (six halves).
   That's where every file has Views and Runtime and separate TV/film sheets.
   2023 H1 would have to be split into TV and film by guessing from the title
   suffix, and it has hours only. Either way, the catch-all rows get excluded
   from anything title-level.
