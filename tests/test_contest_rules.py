"""Tests for contest rules: loading, exchange validation, and scoring."""

import pytest
from datetime import datetime

from stats.contest_data import QSO, ContestLog
from stats.contest_rules import (
    load_contest_definitions, lookup_contest,
    validate_exchanges, estimate_score,
)


@pytest.fixture(scope="module")
def definitions():
    return load_contest_definitions()


class TestLoadContests:
    def test_load_contests_json(self, definitions):
        assert len(definitions) == 14

    def test_all_expected_keys(self, definitions):
        expected = {
            "CQ-WW-SSB", "CQ-WW-CW", "CQ-WPX-SSB", "CQ-WPX-CW",
            "ARRL-FIELD-DAY", "WFD", "ARRL-SS-CW", "ARRL-SS-SSB",
            "NAQP-CW", "NAQP-SSB", "NAQP-RTTY",
            "ARRL-DX-CW", "ARRL-DX-SSB", "ARRL-RTTY",
        }
        assert set(definitions.keys()) == expected

    def test_lookup_known_contest(self, definitions):
        cdef = lookup_contest("CQ-WW-SSB", definitions)
        assert cdef is not None
        assert cdef.name == "CQ World Wide DX Contest SSB"
        assert cdef.dupe_rule == "per_band_mode"
        assert cdef.scoring_type == "cq_ww"

    def test_lookup_unknown_contest(self, definitions):
        assert lookup_contest("MADE-UP-CONTEST", definitions) is None


def _make_qso(call="W1AW", band="20m", mode_group="CW", srx="5",
              country="", continent="", cq_zone=0, prefix="W1"):
    return QSO(
        call=call, band=band, mode="CW", mode_group=mode_group,
        freq_mhz=14.035, datetime_utc=datetime(2025, 6, 28, 18, 0),
        operator="OP1", rst_sent="599", rst_rcvd="599",
        stx="5", srx=srx, country=country, continent=continent,
        cq_zone=cq_zone, prefix=prefix,
    )


def _make_log(qsos, station_call="W4TA", station_country="United States",
              station_continent="NA"):
    return ContestLog(
        station_call=station_call, locator="EL98",
        contest_name="Test", qsos=qsos, operators=["OP1"],
        start_time=datetime(2025, 6, 28, 18, 0),
        end_time=datetime(2025, 6, 28, 20, 0),
        contest_id="TEST", station_country=station_country,
        station_continent=station_continent,
    )


class TestExchangeValidation:
    def test_validate_exchange_cqww_valid(self, definitions):
        cdef = lookup_contest("CQ-WW-SSB", definitions)
        qsos = [_make_qso(srx="5"), _make_qso(srx="33")]
        validate_exchanges(qsos, cdef)
        assert all(q.exchange_error == "" for q in qsos)

    def test_validate_exchange_cqww_invalid(self, definitions):
        cdef = lookup_contest("CQ-WW-SSB", definitions)
        qsos = [_make_qso(srx="ABC")]
        validate_exchanges(qsos, cdef)
        assert qsos[0].exchange_error != ""

    def test_validate_exchange_fd_valid(self, definitions):
        cdef = lookup_contest("ARRL-FIELD-DAY", definitions)
        qsos = [_make_qso(srx="3A WCF"), _make_qso(srx="1D CT")]
        validate_exchanges(qsos, cdef)
        assert all(q.exchange_error == "" for q in qsos)

    def test_validate_exchange_fd_invalid(self, definitions):
        cdef = lookup_contest("ARRL-FIELD-DAY", definitions)
        qsos = [_make_qso(srx="WCF")]
        validate_exchanges(qsos, cdef)
        assert qsos[0].exchange_error != ""

    def test_validate_exchange_empty(self, definitions):
        cdef = lookup_contest("CQ-WW-CW", definitions)
        qsos = [_make_qso(srx="")]
        validate_exchanges(qsos, cdef)
        assert "Empty" in qsos[0].exchange_error

    def test_dupes_skipped(self, definitions):
        cdef = lookup_contest("CQ-WW-SSB", definitions)
        qsos = [_make_qso(srx="BAD")]
        qsos[0].is_dupe = True
        validate_exchanges(qsos, cdef)
        assert qsos[0].exchange_error == ""


