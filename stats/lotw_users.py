"""LOTW user list loader: find, download, and parse the LoTW user activity CSV."""

import os
import urllib.request

LOTW_URL = "https://lotw.arrl.org/lotw-user-activity.csv"
LOTW_FILENAME = "lotw-user-activity.csv"
CACHE_DIR = os.path.expanduser("~/.publicLogProcessor")


def find_lotw_users(cli_path: str | None = None) -> str | None:
    """Return lotw-user-activity.csv path from ./databases/ (or CLI override)."""
    from .paths import find_data_file
    return find_data_file(LOTW_FILENAME, cli_path)


def download_lotw_users(dest_dir: str) -> str:
    """Download lotw-user-activity.csv to dest_dir, return path."""
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, LOTW_FILENAME)
    urllib.request.urlretrieve(LOTW_URL, dest)
    return dest


def load_lotw_users(path: str) -> set[str]:
    """Parse lotw-user-activity.csv, return uppercase callsign set.

    CSV format: callsign,YYYY-MM-DD,HH:MM:SS (no header row).
    """
    calls = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if parts:
                calls.add(parts[0].strip().upper())
    return calls
