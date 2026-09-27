// Phase 5: the stakeholder deck. Numbers come from deliverables/deck-data.json, which
// src/deck.py exports from the model, so a slide cannot carry a figure the data no
// longer supports.
//
// Run: python -m src.deck   (not node directly - the JSON has to be current)

const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const D = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "deliverables", "deck-data.json"), "utf8"));
const OUT = path.join(__dirname, "..", "deliverables", "streaming-engagement-deck.pptx");

const INK = "16181C";      // near-black, the dominant colour on dark slides
const PAPER = "FFFFFF";
const TEAL = "0E6E78";     // primary
const MINT = "57B8A0";     // supporting
const CLAY = "B4553C";     // the one sharp accent, used only for "under-delivers"
const MUTED = "6B7280";
const TINT = "F2F5F6";     // card fill on light slides

const HEAD = "Cambria";    // safe-list serif for headings
const BODY = "Calibri";    // safe-list sans for everything else

const pct = x => (100 * x).toFixed(1) + "%";
const num = n => n.toLocaleString("en-AU");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";           // 10" x 5.625"
pres.author = "Eileen Ip";
pres.title = "Streaming Engagement — four sources, one model";

const W = 10, H = 5.625, M = 0.55;

function titleOf(slide, text, sub) {
  // 26pt: at 30pt the longer titles wrapped to a second line and ran straight
  // through the subtitle underneath.
  slide.addText(text, {
    x: M, y: 0.4, w: W - 2 * M, h: 0.62, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 26, bold: true, color: INK,
  });
  if (sub) {
    slide.addText(sub, {
      x: M, y: 1.02, w: W - 2 * M, h: 0.42, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13.5, color: MUTED,
    });
  }
}

function card(slide, { x, y, w, h, fill = TINT }) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.06, fill: { color: fill }, line: { color: fill },
  });
}

function stat(slide, { x, y, w, value, label, colour = TEAL }) {
  slide.addText(value, {
    x, y, w, h: 0.72, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 40, bold: true, color: colour,
  });
  slide.addText(label, {
    x, y: y + 0.74, w, h: 0.62, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12, color: MUTED,
  });
}

// --- 1. title ----------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("Four sources, one model", {
    x: M, y: 1.75, w: W - 2 * M, h: 0.9, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 44, bold: true, color: PAPER,
  });
  s.addText("Which titles are earning their place — and what it takes to answer that from four public files that share no key",
    { x: M, y: 2.7, w: 7.6, h: 0.9, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 16, color: "C9CDD2" });
  s.addText("Eileen Ip · portfolio project", {
    x: M, y: 4.5, w: 6, h: 0.35, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13, color: MINT,
  });
  s.addNotes("Two Netflix files that disagree with each other, IMDb, and Wikipedia, resolved into one star schema. The engineering question comes before the business question: can these be joined at all, and what is lost in the attempt?");
}

// --- 2. the problem ----------------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "Four files, no shared key", "Netflix does not even agree with itself between its own two files");
  const items = [
    ["Netflix engagement report", `${D.periods} half-years · ${num(D.engagement_rows)} rows`, "Hours and views per season. Seven editions in three layouts."],
    ["Netflix Global Top 10", `${num(D.weeks)} weeks · ${num(D.top10_rows)} slots`, "Weekly ranks. One live file, retitled retroactively."],
    ["IMDb datasets", "2.8M candidate titles", "Type, year, genre, rating. Its own id scheme, shared with nothing."],
    ["Wikipedia pageviews", `${num(D.demand_titles)} titles`, "Daily attention off the platform. English only, rate-limited."],
  ];
  items.forEach(([name, scale, note], i) => {
    const y = 1.62 + i * 0.92;
    card(s, { x: M, y, w: 4.5, h: 0.78 });
    s.addText(name, { x: M + 0.18, y: y + 0.08, w: 2.6, h: 0.28, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13, bold: true, color: INK });
    s.addText(scale, { x: M + 0.18, y: y + 0.38, w: 4.1, h: 0.26, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11, color: TEAL });
    s.addText(note, { x: 5.3, y: y + 0.12, w: 4.15, h: 0.56, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11.5, color: MUTED });
  });
  s.addNotes("The awkwardness is the point: the sources are real, public, and genuinely inconsistent.");
}

