# Contest Log Stats

Generate SH5-style HTML statistics pages from amateur radio contest ADIF logs.

Parses an ADIF file, enriches QSOs with country/prefix/distance data from `cty.dat`, detects duplicates, and renders a full set of interactive HTML statistics pages with charts, maps, and tables.

## Features

- ADIF parsing with mode-group classification (CW/PH/DIG)
- Country, continent, CQ/ITU zone lookup via `cty.dat`
- WPX prefix extraction
- Duplicate detection (per-band-mode, per-band, or all-band-mode); POTA-aware (N-fer hunts at different parks are not dupes)
- Distance and beam heading in km or miles (defaults to mi for US callsigns)
- Operator privacy/anonymization mode
- MASTER.SCP / LOTW / FCC ULS / Census ZCTA / BigCTY downloaded on demand via `--update-data`
- POTA park-grid override for portable ops; Parks page with per-park stats; clickable `pota.app` links on the map
- LCR (Log Checking Report) error overlay (HTML and PDF formats)
- Configurable callsign lookup hyperlinks (QRZ or HamQTH)
- KMZ export for Google Earth
- 30+ HTML output pages with charts and interactive maps

## Installation

Requires Python 3.8+.

```bash
pip install -r requirements.txt
```

Optional, for PDF LCR support:

```bash
pip install pypdf
```

## Usage

### First-run setup

All data files live in `./databases/`. Fetch them once:

```bash
python generate_stats.py --update-data
```

This downloads BigCTY (`cty.dat` + `cty.csv`), `MASTER.SCP`, the LOTW user list, the FCC ULS amateur database, and Census ZCTA centroids into `./databases/`. `cty.dat` is **required**; the script faults with a pointer to `--update-data` if it is missing.

### Statistics Generator

```bash
python generate_stats.py <adif_file> [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--update-data` | Download/refresh all data files into `./databases/` and exit |
| `--output-dir`, `-o` | Output directory (default: auto-named under `./stats_output/`) |
| `--callsign`, `-c` | Station callsign (overrides ADIF header) |
| `--locator`, `-l` | Station Maidenhead locator (overrides ADIF header) |
| `--contest` | Contest name (overrides ADIF header) |
| `--cty-dat` | Path to `cty.dat` file (overrides `./databases/cty.dat`) |
| `--hide-operators` | Anonymize operator names in output |
| `--dupe-rule` | Dupe detection: `per_band_mode` (default), `per_band`, or `all_band_mode` |
| `--lcr` | Path to LCR file for error overlay |
| `--master-scp` | Path to `MASTER.SCP` file |
| `--lotw` | Path to LOTW user activity CSV file |
| `--no-download` | Skip auto-download of `MASTER.SCP` and LOTW when missing |
| `--callsign-lookup` | Callsign lookup service: `qrz` (default) or `hamqth` |
| `--no-qrz` | Skip QRZ.com lookups for grid squares |
| `--qrz-cfg` | Path to QRZ settings file (default: `~/qrz_settings.cfg`) |
| `--units` | Distance units `km` or `mi` (default: `mi` for US callsigns, else `km`) |
| `--photos` | Directory of operator portraits (matched by callsign stem; prefers `.jpg` over `.png`) |
| `--remote` | Remote `user@host:/path` for a hint-only scp command in the output |

**Example:**

```bash
python generate_stats.py mylog.adi -c W4TA -l EM73 --lcr errors.lcr
```

Output directory is auto-named (e.g. `stats_output/2026-APR-18-POTA-US-1880-W4AFC/` for a POTA activation, or `stats_output/2026-APR-W4TA-ARRL-FIELD-DAY/` otherwise). Override with `-o`.

### QRZ credentials (`~/qrz_settings.cfg`)

QRZ lookups require a QRZ.com XML Logbook Data subscription. Create `~/qrz_settings.cfg` in INI format:

```ini
[qrz]
username=YOURCALL
password=YOURPASSWORD
```

The file is read by default; override the location with `--qrz-cfg`. Skip QRZ lookups entirely with `--no-qrz`. Keep this file out of version control — credentials are cached per-callsign in `~/.publicLogProcessor/qrz_cache.json` so the password is only transmitted on the first lookup per call.

### LCR Error Analyzer

