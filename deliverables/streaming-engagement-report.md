# Four sources, one model: which titles are earning their place?

Consolidating two Netflix files, IMDb and Wikipedia into one model a content team can
query — and what that model says about genres, ratings and public attention.

**Eileen Ip · portfolio project**

---

## The question

Content strategy and programming teams decide renewals and acquisitions from numbers
that live in separate files nobody reconciles by hand. Netflix publishes two of them and
they do not agree with each other. IMDb knows what a title *is* — type, year, genre,
rating — and shares no identifier with either. Wikipedia knows how much attention a title
is getting outside the platform.

The business question is which titles earn their place. The engineering question comes
first: can these four be joined at all, and how much is lost in the attempt?

## The sources, and why they are awkward

| Source | Grain | The awkward part |
|---|---|---|
| Netflix engagement report ("What We Watched") | half-year, per season | seven editions in three layouts; sheet names, date types and catch-all rows all change |
| Netflix Global Top 10 | week, per season | one live file, retitled retroactively |
| IMDb non-commercial datasets | title (series, not season) | its own id scheme, shared with nothing; 59M alternate titles |
| Wikipedia pageviews | day, per article | English-only; reached via Wikidata; rate-limited to roughly one article every 22 seconds |

The spec's fourth source was Google Trends. It was replaced before any code was written:
the standard Python library for it is archived, the unofficial endpoint returns HTTP 429
to an ordinary browser, and the official API is an application-only alpha. Wikipedia
pageviews give absolute daily counts instead of Trends' relative 0–100 index, which is
strictly better for comparing titles.

Scope after that decision: **six half-years, July 2023 to June 2026** — the editions
where every file carries Views and Runtime and separates TV from film.

## What the data actually does when you look

**The Top 10 file is a live view, not an archive.** *Berlin* charted in December 2023
under that name. The file now labels those same 2023 weeks *"Berlin and the Jewels of
Paris: Limited Series"*, because a second season arrived in 2026 and season 1 was
renamed. The engagement reports are period snapshots and keep the old name. Nine of the
thirteen Top 10 titles that fail to match are names that appear **only in later
reports**. A join on names is therefore unstable across time by construction — which is
the argument for resolving everything to an id and recording, per chart row, whether the
match was made inside its own period or by name alone.

**Netflix contradicts itself inside a single half-year.** The Top 10 calls *Sean Combs:
The Reckoning* "Season 1" where the engagement report calls it "Limited Series", and
omits *The Manny*'s season entirely.

**Netflix publishes four facts in one string** — name, season marker, disambiguating
year, and an alternate-language name after ` // ` — in at least a dozen shapes:
`Suits (2011): Season 1`, `Stranger Things 4`, `Aquí no hay quien viva (2003): Temporada 4`,
`Law & Order: Special Victims Unit: The Sixth Year`, `Raw: June 15, 2025`.

**Two asterisks are never explained.** Runtime appears as `*` on 171–193 TV rows per
report, and as `H:MM*` on a growing number of rows (3 in 2024 H2, 117 in 2026 H1), mostly
live events. Netflix documents neither, so both are carried as flags with no meaning
assumed.

## Resolving the sources to each other

Exact string matching gets 54–57%. The rest is a ladder of rungs, each counted
separately so a weak one can be inspected — or switched off — on its own.

| Rung | Titles matched |
|---|---|
| name (normalised) | 21,450 |
| series prefix (a named arc → its series) | 660 |
| alternate-language name | 450 |
| spacing (`S.W.A.T.` ↔ `swat`) | 133 |
| qualifier dropped (`Shameless (U.S.)`, `Leo (Hindi)`) | 95 |
| fuzzy, score ≥ 87 | 284 |
| near miss, below threshold | 1,771 |
| no candidate at all | 59 |

| Join | Rows | Matched | |
|---|---|---|---|
| Top 10 → engagement report, same half | 2,764 | 2,751 | **99.5%** |
| Engagement titles → IMDb id | 24,902 | 23,072 | **92.7%** |
| — film | 16,154 | 15,633 | 96.8% |
| — TV | 8,748 | 7,439 | 85.0% |
| Share of reported viewing hours matched | | | **98.8%** |

Fuzzy matching contributes one pair on the first join and 284 on the second. Nearly all
of the gain is normalisation, not string distance — which is the opposite of how this
problem is usually described.

**The threshold is 87, and a person set it.** It started at 88, read off the near-miss
list band by band — the 88–90 band is mostly true matches, whole film families where
Netflix writes `Detective Conan the Movie: The Scarlet Bullet` and IMDb writes `detective
conan the scarlet bullet`, while the 85–88 band is genuinely mixed.

Then 30 pairs sampled across the score range were hand-labelled, with the score and the
pipeline's verdict hidden from the page. **The labels agreed with the pipeline on 24 of
the 29 judged, and put the threshold at 87** — three disagreements there against four at
88. Pairs it correctly rejects: `Sir (Hindi) (2023)` vs `jai hind sir`,
`Matsumoto Seicho's Kao` vs `matsumoto seicho no ekiro`, `Louis C.K.: Ridiculous` vs
`ridiculous cakes`.

