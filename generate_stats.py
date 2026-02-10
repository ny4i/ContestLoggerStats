#!/usr/bin/env python3
"""Contest Log Statistics Generator.

Generates SH5-style HTML statistics pages from ADIF contest logs.
"""

import argparse
import sys
import os

from stats.adif_parser import parse_adif
from stats.cty_dat import CtyDat, extract_wpx_prefix
from stats.geo import grid_to_latlon, haversine_km, bearing_deg
from stats.dupe_detector import find_dupes
from stats.privacy import anonymize, apply_privacy, write_operator_key
from stats.contest_data import ContestLog
from stats.html.renderer import Renderer
from stats.master_scp import find_master_scp, download_master_scp, load_master_scp, CACHE_DIR
from stats.lotw_users import find_lotw_users, download_lotw_users, load_lotw_users


def build_contest_log(adif_path: str, cty: CtyDat,
                      station_call: str, locator: str,
                      contest_name: str, dupe_rule: str) -> ContestLog:
    """Parse ADIF, enrich with cty.dat, detect dupes, return ContestLog."""
    header, qsos = parse_adif(adif_path)

    # Use CLI args or fall back to ADIF header
    if not station_call:
        station_call = header.get('STATION_CALLSIGN', 'UNKNOWN')
    if not locator:
        locator = header.get('MY_GRIDSQUARE', '')
    if not contest_name:
        contest_name = header.get('CONTEST_ID', 'Contest')

    # Station location
    station_lat, station_lon = 0.0, 0.0
    if locator:
        pos = grid_to_latlon(locator)
        if pos:
            station_lat, station_lon = pos

    # Enrich each QSO with cty.dat data
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


def main():
    parser = argparse.ArgumentParser(
        description='Generate contest log statistics HTML pages from ADIF files.'
    )
    parser.add_argument('adif', help='Path to ADIF file (.adi)')
    parser.add_argument('--output-dir', '-o', default='./stats_output',
                        help='Output directory (default: ./stats_output)')
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
    parser.add_argument('--dupe-rule', default='per_band_mode',
                        choices=['per_band_mode', 'per_band'],
                        help='Dupe detection rule (default: per_band_mode)')
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

    args = parser.parse_args()

    if not os.path.isfile(args.adif):
        print(f"Error: ADIF file not found: {args.adif}", file=sys.stderr)
        sys.exit(1)

    # Load cty.dat
    cty = CtyDat()
    cty_path = CtyDat.find_cty_dat(args.cty_dat)
    if cty_path:
        if not cty.load(cty_path):
            print(f"Warning: Failed to load cty.dat from {cty_path}", file=sys.stderr)
        else:
            print(f"Loaded {cty.country_count} countries from {cty_path}")
    else:
        print("Warning: cty.dat not found. Country data will be empty.", file=sys.stderr)

    # Build contest log
    log = build_contest_log(
        args.adif, cty,
        args.callsign, args.locator, args.contest,
        args.dupe_rule,
    )

    print(f"Parsed {len(log.qsos)} QSOs from {args.adif}")
    print(f"  Station: {log.station_call} @ {log.locator}")
    print(f"  Contest: {log.contest_name}")
    print(f"  Operators: {len(log.operators)}")
    print(f"  Bands: {', '.join(log.active_bands)}")
    print(f"  Dupes: {sum(1 for q in log.qsos if q.is_dupe)}")
    print(f"  Countries: {len({q.country for q in log.qsos if q.country})}")

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
            scp_path = download_master_scp(CACHE_DIR)
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
            lotw_path = download_lotw_users(CACHE_DIR)
        except Exception as e:
            print(f"Warning: Failed to download LOTW user list: {e}", file=sys.stderr)
    if lotw_path:
        lotw_users = load_lotw_users(lotw_path)
        print(f"Loaded {len(lotw_users)} LOTW users from {lotw_path}")
    else:
        print("LOTW user list not available; LOTW check page will be skipped.")

    # Render HTML
    renderer = Renderer(log, args.output_dir,
                        scp_calls=scp_calls, lotw_users=lotw_users,
                        callsign_lookup=args.callsign_lookup)
    renderer.render_all()

    print(f"\nOutput written to {os.path.abspath(args.output_dir)}/")
    print(f"Open {os.path.join(os.path.abspath(args.output_dir), 'index.htm')} in a browser.")


if __name__ == '__main__':
    main()
