"""Contest definition loading, exchange validation, and estimated scoring.

Loads contest rules from contests.json (dupe rule, exchange regex, scoring type).
Scoring formulas live here in Python because they depend on continent comparisons,
band-dependent points, etc. — not expressible as simple JSON.

All scores are estimates. Field Day power multiplier, bonus points, WPX band-change
rules, etc. are not in ADIF and cannot be calculated.
"""

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field

from .contest_data import ContestLog, QSO
from .cty_dat import extract_wpx_prefix


@dataclass
class ContestDefinition:
    contest_id: str
    name: str
    dupe_rule: str
    exchange_pattern: re.Pattern | None
    exchange_pattern_wve: re.Pattern | None
    exchange_pattern_dx: re.Pattern | None
    exchange_description: str
    scoring_type: str
    mult_description: str


@dataclass
class ScoreResult:
    qso_points: int
    multipliers: int
    total_score: int
    mult_detail: str
    scoring_notes: list[str] = field(default_factory=list)


def _compile_pattern(raw: str | None) -> re.Pattern | None:
    if raw:
        return re.compile(raw, re.IGNORECASE)
    return None


def load_contest_definitions(json_path: str | None = None) -> dict[str, ContestDefinition]:
    """Load contest definitions from contests.json."""
    if json_path is None:
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "contests.json")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    defs = {}
    for contest_id, entry in data.items():
        defs[contest_id] = ContestDefinition(
            contest_id=contest_id,
            name=entry.get("name", contest_id),
            dupe_rule=entry.get("dupe_rule", "per_band_mode"),
            exchange_pattern=_compile_pattern(entry.get("exchange_pattern")),
            exchange_pattern_wve=_compile_pattern(entry.get("exchange_pattern_wve")),
            exchange_pattern_dx=_compile_pattern(entry.get("exchange_pattern_dx")),
            exchange_description=entry.get("exchange_description", ""),
            scoring_type=entry.get("scoring_type", "generic"),
            mult_description=entry.get("mult_description", ""),
        )

    return defs


def lookup_contest(contest_id: str,
                   definitions: dict[str, ContestDefinition]) -> ContestDefinition | None:
    """Look up a contest definition by ADIF contest ID. Returns None if unknown."""
    return definitions.get(contest_id)


# ── Exchange Validation ──────────────────────────────────────────────


def _is_wve_station(station_country: str) -> bool:
    """Check if station is in W/VE (US or Canada)."""
    wve = {"United States", "Canada", "Alaska", "Hawaii"}
    return station_country in wve


def validate_exchanges(qsos: list[QSO], contest_def: ContestDefinition,
                       station_country: str = "") -> None:
    """Set qso.exchange_error on QSOs with malformed srx field."""
    # Pick the right pattern
    if contest_def.exchange_pattern_wve and contest_def.exchange_pattern_dx:
        # ARRL DX / ARRL RTTY: pattern depends on station's side
        if _is_wve_station(station_country):
            # W/VE station receives DX exchange
            pattern = contest_def.exchange_pattern_dx
        else:
            # DX station receives W/VE exchange
            pattern = contest_def.exchange_pattern_wve
    elif contest_def.exchange_pattern:
        pattern = contest_def.exchange_pattern
    else:
        return  # No pattern defined

    for qso in qsos:
        if qso.is_dupe:
            continue
        srx = qso.srx.strip()
        if not srx:
            qso.exchange_error = f"Empty exchange (expected: {contest_def.exchange_description})"
        elif not pattern.match(srx):
            qso.exchange_error = (
                f"'{srx}' doesn't match expected format: "
                f"{contest_def.exchange_description}"
            )


# ── Scoring ──────────────────────────────────────────────────────────


def estimate_score(log: ContestLog,
                   contest_def: ContestDefinition) -> ScoreResult:
    """Compute estimated score. Dispatches by scoring_type."""
    scorers = {
        "cq_ww": _score_cq_ww,
        "cq_wpx": _score_cq_wpx,
        "field_day": _score_field_day,
        "arrl_ss": _score_arrl_ss,
        "naqp": _score_naqp,
        "arrl_dx": _score_arrl_dx,
        "arrl_rtty": _score_arrl_rtty,
        "generic": _score_generic,
    }
    scorer = scorers.get(contest_def.scoring_type, _score_generic)
    return scorer(log, contest_def)


