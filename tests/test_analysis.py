"""Phase 4: the statistics do what they claim on data whose answer is known.

Analysis code is where a portfolio project is most likely to be quietly wrong, because
a plausible number comes back either way. These tests use series and tables built so
the right answer is known in advance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import analysis


# --- lead and lag ----------------------------------------------------------------------

def shifted_pair(lead_weeks: int, n=30, seed=1):
    """Pageviews that move `lead_weeks` before hours, plus a little noise."""
    rng = np.random.default_rng(seed)
    signal = np.abs(rng.normal(0, 1, n + abs(lead_weeks) + 1)).cumsum()
    bumps = rng.normal(0, 0.05, len(signal))
    pageviews = np.exp(signal + bumps)
    hours = np.exp(np.roll(signal, lead_weeks) + rng.normal(0, 0.05, len(signal)))
    return hours[abs(lead_weeks):abs(lead_weeks) + n], pageviews[abs(lead_weeks):abs(lead_weeks) + n]


def test_a_known_lead_is_recovered_with_the_right_sign():
    """A negative lag must mean pageviews moved first - the sign convention is the finding."""
    hours, pageviews = shifted_pair(lead_weeks=2)
    fit = analysis.best_lag(hours, pageviews)
    assert fit["lag"] == -2, fit["by_lag"]
    assert fit["r"] > 0.5

    hours, pageviews = shifted_pair(lead_weeks=-3)   # hours move first
    assert analysis.best_lag(hours, pageviews)["lag"] == 3


def test_simultaneous_series_give_lag_zero():
    hours, pageviews = shifted_pair(lead_weeks=0)
    assert analysis.best_lag(hours, pageviews)["lag"] == 0


def test_a_lag_is_only_tried_when_enough_weeks_survive_the_shift():
    """Without this floor an eight-week series scored r = 0.99 at lag 4, from three points."""
    hours, pageviews = shifted_pair(lead_weeks=0, n=8)
    fit = analysis.best_lag(hours, pageviews, max_lag=4, min_pairs=6)
    assert set(fit["by_lag"]) == {-1, 0, 1}, "7 differences and 6 pairs leaves only lags -1..1"
    assert analysis.best_lag(hours[:5], pageviews[:5], min_pairs=6) is None


def test_a_flat_series_has_no_lag_to_find():
    assert analysis.best_lag(np.ones(20), np.ones(20)) is None


def test_the_placebo_separates_a_real_relationship_from_a_shared_shape():
    """Every title here shares the same decay shape, but only the real pairs share noise."""
    rows = []
    for i in range(12):
        hours, pageviews = shifted_pair(lead_weeks=0, n=20, seed=100 + i)
        rows += [{"title_id": f"t{i}", "week": pd.Timestamp("2025-01-05") + pd.Timedelta(weeks=w),
                  "hours": hours[w], "pageviews": pageviews[w]} for w in range(20)]
    out = analysis.placebo_comovement(pd.DataFrame(rows), min_weeks=8, draws=200)
    assert out["n_titles"] == 12
    assert out["real_median"] > out["placebo_median"]


# --- the sign test ----------------------------------------------------------------------

def test_sign_test_ignores_ties_and_counts_directions():
    out = analysis.sign_test(pd.Series([-1, -2, -3, 1, 0, 0]))
    assert (out["leads"], out["lags"], out["same_week"], out["n_decisive"]) == (3, 1, 2, 4)
    assert 0 < out["p"] <= 1
    balanced = analysis.sign_test(pd.Series([-1, 1]))
    assert balanced["p"] == 1


# --- genre delivery ---------------------------------------------------------------------

def genre_frame(rows):
    return pd.DataFrame([{"title_id": t, "kind": "film", "genre": g, "hours": h,
                          "slots": s, "weeks_charted": w}
                         for t, g, h, s, w in rows])


def test_delivery_is_one_when_hours_and_chart_share_agree(monkeypatch):
    monkeypatch.setattr(analysis, "MIN_GENRE_TITLES", 2)
    monkeypatch.setattr(analysis, "BOOTSTRAP", 200)
    rows = []
    for i in range(6):
        rows.append((f"a{i}", "Drama", 100, 1, 1))
        rows.append((f"b{i}", "Horror", 100, 1, 1))
    out = analysis.delivery_ratio(genre_frame(rows))
    assert out.delivery.round(3).tolist() == [1.0, 1.0]
    assert (out.ci_low <= 1).all() and (out.ci_high >= 1).all()


def test_a_genre_watched_without_charting_delivers_above_one(monkeypatch):
    monkeypatch.setattr(analysis, "MIN_GENRE_TITLES", 2)
    monkeypatch.setattr(analysis, "BOOTSTRAP", 200)
    rows = []
    for i in range(8):
        rows.append((f"kid{i}", "Family", 400, 1, 1))     # watched four times as much
        rows.append((f"thr{i}", "Thriller", 100, 1, 1))   # same chart presence
    out = analysis.delivery_ratio(genre_frame(rows))
    assert out.loc["Family", "delivery"] > 1.5
    assert out.loc["Thriller", "delivery"] < 0.7
    assert out.loc["Family", "ci_low"] > 1, "the interval should exclude parity"


def test_a_multi_genre_title_counts_in_each_genre_and_shares_still_sum_to_one(monkeypatch):
    monkeypatch.setattr(analysis, "MIN_GENRE_TITLES", 1)
    monkeypatch.setattr(analysis, "BOOTSTRAP", 50)
    rows = [("x", "Drama", 100, 2, 1), ("x", "Crime", 100, 2, 1), ("y", "Comedy", 50, 1, 1)]
    out = analysis.delivery_ratio(genre_frame(rows))
    assert out.titles.sum() == 3           # two genres for x, one for y
    assert out.hours_share.sum() == pytest.approx(1.0)
    assert out.slots_share.sum() == pytest.approx(1.0)


# --- the regression ---------------------------------------------------------------------

def test_ols_recovers_a_planted_relationship():
    rng = np.random.default_rng(7)
    n = 400
    rating = rng.uniform(4, 9, n)
    log_hours = rng.uniform(6, 9, n)
    y = 2.0 + 0.5 * rating + 3.0 * log_hours + rng.normal(0, 0.2, n)
    X = np.column_stack([np.ones(n), rating, log_hours])
    beta, r2 = analysis.ols(X, y)
    assert beta[1] == pytest.approx(0.5, abs=0.05)
    assert beta[2] == pytest.approx(3.0, abs=0.05)
    assert r2 > 0.98


def test_rating_effect_reports_an_interval_that_can_contain_zero():
    """The real answer is a null, so the code must be able to express one."""
    rng = np.random.default_rng(11)
    n = 300
    df = pd.DataFrame({
        "imdb_rating": rng.uniform(4, 9, n),
        "imdb_votes": rng.integers(100, 100000, n),
        "hours": rng.integers(1_000_000, 900_000_000, n),
        "kind": rng.choice(["tv", "film"], n),
        "language": rng.choice(["english", "non-english"], n),
        "last_week": pd.Timestamp("2026-06-28"),
    })
    df["weeks_charted"] = rng.integers(1, 12, n)     # unrelated to rating, by construction
    out = analysis.rating_vs_longevity(df)
    i = out["terms"].index("rating")
    low, high = out["ci"][0][i], out["ci"][1][i]
    assert low < 0 < high, "an unrelated predictor should not come back significant"
    assert out["n"] == n
