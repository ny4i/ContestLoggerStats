"""MASTER.SCP loader: find, download, and parse the Super Check Partial file."""

import os
import urllib.request

MASTER_SCP_URL = "http://www.supercheckpartial.com/MASTER.SCP"
MASTER_SCP_FILENAME = "MASTER.SCP"
CACHE_DIR = os.path.expanduser("~/.publicLogProcessor")


def find_master_scp(cli_path: str | None = None) -> str | None:
    """Return MASTER.SCP path from ./databases/ (or CLI override)."""
    from .paths import find_data_file
    return find_data_file(MASTER_SCP_FILENAME, cli_path)


def download_master_scp(dest_dir: str) -> str:
    """Download MASTER.SCP to dest_dir, return path."""
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, MASTER_SCP_FILENAME)
    urllib.request.urlretrieve(MASTER_SCP_URL, dest)
    return dest


def load_master_scp(path: str) -> set[str]:
    """Parse MASTER.SCP, return uppercase callsign set.

    Skips lines starting with # or //.
    """
    calls = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            calls.add(line.upper())
    return calls
