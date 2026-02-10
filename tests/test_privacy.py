"""Tests for privacy/anonymization."""

from datetime import datetime
from stats.privacy import anonymize, apply_privacy
from stats.contest_data import QSO


class TestAnonymize:
    def test_mapping(self):
        mapping, anon_list = anonymize(["NY4I", "K2BHS", "K4OB"])
        assert len(mapping) == 3
        assert mapping["K2BHS"] == "Op1"  # Sorted alphabetically
        assert mapping["K4OB"] == "Op2"
        assert mapping["NY4I"] == "Op3"
        assert anon_list == ["Op1", "Op2", "Op3"]


class TestApplyPrivacy:
    def test_replaces_operator(self):
        qso = QSO(
            call="W1AW", band="20m", mode="CW", mode_group="CW",
            freq_mhz=14.035, datetime_utc=datetime(2025, 6, 28, 18, 0),
            operator="NY4I", rst_sent="599", rst_rcvd="599",
            stx="3A WCF", srx="1A CT",
        )
        mapping = {"NY4I": "Op1"}
        apply_privacy([qso], mapping)
        assert qso.operator == "Op1"

    def test_unmapped_operator_unchanged(self):
        qso = QSO(
            call="W1AW", band="20m", mode="CW", mode_group="CW",
            freq_mhz=14.035, datetime_utc=datetime(2025, 6, 28, 18, 0),
            operator="UNKNOWN", rst_sent="599", rst_rcvd="599",
            stx="", srx="",
        )
        apply_privacy([qso], {"NY4I": "Op1"})
        assert qso.operator == "UNKNOWN"
