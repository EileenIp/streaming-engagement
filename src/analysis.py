"""Phase 4: the analysis layer. Three questions the spec asks, answered with the
uncertainty attached.

  1. Which genres over- or under-deliver hours relative to their Top 10 presence?
  2. Do higher-rated titles hold their chart position longer?
  3. Does outside interest lead or lag on-platform viewing?

Statistical care is the point of this file, not decoration. Three things shape it:

* **n per period is small and the grain is coarse.** Six half-years, hours rounded to
  100,000, and a title's whole half-year is one number. Nothing here tries to say
  anything about a month.
* **The Top 10 is zero-sum; hours are not.** Ten slots per category per week exist
  whatever gets released, so chart share and hours share are different kinds of
  quantity. That is what makes the comparison interesting and also what stops it
  being a like-for-like ratio.
* **Every interval is a bootstrap over titles, not over rows.** A title contributes
  many rows, so resampling rows would treat one title's seasons as independent
  evidence and shrink the intervals to nothing.

Run: python -m src.analysis
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

from src import config, model

OUT = config.ROOT / "data" / "validation" / "phase4-findings.md"
SEED = 20260927
BOOTSTRAP = 2000
MIN_GENRE_TITLES = 25      # a genre needs a real sample before a ratio means anything
MIN_DEMAND_WEEKS = 8       # weeks of overlap before a lead/lag estimate is worth having
MAX_LAG = 4                # weeks either side
MIN_PAIRS = 6              # overlapping points a lagged correlation needs to mean anything


# --- question 1: genre delivery ---------------------------------------------------------

def genre_rows(con) -> pd.DataFrame:
    """One row per (title, genre) with the title's hours and Top 10 slots inside the periods."""
    return con.execute("""
        WITH inperiod_top10 AS (
            SELECT f.title_id, count(*) AS slots, count(DISTINCT f.week) AS weeks_charted
            FROM fact_top10_weekly f
            JOIN dim_period p ON f.week BETWEEN p.period_start AND p.period_end
            WHERE f.title_id IS NOT NULL
            GROUP BY 1
        ),
        hours AS (
            SELECT title_id, sum(hours_viewed) AS hours FROM fact_engagement_halfyear GROUP BY 1
        )
        SELECT t.title_id, t.kind, trim(g.genre) AS genre, h.hours,
               coalesce(x.slots, 0) AS slots, coalesce(x.weeks_charted, 0) AS weeks_charted
        FROM dim_title t
        JOIN hours h USING (title_id)
        LEFT JOIN inperiod_top10 x USING (title_id)
        CROSS JOIN unnest(string_split(t.imdb_genres, ',')) AS g(genre)
        WHERE t.imdb_genres IS NOT NULL AND t.imdb_genres <> ''
    """).fetchdf()


