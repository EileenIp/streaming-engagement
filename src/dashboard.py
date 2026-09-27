"""Phase 5: the dashboard — four sources on one screen, in one self-contained file.

Everything is embedded: no CDN, no fetch, no build step. Open the file from disk or
from GitHub Pages and it works, which is the only way a dashboard survives being sent
to someone as a link.

Two decisions about what goes in it:

* **Titles below 10M reported hours are left out** (6,935 of 24,902 remain). Hours are
  published rounded to the nearest 100,000 with a floor of 100,000, so the tail is
  mostly rounding artefacts, and shipping all 24,902 would double the file for rows
  nobody can read.
* **No IMDb ratings or vote counts per title.** IMDb's datasets are licensed for
  personal, non-commercial use, so this publishes the genre labels the analysis needs
  to be filterable and nothing else from IMDb per title; the rating finding appears as
  model coefficients, which are aggregates. Netflix's own figures are already public.

Run: python -m src.dashboard
"""
from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd

from src import analysis, config, model

OUT = config.ROOT / "dashboard" / "index.html"
HOURS_FLOOR = 10_000_000


def collect(con) -> dict:
    periods = con.execute("SELECT period, period_start, period_end FROM dim_period "
                          "ORDER BY period_start").fetchdf()
    period_labels = periods.period.tolist()

    rows = con.execute(f"""
        WITH per_period AS (
            SELECT title_id, period, sum(hours_viewed) AS hours, sum(views) AS views
            FROM fact_engagement_halfyear GROUP BY 1, 2
        ),
        charted AS (
            SELECT f.title_id, count(DISTINCT f.week) AS weeks_charted, min(f.weekly_rank) AS best_rank,
                   any_value(f.language) AS language
            FROM fact_top10_weekly f
            JOIN dim_period p ON f.week BETWEEN p.period_start AND p.period_end
            WHERE f.title_id IS NOT NULL GROUP BY 1
        )
        SELECT h.title_id, h.canonical_title, h.kind, h.imdb_genres, h.hours,
               h.weeks_available, h.available_from_source,
               coalesce(c.weeks_charted, 0) AS weeks_charted, c.best_rank,
               coalesce(c.language, 'unknown') AS language,
               list(p.period ORDER BY p.period) AS period_list,
               list(p.hours ORDER BY p.period) AS period_hours
        FROM v_headline h
        LEFT JOIN charted c USING (title_id)
        LEFT JOIN per_period p USING (title_id)
        WHERE h.hours >= {HOURS_FLOOR}
        GROUP BY ALL
        ORDER BY h.hours DESC
    """).fetchdf()

    genres = sorted({g.strip() for gs in rows.imdb_genres.dropna() for g in gs.split(",") if g.strip()})
    genre_index = {g: i for i, g in enumerate(genres)}
    sources = ["netflix_release_date", "imdb_start_year", "first_period_reported"]

    titles = []
    for r in rows.itertuples():
        # DuckDB returns list columns as numpy arrays, so `or []` would test truthiness
        # of an array rather than substitute a default.
        labels = r.period_list if r.period_list is not None else []
        hours = r.period_hours if r.period_hours is not None else []
        by_period = dict(zip(labels, hours))
        titles.append([
            r.canonical_title,
            0 if r.kind == "tv" else 1,
            [genre_index[g.strip()] for g in (r.imdb_genres or "").split(",") if g.strip()],
            [round(float(by_period.get(p, 0)) / 1e6, 1) for p in period_labels],
            int(r.weeks_available),
            int(r.weeks_charted),
            None if pd.isna(r.best_rank) else int(r.best_rank),
            sources.index(r.available_from_source),
            0 if r.language == "english" else (1 if r.language == "non-english" else 2),
        ])

    delivery = analysis.delivery_ratio(analysis.genre_rows(con))
    def finite(x):
        """NaN is legal JavaScript but not legal JSON, and one NaN reaching Math.max
        poisons a whole chart's scale. Non-finite values leave as null."""
        return None if x is None or not np.isfinite(x) else round(float(x), 2)

    genre_delivery = [{
        "genre": g,
        "titles": int(row.titles), "charting": int(row.charting),
        "hours_share": finite(row.hours_share * 100),
        "slots_share": finite(row.slots_share * 100),
        "delivery": finite(row.delivery),
        "ci": [finite(row.ci_low), finite(row.ci_high)],
    } for g, row in delivery.iterrows()]
    genre_delivery = [g for g in genre_delivery if g["delivery"] is not None and None not in g["ci"]]

    longevity = analysis.rating_vs_longevity(analysis.longevity_rows(con))
    coefficients = [{"term": t, "estimate": round(float(b), 3),
                     "ci": [round(float(lo), 3), round(float(hi), 3)]}
                    for t, b, lo, hi in zip(longevity["terms"], longevity["beta"],
                                            longevity["ci"][0], longevity["ci"][1])
                    if t != "intercept"]

    series = analysis.demand_series(con)
    fits = analysis.lead_lag(series)
    placebo = analysis.placebo_comovement(series)
    lag_counts = fits.best_lag.value_counts().sort_index()
    # One title's two series, to show what the co-movement looks like rather than assert it.
    example_id = fits.sort_values("weeks", ascending=False).iloc[0].title_id
    example = series[series.title_id == example_id].sort_values("week")

    join_rates = con.execute("""
        SELECT (SELECT count(*) FROM dim_title) AS titles,
               (SELECT count(*) FROM dim_title WHERE matched) AS matched,
               (SELECT count(*) FROM fact_engagement_halfyear) AS engagement_rows,
               (SELECT count(*) FROM fact_top10_weekly) AS top10_rows,
               (SELECT count(DISTINCT week) FROM fact_top10_weekly) AS weeks,
               (SELECT sum(hours_viewed) FROM fact_engagement_halfyear) AS hours,
               (SELECT sum(hours_viewed) FROM fact_engagement_halfyear f
                  JOIN dim_title t USING (title_id) WHERE t.matched) AS matched_hours,
               (SELECT count(*) FROM fact_pageviews) AS pageview_rows,
               (SELECT count(DISTINCT title_id) FROM fact_pageviews) AS pageview_titles
    """).fetchdf().iloc[0]

    return {
        "generated": str(np.datetime64("today")),
        # .date(): DuckDB hands these back as timestamps, and str() on a timestamp puts
        # ' 00:00:00' in the middle of every dropdown label.
        "periods": [{"label": r.period, "start": str(r.period_start.date()),
                     "end": str(r.period_end.date())} for r in periods.itertuples()],
        "genres": genres,
        "sources": sources,
        "titles": titles,
        "genre_delivery": genre_delivery,
        "coefficients": coefficients,
        "longevity": {"n": int(longevity["n"]), "rho": round(float(longevity["spearman_rho"]), 3),
                      "r2": round(float(longevity["r2"]), 3)},
        "lead_lag": {
            "titles": int(len(fits)),
            "distribution": [[int(k), int(v)] for k, v in lag_counts.items()],
            "median_lag": float(fits.best_lag.median()),
            "median_r": round(float(fits.r.median()), 2),
            "placebo_median": round(float(placebo["placebo_median"]), 2),
            "real_median": round(float(placebo["real_median"]), 2),
            "example": {
                "title": example.canonical_title.iloc[0],
                "weeks": [str(w) for w in example.week],
                "hours": [round(float(h) / 1e6, 1) for h in example.hours],
                "pageviews": [int(v) for v in example.pageviews],
            },
        },
        "coverage": {
            "titles": int(join_rates.titles), "matched": int(join_rates.matched),
            "engagement_rows": int(join_rates.engagement_rows),
            "top10_rows": int(join_rates.top10_rows), "weeks": int(join_rates.weeks),
            "hours": int(join_rates.hours), "matched_hours": int(join_rates.matched_hours),
            "pageview_rows": int(join_rates.pageview_rows),
            "pageview_titles": int(join_rates.pageview_titles),
            "shown": len(titles), "hours_floor": HOURS_FLOOR,
        },
    }


