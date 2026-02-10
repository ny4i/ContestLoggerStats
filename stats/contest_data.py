"""Central data model for contest log statistics."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class QSO:
    call: str
    band: str               # "20m", "40m", etc.
    mode: str               # "SSB", "CW", "FT8", etc.
    mode_group: str          # "PH", "CW", "DIG"
    freq_mhz: float
    datetime_utc: datetime
    operator: str
    rst_sent: str
    rst_rcvd: str
    stx: str                # Sent exchange
    srx: str                # Received exchange
    # Enriched by cty.dat:
    country: str = ""
    continent: str = ""
    cq_zone: int = 0
    itu_zone: int = 0
    dxcc_lat: float = 0.0
    dxcc_lon: float = 0.0
    distance_km: float = 0.0
    bearing_deg: float = 0.0
    prefix: str = ""
    grid: str = ""
    # Annotations:
    is_dupe: bool = False
    lcr_error: Optional[str] = None
    lcr_detail: str = ""


@dataclass
class ContestLog:
    station_call: str
    locator: str
    contest_name: str
    qsos: list[QSO]
    operators: list[str]
    start_time: datetime
    end_time: datetime
    category: str = ""
    station_lat: float = 0.0
    station_lon: float = 0.0

    @property
    def active_bands(self) -> list[str]:
        """Return bands that have at least one QSO, in frequency order."""
        band_order = ["160m", "80m", "40m", "20m", "15m", "10m", "6m", "2m"]
        bands = {q.band for q in self.qsos}
        return [b for b in band_order if b in bands]

    @property
    def active_mode_groups(self) -> list[str]:
        """Return mode groups that have at least one QSO."""
        group_order = ["CW", "DIG", "PH"]
        groups = {q.mode_group for q in self.qsos}
        return [g for g in group_order if g in groups]