def delivery_ratio(df: pd.DataFrame) -> pd.DataFrame:
    """Share of hours over share of Top 10 slots, per genre, with a bootstrap interval.

    Above 1: the genre earns more viewing than its chart presence suggests - watched
    without being a hit. Below 1: it charts more than it is watched.
    """
    # As matrices, because the bootstrap resamples titles 2,000 times: a title x genre
    # incidence matrix turns each draw into two matrix-vector products instead of
    # rebuilding a 16,000-row frame.
    titles = df.title_id.unique()
    genre_names = sorted(df.genre.unique())
    title_index = {t: i for i, t in enumerate(titles)}
    genre_index = {g: j for j, g in enumerate(genre_names)}
    incidence = np.zeros((len(titles), len(genre_names)))
    for r in df.itertuples():
        incidence[title_index[r.title_id], genre_index[r.genre]] = 1.0
    per_title = df.groupby("title_id")[["hours", "slots"]].first().reindex(titles)
    hours = per_title.hours.to_numpy(dtype=float)
    slots = per_title.slots.to_numpy(dtype=float)
    # A title with three genres counts in all three, so the denominator counts it three
    # times too - that is what makes the shares sum to one across genres.
    genres_per_title = incidence.sum(axis=1)

    def ratios(counts):
        h = (counts * hours) @ incidence
        s = (counts * slots) @ incidence
        total_h = float(counts @ (hours * genres_per_title))
        total_s = float(counts @ (slots * genres_per_title))
        with np.errstate(divide="ignore", invalid="ignore"):
            return pd.Series((h / total_h) / (s / total_s), index=genre_names)

    ones = np.ones(len(titles))
    point = ratios(ones)
    rng = np.random.default_rng(SEED)
    draws = [ratios(np.bincount(rng.integers(0, len(titles), len(titles)), minlength=len(titles))
                    .astype(float)) for _ in range(BOOTSTRAP)]
    boot = pd.DataFrame(draws)
    out = df.groupby("genre").agg(titles=("title_id", "nunique"), hours=("hours", "sum"),
                                  slots=("slots", "sum"), charting=("weeks_charted", lambda s: (s > 0).sum()))
    out["hours_share"] = out.hours / float(ones @ (hours * genres_per_title))
    out["slots_share"] = out.slots / float(ones @ (slots * genres_per_title))
    out["delivery"] = point
    out["ci_low"] = boot.quantile(0.025)
    out["ci_high"] = boot.quantile(0.975)
    return out[out.titles >= MIN_GENRE_TITLES].sort_values("delivery", ascending=False)


# --- question 2: rating and chart longevity ---------------------------------------------

def longevity_rows(con) -> pd.DataFrame:
    return con.execute("""
        WITH inperiod AS (
            SELECT f.title_id, count(DISTINCT f.week) AS weeks_charted, min(f.weekly_rank) AS best_rank,
                   min(f.week) AS first_week, max(f.week) AS last_week,
                   any_value(f.language) AS language
            FROM fact_top10_weekly f
            JOIN dim_period p ON f.week BETWEEN p.period_start AND p.period_end
            WHERE f.title_id IS NOT NULL
            GROUP BY 1
        ),
        hours AS (SELECT title_id, sum(hours_viewed) AS hours FROM fact_engagement_halfyear GROUP BY 1)
        SELECT t.title_id, t.canonical_title, t.kind, t.imdb_rating, t.imdb_votes,
               h.hours, i.weeks_charted, i.best_rank, i.language, i.last_week
        FROM inperiod i
        JOIN dim_title t USING (title_id)
        JOIN hours h USING (title_id)
        WHERE t.imdb_rating IS NOT NULL
    """).fetchdf()


def ols(X: np.ndarray, y: np.ndarray):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    r2 = 1 - resid.var() / y.var()
    return beta, r2


def rating_vs_longevity(df: pd.DataFrame) -> dict:
    """Spearman first, then a regression that holds size and kind constant.

    Rating on its own is confounded: big titles get watched, rated and charted, all at
    once. log10(hours) stands in for size; kind and language are the other obvious
    splits. Intervals come from resampling titles.
    """
    rho, p = stats.spearmanr(df.imdb_rating, df.weeks_charted)
    design = pd.DataFrame({
        "intercept": 1.0,
        "rating": df.imdb_rating.to_numpy(),
        "log_hours": np.log10(df.hours.to_numpy()),
        "log_votes": np.log10(df.imdb_votes.clip(lower=1).to_numpy()),
        "is_tv": (df.kind == "tv").astype(float).to_numpy(),
        "non_english": (df.language == "non-english").astype(float).to_numpy(),
    })
    y = df.weeks_charted.to_numpy(dtype=float)
    beta, r2 = ols(design.to_numpy(), y)
    rng = np.random.default_rng(SEED)
    draws = []
    for _ in range(BOOTSTRAP):
        idx = rng.integers(0, len(df), len(df))
        b, _ = ols(design.to_numpy()[idx], y[idx])
        draws.append(b)
    draws = np.array(draws)
    return {
        "n": len(df),
        "spearman_rho": rho, "spearman_p": p,
        "terms": list(design.columns),
        "beta": beta,
        "ci": np.percentile(draws, [2.5, 97.5], axis=0),
        "r2": r2,
        "still_charting_at_file_end": int((df.last_week >= df.last_week.max()).sum()),
    }


