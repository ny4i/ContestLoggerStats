"""Tests for LOTW user list loader."""

import os
import pytest

from stats.lotw_users import load_lotw_users, find_lotw_users


class TestLoadLotwUsers:
    def test_basic_parse(self, tmp_path):
        csv = tmp_path / "lotw.csv"
        csv.write_text("W1AW,2024-01-15,12:30:00\nVE3RL,2023-06-01,08:00:00\n")
        result = load_lotw_users(str(csv))
        assert result == {"W1AW", "VE3RL"}

    def test_uppercases_calls(self, tmp_path):
        csv = tmp_path / "lotw.csv"
        csv.write_text("w1aw,2024-01-15,12:30:00\n")
        result = load_lotw_users(str(csv))
        assert result == {"W1AW"}

    def test_skips_blank_lines(self, tmp_path):
        csv = tmp_path / "lotw.csv"
        csv.write_text("W1AW,2024-01-15,12:30:00\n\n\nVE3RL,2023-06-01,08:00:00\n")
        result = load_lotw_users(str(csv))
        assert result == {"W1AW", "VE3RL"}

    def test_empty_file(self, tmp_path):
        csv = tmp_path / "lotw.csv"
        csv.write_text("")
        result = load_lotw_users(str(csv))
        assert result == set()

    def test_strips_whitespace(self, tmp_path):
        csv = tmp_path / "lotw.csv"
        csv.write_text("  W1AW  ,2024-01-15,12:30:00\n")
        result = load_lotw_users(str(csv))
        assert result == {"W1AW"}


class TestFindLotwUsers:
    def test_cli_path_found(self, tmp_path):
        csv = tmp_path / "custom.csv"
        csv.write_text("W1AW,2024-01-15,12:30:00\n")
        assert find_lotw_users(str(csv)) == str(csv)

    def test_none_when_no_file_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import stats.lotw_users as mod
        monkeypatch.setattr(mod, "CACHE_DIR", str(tmp_path / "no_cache"))
        assert find_lotw_users() is None

    def test_finds_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        csv = tmp_path / "lotw-user-activity.csv"
        csv.write_text("W1AW,2024-01-15,12:30:00\n")
        assert find_lotw_users() == os.path.join(".", "lotw-user-activity.csv")