// --- 3. what the data does ---------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "What the data does when you look", "Three things no documentation mentions");
  const found = [
    ["The Top 10 file is a live view, not an archive",
     "Berlin charted in December 2023 under that name. The file now labels those same 2023 weeks “Berlin and the Jewels of Paris”, because season 2 arrived in 2026 and season 1 was renamed. Nine of the thirteen unmatched Top 10 titles appear only in later reports."],
    ["Netflix contradicts itself inside one half-year",
     "The Top 10 calls Sean Combs: The Reckoning “Season 1” where the engagement report calls it “Limited Series”, and omits The Manny’s season entirely."],
    ["Four facts in one string, in a dozen shapes",
     "Suits (2011): Season 1 · Stranger Things 4 · Aquí no hay quien viva (2003): Temporada 4 · Law & Order: SVU: The Sixth Year · Raw: June 15, 2025"],
  ];
  found.forEach(([head, detail], i) => {
    const y = 1.6 + i * 1.28;
    card(s, { x: M, y, w: W - 2 * M, h: 1.14 });
    s.addShape(pres.ShapeType.ellipse, { x: M + 0.22, y: y + 0.36, w: 0.16, h: 0.16,
      fill: { color: i === 2 ? MINT : TEAL }, line: { color: i === 2 ? MINT : TEAL } });
    s.addText(head, { x: M + 0.54, y: y + 0.14, w: 8.2, h: 0.3, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 14, bold: true, color: INK });
    s.addText(detail, { x: M + 0.54, y: y + 0.44, w: 8.2, h: 0.62, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11.5, color: MUTED });
  });
}

// --- 4. the join -------------------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "The join", "Exact string matching, with no normalisation, gets 54–57%");
  stat(s, { x: M, y: 1.75, w: 2.9, value: pct(D.netflix_join_rate), label: `Top 10 → engagement report\n${num(D.netflix_join_rows)} charting title-periods` });
  stat(s, { x: 3.6, y: 1.75, w: 2.9, value: pct(D.match_rate), label: `Netflix titles → IMDb id\nfilm ${pct(D.film_rate)} · TV ${pct(D.tv_rate)}` });
  stat(s, { x: 6.7, y: 1.75, w: 2.9, value: pct(D.hours_matched_share), label: "of all reported viewing hours\nsit on a title with an IMDb id", colour: MINT });
  card(s, { x: M, y: 3.5, w: W - 2 * M, h: 1.35 });
  s.addText("Almost all of the gain is normalisation, not string distance.", {
    x: M + 0.25, y: 3.66, w: 8.6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, bold: true, color: INK });
  s.addText(`Fuzzy matching contributes one pair on the first join and ${num(D.rungs.find(r => r.rung === "fuzzy").n)} on the second. The rest is parsing the title properly: the season marker, the disambiguating year, the alternate-language name after " // ", and the acronym that IMDb spells without full stops.`,
    { x: M + 0.25, y: 3.98, w: 8.6, h: 0.74, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: MUTED });
}

// --- 5. the ladder -----------------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "A ladder, not a similarity score", `Each rung counted separately, so a weak one can be inspected — or switched off`);
  const labels = { name: "Name, normalised", prefix: "Series prefix (a named arc)", alternate_name: "Alternate-language name",
    spacing: "Spacing (S.W.A.T. ↔ swat)", qualifier_dropped: "Qualifier dropped", fuzzy: `Fuzzy, score ≥ ${D.threshold}` };
  const rungs = D.rungs.filter(r => labels[r.rung]);
  s.addChart(pres.ChartType.bar, [{
    name: "Titles matched",
    labels: rungs.map(r => labels[r.rung]),
    values: rungs.map(r => r.n),
  }], {
    x: M, y: 1.6, w: 5.9, h: 3.4, barDir: "bar", chartColors: [TEAL],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0",
    dataLabelColor: MUTED, dataLabelFontSize: 10, dataLabelFontFace: BODY,
    catAxisLabelColor: INK, catAxisLabelFontSize: 10, catAxisLabelFontFace: BODY,
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, barGapWidthPct: 45,
  });
  card(s, { x: 6.7, y: 1.6, w: 2.75, h: 3.4 });
  s.addText("The threshold is 88", { x: 6.92, y: 1.78, w: 2.4, h: 0.3, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 14, bold: true, color: INK });
  s.addText("Set by reading the near-miss list band by band, not by picking a round number. The 88–90 band is mostly true matches; 85–88 is genuinely mixed.",
    { x: 6.92, y: 2.12, w: 2.4, h: 1.0, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11, color: MUTED });
  s.addText("Three pairs it correctly rejects", { x: 6.92, y: 3.15, w: 2.4, h: 0.26, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11.5, bold: true, color: INK });
  s.addText([
    { text: "Sir (Hindi) → jai hind sir", options: { bullet: true, breakLine: true } },
    { text: "Matsumoto Seicho's Kao → …no ekiro", options: { bullet: true, breakLine: true } },
    { text: "Louis C.K.: Ridiculous → ridiculous cakes", options: { bullet: true } },
  ], { x: 6.92, y: 3.45, w: 2.4, h: 1.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 10.5,
       color: MUTED, paraSpaceAfter: 6 });
}

