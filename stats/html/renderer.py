"""HTML renderer: orchestrates template rendering and file output."""

import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone

import jinja2

from .. import __version__, REPO_URL
from ..contest_data import ContestLog
from . import pages


@dataclass
class NavPage:
    title: str
    filename: str
    is_child: bool = False


def _build_nav(active_bands: list[str], has_lcr: bool = False,
               has_lotw: bool = False, has_pota: bool = False) -> list[NavPage]:
    """Build full navigation list including band-variant pages."""
    nav = [
        NavPage("Main", "index.htm"),
        NavPage("Summary", "summary.htm"),
        NavPage("Log", "log.htm"),
        NavPage("Operators", "operators.htm"),
        NavPage("All callsigns", "all_callsigns.htm"),
        NavPage("Rates", "rates.htm"),
        NavPage("Countries", "countries.htm"),
        NavPage("Countries by time", "countries_by_time.htm"),
    ]
    if has_pota:
        nav.append(NavPage("POTA parks", "parks.htm"))
    for band in active_bands:
        b = band.replace('m', '')
        nav.append(NavPage(f"Countries by time - {b}", f"{b}_countries_by_time.htm", is_child=True))

    nav.extend([
        NavPage("Qs per station", "qs_per_station.htm"),
        NavPage("Passed QSOs", "passed_qsos.htm"),
        NavPage("Dupes", "dupes.htm"),
        NavPage("Qs by hour sheet", "qs_by_hour_sheet.htm"),
        NavPage("Qs by hour", "graphs_qs_by_hour.htm"),
    ])
    for band in active_bands:
        b = band.replace('m', '')
        nav.append(NavPage(f"Qs by hour - {b}", f"{b}_graphs_qs_by_hour.htm", is_child=True))

    nav.extend([
        NavPage("Qs by minute", "qs_by_minute.htm"),
        NavPage("One minute rates", "one_minute_rates.htm"),
        NavPage("Prefixes", "prefixes.htm"),
        NavPage("Distance", "distance.htm"),
        NavPage("Beam heading", "beam_heading.htm"),
        NavPage("Break time", "breaks.htm"),
        NavPage("Continents", "continents.htm"),
        NavPage("Fields map", "fields_map.htm"),
        NavPage("Callsign length", "callsign_length.htm"),
        NavPage("Callsign structure", "callsign_structure.htm"),
        NavPage("CQ zones", "zones_cq.htm"),
        NavPage("ITU zones", "zones_itu.htm"),
        NavPage("Not in master", "not_in_master.htm"),
        NavPage("Possible errors", "possible_errors.htm"),
    ])

    if has_lotw:
        nav.append(NavPage("LOTW check", "lotw_check.htm"))

    # Phase 3: Charts
    nav.extend([
        NavPage("Charts", "charts_qs_by_band.htm"),
        NavPage("Qs by band chart", "charts_qs_by_band.htm", is_child=True),
        NavPage("Qs by mode chart", "charts_qs_by_mode.htm", is_child=True),
        NavPage("Top 10 countries", "charts_top_10_countries.htm", is_child=True),
        NavPage("Continents chart", "charts_continents.htm", is_child=True),
        NavPage("Beam heading chart", "charts_beam_heading.htm", is_child=True),
        NavPage("Frequencies", "charts_frequencies.htm", is_child=True),
        NavPage("Map", "map.htm"),
        NavPage("KMZ downloads", "kmz.htm"),
    ])

    # LCR summary (only if LCR data present)
    if has_lcr:
        nav.append(NavPage("LCR Summary", "lcr_summary.htm"))

    return nav