# --- question 3: does outside interest lead or lag? -------------------------------------

def demand_series(con) -> pd.DataFrame:
    return con.execute("""
        SELECT d.title_id, t.canonical_title, t.kind, d.week, d.hours, d.pageviews
        FROM v_weekly_demand d JOIN dim_title t USING (title_id)
        WHERE d.hours IS NOT NULL AND d.pageviews IS NOT NULL
        ORDER BY d.title_id, d.week
    """).fetchdf()


def best_lag(hours: np.ndarray, pageviews: np.ndarray, max_lag=MAX_LAG, min_pairs=MIN_PAIRS):
    """Cross-correlate week-on-week changes and return the lag that fits best.

    Differences, not levels: both series jump at release and decay, so their levels
    correlate whatever the timing. A negative lag means pageviews move first.

    A lag is only considered when at least min_pairs weeks survive the shift. Without
    that floor an eight-week series produced r = 0.99 at lag 4 from three points, which
    is not a finding about anything.
    """
    h = np.diff(np.log1p(hours.astype(float)))
    p = np.diff(np.log1p(pageviews.astype(float)))
    if len(h) < min_pairs or np.std(h) == 0 or np.std(p) == 0:
        return None
    out = {}
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            a, b = h[-lag:], p[:len(p) + lag]
        elif lag > 0:
            a, b = h[:len(h) - lag], p[lag:]
        else:
            a, b = h, p
        if len(a) < min_pairs or np.std(a) == 0 or np.std(b) == 0:
            continue
        out[lag] = float(np.corrcoef(a, b)[0, 1])
    if not out:
        return None
    lag = max(out, key=lambda k: out[k])
    return {"lag": lag, "r": out[lag], "by_lag": out, "weeks": len(hours),
            "lags_considered": len(out)}


def lead_lag(df: pd.DataFrame, min_weeks=MIN_DEMAND_WEEKS) -> pd.DataFrame:
    rows = []
    for title_id, g in df.groupby("title_id"):
        g = g.sort_values("week")
        if len(g) < min_weeks:
            continue
        fit = best_lag(g.hours.to_numpy(), g.pageviews.to_numpy())
        if fit:
            rows.append({"title_id": title_id, "title": g.canonical_title.iloc[0],
                         "kind": g.kind.iloc[0], "weeks": fit["weeks"],
                         "best_lag": fit["lag"], "r": fit["r"],
                         "lags_considered": fit["lags_considered"]})
    return pd.DataFrame(rows)


def placebo_comovement(df: pd.DataFrame, min_weeks=MIN_DEMAND_WEEKS, draws=500) -> dict:
    """Pair each title's hours with a *different* title's pageviews and correlate.

    Needed because a high same-week correlation may say nothing about the title: both
    series rise at release and decay afterwards, so any two of them share that shape.
    If the placebo correlation is as high as the real one, the co-movement is the shape,
    not the title.
    """
    series = {}
    for title_id, g in df.groupby("title_id"):
        g = g.sort_values("week")
        if len(g) < min_weeks:
            continue
        h = np.diff(np.log1p(g.hours.to_numpy(dtype=float)))
        p = np.diff(np.log1p(g.pageviews.to_numpy(dtype=float)))
        if np.std(h) > 0 and np.std(p) > 0:
            series[title_id] = (h, p)
    ids = list(series)
    real = [float(np.corrcoef(*series[i])[0, 1]) for i in ids]
    rng = np.random.default_rng(SEED)
    fake = []
    for _ in range(draws):
        a, b = rng.choice(len(ids), 2, replace=False)
        h = series[ids[a]][0]
        p = series[ids[b]][1]
        n = min(len(h), len(p))
        if n < MIN_PAIRS or np.std(h[:n]) == 0 or np.std(p[:n]) == 0:
            continue
        fake.append(float(np.corrcoef(h[:n], p[:n])[0, 1]))
    return {"n_titles": len(ids), "real_median": float(np.median(real)),
            "placebo_median": float(np.median(fake)), "placebo_draws": len(fake),
            "placebo_p95": float(np.percentile(fake, 95)),
            "real_above_placebo_p95": int(sum(r > np.percentile(fake, 95) for r in real))}


