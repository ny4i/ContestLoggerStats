"""Tests for dupe detector."""

from datetime import datetime

from stats.contest_data import QSO
from stats.dupe_detector import find_dupes


def _q(call, band="20m", mode_group="PH", pota_ref="", my_pota_ref="",
       time=datetime(2026, 4, 18, 14, 32, 5)):
    """Factory for minimal QSO with optional POTA refs."""
    return QSO(
        call=call, band=band, mode=mode_group, mode_group=mode_group,
        freq_mhz=14.200, datetime_utc=time,
        operator="NY4I", rst_sent="59", rst_rcvd="59", stx="", srx="",
        pota_ref=pota_ref, my_pota_ref=my_pota_ref,
    )


class TestFindDupes:
    def test_no_dupes(self, sample_qsos):
        # W1AW on 20m CW, VE3RL on 20m PH, W1AW on 40m CW — all unique
        count = find_dupes(sample_qsos[:3], rule="per_band_mode")
        assert count == 0
        assert not any(q.is_dupe for q in sample_qsos[:3])

    def test_dupe_same_band_mode(self, sample_qsos):
        # QSOs 0 and 3 are both W1AW on 20m CW
        count = find_dupes(sample_qsos, rule="per_band_mode")
        assert count == 1
        assert not sample_qsos[0].is_dupe
        assert sample_qsos[3].is_dupe

    def test_dupe_per_band(self, sample_qsos):
        # per_band rule: W1AW on 20m appears in QSO 0 and 3
        # Reset is_dupe first
        for q in sample_qsos:
            q.is_dupe = False
        count = find_dupes(sample_qsos, rule="per_band")
        assert count == 1
        assert sample_qsos[3].is_dupe

    def test_different_band_not_dupe(self, sample_qsos):
        # W1AW on 20m and 40m should not be dupes
        for q in sample_qsos:
            q.is_dupe = False
        find_dupes(sample_qsos, rule="per_band_mode")
        assert not sample_qsos[2].is_dupe  # W1AW 40m CW

    def test_all_band_mode(self, sample_qsos):
        # all_band_mode: any repeat of same callsign is dupe
        for q in sample_qsos:
            q.is_dupe = False
        count = find_dupes(sample_qsos, rule="all_band_mode")
        # W1AW appears at indices 0, 2, 3 — indices 2 and 3 are dupes
        assert count == 2
        assert not sample_qsos[0].is_dupe  # first W1AW
        assert not sample_qsos[1].is_dupe  # VE3RL (unique)
        assert sample_qsos[2].is_dupe      # W1AW 40m (dupe)
        assert sample_qsos[3].is_dupe      # W1AW 20m (dupe)


class TestPotaDupes:
    def test_nfer_hunt_splits_not_dupes(self):
        # Same hunter, same band/mode/timestamp, 3 different park refs:
        # hunter worked an N-fer activator at 3 parks simultaneously.
        qs = [
            _q("K5CIP", pota_ref="US-1111"),
            _q("K5CIP", pota_ref="US-2222"),
            _q("K5CIP", pota_ref="US-3333"),
        ]
        count = find_dupes(qs, rule="per_band_mode")
        assert count == 0
        assert not any(q.is_dupe for q in qs)

    def test_nfer_activator_splits_not_dupes(self):
        # Activator's log: same hunter, 3 different MY_POTA_REF (N-fer activation).
        qs = [
            _q("K5CIP", my_pota_ref="US-1111"),
            _q("K5CIP", my_pota_ref="US-2222"),
        ]
        count = find_dupes(qs, rule="per_band_mode")
        assert count == 0

    def test_same_refs_repeated_still_dupe(self):
        # Identical ref pair repeated — genuine dupe (logger bug or actual double-work).
        qs = [
            _q("K5CIP", pota_ref="US-1111"),
            _q("K5CIP", pota_ref="US-1111"),
        ]
        count = find_dupes(qs, rule="per_band_mode")
        assert count == 1
        assert qs[1].is_dupe

    def test_home_then_park_not_dupe(self):
        # User explicitly confirmed: worked once without POTA context, again at a park → not dupe.
        qs = [
            _q("K5CIP", pota_ref=""),
            _q("K5CIP", pota_ref="US-1111"),
        ]
        count = find_dupes(qs, rule="per_band_mode")
        assert count == 0

    def test_non_pota_log_unchanged(self):
        # Both refs empty on every QSO → behavior identical to pre-POTA rule.
        qs = [
            _q("W1AW"),
            _q("W1AW"),  # dupe
            _q("VE3RL"),
        ]
        count = find_dupes(qs, rule="per_band_mode")
        assert count == 1
        assert qs[1].is_dupe
        assert not qs[0].is_dupe
        assert not qs[2].is_dupe