Standalone tool to analyze Log Checking Report errors against your ADIF log by operator, band, and time of day.

```bash
python analyze_lcr.py <lcr_file> <adif_file>
```

Supports `.lcr`, `.html`, and `.pdf` LCR formats.

## Reference Data

All data files live in `./databases/` (gitignored). Populate with `python generate_stats.py --update-data`.

| File | Source | Required |
|------|--------|----------|
| `cty.dat`, `cty.csv` | [country-files.com BigCTY](https://www.country-files.com/bigcty/download/bigcty.zip) | Yes — script faults without `cty.dat` |
| `MASTER.SCP` | [supercheckpartial.com](http://www.supercheckpartial.com/) | No (used for "Not in master") |
| LOTW users | [ARRL LOTW](https://lotw.arrl.org/lotw-user-activity.csv) | No (LOTW check page skipped when absent) |
| `fcc_amateur.db` | Built from [FCC ULS](https://data.fcc.gov/download/pub/uls/complete/l_amat.zip) by `fcc_uls_to_sqlite.py` | No (US callsigns fall through to QRZ) |
| `zcta_centroids.csv` | [U.S. Census Gazetteer](https://www2.census.gov/geo/docs/maps-data/data/gazetteer/) | No (used by FCC zip→grid) |
| `pota_parks.csv` | [pota.app](https://pota.app/all_parks_ext.csv) — lazy-loaded only when the ADIF has POTA refs | No (auto-downloaded on first POTA log) |
| `vuccgrids.dat` | TQSL (manual placement) | No (DXCC grid validation disabled when absent) |

## Output Pages

**Core:**
Index, Summary, Full Log, Operators, Dupes

**Geographic & Rate Analysis:**
All Callsigns, Rates, Countries, Countries by Time (all + per-band), QSOs per Station, Passed QSOs, QSOs by Hour (sheet + graphs, all + per-band), QSOs by Minute, One Minute Rates, Prefixes, Distance, Beam Heading, Break Time, Continents, Fields Map, Callsign Length, Callsign Structure, CQ Zones, ITU Zones, Not in Master, Possible Errors, LOTW Check

**Charts & Maps:**
QSOs by Band, QSOs by Mode, Top 10 Countries, Continents, Beam Heading, Frequencies, Interactive Map, KMZ Export

**POTA (only when the ADIF contains POTA references):**
Parks page (activator- and hunter-side tables with park name / grid / state / QSO count), pota.app links on map popups, park-grid overrides for portable ops, POTA-aware dupe detection, auto-named output directory with date + activated park

**Optional:**
LCR Error Summary (when `--lcr` provided)

## Hardening the hosted output
**Note: These are hardening suggestions. You assume all the risk to ensure your website is well-protected. WHile every effort has been extended to ensure these steps will help protect the pages generated by these scripts, you assume the ultimate responsibility to ensure they are safe.**

The generated pages already include a CSP meta tag, `rel="noopener noreferrer"` on external links, and a `referrer` policy. Clickjacking protection (`frame-ancestors` / `X-Frame-Options`) **must be set as an HTTP response header** — meta-tag equivalents are ignored by browsers. Set these once at your webserver level; they'll cover every log you publish.

**Apache** (site config or `.htaccess` with `AllowOverride All`):

```apache
Header always set X-Frame-Options "DENY"
Header always set Content-Security-Policy "frame-ancestors 'none';"
Header always set X-Content-Type-Options "nosniff"
Header always set Referrer-Policy "strict-origin-when-cross-origin"
```

**nginx** (inside the `server` block):

```nginx
add_header X-Frame-Options "DENY" always;
add_header Content-Security-Policy "frame-ancestors 'none';" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

If you serve over HTTPS, also set HSTS (`Strict-Transport-Security: max-age=63072000; includeSubDomains`) once you're confident the cert is stable.

Ready-to-deploy `.htaccess` and matching stylesheet for the directory index are in [`websiteFormattingTools/`](websiteFormattingTools/) — see its [README](websiteFormattingTools/README.md).

## Testing

```bash
pip install pytest
pytest tests/
```

The test suite includes a bundled `cty.dat` in `tests/data/` so no external files are needed.

## License

GPL-3.0. See [LICENSE](LICENSE).
