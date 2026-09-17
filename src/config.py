"""Every path, URL, period and expected schema in one place.

When Netflix publishes the next report, the change should be one new entry in
ENGAGEMENT_PERIODS. From 2027 the report is annual (announced July 2026), so a
period is a start and end date, never an H1/H2 label baked into logic.
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
MANIFEST = ROOT / "data" / "manifest.json"  # tracked: provenance for gitignored raw files

# Netflix returns an "unsupported browser" HTML page with HTTP 200 to an old
# user agent, so the loaders also check what came back. See checkpoint0-sources.md.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
# Wikimedia asks API clients to identify themselves.
API_UA = "EileenIp-portfolio-streaming-engagement/0.1 (github.com/EileenIp)"


@dataclass(frozen=True)
class Period:
    label: str
    start: date
    end: date
    news_slug: str  # About Netflix post that links the xlsx


# Checkpoint 0 (Eileen, 2026-09-17): 2023 H2 onwards. 2023 H1 has no Views or
# Runtime and mixes TV and film on one sheet.
ENGAGEMENT_PERIODS = [
    Period("2023H2", date(2023, 7, 1), date(2023, 12, 31), "what-we-watched-the-second-half-of-2023"),
    Period("2024H1", date(2024, 1, 1), date(2024, 6, 30), "what-we-watched-the-first-half-of-2024"),
    Period("2024H2", date(2024, 7, 1), date(2024, 12, 31), "what-we-watched-the-second-half-of-2024"),
    Period("2025H1", date(2025, 1, 1), date(2025, 6, 30), "what-we-watched-the-first-half-of-2025"),
    Period("2025H2", date(2025, 7, 1), date(2025, 12, 31), "what-we-watched-the-second-half-of-2025"),
    Period("2026H1", date(2026, 1, 1), date(2026, 6, 30), "what-we-watched-the-first-half-of-2026"),
]
NETFLIX_NEWS_URL = "https://about.netflix.com/en/news/{slug}"

# Sheet names changed between reports (TV/Film, then Shows/Movies); the content did not.
ENGAGEMENT_SHEET_KIND = {"TV": "tv", "Shows": "tv", "Film": "film", "Movies": "film"}
ENGAGEMENT_COLUMNS = ["Title", "Available Globally?", "Release Date", "Hours Viewed", "Runtime", "Views"]
ENGAGEMENT_HEADER_ROW = 6  # 1-based; five preamble rows above it
ENGAGEMENT_FIRST_COL = 2   # data starts in column B
# Viewing from titles under 50k views, first reported 2025 H2. Not titles.
ENGAGEMENT_CATCH_ALL = {"Other Shows", "Other Movies"}

TOP10_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-global.tsv"
TOP10_COLUMNS = ["week", "category", "weekly_rank", "show_title", "season_title",
                 "weekly_hours_viewed", "runtime", "weekly_views", "cumulative_weeks_in_top_10"]

IMDB_URL = "https://datasets.imdbws.com/{name}.tsv.gz"
IMDB_COLUMNS = {
    "title.basics": ["tconst", "titleType", "primaryTitle", "originalTitle", "isAdult",
                     "startYear", "endYear", "runtimeMinutes", "genres"],
    "title.ratings": ["tconst", "averageRating", "numVotes"],
    "title.akas": ["titleId", "ordering", "title", "region", "language", "types",
                   "attributes", "isOriginalTitle"],
    "title.episode": ["tconst", "parentTconst", "seasonNumber", "episodeNumber"],
}
IMDB_DB = PROCESSED / "imdb.duckdb"

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_BATCH = 200  # IMDb ids per SPARQL query
PAGEVIEWS_URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                 "en.wikipedia/all-access/user/{article}/daily/{start}/{end}")
# Covers every engagement period plus the Top 10 weeks around them.
PAGEVIEWS_START = date(2023, 6, 1)
PAGEVIEWS_END = date(2026, 6, 30)
