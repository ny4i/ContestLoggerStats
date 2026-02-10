"""Tests for dupe detector."""

from stats.dupe_detector import find_dupes


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
