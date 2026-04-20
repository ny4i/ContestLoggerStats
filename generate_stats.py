#!/usr/bin/env python3
"""Contest Log Statistics Generator.

Generates SH5-style HTML statistics pages from ADIF contest logs.
"""

import argparse
import re
import shutil
import subprocess
import sys
import os
import urllib.request

from stats.adif_parser import parse_adif, parse_adif_raw
from stats.cty_dat import CtyDat, extract_wpx_prefix
from stats.geo import grid_to_latlon, haversine_km, bearing_deg
from stats.dupe_detector import find_dupes
from stats.privacy import anonymize, apply_privacy, write_operator_key
from stats.contest_data import ContestLog
from stats.contest_rules import load_contest_definitions, lookup_contest, validate_exchanges, estimate_score
from stats.html.renderer import Renderer
from stats.master_scp import find_master_scp, download_master_scp, load_master_scp
from stats.paths import databases_dir
from stats.lotw_users import find_lotw_users, download_lotw_users, load_lotw_users
from stats.qrz_lookup import QRZLookup
from stats.fcc_lookup import FCCLookup
from stats.grid_state import load_vucc_grid_map, load_prefix_dxcc_map, grid_matches_dxcc
from stats.pota_lookup import (
    POTALookup, has_any_pota_refs, find_pota_parks, download_pota_parks,
)


def build_contest_log(adif_path: str, cty: CtyDat,
                      station_call: str, locator: str,
                      contest_name: str, dupe_rule: str,
                      prefix_dxcc_map: dict[str, int] | None = None,
                      pota_lookup: POTALookup | None = None) -> ContestLog:
    """Parse ADIF, enrich with cty.dat, detect dupes, return ContestLog."""
    header, qsos = parse_adif(adif_path)

    # Use CLI args or fall back to ADIF header
    if not station_call:
        station_call = header.get('STATION_CALLSIGN', 'UNKNOWN')
    if not locator:
        locator = header.get('MY_GRIDSQUARE', '')
    # POTA fallback for station locator when MY_GRIDSQUARE is absent.
    # MY_POTA_REF wins over MY_SIG_INFO (when MY_SIG == POTA).
    if not locator and pota_lookup:
        my_ref_field = header.get('MY_POTA_REF', '')
        if not my_ref_field and header.get('MY_SIG', '').strip().upper() == 'POTA':
            my_ref_field = header.get('MY_SIG_INFO', '')
        if my_ref_field:
            park_grid = pota_lookup.grid_for_field(my_ref_field)
            if park_grid:
                locator = park_grid
    if not contest_name:
        contest_name = header.get('CONTEST_ID', 'Contest')

    # Station location
    station_lat, station_lon = 0.0, 0.0
    if locator:
        pos = grid_to_latlon(locator)
        if pos:
            station_lat, station_lon = pos

    # Enrich each QSO with cty.dat data
    pdm = prefix_dxcc_map or {}
    for qso in qsos:
        data = cty.lookup(qso.call)
        if data.is_valid():
            qso.country = data.name
            qso.continent = data.continent
            qso.cq_zone = data.cq_zone
            qso.itu_zone = data.itu_zone
            qso.dxcc_lat = data.latitude
            qso.dxcc_lon = data.longitude
            qso.prefix = extract_wpx_prefix(qso.call)
            # Fill DXCC entity number from cty.csv if ADIF didn't provide it
            if qso.dxcc == 0 and data.primary_prefix in pdm:
                qso.dxcc = pdm[data.primary_prefix]

            if station_lat != 0.0 or station_lon != 0.0:
                qso.distance_km = haversine_km(
                    station_lat, station_lon, data.latitude, data.longitude
                )
                qso.bearing_deg = bearing_deg(
                    station_lat, station_lon, data.latitude, data.longitude
                )

    # Sort by datetime
    qsos.sort(key=lambda q: q.datetime_utc)

    # Detect dupes
    find_dupes(qsos, rule=dupe_rule)

    # Build operator list
    operators = sorted({q.operator for q in qsos if q.operator})

    # Time window
    start_time = qsos[0].datetime_utc if qsos else None
    end_time = qsos[-1].datetime_utc if qsos else None

    return ContestLog(
        station_call=station_call,
        locator=locator,
        contest_name=contest_name,
        qsos=qsos,
        operators=operators,
        start_time=start_time,
        end_time=end_time,
        station_lat=station_lat,
        station_lon=station_lon,
    )