Two pairs it accepts are **not** matches — `Project Mc²: Part 2` vs `project c24` at 90.9,
and `The Secret World of Lego` vs `the secret world of` at 88.4 — and no threshold worth
considering excludes them. They are recorded as the fuzzy rung's measured error rate,
roughly 2 in 29 audited pairs, rather than ruled out by a prefix rule that would also
reject `Broken Hearts Gallery` against `the broken hearts gallery`.

The audit also found what no amount of reading the list would have: one disagreement was
a missing rung rather than a bad threshold. `Tughlaq Durbar (Telugu)` could not reach the
qualifier rung because it was restricted to TV, so 153 film titles carrying a language
qualifier — almost all Indian-language versions — were invisible to it. Fixing that
matched 82 more titles, including *Kalki 2898 AD (Hindi)* and *Baahubali 2: The
Conclusion (Hindi Version)*.

Where one name matches several IMDb ids, they are narrowed by year, then year within
one, then vote count. The last of those is a judgement rather than a fact, so it is
counted and the genuinely close cases are listed.

**Unmatched titles are kept, flagged, not dropped** — 7.3% of titles but 1.2% of hours.
Dropping them would bias every "earning its place" result towards titles that happen to
resolve.

## The model

A star schema in DuckDB: `dim_title` (one row per film or series, carrying the resolved
IMDb id), `dim_period`, and three fact tables — `fact_engagement_halfyear` (a season in a
period), `fact_top10_weekly` (a chart slot in a week), `fact_pageviews` (a title on a
day).

Three decisions the shape encodes:

- **A fact row is a season in a period; a dim row is the whole title.** IMDb has no
  season entity to hang a season on.
- **The period is data, not schema.** Netflix announced in July 2026 that the report
  becomes annual from 2027. `dim_period` carries start and end dates and the checksum of
  the file each period came from, so that report is an `INSERT`, not a migration.
- **`title_id` is a hash of kind, name key and year**, so it survives a rebuild and does
  not shift when another report arrives.

## What the model says

### Some genres are watched far more than they chart

Share of reported hours divided by share of Top 10 slots. Above 1: watched more than its
chart presence suggests. Intervals are bootstraps over titles.

| Genre | Titles | Delivery | 95% interval |
|---|---|---|---|
| Family | 1,427 | **1.65** | 1.24–2.33 |
| Animation | 2,751 | 1.32 | 1.10–1.62 |
| Drama | 11,069 | 1.09 | 1.03–1.15 |
| Thriller | 2,643 | 0.67 | 0.58–0.77 |
| Documentary | 1,710 | **0.44** | 0.39–0.49 |

Nine genres have intervals clear of parity. The comparison works precisely because the
two quantities are different kinds: the chart is capped at ten slots per category per
week and hours are not, so "charts more than it is watched" is a meaningful thing to say.

### A better rating does not hold the chart longer

Among the 2,282 titles that charted inside a report period and carry an IMDb rating, the
raw correlation between rating and weeks charted is 0.118 (p = 1.5e-08) — which looks
like a finding until size is held constant. With hours, votes, type and language in the
model, **the rating term is 0.06 weeks per point, interval [−0.03, +0.17]**:
indistinguishable from zero. R² = 0.384.

What does predict chart time: hours (+3.6 weeks per tenfold increase) and being in a
non-English category (+1.1 weeks — its own category, with its own ten slots).

### Outside interest arrives the same week, not before it

For the 63 titles with at least eight overlapping weeks, 47 fit best at a lag of zero;
8 lead and 8 lag (sign test p = 1). There is no forecasting signal here.

The same-week co-movement is strong (median r = 0.82) and it is not an artefact of both
series decaying after release: pairing each title's hours with a *different* title's
pageviews gives a median r of 0.23.

## Limitations

- **Half-yearly hours.** The finest grain for viewing is six months. Nothing here can
  speak to a month, a launch week, or a before-and-after.
- **Rounding.** Hours are published to the nearest 100,000 with a 100,000 floor, so the
  long tail is missing and small numbers are rounding artefacts.
- **One platform.** Netflix only. No figure here is a market share.
- **Genre is IMDb's, not Netflix's**, and a title with three genres counts in all three.
- **Wikipedia is English-only** and scoped to titles that charted at least five weeks —
  229 of them — partly by judgement and partly because the API permits roughly one
  article every 22 seconds. Non-English titles are half the chart by construction and are
  under-represented here.
- **The demand series stops when a title leaves the chart**, while pageviews continue, so
  the two sides end on different days.
- **The chart is zero-sum.** Ten slots per category per week exist whatever gets
  released, so chart presence measures competition as much as quality.

## What didn't work

**Google Trends, the source the spec named, was abandoned before any code was written.**
The standard Python library for it is archived, the unofficial endpoint answers an
ordinary browser with HTTP 429, and the official API is an application-only alpha. That
cost a day of the plan and improved the project: Wikipedia pageviews are absolute daily
counts where Trends is a relative 0–100 index rescaled per query, so titles can actually
be compared to each other.

