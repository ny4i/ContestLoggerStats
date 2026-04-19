"""QRZ.com XML API lookup with local JSON cache.

Looks up callsign grid squares (and other data) via the QRZ XML API.
Results are cached in ~/.publicLogProcessor/qrz_cache.json so each
callsign is only queried once across runs.

Credentials are read from ~/qrz_settings.cfg:
    [qrz]
    username=YOURCALL
    password=YOURPASSWORD
"""

import configparser
import json
import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

CACHE_DIR = os.path.expanduser("~/.publicLogProcessor")
CACHE_FILE = os.path.join(CACHE_DIR, "qrz_cache.json")
DEFAULT_CFG = os.path.expanduser("~/qrz_settings.cfg")
QRZ_API_URL = "https://xmldata.qrz.com/xml/current/"


@dataclass
class QRZResult:
    """Subset of QRZ data we care about."""
    call: str
    grid: str = ""
    state: str = ""
    country: str = ""
    lat: float = 0.0
    lon: float = 0.0


class QRZLookup:
    """QRZ XML API client with persistent JSON cache."""

    def __init__(self, cfg_path: str = DEFAULT_CFG):
        self._cfg_path = cfg_path
        self._session_key: Optional[str] = None
        self._cache: dict[str, dict] = {}
        self._cache_dirty = False
        self._load_cache()

    def _load_cache(self):
        if os.path.isfile(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                self._cache = json.load(f)

    def save_cache(self):
        """Write cache to disk if modified."""
        if not self._cache_dirty:
            return
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(self._cache, f, indent=1)
        self._cache_dirty = False

    def _read_credentials(self) -> tuple[str, str]:
        cfg = configparser.ConfigParser()
        cfg.read(os.path.expanduser(self._cfg_path))
        if not cfg.has_section('qrz'):
            raise RuntimeError(f"No [qrz] section in {self._cfg_path}")
        username = cfg.get('qrz', 'username', fallback='')
        password = cfg.get('qrz', 'password', fallback='')
        if not username or not password:
            raise RuntimeError(f"Missing username or password in {self._cfg_path}")
        return username, password

    def _get_session(self):
        username, password = self._read_credentials()
        params = urllib.parse.urlencode({
            'username': username,
            'password': password,
        })
        url = f"{QRZ_API_URL}?{params}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml_bytes = resp.read()
        root = ET.fromstring(xml_bytes)
        ns = root.tag.split('}')[0] + '}' if '}' in root.tag else ''
        session = root.find(f'{ns}Session')
        if session is None:
            raise RuntimeError("QRZ API: no Session element")
        error = session.findtext(f'{ns}Error')
        if error:
            raise RuntimeError(f"QRZ session error: {error}")
        key = session.findtext(f'{ns}Key')
        if not key:
            raise RuntimeError("QRZ API: no session key returned")
        self._session_key = key

    def _api_lookup(self, callsign: str, retry: bool = True) -> Optional[dict]:
        """Raw XML lookup, returns dict of QRZ fields or None."""
        if self._session_key is None:
            self._get_session()
        params = urllib.parse.urlencode({
            's': self._session_key,
            'callsign': callsign,
        })
        url = f"{QRZ_API_URL}?{params}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml_bytes = resp.read()
        root = ET.fromstring(xml_bytes)
        ns = root.tag.split('}')[0] + '}' if '}' in root.tag else ''

        session = root.find(f'{ns}Session')
        if session is not None:
            error = session.findtext(f'{ns}Error')
            if error:
                if retry and ('Timeout' in error or 'Invalid session' in error):
                    self._session_key = None
                    return self._api_lookup(callsign, retry=False)
                if 'not found' in error.lower():
                    return None
                raise RuntimeError(f"QRZ lookup error: {error}")

        cs = root.find(f'{ns}Callsign')
        if cs is None:
            return None

        result = {}
        for child in cs:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if child.text:
                result[tag] = child.text
        return result

    def lookup(self, callsign: str) -> Optional[QRZResult]:
        """Look up a callsign, using cache first."""
        key = callsign.upper().strip()
        if not key:
            return None

        if key in self._cache:
            d = self._cache[key]
            return QRZResult(
                call=key,
                grid=d.get('grid', ''),
                state=d.get('state', ''),
                country=d.get('country', ''),
                lat=float(d.get('lat', 0)),
                lon=float(d.get('lon', 0)),
            )

        raw = self._api_lookup(key)
        if raw is None:
            # Cache the miss so we don't retry
            self._cache[key] = {}
            self._cache_dirty = True
            return None

        entry = {
            'grid': raw.get('grid', ''),
            'state': raw.get('state', ''),
            'country': raw.get('country', ''),
            'lat': raw.get('lat', '0'),
            'lon': raw.get('lon', '0'),
        }
        self._cache[key] = entry
        self._cache_dirty = True

        return QRZResult(
            call=key,
            grid=entry['grid'],
            state=entry['state'],
            country=entry['country'],
            lat=float(entry['lat'] or 0),
            lon=float(entry['lon'] or 0),
        )

    @property
    def cache_size(self) -> int:
        return len(self._cache)