def _find_data_file(filename: str, sibling_path: str | None = None) -> str | None:
    """Return ./databases/<filename> if it exists, else a sibling-of-cty fallback."""
    from stats.paths import find_data_file
    p = find_data_file(filename)
    if p:
        return p
    if sibling_path:
        alt = os.path.join(os.path.dirname(sibling_path), filename)
        if os.path.isfile(alt):
            return alt
    return None


def update_all_data():
    """Download/refresh all external data files."""
    import io
    import zipfile
    import time
    import subprocess

    cache_dir = databases_dir()
    os.makedirs(cache_dir, exist_ok=True)
    print(f"Data directory: {cache_dir}\n")

    # 1. BigCTY (cty.dat + cty.csv from AD1C)
    print("=" * 60)
    print("[1/5] BigCTY (cty.dat + cty.csv)")
    bigcty_url = "https://www.country-files.com/bigcty/download/bigcty.zip"
    try:
        print(f"  Downloading from country-files.com...")
        req = urllib.request.urlopen(bigcty_url, timeout=60)
        zf = zipfile.ZipFile(io.BytesIO(req.read()))
        wanted = {"cty.dat", "cty.csv"}
        extracted = []
        for name in zf.namelist():
            base = os.path.basename(name)
            if base in wanted:
                target = os.path.join(cache_dir, base)
                with open(target, "wb") as f:
                    f.write(zf.read(name))
                size_kb = os.path.getsize(target) / 1024
                extracted.append(f"{base} ({size_kb:.0f} KB)")
        if extracted:
            print(f"  Extracted to {cache_dir}: " + ", ".join(extracted))
        else:
            print(f"  FAILED: cty.dat/cty.csv not found in zip")
    except Exception as e:
        print(f"  FAILED: {e}")

    # 2. MASTER.SCP
    print("=" * 60)
    print("[2/5] MASTER.SCP (Super Check Partial)")
    try:
        path = download_master_scp(cache_dir)
        calls = load_master_scp(path)
        print(f"  Downloaded {len(calls)} callsigns to {path}")
    except Exception as e:
        print(f"  FAILED: {e}")

    # 3. LOTW user activity
    print("=" * 60)
    print("[3/5] LOTW user activity list")
    try:
        path = download_lotw_users(cache_dir)
        users = load_lotw_users(path)
        print(f"  Downloaded {len(users)} users to {path}")
    except Exception as e:
        print(f"  FAILED: {e}")

    # 4. FCC ULS amateur database
    print("=" * 60)
    print("[4/5] FCC ULS amateur radio database")
    db_path = os.path.join(cache_dir, "fcc_amateur.db")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "fcc_uls_to_sqlite.py")
    if os.path.isfile(script):
        try:
            result = subprocess.run(
                [sys.executable, script, "--output", db_path],
                timeout=600,
            )
            if result.returncode == 0:
                size_mb = os.path.getsize(db_path) / (1024 * 1024)
                print(f"  Database: {db_path} ({size_mb:.0f} MB)")
            else:
                print(f"  FAILED: exit code {result.returncode}")
        except Exception as e:
            print(f"  FAILED: {e}")
    else:
        print(f"  Script not found: {script}")

    # 5. Census ZCTA zip code centroids
    print("=" * 60)
    print("[5/5] Census ZCTA zip code centroids")
    zcta_csv = os.path.join(cache_dir, "zcta_centroids.csv")
    zcta_url = ("https://www2.census.gov/geo/docs/maps-data/data/"
                "gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip")
    try:
        print(f"  Downloading from Census Bureau...")
        req = urllib.request.urlopen(zcta_url, timeout=60)
        data = req.read()
        zf = zipfile.ZipFile(io.BytesIO(data))
        content = zf.read(zf.namelist()[0]).decode('latin-1')
        lines = content.strip().split('\n')
        count = 0
        with open(zcta_csv, 'w') as f:
            f.write('zip,lat,lon\n')
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) >= 7:
                    z = parts[0].strip()
                    lat = parts[5].strip()
                    lon = parts[6].strip()
                    if z and lat and lon:
                        f.write(f'{z},{lat},{lon}\n')
                        count += 1
        print(f"  Saved {count} zip centroids to {zcta_csv}")
    except Exception as e:
        print(f"  FAILED: {e}")

    print("=" * 60)
    print("\nAll data updated. Files in", cache_dir + ":")
    for f in sorted(os.listdir(cache_dir)):
        fpath = os.path.join(cache_dir, f)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            if size > 1024 * 1024:
                print(f"  {f:40s} {size / (1024*1024):8.1f} MB")
            else:
                print(f"  {f:40s} {size / 1024:8.1f} KB")


