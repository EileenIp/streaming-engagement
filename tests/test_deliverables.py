"""Phase 5: the deliverables say who wrote what, and carry the run's real numbers.

The interpretation and the recommendation were drafted by the agent at Eileen's request.
That has to stay visible: a note like this is exactly the kind of thing that gets lost in
a later edit, and losing it turns an honest project into a misleading one.
"""
from __future__ import annotations

import json

import duckdb
import pytest

from src import config, model

REPORT = config.ROOT / "deliverables" / "streaming-engagement-report.md"
DECK_SCRIPT = config.ROOT / "scripts" / "build_deck.js"
DECK_DATA = config.ROOT / "deliverables" / "deck-data.json"
DASHBOARD = config.ROOT / "dashboard" / "index.html"


def test_the_report_says_who_drafted_the_reserved_sections():
    text = REPORT.read_text(encoding="utf-8")
    assert "Authorship, stated plainly" in text
    assert "drafted by the agent" in text
    assert "defend them as your own" in text
    # The sections themselves must be written, not still marked as reserved.
    assert "[RESERVED FOR EILEEN]" not in text
    for heading in ["## What didn't work", "## Recommendation", "## Limitations"]:
        assert heading in text, heading


def test_the_deck_carries_the_same_authorship_note():
    text = DECK_SCRIPT.read_text(encoding="utf-8")
    assert "Interpretation drafted by the agent" in text
    assert "the checkpoint decisions are Eileen's" in text


def test_the_report_quotes_figures_the_run_actually_produced():
    text = REPORT.read_text(encoding="utf-8")
    for figure in ["99.5%", "92.2%", "98.7%", "1.65", "0.44", "0.06", "47 of 63", "88"]:
        assert figure in text, figure
    # A claim that outlived its evidence is worse than no claim.
    assert "Google Trends" in text and "429" in text


@pytest.mark.skipif(not DECK_DATA.exists() or not model.MODEL_DB.exists(),
                    reason="deck data or model not built")
def test_the_deck_numbers_come_from_the_model_not_from_a_slide():
    data = json.loads(DECK_DATA.read_text(encoding="utf-8"))
    con = duckdb.connect(str(model.MODEL_DB), read_only=True)
    titles, matched = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE matched) FROM dim_title").fetchone()
    assert data["titles"] == titles
    assert data["matched"] == matched
    assert data["engagement_rows"] == con.execute(
        "SELECT count(*) FROM fact_engagement_halfyear").fetchone()[0]
    assert data["top10_rows"] == con.execute(
        "SELECT count(*) FROM fact_top10_weekly").fetchone()[0]


@pytest.mark.skipif(not DASHBOARD.exists(), reason="dashboard not built")
def test_the_dashboard_is_self_contained_and_publishable():
    html = DASHBOARD.read_text(encoding="utf-8")
    # No CDN, no fetch: it has to work from a file:// path and from Pages alike.
    for forbidden in ["<script src=", "cdn.", "fetch(", "https://unpkg", "googleapis"]:
        assert forbidden not in html, forbidden
    # IMDb's licence is why per-title ratings and votes are not in here.
    assert "non-commercial" in html
    assert '"imdb_rating"' not in html and '"imdb_votes"' not in html
    data = json.loads(html.split("const DATA = ", 1)[1].split(";\n", 1)[0])
    assert data["coverage"]["shown"] > 1000
    assert all(g["delivery"] is not None for g in data["genre_delivery"])
    assert DASHBOARD.stat().st_size < 1_500_000, "a page this size stops being a link you send"