TEMPLATE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Streaming Engagement — four sources, one screen</title>
<style>
  :root {
    color-scheme: light dark;
    --ink:#15181d; --dim:#5f6570; --paper:#fbfbf9; --card:#fff; --line:#dedbd4;
    --accent:#2f5d8a; --over:#2f7d5d; --under:#a2503c; --grid:#e8e5de;
  }
  @media (prefers-color-scheme: dark) {
    :root { --ink:#e9e7e3; --dim:#9aa0a8; --paper:#15171a; --card:#1d2024; --line:#32363c;
            --accent:#7fa9d4; --over:#6cba92; --under:#d98a72; --grid:#2a2e33; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink);
         font:15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, sans-serif; }
  .wrap { max-width:1060px; margin:0 auto; padding:0 20px 80px; }
  header { border-bottom:1px solid var(--line); background:var(--card); }
  header .wrap { padding:26px 20px 22px; }
  h1 { font-size:24px; margin:0 0 6px; letter-spacing:-.01em; }
  h2 { font-size:17px; margin:34px 0 4px; }
  h3 { font-size:14px; margin:0 0 10px; color:var(--dim); font-weight:600;
       text-transform:uppercase; letter-spacing:.05em; }
  p { margin:6px 0 10px; max-width:70ch; }
  .lede { color:var(--dim); font-size:15px; max-width:74ch; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:18px 0 0; }
  .kpi { background:var(--card); border:1px solid var(--line); border-radius:9px; padding:12px 14px; }
  .kpi b { display:block; font-size:21px; font-variant-numeric:tabular-nums; }
  .kpi span { color:var(--dim); font-size:12px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:11px;
          padding:18px 20px; margin:14px 0; }
  .controls { display:flex; gap:14px; flex-wrap:wrap; align-items:flex-end; }
  label { display:block; font-size:12px; color:var(--dim); margin-bottom:4px; }
  select, input[type=search] { font:inherit; padding:6px 9px; border:1px solid var(--line);
    border-radius:7px; background:var(--paper); color:var(--ink); min-width:150px; }
  table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
  th, td { text-align:right; padding:7px 9px; border-bottom:1px solid var(--grid); font-size:14px; }
  th:first-child, td:first-child { text-align:left; }
  th { color:var(--dim); font-size:12px; font-weight:600; cursor:pointer; user-select:none;
       text-transform:uppercase; letter-spacing:.04em; white-space:nowrap; }
  th[aria-sort] { color:var(--ink); }
  tbody tr:hover { background:color-mix(in srgb, var(--accent) 7%, transparent); }
  .tag { font-size:11px; color:var(--dim); border:1px solid var(--line); border-radius:20px;
         padding:1px 7px; margin-left:5px; white-space:nowrap; }
  .note { color:var(--dim); font-size:13px; max-width:78ch; }
  .over { color:var(--over); } .under { color:var(--under); }
  svg { display:block; max-width:100%; height:auto; overflow:visible; }
  .two { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  @media (max-width:820px) { .two { grid-template-columns:1fr; } }
  footer { color:var(--dim); font-size:13px; border-top:1px solid var(--line); margin-top:36px;
           padding-top:16px; }
  code { font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:.92em; }
  .empty { color:var(--dim); padding:18px 0; }
</style>
<header><div class="wrap">
  <h1>Which titles are earning their place?</h1>
  <p class="lede">Four public sources — two Netflix files that disagree with each other, IMDb,
  and Wikipedia — resolved to one model. Everything below is filterable by period, genre and
  type, which is the point: it replaces four spreadsheets nobody reconciles by hand.</p>
  <div id="hero"></div>
</div></header>

<div class="wrap">
  <div class="kpis" id="kpis"></div>

  <h2>Titles, ranked</h2>
  <p class="note">Headline metric: <b>reported hours per week available since release</b>, with
  Top 10 longevity beside it. Titles need eight weeks available to be ranked — a title released
  days before a report closes would otherwise divide half a year of viewing by one week.</p>
  <div class="card">
    <div class="controls">
      <div><label for="period">Period</label><select id="period"></select></div>
      <div><label for="genre">Genre</label><select id="genre"></select></div>
      <div><label for="kind">Type</label><select id="kind">
        <option value="">Film and TV</option><option value="0">TV</option><option value="1">Film</option>
      </select></div>
      <div><label for="chart">Chart</label><select id="chart">
        <option value="">All titles</option><option value="1">Charted in the Top 10</option>
        <option value="0">Never charted</option>
      </select></div>
      <div><label for="q">Title contains</label><input type="search" id="q" placeholder="e.g. Wednesday"></div>
    </div>
    <p class="note" id="filterState"></p>
    <table>
      <thead><tr>
        <th data-key="0">Title</th>
        <th data-key="hours" aria-sort="descending">Hours (M)</th>
        <th data-key="hpw">Hours / week (M)</th>
        <th data-key="4">Weeks available</th>
        <th data-key="5">Weeks charted</th>
        <th data-key="6">Best rank</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <p class="note" id="tableNote"></p>
  </div>

  <h2>Genres that are watched more than they chart</h2>
  <p class="note">Share of reported hours divided by share of Top 10 slots. Above 1 means a genre
  gets watched more than its chart presence suggests. The chart is capped at ten slots per
  category per week and hours are not, which is what makes the comparison say something.
  Bars show 95% bootstrap intervals over titles; genres whose interval clears 1 are the real
  ones.</p>
  <div class="card" id="genreChart"></div>

  <div class="two">
    <div class="card">
      <h3>Does a better rating hold the chart longer?</h3>
      <p class="note">No. Raw correlation looks positive, but with size held constant the rating
      term is indistinguishable from zero. Weeks of chart time per unit, 95% intervals.</p>
      <div id="coefChart"></div>
    </div>
    <div class="card">
      <h3>Does outside interest arrive first?</h3>
      <p class="note">No — it arrives the same week. Best-fitting lag per title, negative meaning
      Wikipedia moved first.</p>
      <div id="lagChart"></div>
      <div id="exampleChart"></div>
    </div>
  </div>

  <footer>
    <p><b>Sources.</b> Netflix engagement reports ("What We Watched", six half-years to June
    2026) and the Netflix Global Top 10 weekly file, both published by Netflix; IMDb
    non-commercial datasets; English Wikipedia pageviews via the Wikimedia API, reached from
    IMDb ids through Wikidata.</p>
    <p><b>What this cannot tell you.</b> Hours are half-yearly, rounded to 100,000, and one
    platform only — nothing here is a market share. Genre comes from IMDb, not Netflix, and a
    title with three genres counts in all three. Wikipedia pageviews are English-language, so
    they under-represent non-English titles, which are half the Top 10 by construction. Titles
    under <span id="floorNote"></span> reported hours are left out of the table.</p>
    <p><b>Per-title IMDb ratings and vote counts are deliberately not published here</b> —
    IMDb's datasets are licensed for personal, non-commercial use, so this page carries the
    genre labels the analysis needs and the model coefficients, which are aggregates.</p>
    <p id="built"></p>
  </footer>
</div>

<script>
const DATA = __DATA__;
const fmt = (n, d = 0) => n == null ? "—" : n.toLocaleString("en-AU", {minimumFractionDigits: d, maximumFractionDigits: d});
const el = id => document.getElementById(id);
const KIND = ["TV", "Film"];
const SRC = {netflix_release_date: "Netflix release date", imdb_start_year: "IMDb start year",
             first_period_reported: "first period reported"};

// --- hero: four sources feeding one model ------------------------------------------------
function hero() {
  const c = DATA.coverage, boxes = [
    ["Netflix engagement report", `6 half-years · ${fmt(c.engagement_rows)} rows`],
    ["Netflix Global Top 10", `${fmt(c.weeks)} weeks · ${fmt(c.top10_rows)} slots`],
    ["IMDb datasets", `${fmt(c.matched)} of ${fmt(c.titles)} titles matched`],
    ["Wikipedia pageviews", `${fmt(c.pageview_titles)} titles · ${fmt(c.pageview_rows)} days`],
  ];
  const w = 1000, rowH = 46, h = boxes.length * rowH + 26;
  let s = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Four sources feeding one model">`;
  boxes.forEach(([name, detail], i) => {
    const y = 8 + i * rowH;
    s += `<rect x="0" y="${y}" width="330" height="36" rx="8" fill="var(--paper)" stroke="var(--line)"/>
      <text x="14" y="${y + 15}" font-size="13" font-weight="600" fill="var(--ink)">${name}</text>
      <text x="14" y="${y + 29}" font-size="11" fill="var(--dim)">${detail}</text>
      <path d="M334 ${y + 18} C 420 ${y + 18}, 470 ${h / 2}, 560 ${h / 2}" fill="none"
            stroke="var(--accent)" stroke-width="1.4" opacity=".65"/>`;
  });
  s += `<rect x="566" y="${h / 2 - 32}" width="240" height="64" rx="9" fill="var(--card)" stroke="var(--accent)"/>
    <text x="586" y="${h / 2 - 10}" font-size="13" font-weight="600" fill="var(--ink)">One star schema</text>
    <text x="586" y="${h / 2 + 8}" font-size="11" fill="var(--dim)">${fmt(c.titles)} titles · ${fmt(Math.round(c.hours / 1e9))}B hours</text>
    <text x="586" y="${h / 2 + 24}" font-size="11" fill="var(--dim)">${(100 * c.matched_hours / c.hours).toFixed(1)}% of hours carry an IMDb id</text>
    <path d="M810 ${h / 2} H 880" fill="none" stroke="var(--accent)" stroke-width="1.4"/>
    <text x="890" y="${h / 2 + 4}" font-size="13" fill="var(--ink)">This screen</text></svg>`;
  el("hero").innerHTML = s;
}

// --- filters and table ------------------------------------------------------------------
let sortKey = "hours", sortDir = -1;

function periodHours(t) {
  const p = el("period").value;
  return p === "" ? t[3].reduce((a, b) => a + b, 0) : t[3][+p];
}
function filtered() {
  const g = el("genre").value, k = el("kind").value, ch = el("chart").value,
        q = el("q").value.trim().toLowerCase();
  return DATA.titles.filter(t =>
    (g === "" || t[2].includes(+g)) &&
    (k === "" || t[1] === +k) &&
    (ch === "" || (ch === "1" ? t[5] > 0 : t[5] === 0)) &&
    (q === "" || t[0].toLowerCase().includes(q)) &&
    periodHours(t) > 0);
}
function value(t, key) {
  if (key === "hours") return periodHours(t);
  if (key === "hpw") return periodHours(t) / t[4];
  return t[key];
}
function draw() {
  const rows = filtered();
  rows.sort((a, b) => {
    const x = value(a, sortKey), y = value(b, sortKey);
    if (typeof x === "string") return sortDir * x.localeCompare(y);
    return sortDir * ((x ?? -1) - (y ?? -1));
  });
  const shown = rows.slice(0, 200);
  el("rows").innerHTML = shown.length ? shown.map(t => `<tr>
      <td>${t[0]}<span class="tag">${KIND[t[1]]}</span>${t[2].map(i => `<span class="tag">${DATA.genres[i]}</span>`).join("")}</td>
      <td>${fmt(periodHours(t), 1)}</td>
      <td>${fmt(periodHours(t) / t[4], 2)}</td>
      <td>${fmt(t[4])}<span class="tag">${SRC[DATA.sources[t[7]]]}</span></td>
      <td>${t[5] || "—"}</td>
      <td>${t[6] ?? "—"}</td></tr>`).join("")
    : `<tr><td colspan="6" class="empty">No titles match those filters.</td></tr>`;
  const total = rows.reduce((a, t) => a + periodHours(t), 0);
  el("filterState").textContent =
    `${fmt(rows.length)} titles · ${fmt(total, 0)}M reported hours` +
    (rows.length > shown.length ? ` · showing the top ${shown.length}` : "");
  el("tableNote").textContent = shown.length && el("period").value !== ""
    ? "Hours are for the selected period; hours per week still divides by weeks available since release."
    : "";
}

// --- charts -----------------------------------------------------------------------------
function genreChart() {
  const d = DATA.genre_delivery.slice().sort((a, b) => b.delivery - a.delivery);
  const rowH = 22, padL = 112, w = 900, h = d.length * rowH + 34;
  const highs = d.map(x => x.ci[1]).filter(Number.isFinite);
  const max = Math.max(...highs, 2.4), scale = v => padL + (v / max) * (w - padL - 60);
  let s = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Genre delivery ratios">`;
  [0.5, 1, 1.5, 2].forEach(v => {
    if (v > max) return;
    s += `<line x1="${scale(v)}" y1="18" x2="${scale(v)}" y2="${h - 16}" stroke="var(--grid)"
      ${v === 1 ? 'stroke-dasharray="3 3" stroke="var(--dim)"' : ""}/>
      <text x="${scale(v)}" y="12" font-size="10" fill="var(--dim)" text-anchor="middle">${v}</text>`;
  });
  d.forEach((x, i) => {
    const y = 24 + i * rowH, cls = x.ci[0] > 1 ? "var(--over)" : (x.ci[1] < 1 ? "var(--under)" : "var(--dim)");
    s += `<text x="0" y="${y + 4}" font-size="12" fill="var(--ink)">${x.genre}</text>
      <line x1="${scale(x.ci[0])}" y1="${y}" x2="${scale(x.ci[1])}" y2="${y}" stroke="${cls}" stroke-width="1.5" opacity=".55"/>
      <circle cx="${scale(x.delivery)}" cy="${y}" r="4" fill="${cls}"/>
      <text x="${scale(x.ci[1]) + 8}" y="${y + 4}" font-size="11" fill="var(--dim)">${x.delivery.toFixed(2)} · ${fmt(x.titles)} titles</text>`;
  });
  el("genreChart").innerHTML = s + "</svg>";
}

function coefChart() {
  const d = DATA.coefficients, names = {rating: "IMDb rating (per point)",
    log_hours: "Hours (per 10×)", log_votes: "Votes (per 10×)", is_tv: "Is TV, not film",
    non_english: "Non-English category"};
  const rowH = 30, padL = 150, w = 470, h = d.length * rowH + 26;
  const lo = Math.min(...d.map(x => x.ci[0]), -1), hi = Math.max(...d.map(x => x.ci[1]), 1);
  const scale = v => padL + ((v - lo) / (hi - lo)) * (w - padL - 34);
  let s = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Regression coefficients">
    <line x1="${scale(0)}" y1="14" x2="${scale(0)}" y2="${h - 12}" stroke="var(--dim)" stroke-dasharray="3 3"/>`;
  d.forEach((x, i) => {
    const y = 26 + i * rowH, crosses = x.ci[0] <= 0 && x.ci[1] >= 0;
    s += `<text x="0" y="${y + 4}" font-size="12" fill="var(--ink)">${names[x.term] || x.term}</text>
      <line x1="${scale(x.ci[0])}" y1="${y}" x2="${scale(x.ci[1])}" y2="${y}"
            stroke="${crosses ? "var(--dim)" : "var(--accent)"}" stroke-width="1.5" opacity=".6"/>
      <circle cx="${scale(x.estimate)}" cy="${y}" r="4" fill="${crosses ? "var(--dim)" : "var(--accent)"}"/>
      <text x="${w - 30}" y="${y + 4}" font-size="11" fill="var(--dim)" text-anchor="end">${x.estimate.toFixed(2)}</text>`;
  });
  s += `<text x="0" y="${h - 1}" font-size="10" fill="var(--dim)">weeks of chart time · n = ${fmt(DATA.longevity.n)} · R² = ${DATA.longevity.r2}</text>`;
  el("coefChart").innerHTML = s + "</svg>";
}

function lagChart() {
  const d = DATA.lead_lag, max = Math.max(...d.distribution.map(x => x[1]));
  const w = 470, h = 150, padL = 30, barW = (w - padL - 20) / d.distribution.length;
  let s = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Best lag distribution">`;
  d.distribution.forEach(([lag, n], i) => {
    const bh = (n / max) * (h - 56), x = padL + i * barW;
    s += `<rect x="${x + 3}" y="${h - 34 - bh}" width="${barW - 6}" height="${bh}" rx="3"
        fill="${lag === 0 ? "var(--accent)" : "var(--grid)"}"/>
      <text x="${x + barW / 2}" y="${h - 20}" font-size="10" fill="var(--dim)" text-anchor="middle">${lag > 0 ? "+" + lag : lag}</text>
      <text x="${x + barW / 2}" y="${h - 40 - bh}" font-size="10" fill="var(--dim)" text-anchor="middle">${n}</text>`;
  });
  s += `<text x="${padL}" y="${h - 4}" font-size="10" fill="var(--dim)">weeks Wikipedia leads (−) or lags (+) · ${fmt(d.titles)} titles</text>
    <text x="0" y="12" font-size="11" fill="var(--ink)">median lag ${d.median_lag > 0 ? "+" : ""}${d.median_lag}, r = ${d.median_r}; shuffled titles give r = ${d.placebo_median}</text></svg>`;
  el("lagChart").innerHTML = s;
}

function exampleChart() {
  const e = DATA.lead_lag.example, n = e.weeks.length;
  const w = 470, h = 130, padL = 8, padR = 8;
  const x = i => padL + (i / (n - 1)) * (w - padL - padR);
  const norm = a => { const m = Math.max(...a); return a.map(v => v / m); };
  const line = (a, colour) => `<polyline fill="none" stroke="${colour}" stroke-width="1.6"
      points="${norm(a).map((v, i) => `${x(i)},${h - 26 - v * (h - 46)}`).join(" ")}"/>`;
  el("exampleChart").innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img"
      aria-label="One title's weekly hours and pageviews">
    ${line(e.hours, "var(--accent)")}${line(e.pageviews, "var(--under)")}
    <text x="0" y="10" font-size="11" fill="var(--ink)">${e.title}</text>
    <text x="0" y="${h - 10}" font-size="10" fill="var(--dim)">
      <tspan fill="var(--accent)">weekly hours</tspan> and
      <tspan fill="var(--under)">Wikipedia pageviews</tspan>, each scaled to its own maximum,
      ${e.weeks[0]} to ${e.weeks[n - 1]}</text></svg>`;
}

// --- wiring -----------------------------------------------------------------------------
function init() {
  const c = DATA.coverage;
  el("kpis").innerHTML = [
    [fmt(c.titles), "titles in the model"],
    [(100 * c.matched / c.titles).toFixed(1) + "%", "matched to an IMDb id"],
    [fmt(Math.round(c.hours / 1e9)) + "B", "reported hours"],
    [fmt(c.weeks), "Top 10 weeks"],
    [fmt(c.shown), `titles ranked below (≥ ${fmt(c.hours_floor / 1e6)}M hours)`],
  ].map(([v, k]) => `<div class="kpi"><b>${v}</b><span>${k}</span></div>`).join("");
  el("floorNote").textContent = fmt(c.hours_floor / 1e6) + "M";
  el("built").textContent = `Built ${DATA.generated} from the project's own star schema. `
    + `Every figure on this page is reproducible with python -m src.dashboard.`;
  el("period").innerHTML = `<option value="">All six half-years</option>` +
    DATA.periods.map((p, i) => `<option value="${i}">${p.label} (${p.start} to ${p.end})</option>`).join("");
  el("genre").innerHTML = `<option value="">Every genre</option>` +
    DATA.genres.map((g, i) => `<option value="${i}">${g}</option>`).join("");
  ["period", "genre", "kind", "chart", "q"].forEach(id =>
    el(id).addEventListener(id === "q" ? "input" : "change", draw));
  document.querySelectorAll("th[data-key]").forEach(th => th.addEventListener("click", () => {
    const key = th.dataset.key === "0" ? 0 : (isNaN(+th.dataset.key) ? th.dataset.key : +th.dataset.key);
    if (key === sortKey) sortDir = -sortDir; else { sortKey = key; sortDir = key === 0 ? 1 : -1; }
    document.querySelectorAll("th[data-key]").forEach(o => o.removeAttribute("aria-sort"));
    th.setAttribute("aria-sort", sortDir === 1 ? "ascending" : "descending");
    draw();
  }));
  hero(); genreChart(); coefChart(); lagChart(); exampleChart(); draw();
}
init();
</script>
</html>
"""


def build(out=OUT):
    con = duckdb.connect(str(model.MODEL_DB), read_only=True)
    data = collect(con)
    out.parent.mkdir(parents=True, exist_ok=True)
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    out.write_text(html, encoding="utf-8")
    return data, out


def main():
    data, out = build()
    size = out.stat().st_size
    print(f"wrote {out} ({size / 1024:.0f} KB)")
    print(f"  {data['coverage']['shown']:,} titles in the table, "
          f"{len(data['genres'])} genres, {len(data['genre_delivery'])} genre rows")
    print(f"  lead/lag on {data['lead_lag']['titles']} titles; example series "
          f"{data['lead_lag']['example']['title']}")


if __name__ == "__main__":
    main()
