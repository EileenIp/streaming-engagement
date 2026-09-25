"""Build the 30-pair labelling tool: genuine ground truth for the match tests.

The pairs are sampled across score bands, and the page shows Eileen the two
titles and nothing else - no score, no stage, no hint that the pipeline accepted
or rejected the pair. A fixture built from pairs she labelled while knowing the
answer would only confirm the threshold that produced it.

Sampling is seeded, so the same run produces the same 30 pairs.

Run: python -m src.label_pairs
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src import config

TARGET = 30
BANDS = [(97, 101), (93, 97), (90, 93), (85, 90), (78, 85), (0, 78)]
PER_BAND = 5
SEED = 20260925

OUT_JSON = config.ROOT / "data" / "validation" / "label-pairs.json"
OUT_HTML = config.ROOT / "label.html"

PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Streaming Engagement — title match audit</title>
<style>
  :root { color-scheme: light dark; --ink:#16181d; --paper:#fbfbfa; --line:#d8d6d1;
          --card:#fff; --muted:#6b6f76; --accent:#2f5d8a; }
  @media (prefers-color-scheme: dark) {
    :root { --ink:#e8e6e3; --paper:#17191c; --line:#32363c; --card:#1e2125;
            --muted:#9aa0a8; --accent:#7fa9d4; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink);
         font:15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  header { position:sticky; top:0; background:var(--paper); border-bottom:1px solid var(--line);
           padding:14px 20px; z-index:2; }
  h1 { font-size:15px; margin:0 0 4px; font-weight:600; }
  .sub { color:var(--muted); font-size:13px; }
  .bar { height:4px; background:var(--line); border-radius:2px; margin-top:10px; overflow:hidden; }
  .bar span { display:block; height:100%; background:var(--accent); width:0; transition:width .18s; }
  main { max-width:720px; margin:0 auto; padding:22px 20px 140px; }
  .pair { background:var(--card); border:1px solid var(--line); border-radius:10px;
          padding:16px 18px; margin-bottom:16px; }
  .n { color:var(--muted); font-size:12px; letter-spacing:.04em; text-transform:uppercase; }
  .t { font-size:16px; margin:8px 0; word-wrap:break-word; }
  .t b { font-weight:600; }
  .src { color:var(--muted); font-size:12px; }
  .btns { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
  button { font:inherit; padding:7px 13px; border:1px solid var(--line); border-radius:7px;
           background:transparent; color:var(--ink); cursor:pointer; }
  button[aria-pressed="true"] { background:var(--accent); border-color:var(--accent); color:#fff; }
  footer { position:fixed; bottom:0; left:0; right:0; background:var(--paper);
           border-top:1px solid var(--line); padding:12px 20px; display:flex; gap:10px;
           align-items:center; flex-wrap:wrap; }
  .note { color:var(--muted); font-size:12px; max-width:720px; margin:0 auto 18px; }
  textarea { width:100%; height:120px; font:12px/1.4 ui-monospace, monospace; margin-top:10px;
             background:var(--card); color:var(--ink); border:1px solid var(--line); border-radius:7px; }
</style>
<header>
  <h1>Do these two names mean the same title?</h1>
  <div class="sub"><span id="done">0</span> of __N__ answered</div>
  <div class="bar"><span id="fill"></span></div>
</header>
<main>
  <p class="note">One pair at a time: the left name comes from one Netflix or IMDb source,
  the right from another. Answer <b>same</b> if they are the same title (the same season of
  the same show, or the same film), <b>different</b> if they are not, and <b>can't tell</b>
  if you would need to look it up. Nothing here tells you what the pipeline decided —
  that is the point. Answers save as you go; export at any time.</p>
  <div id="list"></div>
  <textarea id="out" readonly></textarea>
</main>
<footer>
  <button onclick="save()">Download answers</button>
  <button onclick="copy()">Copy to clipboard</button>
  <span class="src" id="status"></span>
</footer>
<script>
const PAIRS = __PAIRS__;
const KEY = 'streaming-engagement-pair-labels';
let V = JSON.parse(localStorage.getItem(KEY) || '{}');

function draw() {
  document.getElementById('list').innerHTML = PAIRS.map((p, i) => `
    <div class="pair">
      <div class="n">Pair ${i + 1}</div>
      <div class="t"><b>${esc(p.left)}</b></div>
      <div class="t"><b>${esc(p.right)}</b></div>
      <div class="src">${esc(p.left_source)} &nbsp;vs&nbsp; ${esc(p.right_source)}</div>
      <div class="btns">
        ${['same', 'different', "can't tell"].map(v => `
          <button aria-pressed="${V[p.id] === v}" onclick="pick('${p.id}', '${v}')">${v}</button>`).join('')}
      </div>
    </div>`).join('');
  const n = Object.keys(V).length;
  document.getElementById('done').textContent = n;
  document.getElementById('fill').style.width = (100 * n / PAIRS.length) + '%';
  document.getElementById('out').value = payload();
}
function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function pick(id, v) { V[id] = v; localStorage.setItem(KEY, JSON.stringify(V)); draw(); }
function payload() { return JSON.stringify({version: 1, labels: V}, null, 1); }
function save() {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([payload()], {type: 'application/json'}));
  a.download = 'pair-labels.json';
  a.click();
  document.getElementById('status').textContent = 'saved pair-labels.json';
}
function copy() {
  navigator.clipboard.writeText(payload()).then(
    () => document.getElementById('status').textContent = 'copied - paste it into a file',
    () => document.getElementById('status').textContent = 'copy blocked - select the box and copy by hand');
}
draw();
</script>
</html>
"""


def sample_pairs(candidates: pd.DataFrame, target=TARGET, seed=SEED) -> pd.DataFrame:
    """Stratify by score band so the fixture covers both ends, not just the easy middle."""
    picks = []
    for low, high in BANDS:
        band = candidates[(candidates.score >= low) & (candidates.score < high)]
        if band.empty:
            continue
        picks.append(band.sample(min(PER_BAND, len(band)), random_state=seed))
    out = pd.concat(picks).drop_duplicates(subset=["left", "right"])
    if len(out) < target:  # top up from whatever is left, so the fixture still reaches 30
        rest = candidates.drop(out.index, errors="ignore")
        if not rest.empty:
            out = pd.concat([out, rest.sample(min(target - len(out), len(rest)), random_state=seed)])
    return out.head(target).sample(frac=1, random_state=seed).reset_index(drop=True)


def build(pairs: pd.DataFrame, out_json: Path = OUT_JSON, out_html: Path = OUT_HTML):
    records = []
    for i, r in pairs.iterrows():
        records.append({"id": f"p{i:02d}", "left": r.left, "right": r.right,
                        "left_source": r.left_source, "right_source": r.right_source,
                        # kept in the JSON for scoring later, never rendered on the page
                        "score": None if pd.isna(r.score) else round(float(r.score), 1),
                        "stage": r.stage})
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"seed": SEED, "pairs": records}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    shown = [{k: v for k, v in rec.items() if k not in ("score", "stage")} for rec in records]
    out_html.write_text(PAGE.replace("__PAIRS__", json.dumps(shown, ensure_ascii=False))
                            .replace("__N__", str(len(shown))), encoding="utf-8")
    return records
