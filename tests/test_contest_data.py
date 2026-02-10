"""Tests for contest data model."""

from datetime import datetime
from stats.contest_data import QSO, ContestLog


class TestQSO:
    def test_default_annotations(self):
        q = QSO(
            call="W1AW", band="20m", mode="CW", mode_group="CW",
            freq_mhz=14.035, datetime_utc=datetime(2025, 6, 28, 18, 0),
            operator="NY4I", rst_sent="599", rst_rcvd="599",
            stx="3A WCF", srx="1A CT",
        )
        assert not q.is_dupe
        assert q.lcr_error is None
        assert q.country == ""


class TestContestLog:
    def test_active_bands(self, sample_qsos):
        log = ContestLog(
            station_call="W4TA", locator="EL87PS",
            contest_name="Test", qsos=sample_qsos,
            operators=["NY4I", "K2BHS", "K4OB"],
            start_time=datetime(2025, 6, 28, 18, 0),
            end_time=datetime(2025, 6, 29, 18, 0),
        )
        bands = log.active_bands
        assert "20m" in bands
        assert "40m" in bands
        assert "10m" not in bands
        # Should be in frequency order
        assert bands.index("40m") < bands.index("20m")

    def test_active_mode_groups(self, sample_qsos):
        log = ContestLog(
            station_call="W4TA", locator="EL87PS",
            contest_name="Test", qsos=sample_qsos,
            operators=["NY4I", "K2BHS"],
            start_time=datetime(2025, 6, 28, 18, 0),
            end_time=datetime(2025, 6, 29, 18, 0),
        )
        groups = log.active_mode_groups
        assert "CW" in groups
        assert "PH" in groups
