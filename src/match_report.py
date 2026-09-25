"""The Checkpoint 2 match report: rates per source pair, what each rung bought,
score distribution, threshold sensitivity, and the full near-miss list.

Writes:
  data/validation/match-report.md      the report Eileen reads
  data/validation/near-misses.csv      every sub-threshold pair, worst to best
  data/processed/match_*.parquet       the matches, so later phases need not rematch

Run: python -m src.match_report
"""
from __future__ import annotations

import pandas as pd

from src import config, label_pairs, match, match_imdb, match_netflix

VALIDATION = config.ROOT / "data" / "validation"
THRESHOLDS = [80, 85, 88, 90, 92, 95, 98]


def fmt(n):
    return f"{n:,}"


def pct(x):
    return f"{x:.1%}"


def build(netflix: pd.DataFrame, imdb: pd.DataFrame, index_stats: dict) -> str:
    n_stats = match.rate(netflix)
    lines = ["# Match report — Phase 2", "",
             f"Built {pd.Timestamp.now():%Y-%m-%d} at fuzzy threshold **{match.FUZZY_THRESHOLD:.0f}**, "
             "which is the value Checkpoint 2 exists to set. Every figure here comes from "
             "`python -m src.match_report`.", "",
             "## The two joins", "",
             "| join | rows | matched | rate |", "|---|---|---|---|",
             f"| Netflix Top 10 → engagement report (same half) | {fmt(n_stats['rows'])} | "
             f"{fmt(n_stats['matched'])} | {pct(n_stats['match_rate'])} |",
             f"| Netflix engagement titles → IMDb id | {fmt(len(imdb))} | "
             f"{fmt(int(imdb.matched.sum()))} | {pct(imdb.matched.mean())} |", "",
             "Exact string matching with no normalisation at all managed 57.0% and 54.0% on the "
             "first join (Phase 0). The difference is what the normalisation ladder is worth.", "",
             "## Netflix Top 10 → engagement report", "",
             "| rung | pairs |", "|---|---|"]
    for stage in match.STAGES + ["near_miss", "unmatched"]:
        lines.append(f"| {stage} | {fmt(n_stats[stage])} |")
    lines += ["", "By period and kind:", "",
              "| period | matched | of | rate |", "|---|---|---|---|"]
    for period, g in netflix.groupby(netflix.block.str[0]):
        lines.append(f"| {period} | {fmt(int(g.matched.sum()))} | {fmt(len(g))} | {pct(g.matched.mean())} |")
    for kind, g in netflix.groupby(netflix.block.str[1]):
        lines.append(f"| all periods, {kind} | {fmt(int(g.matched.sum()))} | {fmt(len(g))} | {pct(g.matched.mean())} |")

    lines += ["", "## Netflix → IMDb", "",
              f"The IMDb index holds {fmt(index_stats['keys'])} names for "
              f"{fmt(index_stats['titles'])} candidate titles, including alternate titles.", "",
              "| rung | matched | share of all entities |", "|---|---|---|"]
    for rung in match_imdb.RUNGS:
        n = int((imdb.rung == rung).sum())
        lines.append(f"| {rung} | {fmt(n)} | {pct(n / len(imdb))} |")
    lines.append(f"| fuzzy (≥ {match.FUZZY_THRESHOLD:.0f}) | {fmt(int((imdb.stage == 'imdb_fuzzy').sum()))} | "
                 f"{pct((imdb.stage == 'imdb_fuzzy').mean())} |")
    lines.append(f"| near miss (best score below threshold) | {fmt(int((imdb.stage == 'near_miss').sum()))} | "
                 f"{pct((imdb.stage == 'near_miss').mean())} |")
    lines.append(f"| no candidate at all | {fmt(int((imdb.stage == 'unmatched').sum()))} | "
                 f"{pct((imdb.stage == 'unmatched').mean())} |")

    hours = imdb.groupby("matched").hours_viewed.sum()
    lines += ["", f"**{pct(hours.get(True, 0) / hours.sum())} of all reported viewing hours** sit on a title "
                  "that reached an IMDb id — the unmatched residue is mostly small titles.", "",
              "| kind | matched | of | rate |", "|---|---|---|---|"]
    for kind, g in imdb.groupby("kind"):
        lines.append(f"| {kind} | {fmt(int(g.matched.sum()))} | {fmt(len(g))} | {pct(g.matched.mean())} |")

    ties = imdb[imdb.matched].tie_break.value_counts()
    votes = imdb[imdb.tie_break == "votes"]
    close = votes[(votes.runner_up_votes.fillna(0) >= 100) &
                  (votes.runner_up_votes.fillna(0) > 0.10 * votes.votes.clip(lower=1))]
    lines += ["", "### Where a name hit more than one IMDb id", "",
              "One name can match several ids. They are resolved in a fixed order — a matching "
              "year, a year within one, then vote count — and the last of those is a judgement, "
              "not a fact.", "",
              "| tie-break | entities |", "|---|---|"]
    for k, v in ties.items():
        lines.append(f"| {k} | {fmt(int(v))} |")
    lines += ["",
              f"Of the {fmt(len(votes))} resolved by votes, {fmt(int((votes.runner_up_votes.fillna(0) < 100).sum()))} "
              f"had a runner-up with under 100 votes — those are not really contests. "
              f"**{fmt(len(close))} are genuinely close** (runner-up within 10% and at least 100 votes); "
              "they are the ones worth a look:", "",
              "| Netflix title | chosen | votes | runner-up votes |", "|---|---|---|---|"]
    for r in close.sort_values("hours_viewed", ascending=False).head(12).itertuples():
        lines.append(f"| {r.example_title} | {r.tconst} ({'' if pd.isna(r.imdb_year) else int(r.imdb_year)}) | "
                     f"{fmt(int(r.votes))} | {fmt(int(r.runner_up_votes))} |")

    film = imdb[(imdb.kind == "film") & imdb.tconst.notna()]
    dup = film.groupby("tconst").filter(lambda g: len(g) > 1)
    tv_seasons = imdb[(imdb.kind == "tv") & imdb.seasons_present.notna()]
    lines += ["", "### Two checks on the result", "",
              f"* **Films sharing an id:** {fmt(dup.tconst.nunique())} ids carry more than one film "
              f"entity ({fmt(len(dup))} entities). Most are the same film published twice by Netflix under "
              "different names — `The Godfather` and `The Godfather (1972)`, `Vertigo // 버티고` and "
              "`Vertigo (1958)` — which is the join doing its job. The rest are wrong, and they are the "
              "reason a Phase 3 fact table must be keyed on the resolved id rather than the published name.",
              f"* **Seasons IMDb does not list:** {fmt(int((~tv_seasons.seasons_present.astype(bool)).sum()))} "
              f"of {fmt(len(tv_seasons))} matched TV entities report a season number IMDb has no episodes for. "
              "That is either a wrong match or IMDb being behind, and it is a cheap ongoing check on match quality.", ""]

    fuzzy = pd.concat([netflix[netflix.score.notna() & (netflix.stage.isin(["fuzzy", "near_miss"]))]
                       .assign(join_name="top10_to_engagement"),
                       imdb[imdb.score.notna() & (imdb.stage.isin(["imdb_fuzzy", "near_miss"]))]
                       .assign(join_name="engagement_to_imdb")], ignore_index=True)
    lines += ["## The fuzzy rung, and the threshold", "",
              f"{fmt(len(fuzzy))} pairs reached the fuzzy rung. Their best-score distribution:", "",
              "| score band | pairs |", "|---|---|"]
    bands = [(98, 101), (95, 98), (92, 95), (90, 92), (85, 90), (80, 85), (70, 80), (0, 70)]
    for low, high in bands:
        n = int(((fuzzy.score >= low) & (fuzzy.score < high)).sum())
        lines.append(f"| {low}–{high if high <= 100 else 100} | {fmt(n)} |")
    lines += ["", "What each threshold would accept:", "",
              "| threshold | fuzzy pairs accepted | left as near misses |", "|---|---|---|"]
    for t in THRESHOLDS:
        acc = int((fuzzy.score >= t).sum())
        lines.append(f"| {t} | {fmt(acc)} | {fmt(len(fuzzy) - acc)} |")
    lines += ["",
              "The full list is in `near-misses.csv`, worst score first. The pairs just below the "
              "current threshold are the ones to read: they decide whether the threshold moves.", ""]
    worst = fuzzy[fuzzy.stage.isin(["near_miss"])].sort_values("score", ascending=False)
    lines += ["### The 20 highest-scoring pairs the threshold currently rejects", "",
              "| score | left | right |", "|---|---|---|"]
    for r in worst.head(20).itertuples():
        left = r.left_raw if isinstance(r.left_raw, str) else r.example_title
        right = r.right_raw if isinstance(r.right_raw, str) else r.imdb_key
        lines.append(f"| {r.score:.1f} | {left} | {right} |")
    lines += ["", "---", "", "## What Checkpoint 2 has to decide", "",
              "1. **The fuzzy threshold**, from the table and the near-miss list above. Record it with "
              "three example pairs it correctly rejects — that is the interview answer.",
              "2. **What happens to unmatched titles.** Dropping them biases the result towards titles "
              "that resolve (the long tail vanishes); keeping them breaks the joins. Either is defensible, "
              "stated plainly. The unmatched residue is "
              f"{pct(1 - imdb.matched.mean())} of entities but only {pct(1 - hours.get(True, 0) / hours.sum())} of hours.",
              "3. **Whether the weak rungs stay.** `qualifier_dropped` merges `Shameless (U.S.)` with "
              "`Shameless`; `prefix` matches `ONE PIECE: East Blue` to the series and gives up knowing "
              "which arc. Their counts are above, and either can be switched off on its own.", ""]
    return "\n".join(lines) + "\n"