def _non_dupe_qsos(log: ContestLog) -> list[QSO]:
    return [q for q in log.qsos if not q.is_dupe]


# ── CQ WW ────────────────────────────────────────────────────────────


def _score_cq_ww(log: ContestLog, contest_def: ContestDefinition) -> ScoreResult:
    """CQ WW: points by continent relationship; mults = countries + zones per band."""
    notes = []
    station_cont = log.station_continent
    if not station_cont:
        notes.append("Station continent unknown; all QSOs scored as 1 point")

    qso_points = 0
    countries_per_band: dict[str, set[str]] = defaultdict(set)
    zones_per_band: dict[str, set[int]] = defaultdict(set)

    for q in _non_dupe_qsos(log):
        # Points
        if not station_cont or not q.continent:
            pts = 1
        elif q.country == log.station_country:
            pts = 0
        elif q.continent == station_cont and station_cont == "NA":
            pts = 2
        elif q.continent == station_cont:
            pts = 1
        else:
            pts = 3

        qso_points += pts

        # Multipliers
        if q.country:
            countries_per_band[q.band].add(q.country)
        if q.cq_zone > 0:
            zones_per_band[q.band].add(q.cq_zone)

    total_countries = sum(len(v) for v in countries_per_band.values())
    total_zones = sum(len(v) for v in zones_per_band.values())
    multipliers = total_countries + total_zones
    mult_detail = f"{total_countries} countries + {total_zones} zones = {multipliers}"

    notes.append("Same-country QSOs score 0 points per CQ WW rules")
    return ScoreResult(
        qso_points=qso_points,
        multipliers=multipliers,
        total_score=qso_points * multipliers,
        mult_detail=mult_detail,
        scoring_notes=notes,
    )


# ── CQ WPX ───────────────────────────────────────────────────────────


def _score_cq_wpx(log: ContestLog, contest_def: ContestDefinition) -> ScoreResult:
    """CQ WPX: band-dependent points; mults = unique prefixes (all-band)."""
    notes = []
    station_cont = log.station_continent
    if not station_cont:
        notes.append("Station continent unknown; using default 1pt/QSO")

    qso_points = 0
    prefixes: set[str] = set()
    low_bands = {"160m", "80m", "40m"}

    for q in _non_dupe_qsos(log):
        pfx = extract_wpx_prefix(q.call)
        if pfx:
            prefixes.add(pfx)

        if not station_cont or not q.continent:
            pts = 1
        elif q.continent == station_cont:
            pts = 1
        elif q.band in low_bands:
            pts = 6
        else:
            pts = 3

        qso_points += pts

    multipliers = len(prefixes)
    mult_detail = f"{multipliers} unique prefixes"
    notes.append("Band-change rule for prefixes not applied (not available in ADIF)")

    return ScoreResult(
        qso_points=qso_points,
        multipliers=multipliers,
        total_score=qso_points * multipliers,
        mult_detail=mult_detail,
        scoring_notes=notes,
    )


# ── Field Day (ARRL + Winter) ────────────────────────────────────────


def _score_field_day(log: ContestLog, contest_def: ContestDefinition) -> ScoreResult:
    """Field Day: CW/DIG=2pts, PH=1pt; no multipliers calculated."""
    notes = [
        "Power multiplier not applied (not available in ADIF)",
        "Bonus points not included",
    ]

    qso_points = 0
    for q in _non_dupe_qsos(log):
        if q.mode_group in ("CW", "DIG"):
            qso_points += 2
        else:
            qso_points += 1

    return ScoreResult(
        qso_points=qso_points,
        multipliers=1,
        total_score=qso_points,
        mult_detail="Power multiplier not applied",
        scoring_notes=notes,
    )


# ── ARRL Sweepstakes ─────────────────────────────────────────────────


def _extract_ss_section(srx: str) -> str:
    """Extract section from SS exchange: 'Nr Prec Check Section'."""
    parts = srx.strip().split()
    if len(parts) >= 4:
        return parts[-1].upper()
    return ""


