"""Entity resolution: deterministic matching first, fuzzy matching only on the residue.

The ladder, in order, and nothing skips a rung:

  1. exact         normalised base name and season agree
  2. alternate     an alternate-language name from either side agrees, same season
  3. year          names agree and one side's disambiguating year matches the other's
  4. season_equiv  names agree and the two season markers mean the same first-and-only
                   season written two ways - 'Season 1', 'Limited Series', or nothing
                   at all. Netflix itself is inconsistent here: the Top 10 file calls
                   Sean Combs: The Reckoning 'Season 1' and the engagement report calls
                   it 'Limited Series'. Only used when the name matches exactly one
                   candidate in the block, so it can never pick between seasons.
  5. fuzzy         best token-sort score within the same block, above a threshold

Blocking matters: comparing every title to every other title is 12k x 16k per
period, and across IMDb it is millions. A fuzzy comparison is only ever made
inside a block where the season (and, for films, nothing) already agrees.

Every fuzzy pair is recorded with its score whether it passes or not, because
the sub-threshold list is what the threshold decision gets made from.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from rapidfuzz import fuzz, process

from src import normalise

# Set at Checkpoint 2 by Eileen on 2026-09-25 at 88, from reading the near-miss list by
# band, and moved to 87 on 2026-10-04 once she had hand-labelled 30 pairs: at 87 the
# pipeline disagrees with her on 3 of the 29 she judged, at 88 on 4. The pairs, the
# disagreements and what each threshold would cost are in
# data/validation/checkpoint2-threshold.md.
FUZZY_THRESHOLD = 87.0
STAGES = ["exact", "alternate", "year", "season_equiv", "fuzzy"]

# A first-and-only season, written three ways. Treated as interchangeable at the
# season_equiv rung, and never anywhere else.
FIRST_SEASON_FORMS = [(None, None, None, None), ("season", 1, None, None), ("limited", None, None, None)]


@dataclass
class Candidate:
    """One side of a match: a title as published, plus what parsing made of it."""
    row_id: int
    raw: str
    block: tuple
    parsed: normalise.ParsedTitle
    payload: dict = field(default_factory=dict)

    @property
    def keys(self):
        return self.parsed.alternate_keys


def candidates(df, raw_column, block_columns, payload_columns=()) -> list[Candidate]:
    out = []
    for row in df.itertuples():
        raw = getattr(row, raw_column)
        parsed = normalise.parse(raw)
        out.append(Candidate(
            row_id=row.Index,
            raw=raw,
            block=tuple(getattr(row, c) for c in block_columns) + (parsed.season_key,),
            parsed=parsed,
            payload={c: getattr(row, c) for c in payload_columns},
        ))
    return out


def _index(cands, key_func):
    index = {}
    for c in cands:
        for key in key_func(c):
            index.setdefault((c.block, key), []).append(c)
    return index


def match(left: list[Candidate], right: list[Candidate], threshold=FUZZY_THRESHOLD,
          fuzzy_limit=3, scorer=fuzz.token_sort_ratio) -> pd.DataFrame:
    """Run the ladder. One row per left candidate, matched or not, with how it matched."""
    primary = _index(right, lambda c: [c.parsed.key])
    alternate = _index(right, lambda c: c.keys)
    # Base-name index that ignores the season, for the season_equiv rung only.
    unseasoned = {}
    for r in right:
        for key in r.keys:
            unseasoned.setdefault((r.block[:-1], key), []).append(r)
    rows, residue = [], []

    for c in left:
        hit = primary.get((c.block, c.parsed.key))
        stage = "exact"
        if not hit:
            for key in c.keys:
                hit = alternate.get((c.block, key))
                if hit:
                    stage = "alternate"
                    break
        if hit and len(hit) > 1 and c.parsed.year is not None:
            # Same name, same season, more than one candidate: the (2011) in
            # 'Suits (2011)' is there to tell them apart.
            by_year = [h for h in hit if h.parsed.year == c.parsed.year]
            if by_year:
                hit, stage = by_year, "year"
        if not hit and c.parsed.season_key in FIRST_SEASON_FORMS:
            for key in c.keys:
                pool = [r for r in unseasoned.get((c.block[:-1], key), [])
                        if r.parsed.season_key in FIRST_SEASON_FORMS]
                # Exactly one candidate, or this rung would be choosing between seasons.
                if len(pool) == 1:
                    hit, stage = pool, "season_equiv"
                    break
        if hit:
            rows.append(_row(c, hit[0], stage, 100.0, len(hit)))
        else:
            residue.append(c)

    # Fuzzy, blocked. Candidates are only ever the right-hand titles in the same block.
    by_block = {}
    for r in right:
        by_block.setdefault(r.block, []).append(r)
    for c in residue:
        pool = by_block.get(c.block, [])
        if not pool:
            rows.append(_row(c, None, "unmatched", None, 0))
            continue
        choices = {i: r.parsed.key for i, r in enumerate(pool)}
        best = process.extract(c.parsed.key, choices, scorer=scorer, limit=fuzzy_limit)
        if not best:
            rows.append(_row(c, None, "unmatched", None, 0))
            continue
        # process.extract over a dict returns (choice, score, dict_key) per hit.
        _, score, idx = best[0]
        winner = pool[idx]
        runner_up = best[1][1] if len(best) > 1 else None
        rows.append(_row(c, winner, "fuzzy" if score >= threshold else "near_miss", score, len(pool),
                         runner_up=runner_up,
                         alternatives="; ".join(f"{pool[i].raw} ({s:.0f})" for _, s, i in best[1:])))
    return pd.DataFrame(rows)


def _row(left: Candidate, right: Candidate | None, stage, score, n_candidates,
         runner_up=None, alternatives=""):
    row = {
        "stage": stage,
        "matched": stage in STAGES,
        "left_row": left.row_id,
        "left_raw": left.raw,
        "left_key": left.parsed.key,
        "season_kind": left.parsed.season_kind,
        "season_number": left.parsed.season_number,
        "block": left.block[:-1],
        "score": score,
        "candidates_in_block": n_candidates,
        "runner_up_score": runner_up,
        "other_candidates": alternatives,
    }
    row.update({"right_row": right.row_id if right else None,
                "right_raw": right.raw if right else None,
                "right_key": right.parsed.key if right else None})
    row.update({f"left_{k}": v for k, v in left.payload.items()})
    row.update({f"right_{k}": v for k, v in (right.payload.items() if right else [])})
    return row


def rate(matched: pd.DataFrame) -> dict:
    counts = matched.stage.value_counts().to_dict()
    n = len(matched)
    return {"rows": n, "matched": int(matched.matched.sum()),
            "match_rate": matched.matched.mean() if n else 0.0,
            **{s: counts.get(s, 0) for s in STAGES + ["near_miss", "unmatched"]}}
