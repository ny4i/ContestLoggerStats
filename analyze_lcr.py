#!/usr/bin/env python3
"""
LCR Error Analyzer - Compares CQ WW Log Checking Reports against ADIF logs
to identify error patterns by operator, band, time of day, and error type.

Usage: python3 analyze_lcr.py <lcr_file> <adif_file>
"""

import re
import sys
import argparse
from collections import defaultdict


def parse_adif(filepath):
    """Parse ADIF file using tag length specifiers. Returns list of QSO dicts."""
    with open(filepath, 'r') as f:
        content = f.read()

    eoh = content.upper().find('<EOH>')
    if eoh >= 0:
        content = content[eoh + 5:]

    qsos = []
    qso = {}
    tag_re = re.compile(r'<(\w+):(\d+)(?::\w)?>', re.IGNORECASE)
    eor_re = re.compile(r'<EOR>', re.IGNORECASE)

    pos = 0
    while pos < len(content):
        eor = eor_re.match(content, pos)
        if eor:
            if qso:
                qsos.append(qso)
                qso = {}
            pos = eor.end()
            continue

        m = tag_re.match(content, pos)
        if m:
            tag = m.group(1).upper()
            length = int(m.group(2))
            value = content[m.end():m.end() + length]
            qso[tag] = value
            pos = m.end() + length
            continue

        pos += 1

    if qso:
        qsos.append(qso)

    return qsos


def parse_lcr(filepath):
    """Parse LCR HTML file. Returns list of error dicts."""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    text = re.sub(r'<[^>]+>', '', content)

    section_map = {
        r'\*+\s*Incorrect Call\s*\*+': 'incorrect_call',
        r'\*+\s*Not In Log\s*\*+': 'not_in_log',
        r'\*+\s*Incorrect Exchange Information\s*\*+': 'incorrect_exchange',
        r'\*+\s*Out Of Band\s*\*+': 'out_of_band',
    }

    error_line_re = re.compile(
        r'(\d+)\s+'                  # freq kHz
        r'(PH|CW|RY)\s+'            # mode
        r'(\d{4}-\d{2}-\d{2})\s+'   # date
        r'(\d{4})\s+'               # time HHMM
        r'(\S+)\s+'                  # my call
        r'(\S+)\s+'                  # my exchange
        r'(\S+)\s+'                  # their call
        r'(\S+)'                     # their exchange
        r'(.*)'                      # remainder
    )

    errors = []
    current_section = None

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        matched_section = False
        for pattern, section_name in section_map.items():
            if re.search(pattern, line, re.IGNORECASE):
                current_section = section_name
                matched_section = True
                break

        if matched_section:
            continue

        if re.match(r'\*{5,}', line):
            current_section = None
            continue

        if current_section:
            m = error_line_re.match(line)
            if m:
                errors.append({
                    'freq_khz': int(m.group(1)),
                    'mode': m.group(2),
                    'date': m.group(3),
                    'time': m.group(4),
                    'my_call': m.group(5),
                    'my_exchange': m.group(6),
                    'their_call': m.group(7),
                    'their_exchange': m.group(8),
                    'extra': m.group(9).strip(),
                    'error_type': current_section,
                })

    return errors


def freq_to_band(freq_khz):
    bands = [
        (1800, 2000, '160m'), (3500, 4000, '80m'), (7000, 7300, '40m'),
        (14000, 14350, '20m'), (21000, 21450, '15m'), (28000, 29700, '10m'),
    ]
    for low, high, name in bands:
        if low <= freq_khz <= high:
            return name
    return '?'


def match_error_to_qso(error, qsos):
    """Find the ADIF QSO matching an LCR error by date, time, and frequency."""
    error_date = error['date'].replace('-', '')
    error_time = error['time']
    error_freq_mhz = error['freq_khz'] / 1000.0
    error_mins = int(error_time[:2]) * 60 + int(error_time[2:])

    best = None
    best_score = float('inf')

    for qso in qsos:
        if qso.get('QSO_DATE', '') != error_date:
            continue

        qso_time = qso.get('TIME_ON', '')[:4]
        try:
            qso_mins = int(qso_time[:2]) * 60 + int(qso_time[2:])
        except (ValueError, IndexError):
            continue

        time_diff = abs(error_mins - qso_mins)
        if time_diff > 2:
            continue

        try:
            freq_diff = abs(float(qso.get('FREQ', '0')) - error_freq_mhz) * 1000
        except ValueError:
            continue

        if freq_diff > 5:
            continue

        score = time_diff + freq_diff
        if score < best_score:
            best_score = score
            best = qso

    return best


ERROR_LABELS = {
    'incorrect_call': 'Incorrect Call',
    'not_in_log': 'Not In Log',
    'incorrect_exchange': 'Incorrect Exchange',
    'out_of_band': 'Out Of Band',
}

BAND_ORDER = ['160m', '80m', '40m', '20m', '15m', '10m']


