"""Tests for MASTER.SCP loader."""

import os
import tempfile
import pytest

from stats.master_scp import load_master_scp, find_master_scp


class TestLoadMasterScp:
    def test_basic_parse(self, tmp_path):
        scp = tmp_path / "MASTER.SCP"
        scp.write_text("W1AW\nVE3RL\nDL1ABC\n")
        result = load_master_scp(str(scp))
        assert result == {"W1AW", "VE3RL", "DL1ABC"}

    def test_skips_comments(self, tmp_path):
        scp = tmp_path / "MASTER.SCP"
        scp.write_text("# Comment line\n// Another comment\nW1AW\nVE3RL\n")
        result = load_master_scp(str(scp))
        assert result == {"W1AW", "VE3RL"}

    def test_skips_blank_lines(self, tmp_path):
        scp = tmp_path / "MASTER.SCP"
        scp.write_text("W1AW\n\n\nVE3RL\n\n")
        result = load_master_scp(str(scp))
        assert result == {"W1AW", "VE3RL"}

    def test_uppercases_calls(self, tmp_path):
        scp = tmp_path / "MASTER.SCP"
        scp.write_text("w1aw\nve3rl\n")
        result = load_master_scp(str(scp))
        assert result == {"W1AW", "VE3RL"}

    def test_strips_whitespace(self, tmp_path):
        scp = tmp_path / "MASTER.SCP"
        scp.write_text("  W1AW  \n  VE3RL\t\n")
        result = load_master_scp(str(scp))
        assert result == {"W1AW", "VE3RL"}

    def test_empty_file(self, tmp_path):
        scp = tmp_path / "MASTER.SCP"
        scp.write_text("")
        result = load_master_scp(str(scp))
        assert result == set()


class TestFindMasterScp:
    def test_cli_path_found(self, tmp_path):
        scp = tmp_path / "custom.scp"
        scp.write_text("W1AW\n")
        assert find_master_scp(str(scp)) == str(scp)

    def test_cli_path_not_found(self, tmp_path):
        result = find_master_scp(str(tmp_path / "nonexistent.scp"))
        # Falls through to check cwd and cache, which also won't have it
        # Result depends on whether MASTER.SCP exists elsewhere
        # Just verify it doesn't crash
        assert result is None or os.path.isfile(result)

    def test_none_when_no_file_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Override CACHE_DIR to a nonexistent location
        import stats.master_scp as mod
        monkeypatch.setattr(mod, "CACHE_DIR", str(tmp_path / "no_cache"))
        assert find_master_scp() is None

    def test_finds_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        scp = tmp_path / "MASTER.SCP"
        scp.write_text("W1AW\n")
        assert find_master_scp() == os.path.join(".", "MASTER.SCP")
