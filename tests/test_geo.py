"""Tests for geographic utilities."""

import math
import pytest
from stats.geo import grid_to_latlon, haversine_km, bearing_deg


class TestGridToLatlon:
    def test_4char_grid_fn31(self):
        result = grid_to_latlon("FN31")
        assert result is not None
        lat, lon = result
        # FN31 center: ~41.5°N, ~73°W
        assert 41.0 < lat < 42.0
        assert -74.0 < lon < -72.0

    def test_6char_grid_el87ps(self):
        """W4TA location."""
        result = grid_to_latlon("EL87PS")
        assert result is not None
        lat, lon = result
        # EL87PS: ~27.8°N, ~82.3°W
        assert 27.5 < lat < 28.5
        assert -83.0 < lon < -81.5

    def test_4char_center_offset(self):
        """4-char grids should return center of the 2°×1° square."""
        result = grid_to_latlon("JN38")
        assert result is not None
        lat, lon = result
        # JN38: Field J=9, N=13 -> lon = -180+9*20+3*2+1 = 7, lat = -90+13*10+8+0.5 = 48.5
        assert abs(lon - 7.0) < 0.01
        assert abs(lat - 48.5) < 0.01

    def test_invalid_length(self):
        assert grid_to_latlon("FN3") is None
        assert grid_to_latlon("FN31234") is None

    def test_invalid_field_chars(self):
        assert grid_to_latlon("ZN31") is None  # Z > R
        assert grid_to_latlon("FZ31") is None  # Z > R

    def test_case_insensitive(self):
        upper = grid_to_latlon("EL87PS")
        lower = grid_to_latlon("el87ps")
        assert upper is not None and lower is not None
        assert abs(upper[0] - lower[0]) < 0.001
        assert abs(upper[1] - lower[1]) < 0.001


class TestHaversine:
    def test_same_point(self):
        assert haversine_km(0, 0, 0, 0) == 0.0

    def test_known_distance(self):
        """EL87PS to FN31 ~ approximately 1800-2000 km."""
        el87 = grid_to_latlon("EL87PS")
        fn31 = grid_to_latlon("FN31")
        d = haversine_km(el87[0], el87[1], fn31[0], fn31[1])
        assert 1500 < d < 2200

    def test_quarter_earth(self):
        """Equator to pole should be ~10000 km."""
        d = haversine_km(0, 0, 90, 0)
        assert 9900 < d < 10100


class TestBearing:
    def test_due_north(self):
        b = bearing_deg(0, 0, 10, 0)
        assert abs(b - 0.0) < 0.1

    def test_due_east(self):
        b = bearing_deg(0, 0, 0, 10)
        assert abs(b - 90.0) < 0.1

    def test_due_south(self):
        b = bearing_deg(10, 0, 0, 0)
        assert abs(b - 180.0) < 0.1

    def test_due_west(self):
        b = bearing_deg(0, 10, 0, 0)
        assert abs(b - 270.0) < 0.1

    def test_northeast(self):
        b = bearing_deg(0, 0, 10, 10)
        assert 0 < b < 90
