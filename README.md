# Contest Log Stats

Generate SH5-style HTML statistics pages from amateur radio contest ADIF logs.

Parses an ADIF file, enriches QSOs with country/prefix/distance data from `cty.dat`, detects duplicates, and renders a full set of interactive HTML statistics pages with charts, maps, and tables.

## Features

- ADIF parsing with mode-group classification (CW/PH/DIG)
- Country, continent, CQ/ITU zone lookup via `cty.dat`
- WPX prefix extraction
- Duplicate detection (per-band-mode or per-band rules)
- Distance and beam heading calculation from Maidenhead locator
- Operator privacy/anonymization mode
- MASTER.SCP checking (auto-downloads if not found)
- LOTW user activity checking (auto-downloads if not found)
- LCR (Log Checking Report) error overlay (HTML and PDF formats)
- Configurable callsign lookup hyperlinks (QRZ or HamQTH)
- KMZ export for Google Earth
- 30+ HTML output pages with charts and interactive maps

## Installation

Requires Python 3.8+.

```bash
pip install jinja2
```

Optional, for PDF LCR support:

```bash
pip install pypdf
```

## Usage

### Statistics Generator

```bash
python generate_stats.py <adif_file> [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--output-dir`, `-o` | Output directory (default: `./stats_output`) |
| `--callsign`, `-c` | Station callsign (overrides ADIF header) |
| `--locator`, `-l` | Station Maidenhead locator (overrides ADIF header) |
| `--contest` | Contest name (overrides ADIF header) |
| `--cty-dat` | Path to `cty.dat` file |
| `--hide-operators` | Anonymize operator names in output |
| `--dupe-rule` | Dupe detection: `per_band_mode` (default) or `per_band` |
| `--lcr` | Path to LCR file for error overlay |
| `--master-scp` | Path to `MASTER.SCP` file |
| `--lotw` | Path to LOTW user activity CSV file |
| `--no-download` | Skip auto-download of MASTER.SCP and LOTW files |
| `--callsign-lookup` | Callsign lookup service: `qrz` (default) or `hamqth` |

**Example:**

```bash
python generate_stats.py mylog.adi -o ./output -c W4TA -l EM73 --lcr errors.lcr
```

### LCR Error Analyzer

Standalone tool to analyze Log Checking Report errors against your ADIF log by operator, band, and time of day.

```bash
python analyze_lcr.py <lcr_file> <adif_file>
```

Supports `.lcr`, `.html`, and `.pdf` LCR formats.

## Reference Data

| File | Source | Auto-download |
|------|--------|--------------|
| `cty.dat` | [country-files.com](https://www.country-files.com/) | No — searches common locations or use `--cty-dat` |
| `MASTER.SCP` | [supercheckpartial.com](http://www.supercheckpartial.com/) | Yes (cached in `~/.cache/contest-stats/`) |
| LOTW users | [ARRL LOTW](https://lotw.arrl.org/lotw-user-activity.csv) | Yes (cached in `~/.cache/contest-stats/`) |

## Output Pages

**Core:**
Index, Summary, Full Log, Operators, Dupes

**Geographic & Rate Analysis:**
All Callsigns, Rates, Countries, Countries by Time (all + per-band), QSOs per Station, Passed QSOs, QSOs by Hour (sheet + graphs, all + per-band), QSOs by Minute, One Minute Rates, Prefixes, Distance, Beam Heading, Break Time, Continents, Fields Map, Callsign Length, Callsign Structure, CQ Zones, ITU Zones, Not in Master, Possible Errors, LOTW Check

**Charts & Maps:**
QSOs by Band, Top 10 Countries, Continents, Beam Heading, Frequencies, Interactive Map, KMZ Export

**Optional:**
LCR Error Summary (when `--lcr` provided)

## Testing

```bash
pip install pytest
pytest tests/
```

The test suite includes a bundled `cty.dat` in `tests/data/` so no external files are needed.

## License

MIT
