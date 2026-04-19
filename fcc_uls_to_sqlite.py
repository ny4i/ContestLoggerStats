#!/usr/bin/env python3
"""
fcc_uls_to_sqlite.py
--------------------
Downloads the FCC ULS amateur radio callsign database (l_amat.zip),
extracts the pipe-delimited .dat files, and imports them into a SQLite
database with proper relational tables.

Tables created:
  hd  - License header (call sign, status, dates, service code)
  en  - Entity / licensee (name, address, contact info)
  am  - Amateur-specific fields (operator class, group code, region)

A convenience view `callsigns` joins all three for easy lookup by call sign.

Usage:
  python3 fcc_uls_to_sqlite.py [--output fcc_amateur.db] [--keep-zip] [--workdir .]

Requirements:
  Python 3.7+, no third-party packages needed.

Data source:
  https://data.fcc.gov/download/pub/uls/complete/l_amat.zip
  (mirror: ftp://wirelessftp.fcc.gov/pub/uls/complete/l_amat.zip)
"""

import argparse
import io
import os
import sqlite3
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Primary URL (HTTPS). Falls back to FTP mirror if it fails.
PRIMARY_URL   = "https://data.fcc.gov/download/pub/uls/complete/l_amat.zip"
FALLBACK_URL  = "ftp://wirelessftp.fcc.gov/pub/uls/complete/l_amat.zip"

DEFAULT_DB    = "fcc_amateur.db"
CHUNK_SIZE    = 1024 * 1024  # 1 MB download chunks
BATCH_SIZE    = 5_000        # rows per INSERT batch

# ---------------------------------------------------------------------------
# Table schemas
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA temp_store   = MEMORY;

-- HD: License header record
CREATE TABLE IF NOT EXISTS hd (
    record_type                              TEXT,
    unique_system_identifier                 INTEGER PRIMARY KEY,
    uls_file_number                          TEXT,
    ebf_number                               TEXT,
    call_sign                                TEXT,
    license_status                           TEXT,   -- A=Active, C=Cancelled, E=Expired, T=Terminated
    radio_service_code                       TEXT,   -- HA=Amateur, HV=Vanity
    grant_date                               TEXT,
    expired_date                             TEXT,
    cancellation_date                        TEXT,
    eligibility_rule_num                     TEXT,
    reserved1                                TEXT,
    alien                                    TEXT,
    alien_government                         TEXT,
    alien_corporation                        TEXT,
    alien_officer                            TEXT,
    alien_control                            TEXT,
    revoked                                  TEXT,
    convicted                                TEXT,
    adjudged                                 TEXT,
    reserved2                                TEXT,
    common_carrier                           TEXT,
    non_common_carrier                       TEXT,
    private_comm                             TEXT,
    fixed                                    TEXT,
    mobile                                   TEXT,
    radiolocation                            TEXT,
    satellite                                TEXT,
    developmental_or_sta_or_demonstration    TEXT,
    interconnected_service                   TEXT,
    certifier_first_name                     TEXT,
    certifier_mi                             TEXT,
    certifier_last_name                      TEXT,
    certifier_suffix                         TEXT,
    certifier_title                          TEXT,
    female                                   TEXT,
    black_or_african_american                TEXT,
    native_american                          TEXT,
    hawaiian                                 TEXT,
    asian                                    TEXT,
    white                                    TEXT,
    hispanic                                 TEXT,
    effective_date                           TEXT,
    last_action_date                         TEXT,
    auction_id                               INTEGER,
    broadcast_services_regulatory_status     TEXT,
    band_manager_regulatory_status           TEXT,
    broadcast_services_type_of_radio_service TEXT,
    alien_ruling                             TEXT,
    licensee_name_change                     TEXT,
    -- FCC added columns (2025+):
    hd_extra_1                               TEXT,
    hd_extra_2                               TEXT,
    hd_extra_3                               TEXT,
    hd_extra_4                               TEXT,
    hd_extra_5                               TEXT,
    hd_extra_6                               TEXT,
    hd_extra_7                               TEXT,
    hd_extra_8                               TEXT,
    hd_extra_9                               TEXT
);

-- EN: Entity record (licensee name & address)
CREATE TABLE IF NOT EXISTS en (
    record_type              TEXT,
    unique_system_identifier INTEGER,
    uls_file_number          TEXT,
    ebf_number               TEXT,
    call_sign                TEXT,
    entity_type              TEXT,   -- L=Licensee, A=Applicant, etc.
    licensee_id              TEXT,
    entity_name              TEXT,
    first_name               TEXT,
    mi                       TEXT,
    last_name                TEXT,
    suffix                   TEXT,
    phone                    TEXT,
    fax                      TEXT,
    email                    TEXT,
    street_address           TEXT,
    city                     TEXT,
    state                    TEXT,
    zip_code                 TEXT,
    po_box                   TEXT,
    attention_line           TEXT,
    sgin                     TEXT,
    frn                      TEXT,
    applicant_type_code      TEXT,   -- I=Individual, B=Amateur Club, etc.
    applicant_type_other     TEXT,
    status_code              TEXT,
    status_date              TEXT,
    lic_category_code        TEXT,
    linked_license_id        INTEGER,
    linked_callsign          TEXT
);

