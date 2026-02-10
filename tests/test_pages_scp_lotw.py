"""Tests for MASTER.SCP and LOTW page generators."""

from datetime import datetime
import pytest

from stats.contest_data import QSO, ContestLog
from stats.html.pages import prepare_not_in_master, prepare_lotw_check


@pytest.fixture
def contest_log():
    qsos = [
        QSO(call="W1AW", band="20m", mode="CW", mode_group="CW",
            freq_mhz=14.035, datetime_utc=datetime(2025, 6, 28, 18, 5),
            operator="OP1", rst_sent="599", rst_rcvd="599",
            stx="3A WCF", srx="1A CT", country="United States"),
        QSO(call="VE3RL", band="20m", mode="SSB", mode_group="PH",
            freq_mhz=14.200, datetime_utc=datetime(2025, 6, 28, 18, 10),
            operator="OP1", rst_sent="59", rst_rcvd="59",
            stx="3A WCF", srx="3A ONE", country="Canada"),
        QSO(call="DL1ABC", band="40m", mode="CW", mode_group="CW",
            freq_mhz=7.035, datetime_utc=datetime(2025, 6, 28, 19, 0),
            operator="OP1", rst_sent="599", rst_rcvd="599",
            stx="3A WCF", srx="DOK", country="Germany"),
        QSO(call="ZZZZZZ", band="20m", mode="CW", mode_group="CW",
            freq_mhz=14.035, datetime_utc=datetime(2025, 6, 28, 20, 0),
            operator="OP1", rst_sent="599", rst_rcvd="599",
            stx="3A WCF", srx=""),
    ]
    return ContestLog(
        station_call="W4TA", locator="EM73", contest_name="TEST",
        qsos=qsos, operators=["OP1"],
        start_time=qsos[0].datetime_utc, end_time=qsos[-1].datetime_utc,
        station_lat=33.0, station_lon=-84.0,
    )


class TestPrepareNotInMaster:
    def test_with_scp_calls(self, contest_log):
        scp = {"W1AW", "VE3RL", "DL1ABC"}
        result = prepare_not_in_master(contest_log, scp_calls=scp)
        # ZZZZZZ is not in SCP
        calls_in_rows = [row[0] for row in result['rows']]
        assert "ZZZZZZ" in calls_in_rows
        assert "W1AW" not in calls_in_rows
        assert "MASTER.SCP" in result['description']

    def test_without_scp_falls_back_to_cty(self, contest_log):
        result = prepare_not_in_master(contest_log)
        # ZZZZZZ has no country set, so it should appear
        calls_in_rows = [row[0] for row in result['rows']]
        assert "ZZZZZZ" in calls_in_rows
        assert "cty.dat" in result['description']

    def test_all_calls_in_scp(self, contest_log):
        scp = {"W1AW", "VE3RL", "DL1ABC", "ZZZZZZ"}
        result = prepare_not_in_master(contest_log, scp_calls=scp)
        assert len(result['rows']) == 0

    def test_scp_check_deduplicates(self, contest_log):
        # Add a dupe of W1AW
        dupe = QSO(call="W1AW", band="40m", mode="CW", mode_group="CW",
                    freq_mhz=7.035, datetime_utc=datetime(2025, 6, 28, 21, 0),
                    operator="OP1", rst_sent="599", rst_rcvd="599",
                    stx="3A WCF", srx="1A CT", country="United States")
        dupe.is_dupe = True
        contest_log.qsos.append(dupe)

        scp = {"VE3RL", "DL1ABC", "ZZZZZZ"}
        result = prepare_not_in_master(contest_log, scp_calls=scp)
        w1aw_rows = [r for r in result['rows'] if r[0] == "W1AW"]
        assert len(w1aw_rows) == 1  # Only one entry, not two


class TestPrepareLotwCheck:
    def test_with_lotw_users(self, contest_log):
        lotw = {"W1AW", "DL1ABC"}
        result = prepare_lotw_check(contest_log, lotw_users=lotw)
        assert result['headers'] == ['Callsign', 'In LOTW']
        # Find rows for specific calls
        row_map = {row[0]: row[1] for row in result['rows']}
        assert row_map["W1AW"] == "Yes"
        assert row_map["VE3RL"] == "No"
        assert row_map["DL1ABC"] == "Yes"
        assert "LOTW users" in result['description']

    def test_without_lotw_users(self, contest_log):
        result = prepare_lotw_check(contest_log)
        assert len(result['rows']) == 0
        assert "not available" in result['description']

    def test_all_in_lotw(self, contest_log):
        lotw = {"W1AW", "VE3RL", "DL1ABC", "ZZZZZZ"}
        result = prepare_lotw_check(contest_log, lotw_users=lotw)
        yes_count = sum(1 for row in result['rows'] if row[1] == "Yes")
        assert yes_count == 4
        assert "100.0%" in result['description']

    def test_none_in_lotw(self, contest_log):
        lotw = set()
        result = prepare_lotw_check(contest_log, lotw_users=lotw)
        no_count = sum(1 for row in result['rows'] if row[1] == "No")
        assert no_count == 4
        assert "0 of 4" in result['description']

    def test_rows_sorted_by_callsign(self, contest_log):
        lotw = {"W1AW"}
        result = prepare_lotw_check(contest_log, lotw_users=lotw)
        calls = [row[0] for row in result['rows']]
        assert calls == sorted(calls)