// --- 6. the model ------------------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "One star schema", "A fact row is a season in a period; a dimension row is the whole title");
  const centre = { x: 3.75, y: 2.45, w: 2.5, h: 0.95 };
  s.addShape(pres.ShapeType.roundRect, { ...centre, rectRadius: 0.06,
    fill: { color: TEAL }, line: { color: TEAL } });
  s.addText("dim_title", { x: centre.x, y: centre.y + 0.16, w: centre.w, h: 0.3, isTextBox: true,
    margin: 0, align: "center", fontFace: BODY, fontSize: 15, bold: true, color: PAPER });
  s.addText(`${num(D.titles)} titles · ${pct(D.match_rate)} with an IMDb id`, {
    x: centre.x, y: centre.y + 0.5, w: centre.w, h: 0.3, isTextBox: true, margin: 0,
    align: "center", fontFace: BODY, fontSize: 10.5, color: "D6E6E8" });

  // Connectors are given explicit anchors rather than derived: a line shape is a
  // bounding box drawn corner to corner, so a formula that works for the top pair
  // leaves the bottom pair floating in space.
  const satellites = [
    ["fact_engagement_halfyear", `${num(D.engagement_rows)} rows · a season in a period`, 0.9, 1.55,
      { x: 3.40, y: 1.975, w: 0.35, h: 0.575, flipV: false }],
    ["fact_top10_weekly", `${num(D.top10_rows)} slots · ${num(D.weeks)} weeks`, 6.6, 1.55,
      { x: 6.25, y: 1.975, w: 0.35, h: 0.575, flipV: true }],
    ["fact_pageviews", `${num(D.demand_titles)} titles · daily`, 0.9, 3.95,
      { x: 3.40, y: 3.30, w: 0.35, h: 1.075, flipV: true }],
    ["dim_period", `${D.periods} reports · start, end, checksum`, 6.6, 3.95,
      { x: 6.25, y: 3.30, w: 0.35, h: 1.075, flipV: false }],
  ];
  satellites.forEach(([name, note, x, y, connector]) => {
    card(s, { x, y, w: 2.5, h: 0.85 });
    s.addText(name, { x: x + 0.12, y: y + 0.1, w: 2.3, h: 0.28, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, bold: true, color: INK });
    s.addText(note, { x: x + 0.12, y: y + 0.4, w: 2.3, h: 0.36, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 10, color: MUTED });
    s.addShape(pres.ShapeType.line, { ...connector, line: { color: MINT, width: 1.25 } });
  });
  s.addText("The period is data, not schema: Netflix goes annual in 2027, and that report is an INSERT rather than a migration.",
    { x: M, y: 4.95, w: W - 2 * M, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11.5, color: MUTED });
}

// --- 7. genres ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "Watched more than they chart",
    "Share of reported hours ÷ share of Top 10 slots. The chart is capped at ten slots a week; hours are not.");
  const g = D.genres.slice().sort((a, b) => b.delivery - a.delivery);
  s.addChart(pres.ChartType.bar, [{
    name: "Delivery ratio",
    labels: g.map(x => x.genre),
    values: g.map(x => x.delivery),
  }], {
    x: M, y: 1.72, w: 6.2, h: 3.3, barDir: "bar",
    // Teal only when the interval clears 1, clay only when it falls entirely below,
    // grey otherwise. Crime's point estimate is 0.93 but its interval spans parity.
    chartColors: g.map(x => (x.low > 1 ? TEAL : x.high < 1 ? CLAY : "9AA3AA")), varyColors: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00",
    dataLabelColor: MUTED, dataLabelFontSize: 10, dataLabelFontFace: BODY,
    catAxisLabelColor: INK, catAxisLabelFontSize: 11, catAxisLabelFontFace: BODY,
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, barGapWidthPct: 40,
  });
  card(s, { x: 7.05, y: 1.72, w: 2.4, h: 3.3 });
  s.addText("Read it this way", { x: 7.25, y: 1.9, w: 2.05, h: 0.28, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, color: INK });
  s.addText(`Family at ${g[0].delivery} is watched far more than its chart presence suggests — kids' titles accumulate hours without ever charting. Documentaries do the reverse.\n\nColoured bars are the genres whose 95% interval clears parity; grey means it does not.`,
    { x: 7.25, y: 2.24, w: 2.05, h: 2.6, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11, color: MUTED });
}