def sign_test(lags: pd.Series) -> dict:
    """Do more titles lead than lag? Zeros are excluded, as a sign test must."""
    leads = int((lags < 0).sum())
    lags_ = int((lags > 0).sum())
    same = int((lags == 0).sum())
    n = leads + lags_
    p = stats.binomtest(leads, n, 0.5).pvalue if n else float("nan")
    return {"leads": leads, "lags": lags_, "same_week": same, "n_decisive": n, "p": p}


# --- the write-up -----------------------------------------------------------------------

def build(con) -> str:
    genres = delivery_ratio(genre_rows(con))
    longevity = rating_vs_longevity(longevity_rows(con))
    series = demand_series(con)
    fits = lead_lag(series)
    signs = sign_test(fits.best_lag) if len(fits) else {}
    placebo = placebo_comovement(series) if len(fits) else {}

    coef = pd.DataFrame({
        "term": longevity["terms"],
        "estimate": np.round(longevity["beta"], 3),
        "ci_low": np.round(longevity["ci"][0], 3),
        "ci_high": np.round(longevity["ci"][1], 3),
    })
    g = genres.assign(
        hours_share=lambda d: (100 * d.hours_share).round(1),
        slots_share=lambda d: (100 * d.slots_share).round(1),
        delivery=lambda d: d.delivery.round(2),
        ci=lambda d: d.ci_low.round(2).astype(str) + "–" + d.ci_high.round(2).astype(str),
    )[["titles", "charting", "hours_share", "slots_share", "delivery", "ci"]]

    lines = [
        "# Phase 4 — findings",
        "",
        f"Built {pd.Timestamp.now():%Y-%m-%d} from the star schema. Intervals are 95% "
        f"bootstrap intervals over {BOOTSTRAP:,} resamples **of titles**, not of rows: a "
        "title contributes several seasons and periods, and resampling rows would treat "
        "those as independent evidence.",
        "",
        "Three limits apply to everything below, so they are stated once. The engagement "
        "reports are half-yearly, so the finest grain available for hours is six months. "
        "Hours are rounded to the nearest 100,000 and the smallest published value is "
        "100,000, so the long tail is cut off. And the Top 10 is capped at ten slots per "
        "category per week, so chart presence is zero-sum in a way hours are not.",
        "",
        "## 1. Which genres over-deliver hours against their chart presence?",
        "",
        "Share of reported hours divided by share of Top 10 slots. Above 1 means a genre "
        "gets watched more than its chart presence would suggest; below 1 means it charts "
        f"more than it is watched. Genres with fewer than {MIN_GENRE_TITLES} titles are "
        "dropped. Genres come from IMDb, not Netflix, and a title with three genres counts "
        "in all three.",
        "",
        g.to_markdown(),
        "",
        "## 2. Do higher-rated titles hold the chart longer?",
        "",
        f"Among the {longevity['n']:,} titles that charted inside a report period and have "
        f"an IMDb rating. Spearman correlation between rating and weeks charted: "
        f"**{longevity['spearman_rho']:.3f}** (p = {longevity['spearman_p']:.3g}).",
        "",
        "Rating on its own is confounded — big titles get watched, rated and charted "
        "together — so the same question with size held constant:",
        "",
        coef.to_markdown(index=False),
        "",
        f"R² = {longevity['r2']:.3f}. The response is weeks charted, so an estimate of "
        "0.5 on `rating` would mean half a week more chart time per rating point.",
        "",
        f"**Censoring:** {longevity['still_charting_at_file_end']} titles were still in the "
        "chart in the file's last week, so their runs are cut short by the data ending, not "
        "by the title falling out.",
        "",
        "## 3. Does outside interest lead or lag on-platform viewing?",
        "",
        f"Weekly Wikipedia pageviews against weekly Top 10 hours, for the {len(fits)} titles "
        f"with at least {MIN_DEMAND_WEEKS} overlapping weeks. Both series are turned into "
        "week-on-week changes first: in levels they both spike at release and decay, so they "
        "correlate whatever the timing. A negative lag means pageviews moved first, and a lag "
        f"is only tried when at least {MIN_PAIRS} weeks survive the shift.",
        "",
        "**The hours series only exists while a title is charting.** Weekly hours come from "
        "the Top 10 file, so the on-platform series stops when the title leaves the chart "
        "while pageviews carry on. Any tail beyond the chart run is missing from one side "
        "and present on the other.",
        "",
    ]
    if len(fits):
        dist = fits.best_lag.value_counts().sort_index()
        lines += ["| best lag (weeks) | titles |", "|---|---|"]
        lines += [f"| {lag:+d} | {n} |" for lag, n in dist.items()]
        lines += [
            "",
            f"Median best lag **{fits.best_lag.median():+.0f} weeks**, median correlation at "
            f"that lag {fits.r.median():.2f}. Of the {signs['n_decisive']} titles with a "
            f"non-zero best lag, {signs['leads']} lead and {signs['lags']} lag "
            f"(sign test p = {signs['p']:.3g}); {signs['same_week']} move in the same week.",
            "",
            f"**Is the same-week co-movement about the title at all?** Both series rise at "
            f"release and decay, so any two of them share that shape. Pairing each title's "
            f"hours with a *different* title's pageviews gives a median correlation of "
            f"**{placebo['placebo_median']:.2f}** against **{placebo['real_median']:.2f}** for "
            f"the real pairings, and {placebo['real_above_placebo_p95']} of "
            f"{placebo['n_titles']} titles beat the placebo's 95th percentile "
            f"({placebo['placebo_p95']:.2f}). "
            + ("So the correlation is mostly title-specific, not just the shared shape."
               if placebo["real_median"] - placebo["placebo_median"] > 0.15
               else "So most of the correlation is the shared release-and-decay shape rather "
                    "than anything about the individual title, and the same-week finding "
                    "should be read that way."),
            "",
            "**What this can and cannot say.** The estimate is the best-fitting lag per "
            "title, picked from nine candidates, so some of the spread is the search itself. "
            "Coverage is the bigger limit: English Wikipedia only, on titles that charted at "
            "least five weeks, which excludes most non-English titles even though they are "
            "half the chart by construction.",
            "",
            "Titles where the relationship is strongest, in either direction:",
            "",
        ]
        strong = fits.reindex(fits.r.abs().sort_values(ascending=False).index).head(10)
        lines.append(strong[["title", "kind", "weeks", "best_lag", "r"]].round(2).to_markdown(index=False))
        lines.append("")
    else:
        lines += ["No title has enough overlapping weeks yet - run `python -m src.fetch_demand`.", ""]

    lines += [
        "---",
        "",
        "## What Checkpoint 4 has to decide",
        "",
        "Interpretation, and the renewal-shaped recommendation. The findings above are "
        "measurements; what a content team should *do* about them is Eileen's, because it "
        "is the part an interviewer will push on.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main():
    con = duckdb.connect(str(model.MODEL_DB), read_only=True)
    report = build(con)
    OUT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
