"""Shared test fixtures."""

import os
import pytest
from datetime import datetime

from stats.contest_data import QSO
from stats.cty_dat import CtyDat


CTY_DAT_PATH = os.path.expanduser("~/Library/Application Support/TR4QT/cty.dat")
SAMPLE_ADIF = "/Volumes/shared/ContestFilesForStats/w4ta.ADI"


@pytest.fixture(scope="session")
def cty():
    """Load cty.dat for test session."""
    c = CtyDat()
    assert c.load(CTY_DAT_PATH), f"Failed to load {CTY_DAT_PATH}"
    return c


@pytest.fixture
def sample_qsos():
    """A small set of QSOs for testing."""
    return [
        QSO(call="W1AW", band="20m", mode="CW", mode_group="CW",
            freq_mhz=14.035, datetime_utc=datetime(2025, 6, 28, 18, 5),
            operator="NY4I", rst_sent="599", rst_rcvd="599",
            stx="3A WCF", srx="1A CT"),
        QSO(call="VE3RL", band="20m", mode="SSB", mode_group="PH",
            freq_mhz=14.200, datetime_utc=datetime(2025, 6, 28, 18, 10),
            operator="K2BHS", rst_sent="59", rst_rcvd="59",
            stx="3A WCF", srx="3A ONE"),
        QSO(call="W1AW", band="40m", mode="CW", mode_group="CW",
            freq_mhz=7.035, datetime_utc=datetime(2025, 6, 28, 19, 0),
            operator="NY4I", rst_sent="599", rst_rcvd="599",
            stx="3A WCF", srx="1A CT"),
        QSO(call="W1AW", band="20m", mode="CW", mode_group="CW",
            freq_mhz=14.035, datetime_utc=datetime(2025, 6, 28, 20, 0),
            operator="K4OB", rst_sent="599", rst_rcvd="599",
            stx="3A WCF", srx="1A CT"),
    ]