def _score_arrl_ss(log: ContestLog, contest_def: ContestDefinition) -> ScoreResult:
    """ARRL Sweepstakes: 2pts/QSO; mults = sections (all-band, max 84)."""
    notes = []
    sections: set[str] = set()
    qso_count = 0

    for q in _non_dupe_qsos(log):
        qso_count += 1
        sec = _extract_ss_section(q.srx)
        if sec:
            sections.add(sec)

    qso_points = qso_count * 2
    multipliers = len(sections)
    mult_detail = f"{multipliers} sections"

    if multipliers == 84:
        notes.append("Clean sweep!")

    return ScoreResult(
        qso_points=qso_points,
        multipliers=multipliers,
        total_score=qso_points * multipliers,
        mult_detail=mult_detail,
        scoring_notes=notes,
    )


# ── NAQP ─────────────────────────────────────────────────────────────


def _score_naqp(log: ContestLog, contest_def: ContestDefinition) -> ScoreResult:
    """NAQP: 1pt/QSO; mults = states/provinces/DX (per-band)."""
    notes = []
    mults_per_band: dict[str, set[str]] = defaultdict(set)

    qso_count = 0
    for q in _non_dupe_qsos(log):
        qso_count += 1
        srx = q.srx.strip().upper()
        if srx:
            mults_per_band[q.band].add(srx)

    qso_points = qso_count
    multipliers = sum(len(v) for v in mults_per_band.values())
    mult_detail = f"{multipliers} mults across {len(mults_per_band)} bands"

    return ScoreResult(
        qso_points=qso_points,
        multipliers=multipliers,
        total_score=qso_points * multipliers,
        mult_detail=mult_detail,
        scoring_notes=notes,
    )


# ── ARRL DX ──────────────────────────────────────────────────────────


def _score_arrl_dx(log: ContestLog, contest_def: ContestDefinition) -> ScoreResult:
    """ARRL DX: 3pts/QSO; mults = countries or states (per-band)."""
    notes = []
    is_wve = _is_wve_station(log.station_country)
    mults_per_band: dict[str, set[str]] = defaultdict(set)

    qso_count = 0
    for q in _non_dupe_qsos(log):
        qso_count += 1
        if is_wve:
            # W/VE station: mults are DXCC countries
            if q.country:
                mults_per_band[q.band].add(q.country)
        else:
            # DX station: mults are US states + VE provinces from srx
            srx = q.srx.strip().upper()
            if srx:
                mults_per_band[q.band].add(srx)

    qso_points = qso_count * 3
    multipliers = sum(len(v) for v in mults_per_band.values())
    mult_type = "countries" if is_wve else "states/provinces"
    mult_detail = f"{multipliers} {mult_type} across {len(mults_per_band)} bands"

    return ScoreResult(
        qso_points=qso_points,
        multipliers=multipliers,
        total_score=qso_points * multipliers,
        mult_detail=mult_detail,
        scoring_notes=notes,
    )


# ── ARRL RTTY Roundup ───────────────────────────────────────────────


def _score_arrl_rtty(log: ContestLog, contest_def: ContestDefinition) -> ScoreResult:
    """ARRL RTTY Roundup: 1pt/QSO; mults = states + provinces + countries (per-band)."""
    notes = []
    mults_per_band: dict[str, set[str]] = defaultdict(set)

    qso_count = 0
    for q in _non_dupe_qsos(log):
        qso_count += 1
        srx = q.srx.strip().upper()
        if srx:
            mults_per_band[q.band].add(srx)
        elif q.country:
            # DX stations send serial; use country as mult
            mults_per_band[q.band].add(q.country)

    qso_points = qso_count
    multipliers = sum(len(v) for v in mults_per_band.values())
    mult_detail = f"{multipliers} mults across {len(mults_per_band)} bands"

    return ScoreResult(
        qso_points=qso_points,
        multipliers=multipliers,
        total_score=qso_points * multipliers,
        mult_detail=mult_detail,
        scoring_notes=notes,
    )


# ── Generic fallback ─────────────────────────────────────────────────


def _score_generic(log: ContestLog, contest_def: ContestDefinition) -> ScoreResult:
    """Fallback scorer: QSO count only."""
    qso_count = len(_non_dupe_qsos(log))
    return ScoreResult(
        qso_points=qso_count,
        multipliers=0,
        total_score=qso_count,
        mult_detail="No multiplier formula available",
        scoring_notes=["Generic scoring: QSO count only, no contest-specific rules applied"],
    )
