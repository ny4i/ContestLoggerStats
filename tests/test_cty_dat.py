"""Tests for CTY.DAT parser and callsign lookup.

Validates against known callsign/country/zone mappings from SH5 reference.
"""

import pytest
from stats.cty_dat import (
    CtyDat, strip_portable, extract_wpx_prefix,
    get_us_call_area_zone, get_us_call_area_grid,
)


class TestCtyDatLoad:
    def test_loads_countries(self, cty):
        assert cty.country_count > 300

    def test_lookup_returns_valid(self, cty):
        result = cty.lookup("W1AW")
        assert result.is_valid()


class TestCallsignLookup:
    """Validate callsign lookups against known SH5/cty.dat values."""

    def test_us_callsign(self, cty):
        result = cty.lookup("W1AW")
        assert result.name == "United States"
        assert result.continent == "NA"
        assert result.cq_zone == 5  # W1 = Zone 5

    def test_us_w4(self, cty):
        result = cty.lookup("W4TA")
        assert result.name == "United States"
        assert result.cq_zone == 5  # W4 = Zone 5

    def test_us_w6(self, cty):
        result = cty.lookup("K6ABC")
        assert result.name == "United States"
        assert result.cq_zone == 3  # W6 = Zone 3

    def test_us_w0(self, cty):
        result = cty.lookup("W0PF")
        assert result.name == "United States"
        assert result.cq_zone == 4  # W0 = Zone 4

    def test_canada(self, cty):
        result = cty.lookup("VE3RL")
        assert result.name == "Canada"
        assert result.continent == "NA"

    def test_canada_ve2(self, cty):
        result = cty.lookup("VE2CWI")
        assert result.name == "Canada"

    def test_japan(self, cty):
        result = cty.lookup("JA1ABC")
        assert result.name == "Japan"
        assert result.continent == "AS"
        assert result.cq_zone == 25

    def test_germany(self, cty):
        result = cty.lookup("DL1ABC")
        assert result.name == "Fed. Rep. of Germany"
        assert result.continent == "EU"
        assert result.cq_zone == 14

    def test_england(self, cty):
        result = cty.lookup("G3ABC")
        assert result.name == "England"
        assert result.continent == "EU"

    def test_hawaii(self, cty):
        result = cty.lookup("KH6ABC")
        assert result.name == "Hawaii"
        assert result.cq_zone == 31

    def test_alaska(self, cty):
        result = cty.lookup("KL7ABC")
        assert result.name == "Alaska"
        assert result.cq_zone == 1

    def test_unknown_callsign(self, cty):
        # QQ prefix is not assigned to any DXCC entity
        result = cty.lookup("QQ1ZZZ")
        assert not result.is_valid()

    def test_empty_callsign(self, cty):
        result = cty.lookup("")
        assert not result.is_valid()

    def test_australia(self, cty):
        result = cty.lookup("VK3ABC")
        assert result.name == "Australia"
        assert result.continent == "OC"

    def test_brazil(self, cty):
        result = cty.lookup("PY1ABC")
        assert result.name == "Brazil"
        assert result.continent == "SA"


class TestPortableStripping:
    def test_no_portable(self):
        assert strip_portable("W1AW") == "W1AW"

    def test_suffix_portable(self):
        assert strip_portable("W1AW/P") == "W1AW"

    def test_prefix_portable(self):
        assert strip_portable("I9/NY4I") == "NY4I"

    def test_suffix_number(self):
        assert strip_portable("W6ABC/7") == "W6ABC"


class TestWPXPrefix:
    def test_standard(self):
        assert extract_wpx_prefix("W1AW") == "W1"

    def test_dl(self):
        assert extract_wpx_prefix("DL1ABC") == "DL1"

    def test_ja(self):
        assert extract_wpx_prefix("JA1XYZ") == "JA1"

    def test_no_digit(self):
        assert extract_wpx_prefix("GXYZ") == "GXYZ"

    def test_portable(self):
        assert extract_wpx_prefix("W6ABC/7") == "W6"


class TestUSCallAreaZone:
    def test_w1_zone5(self):
        assert get_us_call_area_zone("W1AW") == 5

    def test_w6_zone3(self):
        assert get_us_call_area_zone("K6ABC") == 3

    def test_w0_zone4(self):
        assert get_us_call_area_zone("W0PF") == 4

    def test_kh6_zone31(self):
        assert get_us_call_area_zone("KH6ABC") == 31

    def test_kl7_zone1(self):
        assert get_us_call_area_zone("KL7ABC") == 1

    def test_non_us(self):
        assert get_us_call_area_zone("DL1ABC") == -1


class TestUSCallAreaGrid:
    def test_w4(self):
        assert get_us_call_area_grid("W4TA") == "EL83"

    def test_w1(self):
        assert get_us_call_area_grid("W1AW") == "FN43"

    def test_non_us(self):
        assert get_us_call_area_grid("DL1ABC") is None


class TestLongitudeConvention:
    """Verify that CTY.DAT longitude sign is correctly handled."""

    def test_us_western_longitude(self, cty):
        result = cty.lookup("W4TA")
        # US should have negative longitude (western hemisphere)
        assert result.longitude < 0, f"US longitude should be negative, got {result.longitude}"

    def test_japan_eastern_longitude(self, cty):
        result = cty.lookup("JA1ABC")
        # Japan should have positive longitude (eastern hemisphere)
        assert result.longitude > 0, f"Japan longitude should be positive, got {result.longitude}"

    def test_germany_positive_longitude(self, cty):
        result = cty.lookup("DL1ABC")
        # Germany should have small positive longitude
        assert result.longitude > 0, f"Germany longitude should be positive, got {result.longitude}"

    def test_brazil_western_longitude(self, cty):
        result = cty.lookup("PY1ABC")
        # Brazil should have negative longitude
        assert result.longitude < 0, f"Brazil longitude should be negative, got {result.longitude}"
