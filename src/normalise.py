"""Title normalisation: the ladder every match is built on.

Netflix publishes a title as one string that can carry four separate facts:

    'Suits (2011): Season 1'                      base, disambiguating year, season
    'Dear Child: Limited Series // Liebes Kind: Miniserie'   English name // original name
    'Stranger Things 4'                           season with no marker at all
    'Raw: June 15, 2025'                          a dated live episode

Each is pulled apart here and nothing is thrown away: every parse keeps the raw
string, so the match report can always show what was actually published.

Two rules this file follows:

1. Only strip a season marker that is really there. A trailing bare number
   ('Stranger Things 4') is ambiguous with a film sequel ('Extraction 2'), so it
   is parsed but flagged, and the caller decides.
2. Normalisation is for comparison keys only. It is never written back as a title.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

ALTERNATE_SEPARATOR = " // "

# Ordered: the longest, most specific suffix wins. Each pattern anchors to the
# end of the string and captures a number where there is one.
SEASON_PATTERNS = [
    ("season", r":\s*Season\s+(\d+):\s*Part\s+(\d+)$", "season_part"),
    ("season", r":\s*Season\s+(\d+)$", None),
    ("season", r":\s*시즌\s*(\d+)$", None),           # Korean 'Season', in a few titles
    # A season that also carries a name: 'The Sinner: Season 4: Percy',
    # 'Love Is Blind: S10: Ohio'. The number identifies the season; the name is
    # dropped from the key, not from the raw title.
    ("season", r":\s*Season\s+(\d+):\s*\S.*$", None),
    ("season", r":\s*S(\d+):\s*\S.*$", None),
    ("series", r":\s*Series\s+(\d+)$", None),          # British usage: Downton Abbey: Series 1
    # The season word in the title's own language. Netflix publishes these as
    # written: 'Aqui no hay quien viva (2003): Temporada 4'.
    ("season", r":\s*(?:Temporada|Stagione|Staffel|Saison|Sezon|Sezonul|Seizoen|Sesong|Kausi|"
               r"Sezona|Seria|Series|Bolum|Sezon)\s+(\d+)$", None),
    # Netflix names some seasons in words: 'Law & Order: SVU: The Sixth Year'.
    ("season", r":\s*The\s+(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|"
               r"Eleventh|Twelfth|Thirteenth|Fourteenth|Fifteenth|Sixteenth|Seventeenth|"
               r"Eighteenth|Nineteenth|Twentieth)\s+(?:Year|Season)$", "ordinal"),
    ("part", r":\s*Part\s+(\d+)$", None),
    ("part", r"\s+Part\s+(\d+)$", None),               # 'Attack on Titan: The Final Season Part 3'
    ("volume", r":\s*Volume\s+(\d+)$", None),
    ("chapter", r":\s*Chapter\s+(\d+)$", None),
    ("collection", r":\s*Collection\s+(\d+)$", None),
    ("limited", r":\s*Limited\s+Series$", None),
    ("limited", r":\s*Miniserie[s]?$", None),
    ("episode_date", r":\s*(January|February|March|April|May|June|July|August|September|"
                     r"October|November|December)\s+\d{1,2},\s*\d{4}$", None),
]
BARE_NUMBER = re.compile(r"^(?P<base>.*\S)\s+(?P<number>\d{1,2})$")
# Roman numerals, as a season marker after a colon ('Our Planet: II') or bare
# ('Barbarians II'). 'I' alone is excluded: too easy to eat a real word.
ORDINALS = {w: i for i, w in enumerate(
    ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
     "Eleventh", "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth",
     "Eighteenth", "Nineteenth", "Twentieth"], start=1)}
ROMAN = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
ROMAN_SEASON = re.compile(rf"^(?P<base>.*\S)(?::\s*|\s+)(?P<roman>{'|'.join(ROMAN)})$")
YEAR_IN_TITLE = re.compile(r"\s*\((?P<year>(?:19|20)\d\d)\)")
# A trailing parenthetical that is not a year: 'Shameless (U.S.)',
# 'Rosario Tijeras (Mexico)'. Netflix uses it to tell versions apart, so it is
# captured and kept - dropping it merges the UK and US Shameless.
QUALIFIER = re.compile(r"\s*\((?P<qualifier>[^)]+)\)\s*$")
# A title that names two parts at once: 'Part 1 / Part 2', 'Volume 1 & Volume 2'.
MULTI_PART = re.compile(r"(?:Part|Season|Volume|Chapter)\s+\d+\s*[/&,]", re.IGNORECASE)

# Deliberately small: only substitutions that are about writing the same name two
# ways, never ones that change which title is meant.
REPLACEMENTS = [("&", " and "), ("+", " and "), ("×", " x ")]


@dataclass(frozen=True)
class ParsedTitle:
    raw: str
    primary: str          # the part before ' // ', as published
    alternates: tuple     # other names published in the same string
    base: str             # primary with the season marker and year removed
    season_kind: str | None   # season, series, part, volume, chapter, collection, limited, episode_date
    season_number: int | None
    part_number: int | None   # 'Season 2: Part 1'
    year: int | None          # the (2011) in 'Suits (2011)'
    season_from_bare_number: bool  # 'Stranger Things 4': parsed, but ambiguous with a film sequel
    episode_date: str | None       # the ': June 15, 2025' of a dated live episode
    qualifier: str | None = None   # the '(U.S.)' in 'Shameless (U.S.)'

    @property
    def key(self) -> str:
        """Comparison key for the base name, qualifier included."""
        return normalise(self.base)

    @property
    def key_without_qualifier(self) -> str:
        """Same key with a trailing '(U.S.)' or '(Mexico)' dropped. A weaker key: it
        merges different versions of a show, so it is only ever a lower rung."""
        return normalise(QUALIFIER.sub("", self.base)) if self.qualifier else self.key

    @property
    def season_key(self) -> tuple:
        """What has to agree for two rows to be the same season of the same thing."""
        return (self.season_kind, self.season_number, self.part_number, self.episode_date)

    @property
    def alternate_keys(self) -> tuple:
        """Keys for every name published for this title, alternates included."""
        keys = [self.key]
        for alt in self.alternates:
            keys.append(parse(alt).key)
        return tuple(dict.fromkeys(k for k in keys if k))


# 'Shameless (U.S.)' normalises to 'shameless u s', IMDb's aka is 'Shameless US'.
# Runs of single letters are joined back up: 'u s' -> 'us', 'j f k' -> 'jfk'.
SINGLE_LETTER_RUN = re.compile(r"(?<![^\s])(?:[^\W\d_]\s+){1,}[^\W\d_](?![^\s])")


def compact(key: str) -> str:
    """A key with every space removed: 's w a t' and 'swat' both become 'swat'.

    This is how the IMDb side is reached without lookaround, which RE2 (and so
    DuckDB's regexp_replace) does not support. Used as its own rung, never as the
    first one, because it also merges titles that differ only in spacing.
    """
    return key.replace(" ", "")


def normalise(text: str, collapse_acronyms: bool = True) -> str:
    """Casefold, strip accents and punctuation, collapse whitespace. Comparison only.

    collapse_acronyms=False gives exactly what the SQL macro in match_imdb produces;
    a test pins the two together.
    """
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold()
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    # Keep letters and digits from any script (CJK titles must survive), drop the rest.
    text = "".join(c if (c.isalnum() or c.isspace()) else " " for c in text)
    text = re.sub(r"\s+", " ", text).strip()
    if not collapse_acronyms:
        return text
    return SINGLE_LETTER_RUN.sub(lambda m: m.group().replace(" ", ""), text)


def _strip_season(title: str):
    title = title.rstrip(": ")  # 'Furies: Season 1:' is published with a trailing colon
    if MULTI_PART.search(title):
        # 'Sailor Moon Cosmos: Part 1 / Part 2' names two parts at once: one title,
        # not part 2 of anything.
        return title, None, None, None, None, False
    for kind, pattern, variant in SEASON_PATTERNS:
        m = re.search(pattern, title, flags=re.IGNORECASE)
        if not m:
            continue
        base = title[:m.start()].rstrip()
        if base.endswith(("/", "-", "&", ",")):
            # 'Sailor Moon Cosmos: Part 1 / Part 2' is one two-part film, not part 2.
            continue
        if variant == "ordinal":
            return base, kind, ORDINALS[m.group(1).title()], None, None, False
        if variant == "season_part":
            return base, kind, int(m.group(1)), int(m.group(2)), None, False
        if kind == "episode_date":
            return base, kind, None, None, m.group(0).lstrip(": ").strip(), False
        number = int(m.group(1)) if m.groups() and m.group(1) and m.group(1).isdigit() else None
        return base, kind, number, None, None, False
    m = ROMAN_SEASON.match(title)
    if m:
        return m.group("base").rstrip(": "), "season", ROMAN[m.group("roman")], None, None, True
    m = BARE_NUMBER.match(title)
    if m and not re.search(r"\d$", m.group("base")):
        # 'Stranger Things 4' or the film 'Extraction 2' - same shape, different meaning.
        return m.group("base"), "season", int(m.group("number")), None, None, True
    return title, None, None, None, None, False


def parse(title: str) -> ParsedTitle:
    raw = str(title)
    names = [p.strip() for p in raw.split(ALTERNATE_SEPARATOR)]
    primary, alternates = names[0], tuple(n for n in names[1:] if n)
    base, kind, number, part, episode_date, from_bare = _strip_season(primary)
    year_match = YEAR_IN_TITLE.search(base)
    year = int(year_match.group("year")) if year_match else None
    if year_match:
        base = (base[:year_match.start()] + base[year_match.end():]).strip()
    qualifier_match = QUALIFIER.search(base)
    qualifier = qualifier_match.group("qualifier") if qualifier_match else None
    return ParsedTitle(raw=raw, primary=primary, alternates=alternates, base=base,
                       season_kind=kind, season_number=number, part_number=part, year=year,
                       season_from_bare_number=from_bare, episode_date=episode_date,
                       qualifier=qualifier)