def print_header(title):
    print(f'\n{"-" * 70}')
    print(title)
    print('-' * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze CQ WW LCR errors against ADIF log by operator, band, and time.'
    )
    parser.add_argument('lcr', help='Path to LCR file (.lcr)')
    parser.add_argument('adif', help='Path to ADIF file (.adi)')
    args = parser.parse_args()

    qsos = parse_adif(args.adif)
    errors = parse_lcr(args.lcr)

    if not errors:
        print('No errors found in LCR.')
        return

    # Match each error to ADIF QSO for operator info
    for error in errors:
        qso = match_error_to_qso(error, qsos)
        error['operator'] = qso.get('OPERATOR', '?') if qso else 'NO_MATCH'
        error['band'] = freq_to_band(error['freq_khz'])

    # QSO counts from ADIF
    qsos_by_op = defaultdict(int)
    qsos_by_band = defaultdict(int)
    qsos_by_hour = defaultdict(int)
    for q in qsos:
        qsos_by_op[q.get('OPERATOR', '?')] += 1
        qsos_by_band[q.get('BAND', '?').lower()] += 1
        qsos_by_hour[q.get('TIME_ON', '00')[:2]] += 1

    # === Summary ===
    print('=' * 70)
    print('LCR ERROR ANALYSIS REPORT')
    print('=' * 70)
    print(f'  QSOs in log:    {len(qsos)}')
    print(f'  Errors found:   {len(errors)}')
    print(f'  Error rate:     {len(errors)/len(qsos)*100:.1f}%')

    # === By Error Type ===
    print_header('ERRORS BY TYPE')
    by_type = defaultdict(list)
    for e in errors:
        by_type[e['error_type']].append(e)

    for etype, label in ERROR_LABELS.items():
        entries = by_type.get(etype, [])
        if not entries:
            continue
        print(f'\n  {label} ({len(entries)}):')
        for e in entries:
            extra = f'  [{e["extra"]}]' if e['extra'] else ''
            print(f'    {e["date"]} {e["time"]}z  {e["band"]:>4s}  '
                  f'{e["their_call"]:12s}  op={e["operator"]}{extra}')

    # === By Operator ===
    print_header('ERRORS BY OPERATOR')
    by_op = defaultdict(list)
    for e in errors:
        by_op[e['operator']].append(e)

    for op in sorted(by_op):
        op_errors = by_op[op]
        op_qsos = qsos_by_op.get(op, 0)
        rate = (len(op_errors) / op_qsos * 100) if op_qsos > 0 else 0
        print(f'\n  {op}: {len(op_errors)} errors / {op_qsos} QSOs ({rate:.1f}%)')
        op_by_type = defaultdict(int)
        for e in op_errors:
            op_by_type[e['error_type']] += 1
        for etype, label in ERROR_LABELS.items():
            if op_by_type.get(etype, 0):
                print(f'    {label}: {op_by_type[etype]}')

    # === By Band ===
    print_header('ERRORS BY BAND')
    by_band = defaultdict(list)
    for e in errors:
        by_band[e['band']].append(e)

    for band in BAND_ORDER:
        bq = qsos_by_band.get(band, 0)
        errs = by_band.get(band, [])
        if bq == 0 and not errs:
            continue
        rate = (len(errs) / bq * 100) if bq > 0 else 0
        print(f'  {band:>4s}: {len(errs):2d} errors / {bq:3d} QSOs ({rate:5.1f}%)')

    # === By Hour ===
    print_header('ERRORS BY HOUR (UTC)')
    by_hour = defaultdict(list)
    for e in errors:
        by_hour[e['time'][:2]].append(e)

    all_hours = sorted(set(list(by_hour.keys()) + list(qsos_by_hour.keys())))
    for hh in all_hours:
        errs = by_hour.get(hh, [])
        hq = qsos_by_hour.get(hh, 0)
        if hq == 0 and not errs:
            continue
        rate = (len(errs) / hq * 100) if hq > 0 else 0
        bar = '#' * len(errs)
        print(f'  {hh}z: {len(errs):2d} err / {hq:3d} QSOs ({rate:5.1f}%)  {bar}')

    # === By Operator + Band (useful for multi-op) ===
    if len(by_op) > 1:
        print_header('ERRORS BY OPERATOR + BAND')
        for op in sorted(by_op):
            print(f'\n  {op}:')
            op_band = defaultdict(int)
            for e in by_op[op]:
                op_band[e['band']] += 1
            for band in BAND_ORDER:
                if op_band.get(band, 0):
                    print(f'    {band:>4s}: {op_band[band]}')

    # === Detailed List ===
    print_header('DETAILED ERROR LIST')
    print(f'  {"Date":<12s} {"UTC":>4s}  {"Band":>4s} {"FreqkHz":>7s}  '
          f'{"Worked":<12s} {"Type":<20s} {"Operator":<10s} {"Detail"}')
    for e in sorted(errors, key=lambda x: (x['date'], x['time'])):
        print(f'  {e["date"]:<12s} {e["time"]:>4s}  {e["band"]:>4s} {e["freq_khz"]:>7d}  '
              f'{e["their_call"]:<12s} {ERROR_LABELS[e["error_type"]]:<20s} '
              f'{e["operator"]:<10s} {e["extra"]}')

    print()


if __name__ == '__main__':
    main()