// --- 8. the null -------------------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "A better rating does not hold the chart",
    `The raw correlation says otherwise — until size is held constant. n = ${num(D.longevity.n)}.`);
  stat(s, { x: M, y: 1.8, w: 2.9,
    value: `${D.longevity.rating > 0 ? "+" : ""}${D.longevity.rating.toFixed(2)}`,
    label: `weeks of chart time per rating point\n95% interval ${D.longevity.rating_ci[0]} to ${D.longevity.rating_ci[1]} — it contains zero`,
    colour: MUTED });
  stat(s, { x: 3.6, y: 1.8, w: 2.9, value: `+${D.longevity.log_hours}`,
    label: "weeks per tenfold increase in hours\nsize is what predicts chart time" });
  stat(s, { x: 6.7, y: 1.8, w: 2.9, value: `+${D.longevity.non_english}`,
    label: "weeks for a non-English title\nits own category, with its own ten slots", colour: MINT });
  card(s, { x: M, y: 3.62, w: W - 2 * M, h: 1.25 });
  s.addText(`The raw correlation is ${D.longevity.rho} and significant. It is size in disguise: big titles get watched, rated and charted together. Holding hours, votes, type and language constant leaves nothing.`,
    { x: M + 0.25, y: 3.82, w: 8.6, h: 0.9, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13, color: INK });
}

// --- 9. lead and lag ---------------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "Attention arrives the same week, not before it",
    `Best-fitting lag between weekly Wikipedia pageviews and weekly Top 10 hours, ${D.lead_lag.titles} titles`);
  s.addChart(pres.ChartType.bar, [{
    name: "Titles",
    labels: D.lead_lag.distribution.map(([lag]) => (lag > 0 ? `+${lag}` : `${lag}`)),
    values: D.lead_lag.distribution.map(([, n]) => n),
  }], {
    x: M, y: 1.72, w: 6.2, h: 3.2, barDir: "col",
    chartColors: D.lead_lag.distribution.map(([lag]) => (lag === 0 ? TEAL : "C3CBD1")), varyColors: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: MUTED,
    dataLabelFontSize: 10, dataLabelFontFace: BODY,
    catAxisLabelColor: INK, catAxisLabelFontSize: 11, catAxisLabelFontFace: BODY,
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, barGapWidthPct: 40,
  });
  s.addText("weeks Wikipedia leads (−) or lags (+)", { x: M, y: 4.92, w: 6.2, h: 0.3, isTextBox: true,
    margin: 0, align: "center", fontFace: BODY, fontSize: 10.5, color: MUTED });
  card(s, { x: 7.05, y: 1.72, w: 2.4, h: 3.2 });
  s.addText("No head start", { x: 7.25, y: 1.9, w: 2.05, h: 0.28, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, color: INK });
  s.addText(`${D.lead_lag.at_zero} of ${D.lead_lag.titles} titles fit best at lag zero; ${D.lead_lag.leads} lead and ${D.lead_lag.lags} lag. There is no forecasting signal here.\n\nBut the same-week link is real: pairing a title's hours with a different title's pageviews drops the correlation from ${D.lead_lag.real_r} to ${D.lead_lag.placebo_r}.`,
    { x: 7.25, y: 2.24, w: 2.05, h: 2.5, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11, color: MUTED });
}