class Renderer:
    """Renders contest log statistics to HTML files."""

    def __init__(self, log: ContestLog, output_dir: str,
                 scp_calls: set[str] | None = None,
                 lotw_users: set[str] | None = None,
                 callsign_lookup: str = 'qrz',
                 photos_dir: str | None = None,
                 score_result=None,
                 pota_lookup=None,
                 activated_park: str = "",
                 activated_park_date: str = "",
                 distance_unit: str = "km"):
        self.log = log
        self.output_dir = output_dir
        self.scp_calls = scp_calls
        self.lotw_users = lotw_users
        self.photos_dir = photos_dir
        self.score_result = score_result
        self.pota_lookup = pota_lookup
        self.activated_park = activated_park
        self.activated_park_date = activated_park_date
        self.distance_unit = distance_unit
        self.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.version = __version__
        self.repo_url = REPO_URL
        has_lcr = any(q.lcr_error for q in log.qsos)
        self.has_pota = any(q.pota_ref or q.my_pota_ref for q in log.qsos)
        self.nav_pages = _build_nav(log.active_bands, has_lcr,
                                    has_lotw=lotw_users is not None,
                                    has_pota=self.has_pota)

        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=False,
        )
        self.env.globals['loop_class'] = lambda i: 'td0' if i % 2 == 0 else 'td1'

        base_url = ('https://www.hamqth.com/' if callsign_lookup == 'hamqth'
                     else 'https://www.qrz.com/db/')
        self.env.globals['callsign_url'] = lambda call: base_url + call
        self.env.globals['callsign_base_url'] = base_url

    def _common_context(self, page_title: str, filename: str) -> dict:
        """Build the common template context shared by all pages."""
        filenames = [p.filename for p in self.nav_pages]
        try:
            idx = filenames.index(filename)
        except ValueError:
            idx = -1

        prev_page = self.nav_pages[idx - 1] if idx > 0 else None
        next_page = self.nav_pages[idx + 1] if 0 <= idx < len(self.nav_pages) - 1 else None

        year = self.log.start_time.year if self.log.start_time else ""

        if self.activated_park:
            contest_title = (f"{self.activated_park_date} POTA "
                             f"{self.activated_park} {self.log.station_call}")
        else:
            contest_title = f"{self.log.contest_name} {self.log.station_call}"

        return {
            'page_title': page_title,
            'contest_title': contest_title,
            'contest_year': year,
            'contest_id': self.log.contest_name,
            'station_call': self.log.station_call,
            'activated_park': self.activated_park,
            'activated_park_date': self.activated_park_date,
            'nav_pages': self.nav_pages,
            'current_filename': filename,
            'prev_page': prev_page,
            'next_page': next_page,
            'version': self.version,
            'generated_at': self.generated_at,
            'repo_url': self.repo_url,
        }

    def _render_page(self, template_name: str, filename: str,
                     page_title: str, extra_context: dict):
        """Render a single page to the output directory."""
        tmpl = self.env.get_template(template_name)
        ctx = self._common_context(page_title, filename)
        ctx.update(extra_context)

        html = tmpl.render(**ctx)
        out_path = os.path.join(self.output_dir, filename)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        os.chmod(out_path, 0o644)

    def _copy_assets(self):
        """Copy CSS and JS assets to output directory."""
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        for fname in os.listdir(assets_dir):
            src = os.path.join(assets_dir, fname)
            if os.path.isfile(src):
                dest = os.path.join(self.output_dir, fname)
                shutil.copy2(src, dest)
                os.chmod(dest, 0o644)

    def _copy_photos(self) -> dict[str, str]:
        """Find operator photos, copy to output, return call→filename map.

        When a stem has multiple image extensions (e.g. ny4i.jpg AND ny4i.png),
        pick by preference order jpg > jpeg > png and warn once.
        """
        if not self.photos_dir or not os.path.isdir(self.photos_dir):
            return {}

        # Group files by uppercase stem so duplicates can be detected.
        PREF = {'.jpg': 0, '.jpeg': 1, '.png': 2}
        by_stem: dict[str, list[str]] = {}
        for fname in os.listdir(self.photos_dir):
            stem, ext = os.path.splitext(fname)
            if ext.lower() in PREF:
                by_stem.setdefault(stem.upper(), []).append(fname)

        available: dict[str, str] = {}
        for stem, flist in by_stem.items():
            flist.sort(key=lambda f: PREF[os.path.splitext(f)[1].lower()])
            available[stem] = flist[0]
            if len(flist) > 1:
                print(f"Warning: multiple images for {stem} "
                      f"({', '.join(flist)}); using {flist[0]}")

        photo_map: dict[str, str] = {}
        photos_out = os.path.join(self.output_dir, "photos")
        for op in self.log.operators:
            match = available.get(op.upper())
            if match:
                os.makedirs(photos_out, exist_ok=True)
                os.chmod(photos_out, 0o755)
                dest = os.path.join(photos_out, match)
                shutil.copy2(os.path.join(self.photos_dir, match), dest)
                os.chmod(dest, 0o644)
                photo_map[op] = f"photos/{match}"

        return photo_map

    def render_all(self):
        """Render all statistics pages."""
        os.makedirs(self.output_dir, exist_ok=True)
        os.chmod(self.output_dir, 0o755)
        self._copy_assets()
        photo_map = self._copy_photos()

        # ── Phase 1: Core pages ──
        self._render_page("index.html", "index.htm", "Main",
                          pages.prepare_index(self.log, self.score_result,
                                              distance_unit=self.distance_unit))
        self._render_page("summary.html", "summary.htm", "Summary",
                          pages.prepare_summary(self.log, self.score_result))
        self._render_page("log.html", "log.htm", "Log",
                          pages.prepare_log(self.log))
        self._render_page("operators.html", "operators.htm", "Operators",
                          pages.prepare_operators(self.log, photo_map))
        self._render_page("dupes.html", "dupes.htm", "Dupes",
                          pages.prepare_dupes(self.log))

        # ── Phase 2: Geographic + Rate pages ──
        self._render_page("callsigns.html", "all_callsigns.htm", "All callsigns",
                          pages.prepare_callsigns(self.log))
        self._render_page("rates.html", "rates.htm", "Rates",
                          pages.prepare_rates(self.log))
        self._render_page("countries.html", "countries.htm", "Countries",
                          pages.prepare_countries(self.log))

        # Countries by time: all + per-band
        self._render_page("countries_by_time.html", "countries_by_time.htm",
                          "Countries by time",
                          pages.prepare_countries_by_time(self.log))
        for band in self.log.active_bands:
            b = band.replace('m', '')
            self._render_page("countries_by_time.html",
                              f"{b}_countries_by_time.htm",
                              f"Countries by time - {b}",
                              pages.prepare_countries_by_time(self.log, band))

        self._render_page("station.html", "qs_per_station.htm", "Qs per station",
                          pages.prepare_station(self.log))
        self._render_page("passed_qsos.html", "passed_qsos.htm", "Passed QSOs",
                          pages.prepare_passed_qsos(self.log))

        # QSOs by hour sheet (tabular hourly totals using heatmap template)
        self._render_page("hourly_heatmap.html", "qs_by_hour_sheet.htm",
                          "Qs by hour sheet",
                          pages.prepare_hourly_heatmap(self.log))

        # QSOs by hour: all + per-band
        self._render_page("hourly_heatmap.html", "graphs_qs_by_hour.htm",
                          "Qs by hour",
                          pages.prepare_hourly_heatmap(self.log))
        for band in self.log.active_bands:
            b = band.replace('m', '')
            self._render_page("hourly_heatmap.html",
                              f"{b}_graphs_qs_by_hour.htm",
                              f"Qs by hour - {b}",
                              pages.prepare_hourly_heatmap(self.log, band))

        self._render_page("minute.html", "qs_by_minute.htm", "Qs by minute",
                          pages.prepare_minute(self.log))
        self._render_page("minute.html", "one_minute_rates.htm", "One minute rates",
                          pages.prepare_one_minute_rates(self.log))
        self._render_page("prefixes.html", "prefixes.htm", "Prefixes",
                          pages.prepare_prefixes(self.log))
        self._render_page("distance.html", "distance.htm", "Distance",
                          pages.prepare_distance(self.log, distance_unit=self.distance_unit))
        self._render_page("beam_heading.html", "beam_heading.htm", "Beam heading",
                          pages.prepare_beam_heading(self.log))
        self._render_page("breaks.html", "breaks.htm", "Break time",
                          pages.prepare_breaks(self.log))
        self._render_page("continents.html", "continents.htm", "Continents",
                          pages.prepare_continents(self.log))
        self._render_page("fields_map.html", "fields_map.htm", "Fields map",
                          pages.prepare_fields_map(self.log))
        self._render_page("misc.html", "callsign_length.htm", "Callsign length",
                          pages.prepare_callsign_length(self.log))
        self._render_page("misc.html", "callsign_structure.htm", "Callsign structure",
                          pages.prepare_callsign_structure(self.log))
        self._render_page("zones.html", "zones_cq.htm", "CQ zones",
                          pages.prepare_zones(self.log, 'cq'))
        self._render_page("zones.html", "zones_itu.htm", "ITU zones",
                          pages.prepare_zones(self.log, 'itu'))
        self._render_page("misc.html", "not_in_master.htm", "Not in master",
                          pages.prepare_not_in_master(self.log, self.scp_calls))
        self._render_page("misc.html", "possible_errors.htm", "Possible errors",
                          pages.prepare_possible_errors(self.log))

        if self.lotw_users is not None:
            self._render_page("misc.html", "lotw_check.htm", "LOTW check",
                              pages.prepare_lotw_check(self.log, self.lotw_users))

        # POTA parks page — only when log contains POTA references
        if self.has_pota:
            self._render_page("parks.html", "parks.htm", "POTA parks",
                              pages.prepare_parks(self.log, self.pota_lookup))

        # ── Phase 3: Charts + Map + LCR ──
        self._render_page("chart.html", "charts_qs_by_band.htm", "Qs by band chart",
                          pages.prepare_chart_qs_by_band(self.log))
        self._render_page("chart.html", "charts_qs_by_mode.htm", "Qs by mode chart",
                          pages.prepare_chart_qs_by_mode(self.log))
        self._render_page("chart.html", "charts_top_10_countries.htm", "Top 10 countries",
                          pages.prepare_chart_top_countries(self.log))
        self._render_page("chart.html", "charts_continents.htm", "Continents chart",
                          pages.prepare_chart_continents(self.log))
        self._render_page("chart.html", "charts_beam_heading.htm", "Beam heading chart",
                          pages.prepare_chart_beam_heading(self.log))
        self._render_page("chart.html", "charts_frequencies.htm", "Frequencies",
                          pages.prepare_chart_frequencies(self.log))
        self._render_page("map.html", "map.htm", "Map",
                          pages.prepare_map(self.log, self.pota_lookup,
                                            distance_unit=self.distance_unit))

        # LCR summary (only if LCR data present)
        if any(q.lcr_error for q in self.log.qsos):
            self._render_page("lcr_summary.html", "lcr_summary.htm", "LCR Summary",
                              pages.prepare_lcr_summary(self.log))

        # KMZ export (must run before prepare_kmz so file sizes are known)
        from ..kmz_export import export_kmz
        export_kmz(self.log, self.output_dir)

        self._render_page("kmz.html", "kmz.htm", "KMZ downloads",
                          pages.prepare_kmz(self.log, self.output_dir))
