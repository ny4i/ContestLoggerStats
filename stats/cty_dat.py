"""CTY.DAT parser and callsign-to-country lookup.

Ported from TR4QT CountryFile.cpp.

CTY.DAT format (per entry):
  Main line: Name:CQZone:ITUZone:Continent:Lat:Lon:GMTOffset:PrimaryPrefix:
  Alias lines: comma-separated prefixes ending with semicolon.
  Special prefix syntax:
    =CALL   - exact callsign match
    PFX(nn) - CQ zone override
    PFX[nn] - ITU zone override
"""

import os
import re
from dataclasses import dataclass, field


@dataclass
class CountryData:
    name: str = ""
    cq_zone: int = 0
    itu_zone: int = 0
    continent: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    gmt_offset: float = 0.0
    primary_prefix: str = ""
    cq_zone_overrides: dict[str, int] = field(default_factory=dict)
    itu_zone_overrides: dict[str, int] = field(default_factory=dict)

    def is_valid(self) -> bool:
        return self.primary_prefix != ""


# CQ zone override regex: prefix(nn)
_CQ_ZONE_RE = re.compile(r'^(.+?)\((\d+)\)')
# ITU zone override regex: prefix[nn]
_ITU_ZONE_RE = re.compile(r'^(.+?)\[(\d+)\]')