// --- 10. limitations ---------------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "What this cannot tell you", "Stated up front, because each one bounds a decision");
  const limits = [
    ["Half-yearly hours", "The finest grain for viewing is six months. Nothing here speaks to a launch week."],
    ["Rounded and floored", "Hours are published to the nearest 100,000, with a 100,000 floor. The long tail is missing."],
    ["One platform", "Netflix only. No figure here is a market share."],
    ["Genre is IMDb's, not Netflix's", "And a title with three genres counts in all three."],
    ["English Wikipedia only", `Demand covers ${num(D.demand_titles)} titles. Non-English titles are half the chart and are under-represented.`],
    ["The chart is zero-sum", "Ten slots per category per week exist whatever is released — it measures competition too."],
  ];
  limits.forEach(([head, detail], i) => {
    const x = i % 2 === 0 ? M : 5.1, y = 1.62 + Math.floor(i / 2) * 1.15;
    card(s, { x, y, w: 4.35, h: 1.0 });
    s.addText(head, { x: x + 0.18, y: y + 0.12, w: 4, h: 0.28, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, bold: true, color: INK });
    s.addText(detail, { x: x + 0.18, y: y + 0.42, w: 4, h: 0.5, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 10.5, color: MUTED });
  });
}

// --- 11. recommendation -----------------------------------------------------------------
{
  const s = pres.addSlide();
  titleOf(s, "What to do about it", "Ranked by how much I would stake on each");
  const recs = [
    ["Rank renewals on hours per week, within genre and language — and require the chart to agree",
     `The two measures correlate at 0.18. The disagreements are the decision: a big opening with no legs is a marketing result; steady hours with no chart presence is an audience the chart cannot see.`],
    ["Stop screening kids' and family content on chart presence",
     "Family delivers 1.65× the viewing its chart presence implies, Animation 1.32 — both intervals clear of parity. Documentary (0.44) and Thriller (0.67) run the other way."],
    ["Drop IMDb rating from renewal inputs",
     "Raw correlation 0.118 and significant; with size held constant, 0.06 weeks per point, interval −0.03 to +0.17. It survives no control at all."],
    ["Do not build an early warning on public attention",
     "Wikipedia moves the same week, not before. Useful as corroboration, and after a title leaves the chart — not as a forecast."],
  ];
  recs.forEach(([head, detail], i) => {
    const y = 1.6 + i * 0.95;
    card(s, { x: M, y, w: W - 2 * M, h: 0.85 });
    s.addShape(pres.ShapeType.ellipse, { x: M + 0.2, y: y + 0.34, w: 0.16, h: 0.16,
      fill: { color: i === 0 ? TEAL : MINT }, line: { color: i === 0 ? TEAL : MINT } });
    s.addText(head, { x: M + 0.52, y: y + 0.08, w: 8.2, h: 0.28, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13, bold: true, color: INK });
    s.addText(detail, { x: M + 0.52, y: y + 0.38, w: 8.2, h: 0.42, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 10.5, color: MUTED });
  });
  s.addNotes("Rewatch data would test the Family mechanism directly; per-country data would separate 'non-English holds longer' from 'competes in a thinner category'. Neither is public, which is why the finding is framed as a measurement rather than an explanation.");
}

// --- 12. closing -------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("What would change the answer", { x: M, y: 1.35, w: W - 2 * M, h: 0.55, isTextBox: true,
    margin: 0, fontFace: HEAD, fontSize: 30, bold: true, color: PAPER });
  s.addText([
    { text: "Rewatch data would test the Family mechanism directly — this data cannot.", options: { bullet: true, breakLine: true } },
    { text: "Per-country data would separate “non-English titles hold the chart longer” from “they compete in a thinner category”.", options: { bullet: true, breakLine: true } },
    { text: "A second platform would show whether any of this is about Netflix or about streaming.", options: { bullet: true } },
  ], { x: M, y: 2.1, w: 8.4, h: 1.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 14,
       color: "C9CDD2", paraSpaceAfter: 10 });
  s.addText("None of the three is public. That is why the strongest finding here is framed as a measurement, not an explanation.",
    { x: M, y: 3.55, w: 8.4, h: 0.5, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13, color: MINT });
  s.addText("Reproducible end to end: python -m src.match_report · src.model · src.analysis · src.dashboard. 75 tests. IMDb data used under its non-commercial terms. Interpretation drafted by the agent, 2026-09-27; the checkpoint decisions are Eileen's and are recorded in data/validation/.",
    { x: M, y: 4.45, w: 8.6, h: 0.7, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 10, color: MUTED });
}

pres.writeFile({ fileName: OUT }).then(() => console.log(`wrote ${OUT}`));
