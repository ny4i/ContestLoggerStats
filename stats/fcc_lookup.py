"""FCC ULS database lookup for US amateur callsigns.

Provides instant local lookups from the FCC SQLite database
(built by fcc_uls_to_sqlite.py) with zip-to-grid conversion
using Census ZCTA centroid data.

No API calls — everything is local.
"""

import csv
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional

from .geo import latlon_to_grid
from .paths import data_path

DEFAULT_DB = data_path("fcc_amateur.db")
ZCTA_FILE = data_path("zcta_centroids.csv")


@dataclass
class FCCResult:
    """FCC lookup result for a US callsign."""
    call: str
    first_name: str = ""
    last_name: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    operator_class: str = ""
    grid: str = ""
    lat: float = 0.0
    lon: float = 0.0


class FCCLookup:
    """FCC ULS database lookup with zip-to-grid conversion."""

    def __init__(self, db_path: str = DEFAULT_DB,
                 zcta_path: str = ZCTA_FILE):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._zip_coords: dict[str, tuple[float, float]] = {}
        self._available = False

        if not os.path.isfile(db_path):
            return

        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._available = True

        self._load_zcta(zcta_path)

    def _load_zcta(self, path: str):
        """Load zip code centroid lat/lon mapping."""
        if not os.path.isfile(path):
            return
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                z = row['zip'].strip()
                try:
                    lat = float(row['lat'])
                    lon = float(row['lon'])
                    self._zip_coords[z] = (lat, lon)
                except (ValueError, KeyError):
                    pass

    @property
    def available(self) -> bool:
        return self._available

    @property
    def zcta_count(self) -> int:
        return len(self._zip_coords)

    def _row_to_result(self, row) -> FCCResult:
        """Convert a database row to FCCResult with zip→grid."""
        zip_code = (row['zip_code'] or '').strip()
        lat, lon = 0.0, 0.0
        grid = ''

        zip5 = zip_code[:5] if zip_code else ''
        if zip5 in self._zip_coords:
            lat, lon = self._zip_coords[zip5]
            grid = latlon_to_grid(lat, lon)

        return FCCResult(
            call=(row['call_sign'] or '').strip(),
            first_name=(row['first_name'] or '').strip(),
            last_name=(row['last_name'] or '').strip(),
            city=(row['city'] or '').strip(),
            state=(row['state'] or '').strip(),
            zip_code=zip_code,
            operator_class=(row['operator_class'] or '').strip(),
            grid=grid,
            lat=lat,
            lon=lon,
        )

    def lookup(self, callsign: str) -> Optional[FCCResult]:
        """Look up a single US callsign in the FCC database."""
        if not self._available:
            return None
        call = callsign.upper().strip()
        if not call:
            return None
        cur = self._conn.cursor()
        cur.execute(
            "SELECT call_sign, first_name, last_name, city, state, "
            "zip_code, operator_class "
            "FROM callsigns "
            "WHERE call_sign = ? AND license_status = 'A' "
            "LIMIT 1",
            (call,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_result(row)

    def lookup_batch(self, callsigns: set[str]) -> dict[str, FCCResult]:
        """Look up many callsigns in one query. Returns {call: FCCResult}."""
        if not self._available or not callsigns:
            return {}
        calls = [c.upper().strip() for c in callsigns if c.strip()]
        results: dict[str, FCCResult] = {}
        cur = self._conn.cursor()
        # SQLite max variables is 999; batch in chunks
        for i in range(0, len(calls), 900):
            chunk = calls[i:i + 900]
            placeholders = ','.join('?' * len(chunk))
            cur.execute(
                "SELECT call_sign, first_name, last_name, city, state, "
                "zip_code, operator_class "
                "FROM callsigns "
                f"WHERE call_sign IN ({placeholders}) "
                "AND license_status = 'A'",
                chunk,
            )
            for row in cur.fetchall():
                r = self._row_to_result(row)
                results[r.call] = r
        return results

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    @staticmethod
    def is_us_callsign(callsign: str) -> bool:
        """Quick check if a callsign looks like a US amateur call."""
        call = callsign.upper().strip()
        if len(call) < 3:
            return False
        # US amateur prefixes: K, N, W, AA-AL, KA-KZ, NA-NZ, WA-WZ
        if call[0] in 'KNW':
            return True
        if call[:2] >= 'AA' and call[:2] <= 'AL':
            return True
        return False