class CtyDat:
    """CTY.DAT parser and callsign lookup."""

    def __init__(self):
        self._countries: dict[str, CountryData] = {}  # primary_prefix -> data
        self._prefix_map: dict[str, str] = {}  # prefix -> primary_prefix
        self._exact_matches: dict[str, str] = {}  # callsign -> primary_prefix

    @staticmethod
    def find_cty_dat(cli_path: str | None = None) -> str | None:
        """Search for cty.dat in standard locations."""
        candidates = []
        if cli_path:
            candidates.append(cli_path)
        candidates.extend([
            os.path.join(os.getcwd(), "cty.dat"),
            os.path.expanduser("~/Library/Application Support/TR4QT/cty.dat"),
            os.path.expanduser("~/.tr4qt/cty.dat"),
        ])
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def load(self, filepath: str) -> bool:
        """Load and parse a CTY.DAT file. Returns True on success."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except OSError:
            return False

        self._countries.clear()
        self._prefix_map.clear()
        self._exact_matches.clear()

        main_line = ""
        alias_lines: list[str] = []
        in_aliases = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue

            if not in_aliases and ':' in line:
                if main_line:
                    self._parse_entry(main_line, alias_lines)
                    alias_lines = []
                main_line = line
                in_aliases = True
            elif in_aliases:
                alias_lines.append(line)
                if line.endswith(';'):
                    self._parse_entry(main_line, alias_lines)
                    main_line = ""
                    alias_lines = []
                    in_aliases = False

        if main_line:
            self._parse_entry(main_line, alias_lines)

        return len(self._countries) > 0

    def _parse_entry(self, main_line: str, alias_lines: list[str]):
        parts = main_line.split(':')
        if len(parts) < 8:
            return

        country = CountryData()
        country.name = parts[0].strip()
        country.cq_zone = int(parts[1].strip())
        country.itu_zone = int(parts[2].strip())
        country.continent = parts[3].strip()
        country.latitude = float(parts[4].strip())
        country.longitude = float(parts[5].strip())

        # CTY.DAT longitude convention: "west = positive" (inverted from standard).
        # Negate ALL longitudes to convert to standard geographic convention.
        country.longitude = -country.longitude

        country.gmt_offset = float(parts[6].strip())
        country.primary_prefix = parts[7].strip()

        self._countries[country.primary_prefix] = country
        self._prefix_map[country.primary_prefix] = country.primary_prefix

        # Parse alias prefixes
        all_aliases = "".join(alias_lines).rstrip(';')
        for token in all_aliases.split(','):
            token = token.strip()
            if not token:
                continue

            # Exact match
            if token.startswith('='):
                exact_call = token[1:]
                # Strip zone overrides from exact calls too
                exact_call, cq_ov, itu_ov = self._parse_zone_overrides(exact_call)
                exact_call = exact_call.upper()
                self._exact_matches[exact_call] = country.primary_prefix
                if cq_ov is not None:
                    country.cq_zone_overrides[exact_call] = cq_ov
                if itu_ov is not None:
                    country.itu_zone_overrides[exact_call] = itu_ov
                continue

            clean, cq_ov, itu_ov = self._parse_zone_overrides(token)
            clean = clean.upper()
            self._prefix_map[clean] = country.primary_prefix
            if cq_ov is not None:
                country.cq_zone_overrides[clean] = cq_ov
            if itu_ov is not None:
                country.itu_zone_overrides[clean] = itu_ov

    @staticmethod
    def _parse_zone_overrides(token: str) -> tuple[str, int | None, int | None]:
        """Parse CQ zone (nn) and ITU zone [nn] overrides from a prefix token."""
        clean = token
        cq_ov = None
        itu_ov = None

        m = _CQ_ZONE_RE.match(clean)
        if m:
            clean = m.group(1)
            cq_ov = int(m.group(2))

        m = _ITU_ZONE_RE.match(clean)
        if m:
            clean = m.group(1)
            itu_ov = int(m.group(2))

        return clean, cq_ov, itu_ov

    def lookup(self, callsign: str) -> CountryData:
        """Look up country data for a callsign. Returns empty CountryData if not found."""
        if not callsign:
            return CountryData()

        clean_call = strip_portable(callsign).upper()

        # 1. Check exact matches
        if clean_call in self._exact_matches:
            pp = self._exact_matches[clean_call]
            if pp in self._countries:
                country = CountryData(**vars(self._countries[pp]))
                # Copy mutable fields
                country.cq_zone_overrides = dict(self._countries[pp].cq_zone_overrides)
                country.itu_zone_overrides = dict(self._countries[pp].itu_zone_overrides)

                has_cq_override = False
                if clean_call in country.cq_zone_overrides:
                    country.cq_zone = country.cq_zone_overrides[clean_call]
                    has_cq_override = True
                if clean_call in country.itu_zone_overrides:
                    country.itu_zone = country.itu_zone_overrides[clean_call]

                if not has_cq_override and country.name == "United States":
                    us_zone = get_us_call_area_zone(clean_call)
                    if us_zone > 0:
                        country.cq_zone = us_zone

                return country

        # 2. Longest prefix match
        matched = self._find_longest_prefix(clean_call)
        if matched and matched in self._prefix_map:
            pp = self._prefix_map[matched]
            if pp in self._countries:
                country = CountryData(**vars(self._countries[pp]))
                country.cq_zone_overrides = dict(self._countries[pp].cq_zone_overrides)
                country.itu_zone_overrides = dict(self._countries[pp].itu_zone_overrides)

                has_cq_override = False
                if matched in country.cq_zone_overrides:
                    country.cq_zone = country.cq_zone_overrides[matched]
                    has_cq_override = True
                if matched in country.itu_zone_overrides:
                    country.itu_zone = country.itu_zone_overrides[matched]

                if not has_cq_override and country.name == "United States":
                    us_zone = get_us_call_area_zone(clean_call)
                    if us_zone > 0:
                        country.cq_zone = us_zone

                return country

        return CountryData()

    def _find_longest_prefix(self, callsign: str) -> str:
        """Find the longest prefix in the map that matches the callsign."""
        longest = ""
        for prefix in self._prefix_map:
            if callsign.startswith(prefix) and len(prefix) > len(longest):
                longest = prefix
        return longest

    @property
    def country_count(self) -> int:
        return len(self._countries)


def strip_portable(callsign: str) -> str:
    """Remove portable indicators, keeping the longest part."""
    parts = callsign.split('/')
    if len(parts) == 1:
        return callsign
    return max(parts, key=len)


def extract_wpx_prefix(callsign: str) -> str:
    """Extract WPX prefix: everything up to and including the first digit."""
    base = strip_portable(callsign)
    for i, ch in enumerate(base):
        if ch.isdigit():
            return base[:i + 1]
    return base


def get_us_call_area_zone(callsign: str) -> int:
    """Determine CQ zone from US call area. Returns -1 if not applicable."""
    base = strip_portable(callsign).upper()
    if len(base) < 2:
        return -1

    first = base[0]
    if first not in 'KWNA':
        return -1

    # Check Alaska/Hawaii prefixes first
    if len(base) >= 2:
        prefix2 = base[:2]
        if prefix2 in ('KL', 'AL', 'NL', 'WL'):
            return 1   # Alaska
        if prefix2 in ('KH', 'AH', 'NH', 'WH'):
            return 31  # Hawaii

    # Find call area digit
    if not base[1].isdigit():
        return -1

    area = int(base[1])
    if area in (6, 7):
        return 3   # Pacific
    if area in (0, 5, 8, 9):
        return 4   # Central
    if area in (1, 2, 3, 4):
        return 5   # Eastern

    return -1


# US call area grid squares for distance estimation
_US_AREA_GRIDS = {
    1: "FN43", 2: "FN22", 3: "FN10", 4: "EL83", 5: "EM13",
    6: "DM06", 7: "DN42", 8: "EN80", 9: "EN52", 0: "EN04",
}


def get_us_call_area_grid(callsign: str) -> str | None:
    """Map US callsign to approximate grid square. Returns None if not US."""
    base = strip_portable(callsign).upper()
    if len(base) < 2 or base[0] not in 'KWNA':
        return None

    for i in range(1, min(3, len(base))):
        if base[i].isdigit():
            return _US_AREA_GRIDS.get(int(base[i]))
    return None