-- AM: Amateur-specific record
CREATE TABLE IF NOT EXISTS am (
    record_type              TEXT,
    unique_system_identifier INTEGER,
    uls_file_number          TEXT,
    ebf_number               TEXT,
    call_sign                TEXT,
    operator_class           TEXT,   -- T=Technician, G=General, E=Amateur Extra, A=Advanced, N=Novice
    group_code               TEXT,   -- A/B/C/D call sign group
    region_code              INTEGER,
    trustee_call_sign        TEXT,
    trustee_indicator        TEXT,
    physician_certification  TEXT,
    ve_signature             TEXT,
    systematic_call_sign_change TEXT,
    vanity_call_sign_change  TEXT,
    vanity_relationship      TEXT,
    previous_call_sign       TEXT,
    previous_operator_class  TEXT,
    trustee_name             TEXT
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS hd_call_sign_idx  ON hd(call_sign);
CREATE INDEX IF NOT EXISTS hd_status_idx     ON hd(license_status);
CREATE INDEX IF NOT EXISTS en_call_sign_idx  ON en(call_sign);
CREATE INDEX IF NOT EXISTS en_usi_idx        ON en(unique_system_identifier);
CREATE INDEX IF NOT EXISTS am_call_sign_idx  ON am(call_sign);
CREATE INDEX IF NOT EXISTS am_usi_idx        ON am(unique_system_identifier);

-- Convenience view: one row per active license with all useful fields
CREATE VIEW IF NOT EXISTS callsigns AS
SELECT
    h.call_sign,
    h.license_status,
    h.radio_service_code,
    h.grant_date,
    h.expired_date,
    h.effective_date,
    h.last_action_date,
    e.first_name,
    e.mi,
    e.last_name,
    e.entity_name,
    e.street_address,
    e.city,
    e.state,
    e.zip_code,
    e.email,
    e.applicant_type_code,
    a.operator_class,
    a.group_code,
    a.previous_call_sign,
    a.trustee_call_sign,
    h.unique_system_identifier
FROM hd h
LEFT JOIN en e ON e.unique_system_identifier = h.unique_system_identifier
               AND e.entity_type = 'L'
LEFT JOIN am a ON a.unique_system_identifier = h.unique_system_identifier;
"""

# Column counts expected per record type (for validation/padding)
EXPECTED_COLS = {
    "HD": 59,
    "EN": 30,
    "AM": 18,
}

# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _progress_bar(downloaded: int, total: int, width: int = 50) -> str:
    if total <= 0:
        return f"  {downloaded // (1024*1024)} MB downloaded"
    pct  = downloaded / total
    done = int(width * pct)
    bar  = "#" * done + "-" * (width - done)
    mb_d = downloaded / (1024 * 1024)
    mb_t = total      / (1024 * 1024)
    return f"  [{bar}] {mb_d:.1f}/{mb_t:.1f} MB ({pct*100:.1f}%)"


def download_file(url: str, dest: Path) -> None:
    """Download *url* to *dest* with a progress bar."""
    print(f"Downloading: {url}")
    try:
        req = urllib.request.urlopen(url, timeout=120)
    except Exception as exc:
        raise RuntimeError(f"Failed to open URL {url}: {exc}") from exc

    total = int(req.headers.get("Content-Length", 0))
    downloaded = 0
    start = time.time()

    with open(dest, "wb") as fh:
        while True:
            chunk = req.read(CHUNK_SIZE)
            if not chunk:
                break
            fh.write(chunk)
            downloaded += len(chunk)
            elapsed = time.time() - start
            rate = downloaded / elapsed if elapsed > 0 else 0
            print(
                f"\r{_progress_bar(downloaded, total)}  "
                f"{rate/(1024*1024):.1f} MB/s",
                end="",
                flush=True,
            )

    print(f"\nDownload complete: {downloaded/(1024*1024):.1f} MB in {time.time()-start:.1f}s")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_row(line: str, expected: int) -> list:
    """
    Split a pipe-delimited line and normalise to exactly *expected* fields.
    The FCC data uses bare pipes with no quoting, so a simple split is correct.
    Windows CR/LF endings are stripped.
    """
    row = line.rstrip("\r\n").split("|")
    # Pad or truncate to expected column count
    if len(row) < expected:
        row.extend([""] * (expected - len(row)))
    elif len(row) > expected:
        row = row[:expected]
    return [v.strip() if v else None for v in row]


def stream_dat(zf: zipfile.ZipFile, name: str):
    """Yield stripped text lines from a .dat file inside the zip."""
    try:
        info = zf.getinfo(name)
    except KeyError:
        print(f"  WARNING: {name} not found in zip archive – skipping.")
        return
    with zf.open(info) as raw:
        # FCC files are Latin-1 encoded
        for line in io.TextIOWrapper(raw, encoding="latin-1", errors="replace"):
            yield line


# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------

def import_table(conn: sqlite3.Connection, zf: zipfile.ZipFile,
                 dat_name: str, table: str, ncols: int,
                 label: str) -> int:
    """
    Stream *dat_name* from *zf* and bulk-insert into *table*.
    Returns the number of rows inserted.
    """
    placeholders = ", ".join("?" * ncols)
    sql = f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})"
    cur = conn.cursor()

    rows_total = 0
    batch: list = []

    print(f"  Importing {label} ({dat_name}) …")
    t0 = time.time()

    for line in stream_dat(zf, dat_name):
        if not line.strip():
            continue
        row = parse_row(line, ncols)
        batch.append(row)
        if len(batch) >= BATCH_SIZE:
            cur.executemany(sql, batch)
            rows_total += len(batch)
            batch = []
            if rows_total % 100_000 == 0:
                print(f"    … {rows_total:,} rows", flush=True)

    if batch:
        cur.executemany(sql, batch)
        rows_total += len(batch)

    conn.commit()
    elapsed = time.time() - t0
    print(f"    {rows_total:,} rows imported in {elapsed:.1f}s")
    return rows_total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download FCC ULS amateur radio database and load into SQLite"
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_DB,
        help=f"Output SQLite database path (default: {DEFAULT_DB})"
    )
    parser.add_argument(
        "--workdir", "-w",
        default=".",
        help="Working directory for the downloaded zip (default: current dir)"
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep the downloaded l_amat.zip after import"
    )
    parser.add_argument(
        "--zip-file",
        default=None,
        help="Use a previously downloaded l_amat.zip instead of re-downloading"
    )
    args = parser.parse_args()

    workdir  = Path(args.workdir).resolve()
    zip_path = Path(args.zip_file) if args.zip_file else workdir / "l_amat.zip"
    db_path  = Path(args.output).resolve()

    workdir.mkdir(parents=True, exist_ok=True)

    # ---- Download ----
    if args.zip_file and zip_path.exists():
        print(f"Using existing zip: {zip_path}")
    else:
        # Try primary URL first, then fallback
        downloaded = False
        for url in [PRIMARY_URL, FALLBACK_URL]:
            try:
                download_file(url, zip_path)
                downloaded = True
                break
            except RuntimeError as exc:
                print(f"  {exc}")
                if url != FALLBACK_URL:
                    print("  Trying fallback URL …")

        if not downloaded:
            print("ERROR: Could not download the database from any URL.")
            sys.exit(1)

    # ---- Verify zip ----
    if not zipfile.is_zipfile(zip_path):
        print(f"ERROR: {zip_path} is not a valid ZIP file.")
        sys.exit(1)

    print(f"\nOpening zip: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        print(f"  Files in archive: {', '.join(names)}")

    # ---- Create / open database ----
    if db_path.exists():
        print(f"\nRemoving existing database: {db_path}")
        db_path.unlink()

    print(f"Creating database: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    # ---- Import tables ----
    print("\nImporting data …")
    total_rows = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        total_rows += import_table(conn, zf, "HD.dat", "hd", EXPECTED_COLS["HD"], "License Headers")
        total_rows += import_table(conn, zf, "EN.dat", "en", EXPECTED_COLS["EN"], "Entities/Licensees")
        total_rows += import_table(conn, zf, "AM.dat", "am", EXPECTED_COLS["AM"], "Amateur Records")

    conn.close()

    # ---- Summary ----
    print(f"\n{'='*60}")
    print(f"Done.  {total_rows:,} total rows imported.")
    print(f"Database: {db_path}  ({db_path.stat().st_size/(1024*1024):.1f} MB)")
    print(f"{'='*60}")
    print()
    print("Quick-start queries:")
    print(f"  sqlite3 {db_path}")
    print()
    print("  -- Look up a call sign (all fields):")
    print("  SELECT * FROM callsigns WHERE call_sign = 'NY4I';")
    print()
    print("  -- All active Extra class licensees in Georgia:")
    print("  SELECT call_sign, first_name, last_name, city")
    print("  FROM callsigns")
    print("  WHERE license_status = 'A'")
    print("    AND operator_class  = 'E'")
    print("    AND state           = 'GA';")
    print()
    print("  -- Count by operator class:")
    print("  SELECT operator_class, COUNT(*) AS cnt")
    print("  FROM am GROUP BY operator_class ORDER BY cnt DESC;")
    print()

    # ---- Cleanup ----
    if not args.keep_zip and not args.zip_file:
        print(f"Removing {zip_path} (use --keep-zip to retain it)")
        zip_path.unlink()


if __name__ == "__main__":
    main()