def main():
    parser = argparse.ArgumentParser(
        description='Generate contest log statistics HTML pages from ADIF files.'
    )
    parser.add_argument('adif', nargs='?', default=None,
                        help='Path to ADIF file (.adi)')
    parser.add_argument('--update-data', action='store_true',
                        help='Download/refresh all data files (BigCTY, MASTER.SCP, LOTW, FCC, ZCTA) and exit')
    parser.add_argument('--output-dir', '-o', default=None,
                        help='Output directory (default: YYYY-Mon-ContestName-Callsign)')

    parser.add_argument('--callsign', '-c', default='',
                        help='Station callsign (overrides ADIF header)')
    parser.add_argument('--locator', '-l', default='',
                        help='Station Maidenhead locator (overrides ADIF header)')
    parser.add_argument('--contest', default='',
                        help='Contest name (overrides ADIF header)')
    parser.add_argument('--cty-dat', default=None,
                        help='Path to cty.dat file')
    parser.add_argument('--hide-operators', action='store_true',
                        help='Anonymize operator names')
    parser.add_argument('--dupe-rule', default=None,
                        choices=['per_band_mode', 'per_band', 'all_band_mode'],
                        help='Dupe detection rule (default: auto-detect from contest, or per_band_mode)')
    parser.add_argument('--lcr', default=None,
                        help='Path to LCR file for error overlay')
    parser.add_argument('--master-scp', default=None,
                        help='Path to MASTER.SCP file')
    parser.add_argument('--lotw', default=None,
                        help='Path to LOTW user activity CSV file')
    parser.add_argument('--no-download', action='store_true',
                        help='Skip auto-download of MASTER.SCP and LOTW files')
    parser.add_argument('--callsign-lookup', default='qrz',
                        choices=['qrz', 'hamqth'],
                        help='Callsign lookup service for hyperlinks (default: qrz)')
    parser.add_argument('--photos', default=None,
                        help='Directory containing operator photos (CALLSIGN.jpg or .png)')
    parser.add_argument('--remote', default=None,
                        help='Remote destination (user@host:/path) for scp command hint')
    parser.add_argument('--no-qrz', action='store_true',
                        help='Skip QRZ.com lookups for grid squares')
    parser.add_argument('--qrz-cfg', default=None,
                        help='Path to QRZ settings file (default: ~/qrz_settings.cfg)')
    parser.add_argument('--units', default=None, choices=['km', 'mi'],
                        help='Distance units (default: mi for US callsigns, km otherwise)')
    parser.add_argument('--post-script', default=None,
                        help='Executable to invoke after successful generation; '
                             'receives the absolute output directory as its only arg')

    args = parser.parse_args()

    if args.update_data:
        update_all_data()
        sys.exit(0)

    if not args.adif:
        parser.error("adif file is required (unless using --update-data)")

    if not os.path.isfile(args.adif):
        print(f"Error: ADIF file not found: {args.adif}", file=sys.stderr)
        sys.exit(1)

    # Load cty.dat (required; fault if missing)
    cty = CtyDat()
    cty_path = CtyDat.find_cty_dat(args.cty_dat)
    if not cty_path:
        print("Error: cty.dat not found in ./databases/. "
              "Run `python generate_stats.py --update-data` to download required databases.",
              file=sys.stderr)
        sys.exit(2)
    if not cty.load(cty_path):
        print(f"Error: Failed to load cty.dat from {cty_path}", file=sys.stderr)
        sys.exit(2)
    print(f"Loaded {cty.country_count} countries from {cty_path}")

    # Load cty.csv (prefix → DXCC entity number mapping)
    prefix_dxcc_map: dict[str, int] = {}
    cty_csv_path = _find_data_file('cty.csv', cty_path)
    if cty_csv_path:
        prefix_dxcc_map = load_prefix_dxcc_map(cty_csv_path)
        if prefix_dxcc_map:
            print(f"Loaded {len(prefix_dxcc_map)} prefix→DXCC mappings from {cty_csv_path}")
    if not prefix_dxcc_map:
        print("Warning: cty.csv not found. DXCC grid validation will be limited.",
              file=sys.stderr)

    # Load vuccgrids.dat (grid → DXCC entity validation)
    vucc_grid_map: dict[str, list[int]] = {}
    vucc_path = _find_data_file('vuccgrids.dat')
    if vucc_path:
        vucc_grid_map, vucc_date = load_vucc_grid_map(vucc_path)
        if vucc_grid_map:
            date_info = f" (updated {vucc_date})" if vucc_date else ""
            print(f"Loaded {len(vucc_grid_map)} grid→DXCC mappings from {vucc_path}"
                  f"{date_info}")
    if not vucc_grid_map:
        print("Warning: vuccgrids.dat not found. DXCC grid validation disabled.",
              file=sys.stderr)

    # Load contest definitions and auto-detect rules
    definitions = load_contest_definitions()
    header_peek, raw_qsos = parse_adif_raw(args.adif)

    # Lazy-load POTA parks: only when the ADIF actually references POTA.
    pota_lookup: POTALookup | None = None
    if has_any_pota_refs(raw_qsos):
        pota_path = find_pota_parks()
        if not pota_path and not args.no_download:
            try:
                print("Downloading POTA parks CSV...")
                pota_path = download_pota_parks()
            except Exception as e:
                print(f"Warning: POTA parks download failed: {e}", file=sys.stderr)
        if pota_path:
            pl = POTALookup()
            count = pl.load(pota_path)
            pota_lookup = pl
            print(f"Loaded {count} POTA parks from {pota_path}")
        else:
            print("Warning: ADIF has POTA refs but pota_parks.csv unavailable; "
                  "park-grid override disabled.", file=sys.stderr)
    # CONTEST_ID may be in first QSO record rather than header
    if 'CONTEST_ID' not in header_peek and raw_qsos:
        header_peek['CONTEST_ID'] = raw_qsos[0].get('CONTEST_ID', '')
    contest_id = header_peek.get('CONTEST_ID', '')
    contest_def = lookup_contest(contest_id, definitions)

    # Resolve dupe rule: CLI overrides auto-detect
    if args.dupe_rule is not None:
        dupe_rule = args.dupe_rule
    elif contest_def:
        dupe_rule = contest_def.dupe_rule
    else:
        dupe_rule = 'per_band_mode'

    # Build contest log
    log = build_contest_log(
        args.adif, cty,
        args.callsign, args.locator, args.contest,
        dupe_rule,
        prefix_dxcc_map=prefix_dxcc_map,
        pota_lookup=pota_lookup,
    )

    # Park-grid override (their side): apply before FCC/QRZ home-grid lookups.
    # ADIF GRIDSQUARE always wins (already in q.grid); we only fill empties.
    if pota_lookup:
        pota_grid_applied = 0
        for q in log.qsos:
            if q.grid or not q.pota_ref:
                continue
            park_grid = pota_lookup.grid_for_field(q.pota_ref)
            if park_grid:
                q.grid = park_grid
                pota_grid_applied += 1
        if pota_grid_applied:
            print(f"POTA park grids: {pota_grid_applied} applied from park refs")

    # Store contest_id on log
    log.contest_id = contest_id

    # Populate station country/continent from cty.dat
    station_data = cty.lookup(log.station_call)
    if station_data.is_valid():
        log.station_country = station_data.name
        log.station_continent = station_data.continent

    # Resolve distance units: CLI flag wins; otherwise default by callsign.
    if args.units:
        distance_unit = args.units
    else:
        distance_unit = 'mi' if FCCLookup.is_us_callsign(log.station_call) else 'km'

    # For POTA activations, pull the first activated park ref so we can
    # include it in the output directory name and the page title.
    activated_park = ""
    activated_park_date = ""
    for q in log.qsos:
        if q.my_pota_ref:
            activated_park = q.my_pota_ref.split(",")[0].strip().upper()
            if log.start_time:
                activated_park_date = (
                    f"{log.start_time.strftime('%Y')}-"
                    f"{log.start_time.strftime('%b').upper()}-"
                    f"{log.start_time.strftime('%d')}"
                )
            break

    # Build output directory name if not specified.
    # All auto-named runs land under ./stats_output/ so the repo root stays tidy.
    if args.output_dir is None:
        year = log.start_time.strftime("%Y") if log.start_time else "unknown"
        mon = log.start_time.strftime("%b").upper() if log.start_time else "unknown"
        call = re.sub(r'[^\w\-]', '-', log.station_call).strip('-')
        if activated_park:
            day = log.start_time.strftime("%d") if log.start_time else "unknown"
            park_slug = re.sub(r'[^\w\-]', '-', activated_park).strip('-')
            dirname = f"{year}-{mon}-{day}-POTA-{park_slug}-{call}"
        else:
            contest = re.sub(r'[^\w\-]', '-', log.contest_name).strip('-')
            dirname = f"{year}-{mon}-{contest}-{call}"
        args.output_dir = os.path.join("stats_output", dirname)

    print(f"Parsed {len(log.qsos)} QSOs from {args.adif}")
    print(f"  Station: {log.station_call} @ {log.locator}")
    if log.station_country:
        print(f"  Station country: {log.station_country} ({log.station_continent})")
    print(f"  Contest: {log.contest_name}")
    if contest_def:
        print(f"  Contest rules: {contest_def.name} (dupe rule: {dupe_rule})")
    print(f"  Operators: {len(log.operators)}")
    print(f"  Bands: {', '.join(log.active_bands)}")
    print(f"  Dupes: {sum(1 for q in log.qsos if q.is_dupe)}")
    print(f"  Countries: {len({q.country for q in log.qsos if q.country})}")

    # Exchange validation
    if contest_def:
        validate_exchanges(log.qsos, contest_def, log.station_country)
        bad = sum(1 for q in log.qsos if q.exchange_error)
        if bad:
            print(f"  Exchange errors: {bad}")

    # Compute estimated score
    score_result = None
    if contest_def:
        score_result = estimate_score(log, contest_def)
        print(f"  Estimated score: {score_result.total_score:,}")

    # Apply LCR overlay if provided
    if args.lcr:
        if not os.path.isfile(args.lcr):
            print(f"Error: LCR file not found: {args.lcr}", file=sys.stderr)
            sys.exit(1)
        from stats.lcr_parser import parse_lcr, match_error_to_qso
        errors = parse_lcr(args.lcr)
        matched = 0
        for error in errors:
            qso = match_error_to_qso(error, log.qsos)
            if qso:
                qso.lcr_error = error['error_type']
                qso.lcr_detail = error.get('extra', '')
                matched += 1
        print(f"  LCR errors: {len(errors)} ({matched} matched to QSOs)")

    # Apply privacy if requested
    if args.hide_operators:
        mapping, anon_list = anonymize(log.operators)
        apply_privacy(log.qsos, mapping)
        log.operators = anon_list
        write_operator_key(mapping, args.output_dir)
        print("  Operator names anonymized")

    # Load MASTER.SCP
    scp_calls = None
    scp_path = find_master_scp(args.master_scp)
    if not scp_path and not args.no_download:
        try:
            print("Downloading MASTER.SCP...")
            scp_path = download_master_scp(databases_dir())
        except Exception as e:
            print(f"Warning: Failed to download MASTER.SCP: {e}", file=sys.stderr)
    if scp_path:
        scp_calls = load_master_scp(scp_path)
        print(f"Loaded {len(scp_calls)} callsigns from {scp_path}")
    else:
        print("MASTER.SCP not available; 'Not in master' will use cty.dat fallback.")

    # Load LOTW user list
    lotw_users = None
    lotw_path = find_lotw_users(args.lotw)
    if not lotw_path and not args.no_download:
        try:
            print("Downloading LOTW user list...")
            lotw_path = download_lotw_users(databases_dir())
        except Exception as e:
            print(f"Warning: Failed to download LOTW user list: {e}", file=sys.stderr)
    if lotw_path:
        lotw_users = load_lotw_users(lotw_path)
        print(f"Loaded {len(lotw_users)} LOTW users from {lotw_path}")
    else:
        print("LOTW user list not available; LOTW check page will be skipped.")

    # ---- Grid resolution for QSOs missing grids ----
    # RULE: QSO record is authoritative. Never override existing QSO data.
    # Lookup priority:
    #   1. FCC ULS database (US calls only — instant, local, free)
    #   2. QRZ XML API (DX calls — cached, needs subscription)
    # Looked-up grids are validated against exchange state and DXCC entity.
    dxcc_skipped = 0  # counter for DXCC-based grid rejections

    missing_grid = [q for q in log.qsos if not q.grid]
    if not missing_grid:
        print("All QSOs have grids — no lookups needed.")
    else:
        us_calls = set()
        dx_calls = set()
        for q in missing_grid:
            if FCCLookup.is_us_callsign(q.call):
                us_calls.add(q.call)
            else:
                dx_calls.add(q.call)

        # --- FCC lookups (US calls — single batch query) ---
        import time as _time
        fcc = FCCLookup()
        fcc_applied = 0
        fcc_skipped = 0
        if fcc.available and us_calls:
            t0 = _time.time()
            fcc_results = fcc.lookup_batch(us_calls)
            for q in missing_grid:
                if q.grid or q.call not in us_calls:
                    continue
                result = fcc_results.get(q.call)
                if not result or not result.grid:
                    continue
                # Validate: FCC state vs exchange state
                if q.state and result.state and q.state.upper() != result.state.upper():
                    fcc_skipped += 1
                    continue
                # Validate: grid vs DXCC entity
                if vucc_grid_map and q.dxcc:
                    match = grid_matches_dxcc(result.grid, q.dxcc, vucc_grid_map)
                    if match is False:
                        dxcc_skipped += 1
                        continue
                q.grid = result.grid
                fcc_applied += 1
            elapsed = _time.time() - t0
            print(f"FCC grids: {fcc_applied} applied for {len(us_calls)} US calls "
                  f"in {elapsed:.1f}s ({fcc.zcta_count} zip centroids)")
            if fcc_skipped:
                print(f"  Skipped {fcc_skipped} — exchange state conflicts "
                      f"with FCC (likely portable/mobile)")
            fcc.close()
        elif us_calls:
            print(f"FCC database not available — {len(us_calls)} US calls "
                  f"will fall through to QRZ")

        # --- QRZ lookups (DX calls + any US calls FCC couldn't resolve) ---
        still_missing = {q.call for q in log.qsos if not q.grid}
        if not args.no_qrz and still_missing:
            try:
                qrz = QRZLookup(args.qrz_cfg or '~/qrz_settings.cfg')
                cached_calls = {c for c in still_missing if c.upper() in qrz._cache}
                need_lookup = still_missing - cached_calls
                if need_lookup:
                    print(f"QRZ: looking up {len(need_lookup)} calls "
                          f"({len(cached_calls)} already cached)...",
                          end='', flush=True)
                cached = qrz.cache_size
                count = 0
                for call in sorted(still_missing):
                    if call.upper() not in qrz._cache:
                        count += 1
                        if count % 25 == 0:
                            print(f" {count}/{len(need_lookup)}",
                                  end='', flush=True)
                            qrz.save_cache()
                    qrz.lookup(call)
                if need_lookup:
                    print(" done.")
                qrz_applied = 0
                qrz_skipped = 0
                for q in log.qsos:
                    if q.grid:
                        continue
                    result = qrz.lookup(q.call)
                    if not result or not result.grid:
                        continue
                    if q.state and result.state and q.state.upper() != result.state.upper():
                        qrz_skipped += 1
                        continue
                    # Validate: grid vs DXCC entity
                    if vucc_grid_map and q.dxcc:
                        match = grid_matches_dxcc(result.grid, q.dxcc, vucc_grid_map)
                        if match is False:
                            dxcc_skipped += 1
                            continue
                    q.grid = result.grid
                    qrz_applied += 1
                qrz.save_cache()
                new_lookups = qrz.cache_size - cached
                print(f"QRZ grids: {qrz_applied} applied for "
                      f"{len(still_missing)} remaining calls "
                      f"({new_lookups} new API lookups, "
                      f"{qrz.cache_size} total cached)")
                if qrz_skipped:
                    print(f"  Skipped {qrz_skipped} — exchange data "
                          f"conflicts with QRZ (likely portable/mobile)")
            except KeyboardInterrupt:
                print("\n  Interrupted — saving cache...")
                qrz.save_cache()
                print(f"  Saved {qrz.cache_size} cached entries. "
                      f"Continuing without remaining lookups.")
            except Exception as e:
                print(f"Warning: QRZ lookup failed: {e}", file=sys.stderr)
                try:
                    qrz.save_cache()
                except Exception:
                    pass
            try:
                qrz.save_cache()
            except Exception:
                pass

    if dxcc_skipped:
        print(f"  Skipped {dxcc_skipped} grid(s) — grid conflicts with "
              f"DXCC entity (vuccgrids.dat)")

    # Render HTML
    renderer = Renderer(log, args.output_dir,
                        scp_calls=scp_calls, lotw_users=lotw_users,
                        callsign_lookup=args.callsign_lookup,
                        photos_dir=args.photos,
                        score_result=score_result,
                        pota_lookup=pota_lookup,
                        activated_park=activated_park,
                        activated_park_date=activated_park_date,
                        distance_unit=distance_unit)
    renderer.render_all()

    # Archive the source ADIF into the output directory so LCR reruns months
    # later can find it without depending on the original path.
    try:
        adif_src = os.path.abspath(args.adif)
        adif_dest = os.path.join(os.path.abspath(args.output_dir),
                                 os.path.basename(args.adif))
        if adif_src != adif_dest:
            shutil.copy2(args.adif, adif_dest)
            os.chmod(adif_dest, 0o644)
    except Exception as e:
        print(f"Warning: could not archive source ADIF: {e}", file=sys.stderr)

    print(f"\nOutput written to {os.path.abspath(args.output_dir)}/")
    print(f"Open {os.path.join(os.path.abspath(args.output_dir), 'index.htm')} in a browser.")

    if args.remote:
        remote = args.remote.rstrip('/')
        print(f"\nTo deploy remotely:")
        print(f"  scp -r {os.path.abspath(args.output_dir)} {remote}/")

    if args.post_script:
        # Resolve bare filenames against CWD first, then PATH — matches shell
        # intuition since Python's subprocess doesn't check CWD by default.
        script = args.post_script
        if not os.path.isabs(script) and '/' not in script:
            cwd_candidate = os.path.join(os.getcwd(), script)
            if os.path.isfile(cwd_candidate):
                script = cwd_candidate
            else:
                which = shutil.which(script)
                if which:
                    script = which

        out_abs = os.path.abspath(args.output_dir)
        print(f"\nRunning post-script: {script} {out_abs}")
        try:
            result = subprocess.run([script, out_abs], check=False)
        except FileNotFoundError:
            print(f"Error: post-script not found: {args.post_script} "
                  f"(not in current directory or on PATH)", file=sys.stderr)
            sys.exit(2)
        except PermissionError:
            print(f"Error: post-script not executable: {script}. "
                  f"Try `chmod +x {args.post_script}`.", file=sys.stderr)
            sys.exit(2)
        if result.returncode != 0:
            print(f"Post-script exited with code {result.returncode}",
                  file=sys.stderr)
            sys.exit(result.returncode)


if __name__ == '__main__':
    main()
