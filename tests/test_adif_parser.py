"""Tests for ADIF parser."""

import os
import pytest
from stats.adif_parser import parse_adif, parse_adif_raw
from tests.conftest import SAMPLE_ADIF


@pytest.mark.skipif(not os.path.isfile(SAMPLE_ADIF), reason="Sample ADIF not available")
class TestParseRealADIF:
    def test_parse_count(self):
        header, qsos = parse_adif(SAMPLE_ADIF)
        # Raw ADIF has 2355 QSOs; SH5 shows 2323 after its own dedup
        assert len(qsos) == 2355

    def test_header_has_station_callsign(self):
        header, _ = parse_adif(SAMPLE_ADIF)
        assert header.get("STATION_CALLSIGN") == "W4TA"

    def test_header_has_contest_id(self):
        header, _ = parse_adif(SAMPLE_ADIF)
        assert header.get("CONTEST_ID") == "ARRL-FIELD-DAY"

    def test_first_qso_fields(self):
        _, qsos = parse_adif(SAMPLE_ADIF)
        q = qsos[0]
        assert q.call == "W2VL"
        assert q.band == "15m"
        assert q.mode == "FT8"
        assert q.mode_group == "DIG"
        assert q.operator == "KB4DSL"

    def test_ssb_mode_group(self):
        _, qsos = parse_adif(SAMPLE_ADIF)
        ssb_qsos = [q for q in qsos if q.mode == "SSB"]
        assert len(ssb_qsos) > 0
        assert all(q.mode_group == "PH" for q in ssb_qsos)

    def test_cw_mode_group(self):
        _, qsos = parse_adif(SAMPLE_ADIF)
        cw_qsos = [q for q in qsos if q.mode == "CW"]
        assert len(cw_qsos) > 0
        assert all(q.mode_group == "CW" for q in cw_qsos)

    def test_all_qsos_have_datetime(self):
        _, qsos = parse_adif(SAMPLE_ADIF)
        for q in qsos:
            assert q.datetime_utc is not None

    def test_operators_present(self):
        _, qsos = parse_adif(SAMPLE_ADIF)
        operators = {q.operator for q in qsos if q.operator}
        assert len(operators) >= 20  # SH5 shows 26 operators


class TestParseSyntheticADIF:
    def test_simple_record(self, tmp_path):
        adif = tmp_path / "test.adi"
        adif.write_text(
            "<EOH>\n"
            "<CALL:4>W1AW <BAND:3>20m <MODE:2>CW <QSO_DATE:8>20250628 "
            "<TIME_ON:6>180000 <FREQ:6>14.035 <EOR>\n"
        )
        header, qsos = parse_adif(str(adif))
        assert len(qsos) == 1
        assert qsos[0].call == "W1AW"
        assert qsos[0].band == "20m"
        assert qsos[0].mode_group == "CW"

    def test_empty_file(self, tmp_path):
        adif = tmp_path / "empty.adi"
        adif.write_text("<EOH>\n")
        _, qsos = parse_adif(str(adif))
        assert len(qsos) == 0
