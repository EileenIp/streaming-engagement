# Project spec — Streaming Engagement: Four Sources, One Model

**For:** Eileen Ip · portfolio project
**Theme:** Media & entertainment (data-engineering-led)
**Agent:** one builder, Sonnet, in Claude Code. Same working rules as the churn spec: stop at every **EILEEN DECIDES**, never invent a number, never write `NOTES.md`, read spec + `NOTES.md` + last commit at session start, commit per phase.

---

## The business question

> Which titles are actually earning their place on a streaming service — and can content teams answer that from one screen instead of four spreadsheets?

The original placeholder card described "consolidating four siloed reporting spreadsheets into one self-serve dashboard." That's the honest angle: this is a **data engineering** project wearing a dashboard. The showcase skill is entity resolution and modelling across inconsistent real sources — the thing every media analytics team actually spends its time on — not the charts.

**Who cares:** content strategy and programming teams deciding renewals and acquisitions; BI teams drowning in manual weekly consolidation.

---

## The four real sources

This is the part that makes the project honest rather than invented: all four are real, public, and genuinely inconsistent with each other.

1. **Netflix Engagement Report** — Netflix publishes a report of what members watched: hours viewed and views per title, published as an Excel download covering six-month periods. Messy in real ways: titles as free text, seasons inconsistently named, multi-language titles.
2. **Netflix Global Top 10 weekly files** — weekly ranked lists with hours viewed, downloadable as spreadsheets from the Top 10 site. Different title formatting from the engagement report, different granularity (weekly vs half-year).
3. **IMDb non-commercial datasets** — official TSV dumps (`title.basics`, `title.ratings`, `title.akas`): ratings, vote counts, genres, year, alternate titles. Its own ID scheme (`tconst`), which nothing in sources 1–2 shares.
4. ~~**Google Trends** interest-over-time for the analysis titles (via `pytrends` or manual export) — demand signal outside the platform.~~ **Replaced at Checkpoint 0 (2026-09-17) by Wikipedia pageviews** — daily absolute article views via the Wikimedia REST API, reached from IMDb IDs through Wikidata (P345). See `data/validation/checkpoint0-sources.md`.

**AGENT, Phase 0:** verify each source's current availability and exact download mechanics before building anything (Netflix has changed report cadence before). Report actual file names, sizes, and column lists. **Checkpoint 0** — Eileen confirms the four sources or swaps one.

---

## Phase 1 — Ingestion, raw and untouched

**AGENT:** one ingestion module per source. Raw files land in `data/raw/` exactly as downloaded, with a manifest recording source URL, download date, and checksum. Loaders validate schema and refuse silently-changed columns. All paths and period definitions in `config.py`.

**Acceptance:** each loader runs standalone and prints rows, columns, nulls, and period covered.

## Phase 2 — The hard part: entity resolution

Matching "Wednesday: Season 1" to "Wednesday" to `tt13443470` across four naming schemes is the project.

**AGENT:**

- Normalisation pipeline: casing, punctuation, season/part suffix extraction, year disambiguation, `title.akas` for alternate names.
- Deterministic exact-match first; then fuzzy matching (e.g. RapidFuzz token-sort) **only** on the residue, with every fuzzy match logged with its score.
- Produce a match report: match rate per source pair, score distribution, and the full list of sub-threshold near-misses.

**EILEEN DECIDES:**

- The fuzzy threshold, after eyeballing the near-miss list. Set it too low and "Avatar" matches "Avatar: The Last Airbender"; too high and sequels drop out. Record the threshold *and three example pairs it correctly rejects* in `NOTES.md` — that's the interview answer.
- What happens to unmatched titles: dropped rows are a completeness bias (the long tail vanishes); keeping them breaks joins. Either is defensible, stated.

**Tests (pytest):** known tricky pairs match correctly (build a 30-pair hand-labelled fixture — **Eileen labels it**, 20 minutes, and it's genuine ground truth to cite); no title maps to two IMDb IDs; join of all four sources loses no more rows than the match report predicts.

**Checkpoint 2.**

## Phase 3 — The unified model

**AGENT:** a small star schema (DuckDB or SQLite): `dim_title` (canonical ID, IMDb ID, genre, year, type), `fact_engagement_halfyear`, `fact_top10_weekly`, `fact_trends`. Documented with a schema diagram in the README. Views for the dashboard queries.

**EILEEN DECIDES:** the definition of the headline metric — "earning its place" needs an operational form. Candidates: hours per available week since release, Top-10 longevity (weeks charted), engagement vs external demand (hours relative to Trends interest). Pick one headline and one supporting metric, and write down why.

## Phase 4 — Analysis layer

**AGENT:** with the model built, answer at least: which genres over/under-deliver hours relative to their Top-10 presence; do high-IMDb-rating titles retain chart longevity better; where does external demand (Trends) lead or lag on-platform hours. Statistical care with the half-year granularity — small n per period, say so.

**EILEEN DECIDES:** interpretation and the renewal-shaped recommendation.

## Phase 5 — Deliverables

The four-output pattern from the churn spec Phase 7: self-contained HTML dashboard on GitHub Pages (hero: one screen replacing four sources — show the four source logos/files feeding one view), stakeholder deck, 3–4 page report, website case study. The dashboard's self-serve claim from the placeholder card is only honest if a non-technical user can actually filter by genre/period without help — test that on a friend.

**EILEEN WRITES:** "what didn't work" (the matching dead ends belong here — they will exist), limitations (half-year granularity, Netflix-only platform view, Trends is relative not absolute), recommendation paragraph.

---

## Readiness gate notes

- **Visualisation-only?** No — entity resolution, a modelled schema, and lead/lag analysis are the depth. If the matching gets hand-waved, the project collapses into "I charted Netflix's spreadsheet"; don't ship that.
- **Overused data?** The Netflix engagement report is analysed plenty in isolation. The four-source join with documented match quality is the differentiator.
- **Business context?** Cleared — renewal and acquisition decisions run on exactly this consolidation.
- **Tutorial clone?** Low risk; no tutorial covers this join.

## Screening audit

Churn spec Appendix C before shipping. At-risk rows: **Implementation thinking** (the manifest/schema-validation story is your answer — a new report drops every six months, the pipeline must survive it) and **Handling ambiguity** (the match-threshold reasoning).

## Cost discipline

Estimate A$20–35. The entity-resolution phase is where an agent can loop — if match rates come back absurd, stop the session and bring the match report here rather than letting it retry. Stop and reassess past A$45.

## Definition of done

- [ ] Four real sources ingested with manifest + schema validation
- [ ] Match report with rates, threshold reasoning, and the 30-pair hand-labelled fixture passing
- [ ] Star schema documented with a diagram
- [ ] Headline metric defined and defended in `NOTES.md`
- [ ] `pytest` green
- [ ] Four deliverables; case study with real numbers only
- [ ] Rehearsed answers: why this threshold, what breaks when the next report drops, why a star schema, what a second platform would change