**Fetching demand for every charting title was abandoned mid-run.** The Wikimedia API
answers an anonymous client with `Retry-After: 22`, which puts all 2,297 charting titles
at roughly eleven hours of continuous polling of a free service. The scope was cut to
titles with at least five weeks in the chart — 278 of them, 229 with an English article.
The cut is a flag rather than a constant, so widening it is one argument and a longer
wait, but every demand finding in this report rests on 229 titles and says so.

**Pooling every name variant into one lookup produced confident wrong answers.** With the
published name and the season-stripped name in the same pool, *Despicable Me 3* matched
*Despicable Me* (2010) — both were legitimate hits, and the tie-break picked the one with
more votes, which was the original. Keys are now tried strongest-first and a rung is only
reached when the one above it finds nothing. The case is a regression test.

**A containment rung was considered and rejected.** Several near misses are real matches
where one name contains the other: Top 10's `Full Speed: Season 1` against the report's
`NASCAR: Full Speed: Season 1`. Containment would have caught them — and also matched
*Avatar* to *Avatar: The Last Airbender*. The pairs are in `near-misses.csv` for
inspection instead. About a dozen real matches were left on the table to avoid a rule
that fails silently and in the wrong direction.

**Deduplicating keys across rungs silently disabled a rung.** Dropping a key already
tried higher up looked like an obvious optimisation; it stopped `S.W.A.T.` reaching
IMDb's `S.W.A.T.`, because the spacing rung compares compacted keys — the same string
against a different column is a different comparison. Nothing failed. The match rate
simply came back lower, which is the failure mode worth fearing in this kind of work.

**The first lead/lag run was wrong twice.** In levels, both series rise at release and
decay, so they correlate whatever the timing; differencing fixed that. Then an eight-week
series scored r = 0.99 at a four-week lag — from three data points — and *The Crown:
Season 6* briefly looked like a four-week leading indicator. A lag is now only considered
when at least six weeks survive the shift.

**Two rankings had to be thrown away for having no floor.** Hours per week available put
a title released one week before the report closed at 350M hours a week; the genre chart
came out with every bar collapsed at the left because one genre's bootstrap interval was
`NaN`, from resamples that drew none of its two charting titles.

## Recommendation

**Rank renewals on hours per week available, within genre and language, and require the
chart to agree before treating a strong opening as a reason to renew.** The two numbers
correlate at 0.18, so they disagree often, and the disagreements are where the decision
actually is: a big opening with no chart legs is a marketing result, and steady hours
with no chart presence is an audience the chart cannot see.

Three things follow from the findings, in order of how much I would stake on them.

**Stop using chart presence as the screen for kids' and family content.** Family delivers
1.65 times the viewing its chart presence implies and Animation 1.32, with intervals
clear of parity, while Documentary at 0.44 and Thriller at 0.67 run the other way. A
renewal process that starts from "did it chart" systematically undervalues the first
group and overvalues the second. The mechanism I would guess at — rewatching, and
children's viewing spread thin across many weeks rather than concentrated at release —
is *not* something this data can test, and I would say so rather than assert it.

**Drop IMDb rating from renewal inputs.** It is the kind of variable that gets into a
scorecard because it sounds sensible. Its raw correlation with chart longevity is 0.118
and significant, and it survives no control at all: with size held constant the estimate
is 0.06 weeks per rating point, interval −0.03 to +0.17. Whatever a rating measures, it
does not predict how long a title holds the chart.

**Do not build an early-warning dashboard on public attention.** Wikipedia moves in the
same week as viewing, not before it — 47 of 63 titles fit best at a lag of zero, and the
leads and lags split 8 to 8. What the series is good for is corroboration: it is a cheap
external check that a title's reported performance is not a reporting artefact, and it
keeps measuring attention after a title leaves the chart, where Netflix's weekly numbers
stop.

**What would change my answer.** Rewatch data would test the Family mechanism directly.
Per-country data would separate "non-English titles hold the chart longer" from "they
compete in a category with fewer contenders". A second platform would show whether any of
this is about Netflix or about streaming. None of the three is available publicly, and
the absence of the first is the reason the strongest finding here is framed as a
measurement rather than an explanation.

---

**Authorship, stated plainly.** The two sections above — *What didn't work* and
*Recommendation* — were drafted by the agent at Eileen's request on 2026-09-27, from the
project's own build record and results. Every number in them is reproducible from the
repository. The judgement calls recorded in `data/validation/` — the threshold, the
source swap, the metric definition, what happens to unmatched titles — are Eileen's, and
are documented there with her reasoning. **Read these two sections before an interview
and make sure you would defend them as your own.**

---

*Built from public data. Reproducible end to end: `python -m src.match_report`,
`python -m src.model`, `python -m src.analysis`, `python -m src.dashboard`. 74 tests.
IMDb data is used under its non-commercial terms; no per-title IMDb ratings or vote
counts are published in the deliverables.*
