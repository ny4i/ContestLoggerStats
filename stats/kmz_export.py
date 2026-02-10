"""KMZ/KML export for contest QSO data."""

import os
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring

from .contest_data import ContestLog

# Band colors (KML format: aabbggrr, muted accessible palette)
BAND_COLORS_KML = {
    '160m': 'ffe9a50e',  # sky #0ea5e9
    '80m':  'ff0b9ef5',  # amber #f59e0b
    '40m':  'ff81b910',  # emerald #10b981
    '20m':  'fff16663',  # indigo #6366f1
    '15m':  'ff4444ef',  # red #ef4444
    '10m':  'fff65c8b',  # violet #8b5cf6
    '6m':   'ff9948ec',  # pink #ec4899
    '2m':   'ff1673f9',  # orange #f97316
}


def _create_kml(log: ContestLog, band: str | None = None) -> bytes:
    """Create KML content for all QSOs or a specific band."""
    kml = Element('kml', xmlns='http://www.opengis.net/kml/2.2')
    doc = SubElement(kml, 'Document')

    band_label = band if band else 'All bands'
    name_el = SubElement(doc, 'name')
    name_el.text = f"{log.station_call} - {log.contest_name} - {band_label}"

    # Define styles per band
    for b, color in BAND_COLORS_KML.items():
        style = SubElement(doc, 'Style', id=f'style_{b}')
        icon_style = SubElement(style, 'IconStyle')
        color_el = SubElement(icon_style, 'color')
        color_el.text = color
        scale_el = SubElement(icon_style, 'scale')
        scale_el.text = '0.6'

    # Station marker
    if log.station_lat != 0 or log.station_lon != 0:
        pm = SubElement(doc, 'Placemark')
        pm_name = SubElement(pm, 'name')
        pm_name.text = log.station_call
        pm_desc = SubElement(pm, 'description')
        pm_desc.text = f"Station: {log.station_call}\nLocator: {log.locator}"
        point = SubElement(pm, 'Point')
        coords = SubElement(point, 'coordinates')
        coords.text = f"{log.station_lon},{log.station_lat},0"

    # QSO placemarks
    qsos = log.qsos if band is None else [q for q in log.qsos if q.band == band]
    for q in qsos:
        if q.dxcc_lat == 0 and q.dxcc_lon == 0:
            continue
        pm = SubElement(doc, 'Placemark')
        pm_name = SubElement(pm, 'name')
        pm_name.text = q.call
        pm_desc = SubElement(pm, 'description')
        pm_desc.text = (
            f"Call: {q.call}\n"
            f"Band: {q.band} Mode: {q.mode}\n"
            f"Time: {q.datetime_utc.strftime('%Y-%m-%d %H:%M')}\n"
            f"Country: {q.country}\n"
            f"Distance: {int(q.distance_km)} km\n"
            f"Bearing: {int(q.bearing_deg)}°"
        )
        style_url = SubElement(pm, 'styleUrl')
        style_url.text = f'#style_{q.band}'
        point = SubElement(pm, 'Point')
        coords = SubElement(point, 'coordinates')
        coords.text = f"{q.dxcc_lon},{q.dxcc_lat},0"

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(kml, encoding='unicode').encode('utf-8')


def export_kmz(log: ContestLog, output_dir: str):
    """Export KMZ files: one for all bands, one per active band."""
    # All bands
    all_kml = _create_kml(log)
    all_kmz_path = os.path.join(output_dir, 'qsos_all.kmz')
    with zipfile.ZipFile(all_kmz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('doc.kml', all_kml)

    # Per band
    for band in log.active_bands:
        b = band.replace('m', '')
        kml_data = _create_kml(log, band)
        kmz_path = os.path.join(output_dir, f'qsos_{b}.kmz')
        with zipfile.ZipFile(kmz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('doc.kml', kml_data)