class TestScoring:
    def test_score_field_day(self, definitions):
        cdef = lookup_contest("ARRL-FIELD-DAY", definitions)
        qsos = [
            _make_qso(mode_group="CW", srx="3A WCF"),   # 2 pts
            _make_qso(mode_group="DIG", srx="1D CT"),    # 2 pts
            _make_qso(mode_group="PH", srx="2A NFL"),    # 1 pt
        ]
        log = _make_log(qsos)
        result = estimate_score(log, cdef)
        assert result.qso_points == 5
        assert result.multipliers == 1
        assert result.total_score == 5

    def test_score_field_day_dupes_excluded(self, definitions):
        cdef = lookup_contest("ARRL-FIELD-DAY", definitions)
        qsos = [
            _make_qso(mode_group="CW", srx="3A WCF"),
            _make_qso(mode_group="CW", srx="3A WCF"),
        ]
        qsos[1].is_dupe = True
        log = _make_log(qsos)
        result = estimate_score(log, cdef)
        assert result.qso_points == 2

    def test_score_cq_ww(self, definitions):
        cdef = lookup_contest("CQ-WW-CW", definitions)
        qsos = [
            # Same continent (NA-NA, different country) = 2 pts
            _make_qso(call="VE3RL", band="20m", srx="4", country="Canada",
                      continent="NA", cq_zone=4, prefix="VE3"),
            # Different continent = 3 pts
            _make_qso(call="G3ABC", band="20m", srx="14", country="England",
                      continent="EU", cq_zone=14, prefix="G3"),
            # Different continent on 40m = 3 pts
            _make_qso(call="JA1ABC", band="40m", srx="25", country="Japan",
                      continent="AS", cq_zone=25, prefix="JA1"),
        ]
        log = _make_log(qsos)
        result = estimate_score(log, cdef)
        assert result.qso_points == 8  # 2 + 3 + 3
        # Mults: countries per band: 20m has 2 (Canada, England), 40m has 1 (Japan) = 3
        # Zones per band: 20m has 2 (4, 14), 40m has 1 (25) = 3
        assert result.multipliers == 6
        assert result.total_score == 48

    def test_score_generic_fallback(self, definitions):
        # Unknown scoring type falls back to generic
        cdef = lookup_contest("CQ-WW-SSB", definitions)
        # Monkey-patch to test generic
        original = cdef.scoring_type
        cdef.scoring_type = "unknown_type"
        qsos = [_make_qso(), _make_qso(call="VE3RL")]
        log = _make_log(qsos)
        result = estimate_score(log, cdef)
        assert result.qso_points == 2
        assert result.total_score == 2
        cdef.scoring_type = original

    def test_score_arrl_ss(self, definitions):
        cdef = lookup_contest("ARRL-SS-CW", definitions)
        qsos = [
            _make_qso(srx="1 A 72 CT"),
            _make_qso(call="VE3RL", srx="23 B 65 ONE"),
        ]
        log = _make_log(qsos)
        result = estimate_score(log, cdef)
        assert result.qso_points == 4  # 2 QSOs * 2 pts
        assert result.multipliers == 2  # CT, ONE
        assert result.total_score == 8

    def test_score_naqp(self, definitions):
        cdef = lookup_contest("NAQP-CW", definitions)
        qsos = [
            _make_qso(band="20m", srx="FL"),
            _make_qso(call="VE3RL", band="20m", srx="ON"),
            _make_qso(band="40m", srx="FL"),  # FL on different band = new mult
        ]
        log = _make_log(qsos)
        result = estimate_score(log, cdef)
        assert result.qso_points == 3  # 1 pt each
        assert result.multipliers == 3  # FL(20m), ON(20m), FL(40m)
        assert result.total_score == 9
