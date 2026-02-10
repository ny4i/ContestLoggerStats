"""LCR (Log Checking Report) parser.

Extracted from analyze_lcr.py. Supports HTML, plain text, and PDF LCR files.
"""

import os
import re
import subprocess
import sys


def extract_text_from_pdf(filepath: str) -> str:
    """Extract plain text from a PDF file."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        return '\n'.join(page.extract_text() or '' for page in reader.pages)
    except ImportError:
        pass

    try:
        result = subprocess.run(
            ['pdftotext', '-layout', filepath, '-'],
            capture_output=True, text=True, check=True,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    print('ERROR: Cannot read PDF. Install pypdf (pip install pypdf) '
          'or pdftotext (brew install poppler).', file=sys.stderr)
    sys.exit(1)


def read_lcr_text(filepath: str) -> str:
    """Read an LCR file (HTML or PDF) and return plain text."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(filepath)

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    return re.sub(r'<[^>]+>', '', content)


def parse_lcr(filepath: str) -> list[dict]:
    """Parse LCR file. Returns list of error dicts."""
    text = read_lcr_text(filepath)

    section_map = {
        r'\*+\s*Incorrect Call\s*\*+': 'incorrect_call',
        r'\*+\s*Not In Log\s*\*+': 'not_in_log',
        r'\*+\s*Incorrect Exchange Information\s*\*+': 'incorrect_exchange',
        r'\*+\s*Out Of Band\s*\*+': 'out_of_band',
    }

    error_line_re = re.compile(
        r'(\d+)\s+'
        r'(PH|CW|RY)\s+'
        r'(\d{4}-\d{2}-\d{2})\s+'
        r'(\d{4})\s+'
        r'(\S+)\s+'
        r'(\S+)\s+'
        r'(\S+)\s+'
        r'(\S+)'
        r'(.*)'
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


def match_error_to_qso(error: dict, qsos) -> object | None:
    """Find the QSO matching an LCR error by date, time, and frequency."""
    error_date_str = error['date'].replace('-', '')
    error_time = error['time']
    error_freq_mhz = error['freq_khz'] / 1000.0
    error_mins = int(error_time[:2]) * 60 + int(error_time[2:])

    best = None
    best_score = float('inf')

    for qso in qsos:
        qso_date = qso.datetime_utc.strftime('%Y%m%d')
        if qso_date != error_date_str:
            continue

        qso_mins = qso.datetime_utc.hour * 60 + qso.datetime_utc.minute
        time_diff = abs(error_mins - qso_mins)
        if time_diff > 2:
            continue

        freq_diff = abs(qso.freq_mhz - error_freq_mhz) * 1000
        if freq_diff > 5:
            continue

        score = time_diff + freq_diff
        if score < best_score:
            best_score = score
            best = qso

    return best
