"""Tests for POTA park reference lookup and ADIF ref extraction."""

import os

from stats.adif_parser import parse_adif
from stats.pota_lookup import (
    POTALookup,
    extract_pota_refs,
    has_any_pota_refs,
)

FIXTURE_CSV = os.path.join(os.path.dirname(__file__), "data", "pota_parks_test.csv")


# ---------------------------------------------------------------------------
# extract_pota_refs — ADIF field precedence
# ---------------------------------------------------------------------------

def test_extract_their_side_from_sig_info():
    raw = {"SIG": "POTA", "SIG_INFO": "US-3017"}
    mine, their = extract_pota_refs(raw)
    assert mine == []
    assert their == ["US-3017"]


def test_extract_their_side_from_pota_ref():
    raw = {"POTA_REF": "US-3017"}
    mine, their = extract_pota_refs(raw)
    assert their == ["US-3017"]


def test_pota_ref_wins_over_sig_info():
    raw = {"POTA_REF": "US-1111", "SIG": "POTA", "SIG_INFO": "US-9999"}
    _, their = extract_pota_refs(raw)
    assert their == ["US-1111"]


def test_sig_ignored_when_not_pota():
    # SIG=WWFF must NOT cause SIG_INFO to be read as POTA ref
    raw = {"SIG": "WWFF", "SIG_INFO": "KFF-1234"}
    _, their = extract_pota_refs(raw)
    assert their == []


def test_my_side_from_my_sig_info():
    raw = {"MY_SIG": "POTA", "MY_SIG_INFO": "US-1880"}
    mine, _ = extract_pota_refs(raw)
    assert mine == ["US-1880"]


def test_my_pota_ref_wins_over_my_sig_info():
    raw = {
        "MY_POTA_REF": "US-2222",
        "MY_SIG": "POTA",
        "MY_SIG_INFO": "US-3333",
    }
    mine, _ = extract_pota_refs(raw)
    assert mine == ["US-2222"]


def test_nfer_comma_split():
    raw = {"POTA_REF": "US-4321,US-8765"}
    _, their = extract_pota_refs(raw)
    assert their == ["US-4321", "US-8765"]


def test_nfer_space_split():
    raw = {"POTA_REF": "US-4321 US-8765"}
    _, their = extract_pota_refs(raw)
    assert their == ["US-4321", "US-8765"]


def test_has_any_pota_refs_true_sig_only():
    raws = [{"CALL": "W1AW"}, {"SIG": "POTA", "SIG_INFO": "US-3017"}]
    assert has_any_pota_refs(raws) is True


def test_has_any_pota_refs_false():
    raws = [{"CALL": "W1AW"}, {"SIG": "WWFF", "SIG_INFO": "KFF-1234"}]
    assert has_any_pota_refs(raws) is False


# ---------------------------------------------------------------------------
# POTALookup — CSV loading and grid resolution
# ---------------------------------------------------------------------------

def test_load_counts_usable_entries():
    pl = POTALookup()
    count = pl.load(FIXTURE_CSV)
    # 8 fixture rows; MY-0023 (no grid) and AQ-0025 (inactive + 0/0) are dropped
    assert count == 6


def test_grid_for_known_ref():
    pl = POTALookup()
    pl.load(FIXTURE_CSV)
    assert pl.grid_for("US-3017") == "EM86qf"


def test_grid_for_case_insensitive():
    pl = POTALookup()
    pl.load(FIXTURE_CSV)
    assert pl.grid_for("us-3017") == "EM86qf"


def test_grid_for_missing_ref_returns_none():
    pl = POTALookup()
    pl.load(FIXTURE_CSV)
    assert pl.grid_for("XX-9999") is None


def test_missing_grid_park_not_loaded():
    pl = POTALookup()
    pl.load(FIXTURE_CSV)
    assert pl.grid_for("MY-0023") is None


def test_inactive_null_island_park_filtered():
    pl = POTALookup()
    pl.load(FIXTURE_CSV)
    assert pl.grid_for("AQ-0025") is None


def test_long_ref_5_digit_suffix():
    pl = POTALookup()
    pl.load(FIXTURE_CSV)
    assert pl.grid_for("US-10092") == "EM00aa"


def test_first_grid_wins_on_nfer():
    pl = POTALookup()
    pl.load(FIXTURE_CSV)
    assert pl.first_grid(["US-4321", "US-8765"]) == "DM04aa"


def test_first_grid_skips_missing_ref():
    pl = POTALookup()
    pl.load(FIXTURE_CSV)
    # First ref has no entry; second resolves
    assert pl.first_grid(["XX-9999", "US-8765"]) == "DM04ca"


def test_grid_for_field_handles_comma_list():
    pl = POTALookup()
    pl.load(FIXTURE_CSV)
    assert pl.grid_for_field("US-4321,US-8765") == "DM04aa"


# ---------------------------------------------------------------------------
# Integration: parse_adif populates q.pota_ref from SIG/SIG_INFO
# ---------------------------------------------------------------------------

def test_parse_adif_populates_pota_ref(tmp_path):
    adif = tmp_path / "test.adi"
    adif.write_text(
        "<EOH>\n"
        "<CALL:5>K5CIP <BAND:3>20m <MODE:3>SSB "
        "<QSO_DATE:8>20260418 <TIME_ON:4>1356 "
        "<SIG:4>POTA <SIG_INFO:7>US-3017 <EOR>\n"
    )
    _, qsos = parse_adif(str(adif))
    assert len(qsos) == 1
    assert qsos[0].pota_ref == "US-3017"


def test_parse_adif_pota_ref_field_wins(tmp_path):
    adif = tmp_path / "test.adi"
    adif.write_text(
        "<EOH>\n"
        "<CALL:5>K5CIP <BAND:3>20m <MODE:3>SSB "
        "<QSO_DATE:8>20260418 <TIME_ON:4>1356 "
        "<POTA_REF:7>US-1111 <SIG:4>POTA <SIG_INFO:7>US-9999 <EOR>\n"
    )
    _, qsos = parse_adif(str(adif))
    assert qsos[0].pota_ref == "US-1111"


def test_parse_adif_my_pota_fields_lift_into_header(tmp_path):
    adif = tmp_path / "test.adi"
    adif.write_text(
        "<EOH>\n"
        "<CALL:5>K5CIP <BAND:3>20m <MODE:3>SSB "
        "<QSO_DATE:8>20260418 <TIME_ON:4>1356 "
        "<MY_SIG:4>POTA <MY_SIG_INFO:7>US-1880 <EOR>\n"
    )
    header, _ = parse_adif(str(adif))
    assert header.get("MY_SIG") == "POTA"
    assert header.get("MY_SIG_INFO") == "US-1880"


def test_parse_adif_no_pota_leaves_ref_empty(tmp_path):
    adif = tmp_path / "test.adi"
    adif.write_text(
        "<EOH>\n"
        "<CALL:4>W1AW <BAND:3>20m <MODE:2>CW "
        "<QSO_DATE:8>20250628 <TIME_ON:6>180000 <EOR>\n"
    )
    _, qsos = parse_adif(str(adif))
    assert qsos[0].pota_ref == ""
