"""Phase 5: the stakeholder deck.

The numbers are exported from the model rather than typed into the slides, so a rebuild
after new data cannot leave a stale figure on a slide nobody re-reads.

Run: python -m src.deck   (writes deliverables/deck-data.json, then runs the generator)
"""
from __future__ import annotations

import json
import subprocess
import sys

import duckdb

from src import analysis, config, match, match_imdb, model

DATA = config.ROOT / "deliverables" / "deck-data.json"
GENERATOR = config.ROOT / "scripts" / "build_deck.js"


def collect() -> dict:
    con = duckdb.connect(str(model.MODEL_DB), read_only=True)
    imdb = con.execute("""
        SELECT count(*) AS titles, count(*) FILTER (WHERE matched) AS matched,
               count(*) FILTER (WHERE kind = 'film') AS films,
               count(*) FILTER (WHERE kind = 'film' AND matched) AS films_matched,
               count(*) FILTER (WHERE kind = 'tv') AS tv,
               count(*) FILTER (WHERE kind = 'tv' AND matched) AS tv_matched
        FROM dim_title
    """).fetchdf().iloc[0]
    hours = con.execute("""
        SELECT sum(f.hours_viewed) AS total,
               sum(f.hours_viewed) FILTER (WHERE t.matched) AS matched
        FROM fact_engagement_halfyear f JOIN dim_title t USING (title_id)
    """).fetchdf().iloc[0]
    rungs = con.execute("""
        SELECT match_rung AS rung, count(*) AS n FROM dim_title
        WHERE matched AND match_rung IS NOT NULL GROUP BY 1 ORDER BY 2 DESC
    """).fetchdf()
    fuzzy = int(con.execute("SELECT count(*) FROM dim_title WHERE matched AND match_rung IS NULL").fetchone()[0])
    counts = con.execute("""
        SELECT (SELECT count(*) FROM fact_engagement_halfyear) AS engagement_rows,
               (SELECT count(*) FROM fact_top10_weekly) AS top10_rows,
               (SELECT count(DISTINCT week) FROM fact_top10_weekly) AS weeks,
               (SELECT count(*) FROM dim_period) AS periods,
               (SELECT count(DISTINCT title_id) FROM fact_pageviews) AS demand_titles
    """).fetchdf().iloc[0]

    genres = analysis.delivery_ratio(analysis.genre_rows(con))
    longevity = analysis.rating_vs_longevity(analysis.longevity_rows(con))
    series = analysis.demand_series(con)
    fits = analysis.lead_lag(series)
    placebo = analysis.placebo_comovement(series)
    terms = dict(zip(longevity["terms"], longevity["beta"]))
    ci = {t: [longevity["ci"][0][i], longevity["ci"][1][i]] for i, t in enumerate(longevity["terms"])}

    netflix_join = match.rate(__import__("src.match_netflix", fromlist=["run"]).run())

    picked = ["Family", "Animation", "Drama", "Comedy", "Crime", "Thriller", "Documentary"]
    return {
        "titles": int(imdb.titles), "matched": int(imdb.matched),
        "match_rate": float(imdb.matched / imdb.titles),
        "film_rate": float(imdb.films_matched / imdb.films),
        "tv_rate": float(imdb.tv_matched / imdb.tv),
        "hours_total": int(hours.total), "hours_matched_share": float(hours.matched / hours.total),
        "engagement_rows": int(counts.engagement_rows), "top10_rows": int(counts.top10_rows),
        "weeks": int(counts.weeks), "periods": int(counts.periods),
        "demand_titles": int(counts.demand_titles),
        "netflix_join_rate": float(netflix_join["match_rate"]),
        "netflix_join_rows": int(netflix_join["rows"]),
        "threshold": float(match.FUZZY_THRESHOLD),
        "rungs": [{"rung": r.rung, "n": int(r.n)} for r in rungs.itertuples()] + [{"rung": "fuzzy", "n": fuzzy}],
        "genres": [{"genre": g, "delivery": round(float(row.delivery), 2),
                    "low": round(float(row.ci_low), 2), "high": round(float(row.ci_high), 2)}
                   for g, row in genres.iterrows() if g in picked],
        "longevity": {
            "n": int(longevity["n"]), "rho": round(float(longevity["spearman_rho"]), 3),
            "rating": round(float(terms["rating"]), 2),
            "rating_ci": [round(float(ci["rating"][0]), 2), round(float(ci["rating"][1]), 2)],
            "log_hours": round(float(terms["log_hours"]), 1),
            "non_english": round(float(terms["non_english"]), 1),
            "r2": round(float(longevity["r2"]), 3),
        },
        "lead_lag": {
            "titles": int(len(fits)),
            "at_zero": int((fits.best_lag == 0).sum()),
            "leads": int((fits.best_lag < 0).sum()), "lags": int((fits.best_lag > 0).sum()),
            "distribution": [[int(k), int(v)] for k, v in fits.best_lag.value_counts().sort_index().items()],
            "real_r": round(float(placebo["real_median"]), 2),
            "placebo_r": round(float(placebo["placebo_median"]), 2),
        },
    }


def main():
    data = collect()
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {DATA}")
    result = subprocess.run(["node", str(GENERATOR)], cwd=config.ROOT, capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr.strip())
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
