"""ADIF file parser.

Extracts QSO records and header metadata from ADIF files.
Based on the parser in analyze_lcr.py, enhanced with header parsing
and QSO dataclass output.
"""

import re
from datetime import datetime

from .contest_data import QSO
from .pota_lookup import extract_pota_refs

# Mode group mapping
_MODE_GROUPS = {
    'SSB': 'PH', 'USB': 'PH', 'LSB': 'PH', 'FM': 'PH', 'AM': 'PH',
    'CW': 'CW',
    'FT8': 'DIG', 'FT4': 'DIG', 'RTTY': 'DIG', 'PSK31': 'DIG',
    'PSK63': 'DIG', 'JT65': 'DIG', 'JT9': 'DIG', 'MFSK': 'DIG',
    'OLIVIA': 'DIG', 'CONTESTI': 'DIG', 'DOMINO': 'DIG', 'ROS': 'DIG',
}

_TAG_RE = re.compile(r'<(\w+):(\d+)(?::\w)?>', re.IGNORECASE)
_EOR_RE = re.compile(r'<EOR>', re.IGNORECASE)


def _mode_group(mode: str) -> str:
    """Map a mode to its group: PH, CW, or DIG."""
    return _MODE_GROUPS.get(mode.upper(), 'DIG')


def _parse_datetime(date_str: str, time_str: str) -> datetime:
    """Parse QSO_DATE (YYYYMMDD) + TIME_ON (HHMMSS or HHMM) into datetime."""
    t = time_str.ljust(6, '0')  # Pad to 6 chars if only HHMM
    return datetime.strptime(date_str + t, '%Y%m%d%H%M%S')


def _parse_freq(raw: str) -> float:
    """Parse frequency string to float MHz."""
    try:
        return float(raw)
    except (ValueError, TypeError):
        return 0.0


def parse_adif_raw(filepath: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Parse ADIF file into raw header fields and QSO dicts.

    Returns (header_dict, list_of_qso_dicts) where all keys are uppercase.
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Split header from body
    header_fields = {}
    eoh_pos = content.upper().find('<EOH>')
    if eoh_pos >= 0:
        header_text = content[:eoh_pos]
        body = content[eoh_pos + 5:]
        # Parse header tags
        pos = 0
        while pos < len(header_text):
            m = _TAG_RE.match(header_text, pos)
            if m:
                tag = m.group(1).upper()
                length = int(m.group(2))
                value = header_text[m.end():m.end() + length]
                header_fields[tag] = value
                pos = m.end() + length
            else:
                pos += 1
    else:
        body = content

    qsos = []
    qso: dict[str, str] = {}
    pos = 0
    while pos < len(body):
        eor = _EOR_RE.match(body, pos)
        if eor:
            if qso:
                qsos.append(qso)
                qso = {}
            pos = eor.end()
            continue

        m = _TAG_RE.match(body, pos)
        if m:
            tag = m.group(1).upper()
            length = int(m.group(2))
            value = body[m.end():m.end() + length]
            qso[tag] = value
            pos = m.end() + length
            continue

        pos += 1

    if qso:
        qsos.append(qso)

    return header_fields, qsos


def parse_adif(filepath: str) -> tuple[dict[str, str], list[QSO]]:
    """Parse ADIF file and return (header, list[QSO]).

    Header dict contains MY_GRIDSQUARE, STATION_CALLSIGN, CONTEST_ID, etc.
    The first QSO's header fields are also checked for station metadata.
    """
    header, raw_qsos = parse_adif_raw(filepath)

    # Extract station metadata from header or first QSO
    if raw_qsos:
        first = raw_qsos[0]
        for key in ('STATION_CALLSIGN', 'CONTEST_ID', 'MY_GRIDSQUARE', 'MY_ARRL_SECT',
                    'MY_POTA_REF', 'MY_SIG', 'MY_SIG_INFO'):
            if key not in header and key in first:
                header[key] = first[key]

    qsos = []
    for raw in raw_qsos:
        mode = raw.get('MODE', '').upper()
        band = raw.get('BAND', '').lower()
        date_str = raw.get('QSO_DATE', '')
        time_str = raw.get('TIME_ON', '')

        if not date_str or not band:
            continue

        try:
            dt = _parse_datetime(date_str, time_str)
        except ValueError:
            continue

        my_refs, their_refs = extract_pota_refs(raw)
        qso = QSO(
            call=raw.get('CALL', '').upper(),
            band=band,
            mode=mode,
            mode_group=_mode_group(mode),
            freq_mhz=_parse_freq(raw.get('FREQ', '0')),
            datetime_utc=dt,
            operator=raw.get('OPERATOR', ''),
            rst_sent=raw.get('RST_SENT', ''),
            rst_rcvd=raw.get('RST_RCVD', ''),
            stx=raw.get('STX_STRING', raw.get('STX', '')),
            srx=raw.get('SRX_STRING', raw.get('SRX', '')),
            grid=raw.get('GRIDSQUARE', ''),
            dxcc=int(raw.get('DXCC', '0') or '0'),
            state=raw.get('STATE', ''),
            cnty=raw.get('CNTY', ''),
            pota_ref=",".join(their_refs),
            my_pota_ref=",".join(my_refs),
        )
        qsos.append(qso)

    return header, qsos