def main():
    netflix = match_netflix.run()
    imdb, index_stats = match_imdb.run()
    VALIDATION.mkdir(parents=True, exist_ok=True)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    netflix.to_parquet(config.PROCESSED / "match_netflix.parquet")
    imdb.to_parquet(config.PROCESSED / "match_imdb.parquet")

    near = pd.concat([
        netflix[netflix.stage == "near_miss"].assign(join_name="top10_to_engagement")
            .rename(columns={"left_raw": "left", "right_raw": "right"})[
                ["join_name", "score", "left", "right", "other_candidates"]],
        imdb[imdb.stage == "near_miss"].assign(join_name="engagement_to_imdb")
            .rename(columns={"example_title": "left", "imdb_key": "right"})[
                ["join_name", "score", "left", "right", "other_candidates"]],
    ], ignore_index=True).sort_values("score", ascending=False)
    near.to_csv(VALIDATION / "near-misses.csv", index=False, encoding="utf-8")

    # The 30-pair fixture is sampled from the same run, so the pairs Eileen judges are
    # the pairs the threshold decision is actually about.
    for_labels = pd.concat([
        netflix[netflix.score.notna()].assign(
            left=lambda d: d.left_raw, right=lambda d: d.right_raw,
            left_source="Netflix Top 10", right_source="Netflix engagement report"),
        imdb[imdb.score.notna()].assign(
            left=lambda d: d.example_title, right=lambda d: d.imdb_key,
            left_source="Netflix engagement report", right_source="IMDb"),
    ], ignore_index=True).dropna(subset=["left", "right"])
    pairs = label_pairs.sample_pairs(for_labels)
    label_pairs.build(pairs)

    report = build(netflix, imdb, index_stats)
    (VALIDATION / "match-report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"wrote {VALIDATION / 'match-report.md'} and {len(near):,} rows to near-misses.csv")


if __name__ == "__main__":
    main()
