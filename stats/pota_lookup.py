"""POTA (Parks on the Air) park reference → grid lookup.

Source: https://pota.app/all_parks_ext.csv (public, freely usable per POTA team).

Lazy-loaded: only fetched/parsed when the ADIF contains POTA references
(POTA_REF/MY_POTA_REF, or SIG/MY_SIG == "POTA" with SIG_INFO/MY_SIG_INFO).
POTA_REF wins over SIG_INFO when both are present; first ref wins on N-fers.
"""

import csv
import os
import re
import urllib.request
from dataclasses import dataclass

POTA_URL = "https://pota.app/all_parks_ext.csv"
CACHE_DIR = os.path.expanduser("~/.publicLogProcessor")
CACHE_FILE = "pota_parks.csv"

_SPLIT_RE = re.compile(r"[,\s]+")


@dataclass
class Park:
    reference: str
    name: str = ""
    grid: str = ""
    location_desc: str = ""   # e.g. "US-ME", "CA-AB"
    entity_id: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    active: bool = True


def _split_refs(value: str) -> list[str]:
    if not value:
        return []
    return [r.strip() for r in _SPLIT_RE.split(value) if r.strip()]


def extract_pota_refs(raw_qso: dict[str, str]) -> tuple[list[str], list[str]]:
    """Return (my_refs, their_refs) from a raw ADIF QSO dict.

    POTA_REF/MY_POTA_REF take precedence over SIG_INFO/MY_SIG_INFO.
    SIG_INFO is only honored when SIG == "POTA" (same for MY_SIG).
    """
    their = raw_qso.get("POTA_REF", "").strip()
    if not their and raw_qso.get("SIG", "").strip().upper() == "POTA":
        their = raw_qso.get("SIG_INFO", "").strip()

    mine = raw_qso.get("MY_POTA_REF", "").strip()
    if not mine and raw_qso.get("MY_SIG", "").strip().upper() == "POTA":
        mine = raw_qso.get("MY_SIG_INFO", "").strip()

    return _split_refs(mine), _split_refs(their)


def has_any_pota_refs(raw_qsos: list[dict[str, str]]) -> bool:
    """Scan raw QSOs — True if any record has a POTA reference."""
    for q in raw_qsos:
        mine, their = extract_pota_refs(q)
        if mine or their:
            return True
    return False


def find_pota_parks(path_hint: str | None = None) -> str | None:
    """Return pota_parks.csv path from ./databases/ (or CLI hint)."""
    from .paths import find_data_file
    return find_data_file(CACHE_FILE, path_hint)


def download_pota_parks(cache_dir: str | None = None) -> str:
    """Download pota_parks.csv into ./databases/. Returns the file path."""
    from .paths import databases_dir
    target_dir = cache_dir or databases_dir()
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, CACHE_FILE)
    req = urllib.request.urlopen(POTA_URL, timeout=60)
    data = req.read()
    with open(target, "wb") as f:
        f.write(data)
    return target


class POTALookup:
    """Park reference → full Park record."""

    def __init__(self) -> None:
        self._parks: dict[str, Park] = {}

    def load(self, filepath: str) -> int:
        """Load pota_parks.csv. Returns count of usable entries."""
        self._parks.clear()
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                ref = (row.get("reference") or "").strip().upper()
                grid = (row.get("grid") or "").strip()
                if not ref or not grid:
                    continue
                try:
                    lat = float(row.get("latitude") or "0")
                    lon = float(row.get("longitude") or "0")
                except ValueError:
                    lat = lon = 0.0
                active_str = (row.get("active") or "").strip()
                # Sentinel-coord filter: inactive parks at (0.0, 0.0) are garbage
                if lat == 0.0 and lon == 0.0 and active_str == "0":
                    continue
                self._parks[ref] = Park(
                    reference=ref,
                    name=(row.get("name") or "").strip(),
                    grid=grid,
                    location_desc=(row.get("locationDesc") or "").strip(),
                    entity_id=(row.get("entityId") or "").strip(),
                    latitude=lat,
                    longitude=lon,
                    active=(active_str != "0"),
                )
        return len(self._parks)

    def park_for(self, ref: str) -> Park | None:
        if not ref:
            return None
        return self._parks.get(ref.strip().upper())

    def grid_for(self, ref: str) -> str | None:
        p = self.park_for(ref)
        return p.grid if p else None

    def first_grid(self, refs: list[str]) -> str | None:
        """N-fer: first ref that resolves wins."""
        for r in refs:
            g = self.grid_for(r)
            if g:
                return g
        return None

    def grid_for_field(self, field_value: str) -> str | None:
        """Convenience: split a raw ADIF ref field and return the first grid."""
        return self.first_grid(_split_refs(field_value))

    @property
    def size(self) -> int:
        return len(self._parks)
