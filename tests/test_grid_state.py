"""Tests for grid-to-DXCC validation using vuccgrids.dat and cty.csv."""

import os
import pytest

from stats.grid_state import (
    load_vucc_grid_map,
    load_prefix_dxcc_map,
    grid_matches_dxcc,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
VUCC_PATH = os.path.join(DATA_DIR, "vuccgrids_test.dat")
CTY_CSV_PATH = os.path.join(DATA_DIR, "cty_test.csv")


@pytest.fixture(scope="module")
def vucc_map():
    grid_map, updatedate = load_vucc_grid_map(VUCC_PATH)
    return grid_map, updatedate


@pytest.fixture(scope="module")
def prefix_map():
    return load_prefix_dxcc_map(CTY_CSV_PATH)


class TestLoadVuccGridMap:
    def test_loads_grids(self, vucc_map):
        grid_map, _ = vucc_map
        assert len(grid_map) > 0

    def test_updatedate_parsed(self, vucc_map):
        _, updatedate = vucc_map
        assert updatedate == "2025-10-22"

    def test_us_grid_has_entity_291(self, vucc_map):
        grid_map, _ = vucc_map
        assert 291 in grid_map["FN31"]

    def test_canada_grid_has_entity_1(self, vucc_map):
        grid_map, _ = vucc_map
        assert 1 in grid_map["FN03"]

    def test_japan_grid_has_entity_339(self, vucc_map):
        grid_map, _ = vucc_map
        assert 339 in grid_map["QM07"]

    def test_shared_grid_has_multiple_entities(self, vucc_map):
        """FN20 is mapped to both entity 291 (US/NY) and 291 (US/NJ)."""
        grid_map, _ = vucc_map
        assert 291 in grid_map["FN20"]

    def test_missing_file_returns_empty(self):
        grid_map, updatedate = load_vucc_grid_map("/nonexistent/path.dat")
        assert grid_map == {}
        assert updatedate == ""

    def test_grids_uppercased(self, vucc_map):
        """All grid keys should be uppercase."""
        grid_map, _ = vucc_map
        for key in grid_map:
            assert key == key.upper()


class TestLoadPrefixDxccMap:
    def test_loads_entries(self, prefix_map):
        assert len(prefix_map) == 5

    def test_us_prefix(self, prefix_map):
        assert prefix_map["K"] == 291

    def test_canada_prefix(self, prefix_map):
        assert prefix_map["VE"] == 1

    def test_japan_prefix(self, prefix_map):
        assert prefix_map["JA"] == 339

    def test_missing_file_returns_empty(self):
        assert load_prefix_dxcc_map("/nonexistent/path.csv") == {}


class TestGridMatchesDxcc:
    def test_us_grid_matches_us_entity(self, vucc_map):
        grid_map, _ = vucc_map
        assert grid_matches_dxcc("FN31", 291, grid_map) is True

    def test_us_grid_rejects_japan_entity(self, vucc_map):
        grid_map, _ = vucc_map
        assert grid_matches_dxcc("FN31", 339, grid_map) is False

    def test_japan_grid_matches_japan_entity(self, vucc_map):
        grid_map, _ = vucc_map
        assert grid_matches_dxcc("QM07", 339, grid_map) is True

    def test_japan_grid_rejects_us_entity(self, vucc_map):
        grid_map, _ = vucc_map
        assert grid_matches_dxcc("QM07", 291, grid_map) is False

    def test_unknown_grid_returns_none(self, vucc_map):
        grid_map, _ = vucc_map
        assert grid_matches_dxcc("ZZ99", 291, grid_map) is None

    def test_empty_grid_returns_none(self, vucc_map):
        grid_map, _ = vucc_map
        assert grid_matches_dxcc("", 291, grid_map) is None

    def test_zero_dxcc_returns_none(self, vucc_map):
        grid_map, _ = vucc_map
        assert grid_matches_dxcc("FN31", 0, grid_map) is None

    def test_six_char_grid_uses_four_char_key(self, vucc_map):
        grid_map, _ = vucc_map
        assert grid_matches_dxcc("FN31ab", 291, grid_map) is True

    def test_case_insensitive_grid(self, vucc_map):
        grid_map, _ = vucc_map
        assert grid_matches_dxcc("fn31", 291, grid_map) is True
