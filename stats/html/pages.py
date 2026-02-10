"""Page content generators for HTML statistics.

Each function takes a ContestLog and returns a dict of template variables.
"""

import json
from collections import Counter, defaultdict
from datetime import timedelta
from ..contest_data import ContestLog, QSO
from ..cty_dat import extract_wpx_prefix


def prepare_index(log: ContestLog) -> dict:
    """Main dashboard page data."""
    total = len(log.qsos)
    dupes = sum(1 for q in log.qsos if q.is_dupe)
    unique_calls = len({q.call for q in log.qsos})
    countries = len({q.country for q in log.qsos if q.country})
    prefixes = len({extract_wpx_prefix(q.call) for q in log.qsos})
    total_km = sum(q.distance_km for q in log.qsos if q.distance_km > 0)
    non_zero_dist = sum(1 for q in log.qsos if q.distance_km > 0)

    # Moves: band/mode changes between consecutive QSOs
    moves = 0
    for i in range(1, len(log.qsos)):
        prev, curr = log.qsos[i - 1], log.qsos[i]
        if prev.band != curr.band or prev.mode_group != curr.mode_group:
            moves += 1

    # Time calculations
    total_seconds = (log.end_time - log.start_time).total_seconds()
    total_mins = int(total_seconds / 60)

    # Break time: gaps > 5 minutes between QSOs
    sorted_qsos = sorted(log.qsos, key=lambda q: q.datetime_utc)
    break_mins = 0
    for i in range(1, len(sorted_qsos)):
        gap = (sorted_qsos[i].datetime_utc - sorted_qsos[i - 1].datetime_utc).total_seconds() / 60
        if gap > 5:
            break_mins += int(gap)

    op_mins = total_mins - break_mins

    def fmt_hhmm(minutes):
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    break_pct = (break_mins / total_mins * 100) if total_mins > 0 else 0

    return {
        'station_country': log.qsos[0].country if log.qsos and log.qsos[0].country else '',
        'locator': log.locator,
        'category': log.category,
        'operators': log.operators,
        'start_time': log.start_time.strftime('%d-%b-%Y %H:%M'),
        'end_time': log.end_time.strftime('%d-%b-%Y %H:%M'),
        'participation_time': f"{fmt_hhmm(total_mins)} ({total_mins} min.)",
        'break_time': f"{fmt_hhmm(break_mins)} ({break_mins} min., {break_pct:.2f} %)",
        'operating_time': f"{fmt_hhmm(op_mins)} ({op_mins} min.)",
        'total_qsos': total,
        'dupe_count': dupes,
        'dupe_pct': (dupes / total * 100) if total else 0,
        'unique_calls': unique_calls,
        'qsos_per_station': total / unique_calls if unique_calls else 0,
        'km_per_qso': int(total_km / non_zero_dist) if non_zero_dist else 0,
        'country_count': countries,
        'prefix_count': prefixes,
        'move_count': moves,
        'software': '',
    }


def prepare_summary(log: ContestLog) -> dict:
    """Band × mode summary matrix."""
    band_order = ["160m", "80m", "40m", "20m", "15m", "10m", "6m", "2m"]
    mode_groups = log.active_mode_groups
    total = len(log.qsos)

    band_rows = []
    totals_by_mode = Counter()

    for band in band_order:
        band_qsos = [q for q in log.qsos if q.band == band]
        if not band_qsos:
            continue

        by_mode = Counter()
        for q in band_qsos:
            by_mode[q.mode_group] += 1
            totals_by_mode[q.mode_group] += 1

        band_countries = len({q.country for q in band_qsos if q.country})

        band_rows.append({
            'label': band.replace('m', ''),
            'by_mode': dict(by_mode),
            'total': len(band_qsos),
            'countries': band_countries,
        })

    return {
        'band_rows': band_rows,
        'mode_groups': mode_groups,
        'totals_by_mode': dict(totals_by_mode),
        'total_qsos': total,
    }


def prepare_operators(log: ContestLog) -> dict:
    """Operator statistics."""
    op_qsos = defaultdict(list)
    for q in log.qsos:
        op_qsos[q.operator].append(q)

    total = len(log.qsos)
    has_lcr = any(q.lcr_error for q in log.qsos)

    stats = []
    for op in sorted(op_qsos.keys()):
        qs = op_qsos[op]
        modes = Counter(q.mode_group for q in qs)
        countries = len({q.country for q in qs if q.country})
        dupes = sum(1 for q in qs if q.is_dupe)
        errors = sum(1 for q in qs if q.lcr_error)

        stats.append({
            'call': op,
            'total': len(qs),
            'pct': len(qs) / total * 100 if total else 0,
            'cw': modes.get('CW', 0),
            'dig': modes.get('DIG', 0),
            'ph': modes.get('PH', 0),
            'countries': countries,
            'dupes': dupes,
            'errors': errors,
        })

    stats.sort(key=lambda x: x['total'], reverse=True)

    return {
        'operator_stats': stats,
        'has_lcr': has_lcr,
    }


def prepare_dupes(log: ContestLog) -> dict:
    """Duplicate QSO list."""
    dupe_qsos = []
    for i, q in enumerate(log.qsos):
        if q.is_dupe:
            dupe_qsos.append({
                'seq': i + 1,
                'date': q.datetime_utc.strftime('%Y-%m-%d'),
                'time': q.datetime_utc.strftime('%H:%M'),
                'call': q.call,
                'band': q.band,
                'mode': q.mode,
                'freq': f"{q.freq_mhz:.3f}" if q.freq_mhz else '',
                'stx': q.stx,
                'srx': q.srx,
                'operator': q.operator,
            })

    return {
        'dupe_qsos': dupe_qsos,
        'dupe_count': len(dupe_qsos),
        'dupe_pct': len(dupe_qsos) / len(log.qsos) * 100 if log.qsos else 0,
        'total_qsos': len(log.qsos),
    }


def prepare_log(log: ContestLog) -> dict:
    """Full log with pagination data."""
    page_size = 500
    qso_rows = []

    for i, q in enumerate(log.qsos):
        page_num = (i // page_size) + 1
        qso_rows.append({
            'seq': i + 1,
            'date': q.datetime_utc.strftime('%Y-%m-%d'),
            'time': q.datetime_utc.strftime('%H:%M'),
            'call': q.call,
            'band': q.band,
            'mode': q.mode,
            'freq': f"{q.freq_mhz:.3f}" if q.freq_mhz else '',
            'rst_sent': q.rst_sent,
            'rst_rcvd': q.rst_rcvd,
            'stx': q.stx,
            'srx': q.srx,
            'country': q.country,
            'operator': q.operator,
            'is_dupe': q.is_dupe,
            'lcr_error': q.lcr_error,
            'page': page_num,
        })

    total = len(log.qsos)
    num_pages = (total + page_size - 1) // page_size
    pages = []
    for p in range(1, num_pages + 1):
        start = (p - 1) * page_size + 1
        end = min(p * page_size, total)
        pages.append({'num': p, 'label': f"{start}-{end}"})

    return {
        'qso_rows': qso_rows,
        'pages': pages,
    }


# ── Phase 2 page generators ──────────────────────────────────────────


def _filter_band(qsos: list[QSO], band: str | None) -> list[QSO]:
    """Filter QSOs by band (None = all bands)."""
    if band is None:
        return qsos
    return [q for q in qsos if q.band == band]


def prepare_countries(log: ContestLog) -> dict:
    """Country breakdown table."""
    total = len(log.qsos)
    mode_groups = log.active_mode_groups
    country_qsos = defaultdict(list)
    for q in log.qsos:
        if q.country:
            country_qsos[q.country].append(q)

    rows = []
    for name in sorted(country_qsos, key=lambda c: len(country_qsos[c]), reverse=True):
        qs = country_qsos[name]
        by_mode = Counter(q.mode_group for q in qs)
        rows.append({
            'name': name,
            'prefix': qs[0].prefix if qs else '',
            'continent': qs[0].continent if qs else '',
            'cq_zone': qs[0].cq_zone if qs else 0,
            'total': len(qs),
            'pct': len(qs) / total * 100 if total else 0,
            'by_mode': dict(by_mode),
        })

    return {'country_rows': rows, 'mode_groups': mode_groups}


def prepare_countries_by_time(log: ContestLog, band: str | None = None) -> dict:
    """Countries by hour heatmap."""
    qsos = _filter_band(log.qsos, band)
    band_label = f"Band: {band}" if band else "All bands"

    country_hour = defaultdict(lambda: defaultdict(int))
    all_hours = set()
    for q in qsos:
        if q.country:
            h = q.datetime_utc.hour
            country_hour[q.country][h] += 1
            all_hours.add(h)

    hours = sorted(all_hours)
    rows = []
    for name in sorted(country_hour, key=lambda c: sum(country_hour[c].values()), reverse=True):
        rows.append({
            'name': name,
            'total': sum(country_hour[name].values()),
            'by_hour': dict(country_hour[name]),
        })

    return {'country_rows': rows, 'hours': hours, 'band_label': band_label}


def prepare_continents(log: ContestLog) -> dict:
    """Continent breakdown."""
    total = len(log.qsos)
    mode_groups = log.active_mode_groups
    cont_qsos = defaultdict(list)
    for q in log.qsos:
        if q.continent:
            cont_qsos[q.continent].append(q)

    rows = []
    for name in sorted(cont_qsos, key=lambda c: len(cont_qsos[c]), reverse=True):
        qs = cont_qsos[name]
        by_mode = Counter(q.mode_group for q in qs)
        countries = len({q.country for q in qs})
        rows.append({
            'name': name,
            'total': len(qs),
            'pct': len(qs) / total * 100 if total else 0,
            'by_mode': dict(by_mode),
            'countries': countries,
        })

    return {'continent_rows': rows, 'mode_groups': mode_groups}


def prepare_zones(log: ContestLog, zone_type: str = 'cq') -> dict:
    """CQ or ITU zone breakdown."""
    total = len(log.qsos)
    mode_groups = log.active_mode_groups
    zone_qsos = defaultdict(list)
    for q in log.qsos:
        z = q.cq_zone if zone_type == 'cq' else q.itu_zone
        if z > 0:
            zone_qsos[z].append(q)

    rows = []
    for z in sorted(zone_qsos):
        qs = zone_qsos[z]
        by_mode = Counter(q.mode_group for q in qs)
        countries = len({q.country for q in qs})
        rows.append({
            'zone': z,
            'total': len(qs),
            'pct': len(qs) / total * 100 if total else 0,
            'by_mode': dict(by_mode),
            'countries': countries,
        })

    return {'zone_rows': rows, 'mode_groups': mode_groups}


def prepare_distance(log: ContestLog) -> dict:
    """Distance histogram in 500km bins."""
    bands = log.active_bands
    bin_size = 500
    max_dist = max((q.distance_km for q in log.qsos if q.distance_km > 0), default=0)
    num_bins = int(max_dist / bin_size) + 1

    bins = defaultdict(lambda: defaultdict(int))
    total_km = 0
    total_count = 0
    max_km = 0
    max_call = ''

    for q in log.qsos:
        if q.distance_km > 0:
            b = int(q.distance_km / bin_size)
            bins[b]['total'] = bins[b].get('total', 0) + 1
            bins[b][q.band] = bins[b].get(q.band, 0) + 1
            total_km += q.distance_km
            total_count += 1
            if q.distance_km > max_km:
                max_km = q.distance_km
                max_call = q.call

    total = len(log.qsos)
    rows = []
    for i in range(num_bins + 1):
        if i not in bins:
            continue
        label = f"{i * bin_size}-{(i + 1) * bin_size}"
        rows.append({
            'label': label,
            'total': bins[i].get('total', 0),
            'pct': bins[i].get('total', 0) / total * 100 if total else 0,
            'by_band': {b: bins[i].get(b, 0) for b in bands},
        })

    return {
        'distance_rows': rows,
        'bands': bands,
        'avg_km': int(total_km / total_count) if total_count else 0,
        'max_km': int(max_km),
        'max_call': max_call,
    }


def prepare_beam_heading(log: ContestLog) -> dict:
    """Beam heading histogram in 10-degree bins."""
    bands = log.active_bands
    bins = defaultdict(lambda: defaultdict(int))
    total = len(log.qsos)

    for q in log.qsos:
        if q.bearing_deg >= 0:
            b = int(q.bearing_deg / 10) * 10
            bins[b]['total'] = bins[b].get('total', 0) + 1
            bins[b][q.band] = bins[b].get(q.band, 0) + 1

    rows = []
    for i in range(0, 360, 10):
        if i not in bins:
            continue
        label = f"{i}°-{i + 10}°"
        rows.append({
            'label': label,
            'total': bins[i].get('total', 0),
            'pct': bins[i].get('total', 0) / total * 100 if total else 0,
            'by_band': {b: bins[i].get(b, 0) for b in bands},
        })

    return {'heading_rows': rows, 'bands': bands}


def prepare_rates(log: ContestLog) -> dict:
    """Max rate windows and hourly totals."""
    bands = log.active_bands
    sorted_qsos = sorted(log.qsos, key=lambda q: q.datetime_utc)

    # Max rate for different windows
    rate_rows = []
    for window_mins in [10, 20, 30, 60, 120]:
        best_count = 0
        best_time = ''
        best_op = ''
        for i in range(len(sorted_qsos)):
            end_time = sorted_qsos[i].datetime_utc + timedelta(minutes=window_mins)
            count = sum(1 for q in sorted_qsos[i:] if q.datetime_utc <= end_time)
            if count > best_count:
                best_count = count
                best_time = sorted_qsos[i].datetime_utc.strftime('%Y-%m-%d %H:%M')
                # Most common operator in window
                ops_in_window = [q.operator for q in sorted_qsos[i:]
                                 if q.datetime_utc <= end_time and q.operator]
                if ops_in_window:
                    best_op = Counter(ops_in_window).most_common(1)[0][0]

        rate = int(best_count * 60 / window_mins) if window_mins > 0 else 0
        rate_rows.append({
            'window': window_mins,
            'rate': rate,
            'count': best_count,
            'time': best_time,
            'operator': best_op,
        })

    # Hourly totals
    hourly = defaultdict(lambda: defaultdict(int))
    for q in sorted_qsos:
        h_label = q.datetime_utc.strftime('%d %b %H:00')
        hourly[h_label]['total'] = hourly[h_label].get('total', 0) + 1
        hourly[h_label][q.band] = hourly[h_label].get(q.band, 0) + 1

    hourly_rows = []
    for label in sorted(hourly):
        hourly_rows.append({
            'label': label,
            'total': hourly[label].get('total', 0),
            'by_band': {b: hourly[label].get(b, 0) for b in bands},
        })

    return {'rate_rows': rate_rows, 'hourly_rows': hourly_rows, 'bands': bands}


def prepare_hourly_heatmap(log: ContestLog, band: str | None = None) -> dict:
    """QSOs by hour heatmap, grouped by operator."""
    qsos = _filter_band(log.qsos, band)
    band_label = f"Band: {band}" if band else "All bands"
    operators = sorted({q.operator for q in qsos if q.operator})

    hourly = defaultdict(lambda: defaultdict(int))
    all_labels = set()
    for q in qsos:
        label = q.datetime_utc.strftime('%d %b %H:00')
        hourly[label][q.operator] += 1
        hourly[label]['total'] = hourly[label].get('total', 0) + 1
        all_labels.add(label)

    max_per_cell = max(
        (v for h in hourly.values() for k, v in h.items() if k != 'total'),
        default=1
    )
    heat_divisor = max(max_per_cell // 9, 1)

    rows = []
    for label in sorted(all_labels):
        rows.append({
            'label': label,
            'total': hourly[label].get('total', 0),
            'by_op': dict(hourly[label]),
        })

    return {
        'hour_rows': rows,
        'operators': operators,
        'band_label': band_label,
        'heat_divisor': heat_divisor,
    }


def prepare_callsigns(log: ContestLog) -> dict:
    """All unique callsigns."""
    call_data = defaultdict(lambda: {'count': 0, 'country': '', 'bands': set()})
    for q in log.qsos:
        call_data[q.call]['count'] += 1
        call_data[q.call]['country'] = q.country
        call_data[q.call]['bands'].add(q.band)

    rows = []
    for call in sorted(call_data):
        d = call_data[call]
        rows.append({
            'call': call,
            'count': d['count'],
            'country': d['country'],
            'bands': ', '.join(sorted(d['bands'])),
        })

    return {'callsign_rows': rows, 'total_unique': len(rows)}


def prepare_prefixes(log: ContestLog) -> dict:
    """WPX prefix table."""
    prefix_data = defaultdict(lambda: {'count': 0, 'country': ''})
    for q in log.qsos:
        pfx = extract_wpx_prefix(q.call)
        prefix_data[pfx]['count'] += 1
        prefix_data[pfx]['country'] = q.country

    rows = []
    for pfx in sorted(prefix_data):
        rows.append({
            'prefix': pfx,
            'count': prefix_data[pfx]['count'],
            'country': prefix_data[pfx]['country'],
        })

    return {'prefix_rows': rows, 'total_prefixes': len(rows)}


def prepare_breaks(log: ContestLog, gap_threshold: int = 5) -> dict:
    """Break time analysis (gaps > threshold minutes)."""
    sorted_qsos = sorted(log.qsos, key=lambda q: q.datetime_utc)
    breaks = []
    total_break = 0

    for i in range(1, len(sorted_qsos)):
        gap = (sorted_qsos[i].datetime_utc - sorted_qsos[i - 1].datetime_utc).total_seconds() / 60
        if gap > gap_threshold:
            breaks.append({
                'start': sorted_qsos[i - 1].datetime_utc.strftime('%d %b %H:%M'),
                'end': sorted_qsos[i].datetime_utc.strftime('%d %b %H:%M'),
                'duration': int(gap),
                'before_band': sorted_qsos[i - 1].band,
                'before_mode': sorted_qsos[i - 1].mode_group,
                'after_band': sorted_qsos[i].band,
                'after_mode': sorted_qsos[i].mode_group,
            })
            total_break += int(gap)

    return {
        'break_rows': breaks,
        'break_count': len(breaks),
        'total_break_mins': total_break,
        'gap_threshold': gap_threshold,
    }


def prepare_station(log: ContestLog) -> dict:
    """QSOs per station/band/mode breakdown by operator."""
    operators = sorted({q.operator for q in log.qsos if q.operator})
    total = len(log.qsos)

    combos = defaultdict(lambda: defaultdict(int))
    for q in log.qsos:
        label = f"{q.band} {q.mode_group}"
        combos[label][q.operator] += 1
        combos[label]['total'] = combos[label].get('total', 0) + 1

    rows = []
    for label in sorted(combos):
        rows.append({
            'label': label,
            'total': combos[label].get('total', 0),
            'pct': combos[label].get('total', 0) / total * 100 if total else 0,
            'by_op': dict(combos[label]),
        })

    return {'station_rows': rows, 'operators': operators}


def prepare_minute(log: ContestLog) -> dict:
    """QSOs by minute detail."""
    by_min = defaultdict(list)
    for q in log.qsos:
        key = q.datetime_utc.strftime('%Y-%m-%d %H:%M')
        by_min[key].append(q)

    rows = []
    for t in sorted(by_min):
        qs = by_min[t]
        rows.append({
            'time': t,
            'count': len(qs),
            'calls': ', '.join(q.call for q in qs[:5]),
            'band': ', '.join(sorted({q.band for q in qs})),
            'mode': ', '.join(sorted({q.mode_group for q in qs})),
        })

    return {'minute_rows': rows, 'subtitle': 'QSOs by minute'}


def prepare_one_minute_rates(log: ContestLog) -> dict:
    """Peak one-minute rates."""
    by_min = defaultdict(list)
    for q in log.qsos:
        key = q.datetime_utc.strftime('%Y-%m-%d %H:%M')
        by_min[key].append(q)

    # Sort by count descending, take top 20
    top = sorted(by_min.items(), key=lambda x: len(x[1]), reverse=True)[:20]

    rows = []
    for t, qs in top:
        rows.append({
            'time': t,
            'count': len(qs),
            'calls': ', '.join(q.call for q in qs[:5]),
            'band': ', '.join(sorted({q.band for q in qs})),
            'mode': ', '.join(sorted({q.mode_group for q in qs})),
        })

    return {'minute_rows': rows, 'subtitle': 'Peak one-minute rates (top 20)'}


def prepare_fields_map(log: ContestLog) -> dict:
    """Maidenhead grid fields heatmap."""
    field_counts = defaultdict(int)
    for q in log.qsos:
        if q.dxcc_lat != 0 or q.dxcc_lon != 0:
            # Convert lat/lon to field (2-char Maidenhead)
            lon_field = int((q.dxcc_lon + 180) / 20)
            lat_field = int((q.dxcc_lat + 90) / 10)
            if 0 <= lon_field < 18 and 0 <= lat_field < 18:
                col = chr(ord('A') + lon_field)
                row = chr(ord('A') + lat_field)
                field = col + row
                field_counts[field] += 1

    field_cols = [chr(ord('A') + i) for i in range(18)]
    field_rows_data = []
    for ri in range(17, -1, -1):
        row_label = chr(ord('A') + ri)
        row_data = {}
        for ci in range(18):
            col_label = chr(ord('A') + ci)
            field = col_label + row_label
            if field in field_counts:
                row_data[col_label] = field_counts[field]
        field_rows_data.append((row_label, row_data))

    total_fields = len(field_counts)
    return {
        'field_rows': field_rows_data,
        'field_cols': field_cols,
        'total_fields': total_fields,
        'field_pct': total_fields / 324 * 100,
    }


def prepare_callsign_length(log: ContestLog) -> dict:
    """Callsign length histogram."""
    lengths = Counter(len(q.call) for q in log.qsos)
    total = len(log.qsos)
    rows = []
    for length in sorted(lengths):
        rows.append([length, lengths[length], f"{lengths[length] / total * 100:.1f}"])
    return {
        'headers': ['Length', 'QSOs', '%'],
        'rows': rows,
        'description': 'Distribution of callsign lengths.',
    }


def prepare_callsign_structure(log: ContestLog) -> dict:
    """Callsign structure analysis (prefix length)."""
    structures = Counter()
    for q in log.qsos:
        pfx = extract_wpx_prefix(q.call)
        suffix = q.call[len(pfx):]
        structure = f"{len(pfx)}+{len(suffix)}"
        structures[structure] += 1

    total = len(log.qsos)
    rows = []
    for struct in sorted(structures, key=lambda s: structures[s], reverse=True):
        rows.append([struct, structures[struct], f"{structures[struct] / total * 100:.1f}"])
    return {
        'headers': ['Structure', 'QSOs', '%'],
        'rows': rows,
        'description': 'Callsign structure: prefix_length+suffix_length.',
    }


def prepare_not_in_master(log: ContestLog,
                          scp_calls: set[str] | None = None) -> dict:
    """Callsigns not found in MASTER.SCP (or cty.dat as fallback)."""
    total_calls = len({q.call for q in log.qsos})

    if scp_calls is not None:
        # Check unique callsigns against MASTER.SCP
        seen = set()
        not_found = []
        for q in log.qsos:
            if q.is_dupe:
                continue
            call_upper = q.call.upper()
            if call_upper not in scp_calls and call_upper not in seen:
                not_found.append([q.call, q.band, q.mode,
                                  q.datetime_utc.strftime('%H:%M')])
                seen.add(call_upper)
        unique_not_found = len(not_found)
        source = "MASTER.SCP"
    else:
        # Fallback: check against cty.dat (country lookup)
        not_found = []
        for q in log.qsos:
            if not q.country:
                not_found.append([q.call, q.band, q.mode,
                                  q.datetime_utc.strftime('%H:%M')])
        unique_not_found = len({row[0] for row in not_found})
        source = "cty.dat"

    pct = (unique_not_found / total_calls * 100) if total_calls else 0
    return {
        'headers': ['Callsign', 'Band', 'Mode', 'Time'],
        'rows': not_found,
        'description': (f'{unique_not_found} callsigns not found in {source} '
                        f'({pct:.1f}% of {total_calls}).'),
    }


def prepare_lotw_check(log: ContestLog,
                       lotw_users: set[str] | None = None) -> dict:
    """LOTW user check: which worked callsigns are LOTW users."""
    if lotw_users is None:
        return {
            'headers': ['Callsign'],
            'rows': [],
            'description': 'LOTW user list not available.',
        }

    unique_calls = sorted({q.call for q in log.qsos if not q.is_dupe})
    rows = []
    in_lotw_count = 0
    for call in unique_calls:
        in_lotw = call.upper() in lotw_users
        if in_lotw:
            in_lotw_count += 1
        rows.append([call, "Yes" if in_lotw else "No"])

    total = len(unique_calls)
    pct = (in_lotw_count / total * 100) if total else 0
    return {
        'headers': ['Callsign', 'In LOTW'],
        'rows': rows,
        'description': (f'{in_lotw_count} of {total} unique callsigns '
                        f'({pct:.1f}%) are LOTW users.'),
    }


def prepare_possible_errors(log: ContestLog) -> dict:
    """Possible logging errors (out-of-band, suspicious calls)."""
    band_ranges = {
        '160m': (1.8, 2.0), '80m': (3.5, 4.0), '40m': (7.0, 7.3),
        '20m': (14.0, 14.35), '15m': (21.0, 21.45), '10m': (28.0, 29.7),
        '6m': (50.0, 54.0), '2m': (144.0, 148.0),
    }
    errors = []
    for q in log.qsos:
        if q.freq_mhz > 0 and q.band in band_ranges:
            low, high = band_ranges[q.band]
            if q.freq_mhz < low or q.freq_mhz > high:
                errors.append([q.call, q.band, f"{q.freq_mhz:.3f}",
                               q.datetime_utc.strftime('%H:%M'), 'Out of band'])

    return {
        'headers': ['Callsign', 'Band', 'Freq', 'Time', 'Issue'],
        'rows': errors,
        'description': f'{len(errors)} possible errors found.',
    }


def prepare_passed_qsos(log: ContestLog) -> dict:
    """Passed QSOs - stations worked on multiple bands/modes by different operators."""
    call_ops = defaultdict(lambda: {'bands': set(), 'operators': set(), 'count': 0})
    for q in log.qsos:
        if not q.is_dupe:
            call_ops[q.call]['bands'].add(q.band)
            call_ops[q.call]['operators'].add(q.operator)
            call_ops[q.call]['count'] += 1

    rows = []
    for call in sorted(call_ops):
        d = call_ops[call]
        if d['count'] > 1 and len(d['operators']) > 1:
            rows.append({
                'call': call,
                'count': d['count'],
                'bands': ', '.join(sorted(d['bands'])),
                'operators': ', '.join(sorted(d['operators'])),
            })

    return {'passed_rows': rows, 'total_passed': len(rows)}


# ── Phase 3 page generators ──────────────────────────────────────────

# Band colors matching CSS .q1-.q6 classes (muted, accessible)
BAND_COLORS = {
    '160m': '#0ea5e9',  # sky
    '80m':  '#f59e0b',  # amber
    '40m':  '#10b981',  # emerald
    '20m':  '#6366f1',  # indigo
    '15m':  '#ef4444',  # red
    '10m':  '#8b5cf6',  # violet
    '6m':   '#ec4899',  # pink
    '2m':   '#f97316',  # orange
}

# Softer colors for chart fills (semi-transparent)
BAND_CHART_COLORS = {
    '160m': 'rgba(14,165,233,0.7)',
    '80m':  'rgba(245,158,11,0.7)',
    '40m':  'rgba(16,185,129,0.7)',
    '20m':  'rgba(99,102,241,0.7)',
    '15m':  'rgba(239,68,68,0.7)',
    '10m':  'rgba(139,92,246,0.7)',
    '6m':   'rgba(236,72,153,0.7)',
    '2m':   'rgba(249,115,22,0.7)',
}

CONTINENT_COLORS = {
    'NA': 'rgba(14,165,233,0.7)',
    'SA': 'rgba(245,158,11,0.7)',
    'EU': 'rgba(16,185,129,0.7)',
    'AF': 'rgba(239,68,68,0.7)',
    'AS': 'rgba(99,102,241,0.7)',
    'OC': 'rgba(249,115,22,0.7)',
}


def prepare_chart_qs_by_band(log: ContestLog) -> dict:
    """QSOs by band doughnut chart."""
    band_counts = Counter(q.band for q in log.qsos)
    bands = log.active_bands
    labels = [f"{b}: {band_counts[b]} Qs" for b in bands]
    data = [band_counts[b] for b in bands]
    colors = [BAND_CHART_COLORS.get(b, 'rgba(128,128,128,0.7)') for b in bands]

    chart_data = {
        'type': 'doughnut',
        'data': {
            'labels': labels,
            'datasets': [{
                'data': data,
                'backgroundColor': colors,
                'borderWidth': 1,
            }],
        },
        'options': {
            'responsive': True,
            'plugins': {
                'legend': {'position': 'right'},
                'title': {'display': True, 'text': f'QSOs by Band ({len(log.qsos)} total)'},
            },
        },
    }

    detail_rows = []
    for b in bands:
        c = band_counts[b]
        pct = c / len(log.qsos) * 100 if log.qsos else 0
        detail_rows.append([b, c, f"{pct:.1f}%"])

    return {
        'chart_type': 'doughnut',
        'chart_data_json': json.dumps(chart_data),
        'description': f'{len(log.qsos)} QSOs across {len(bands)} bands.',
        'detail_table': True,
        'detail_headers': ['Band', 'QSOs', '%'],
        'detail_rows': detail_rows,
    }


def prepare_chart_continents(log: ContestLog) -> dict:
    """Continents doughnut chart."""
    cont_counts = Counter(q.continent for q in log.qsos if q.continent)
    labels = [f"{c}: {cont_counts[c]} Qs" for c in sorted(cont_counts, key=cont_counts.get, reverse=True)]
    continents_sorted = sorted(cont_counts, key=cont_counts.get, reverse=True)
    data = [cont_counts[c] for c in continents_sorted]
    colors = [CONTINENT_COLORS.get(c, 'rgba(128,128,128,0.7)') for c in continents_sorted]

    chart_data = {
        'type': 'doughnut',
        'data': {
            'labels': labels,
            'datasets': [{
                'data': data,
                'backgroundColor': colors,
                'borderWidth': 1,
            }],
        },
        'options': {
            'responsive': True,
            'plugins': {
                'legend': {'position': 'right'},
                'title': {'display': True, 'text': 'QSOs by Continent'},
            },
        },
    }

    detail_rows = []
    total = len(log.qsos)
    for c in continents_sorted:
        cnt = cont_counts[c]
        detail_rows.append([c, cnt, f"{cnt / total * 100:.1f}%"])

    return {
        'chart_type': 'doughnut',
        'chart_data_json': json.dumps(chart_data),
        'description': f'{len(cont_counts)} continents worked.',
        'detail_table': True,
        'detail_headers': ['Continent', 'QSOs', '%'],
        'detail_rows': detail_rows,
    }


def prepare_chart_top_countries(log: ContestLog) -> dict:
    """Top 10 countries horizontal bar chart."""
    country_counts = Counter(q.country for q in log.qsos if q.country)
    top10 = country_counts.most_common(10)
    labels = [c for c, _ in top10]
    data = [n for _, n in top10]

    chart_data = {
        'type': 'bar',
        'data': {
            'labels': labels,
            'datasets': [{
                'label': 'QSOs',
                'data': data,
                'backgroundColor': 'rgba(82,102,223,0.7)',
                'borderColor': 'rgba(82,102,223,1)',
                'borderWidth': 1,
            }],
        },
        'options': {
            'indexAxis': 'y',
            'responsive': True,
            'plugins': {
                'legend': {'display': False},
                'title': {'display': True, 'text': 'Top 10 Countries'},
            },
            'scales': {
                'x': {'beginAtZero': True},
            },
        },
    }

    detail_rows = []
    total = len(log.qsos)
    for c, n in top10:
        detail_rows.append([c, n, f"{n / total * 100:.1f}%"])

    return {
        'chart_type': 'horizontal_bar',
        'chart_data_json': json.dumps(chart_data),
        'description': f'Top 10 countries by QSO count (of {len(country_counts)} total).',
        'detail_table': True,
        'detail_headers': ['Country', 'QSOs', '%'],
        'detail_rows': detail_rows,
    }


def prepare_chart_beam_heading(log: ContestLog) -> dict:
    """Beam heading polar/radar chart."""
    bins = [0] * 36  # 10-degree bins
    for q in log.qsos:
        if q.bearing_deg >= 0:
            idx = int(q.bearing_deg / 10) % 36
            bins[idx] += 1

    labels = [f"{i * 10}°" for i in range(36)]

    chart_data = {
        'type': 'radar',
        'data': {
            'labels': labels,
            'datasets': [{
                'label': 'QSOs',
                'data': bins,
                'backgroundColor': 'rgba(82,102,223,0.3)',
                'borderColor': 'rgba(82,102,223,1)',
                'borderWidth': 1,
                'pointRadius': 2,
            }],
        },
        'options': {
            'responsive': True,
            'plugins': {
                'legend': {'display': False},
                'title': {'display': True, 'text': 'Beam Heading Distribution'},
            },
            'scales': {
                'r': {
                    'beginAtZero': True,
                    'ticks': {'display': True},
                },
            },
        },
    }

    return {
        'chart_type': 'polar',
        'chart_data_json': json.dumps(chart_data),
        'description': 'Beam heading distribution in 10-degree bins.',
        'detail_table': False,
        'detail_headers': [],
        'detail_rows': [],
    }


def prepare_chart_frequencies(log: ContestLog) -> dict:
    """Frequency spectrum bar chart."""
    freq_bins = defaultdict(int)
    bin_width = 5  # 5 kHz bins
    for q in log.qsos:
        if q.freq_mhz > 0:
            freq_khz = int(q.freq_mhz * 1000)
            b = (freq_khz // bin_width) * bin_width
            freq_bins[b] += 1

    sorted_freqs = sorted(freq_bins.keys())
    labels = [str(f) for f in sorted_freqs]
    data = [freq_bins[f] for f in sorted_freqs]

    # Color by band
    band_ranges = {
        '160m': (1800, 2000), '80m': (3500, 4000), '40m': (7000, 7300),
        '20m': (14000, 14350), '15m': (21000, 21450), '10m': (28000, 29700),
        '6m': (50000, 54000), '2m': (144000, 148000),
    }
    colors = []
    for f in sorted_freqs:
        color = 'rgba(128,128,128,0.7)'
        for band, (low, high) in band_ranges.items():
            if low <= f <= high:
                color = BAND_CHART_COLORS.get(band, color)
                break
        colors.append(color)

    chart_data = {
        'type': 'bar',
        'data': {
            'labels': labels,
            'datasets': [{
                'label': 'QSOs',
                'data': data,
                'backgroundColor': colors,
                'borderWidth': 0,
                'barPercentage': 1.0,
                'categoryPercentage': 1.0,
            }],
        },
        'options': {
            'responsive': True,
            'plugins': {
                'legend': {'display': False},
                'title': {'display': True, 'text': 'Frequency Distribution (5 kHz bins)'},
            },
            'scales': {
                'x': {
                    'ticks': {'maxTicksLimit': 30, 'autoSkip': True},
                    'title': {'display': True, 'text': 'Frequency (kHz)'},
                },
                'y': {
                    'beginAtZero': True,
                    'title': {'display': True, 'text': 'QSOs'},
                },
            },
        },
    }

    return {
        'chart_type': 'bar',
        'chart_data_json': json.dumps(chart_data),
        'description': f'Frequency distribution across {len(sorted_freqs)} bins.',
        'detail_table': False,
        'detail_headers': [],
        'detail_rows': [],
    }


def prepare_map(log: ContestLog) -> dict:
    """Leaflet map data."""
    band_colors_list = [(b, BAND_COLORS.get(b, '#888888')) for b in log.active_bands]
    band_color_map = {b: BAND_COLORS.get(b, '#888888') for b in log.active_bands}

    qso_data = []
    for q in log.qsos:
        if q.dxcc_lat == 0 and q.dxcc_lon == 0:
            continue
        qso_data.append({
            'lat': round(q.dxcc_lat, 4),
            'lon': round(q.dxcc_lon, 4),
            'call': q.call,
            'band': q.band,
            'mode': q.mode,
            'time': q.datetime_utc.strftime('%Y-%m-%d %H:%M'),
            'country': q.country,
            'dist': int(q.distance_km),
            'bearing': int(q.bearing_deg),
        })

    return {
        'total_qsos': len(qso_data),
        'station_call': log.station_call,
        'locator': log.locator,
        'station_lat': log.station_lat,
        'station_lon': log.station_lon,
        'band_colors': band_colors_list,
        'band_color_map_json': json.dumps(band_color_map),
        'qso_data_json': json.dumps(qso_data),
    }


def prepare_lcr_summary(log: ContestLog) -> dict:
    """LCR error summary page."""
    error_qsos_list = [q for q in log.qsos if q.lcr_error]
    total_errors = len(error_qsos_list)

    # Error types
    type_counts = Counter(q.lcr_error for q in error_qsos_list)
    type_rows = []
    for t, c in type_counts.most_common():
        type_rows.append({
            'type': t.replace('_', ' ').title(),
            'count': c,
            'pct': c / total_errors * 100 if total_errors else 0,
        })

    # Errors by operator
    op_errors = Counter(q.operator for q in error_qsos_list)
    op_total = Counter(q.operator for q in log.qsos)
    operator_rows = []
    for op in sorted(op_errors, key=op_errors.get, reverse=True):
        operator_rows.append({
            'operator': op,
            'errors': op_errors[op],
            'qsos': op_total[op],
            'pct': op_errors[op] / op_total[op] * 100 if op_total[op] else 0,
        })

    # Detail list
    error_detail = []
    for q in error_qsos_list:
        error_detail.append({
            'date': q.datetime_utc.strftime('%Y-%m-%d'),
            'time': q.datetime_utc.strftime('%H:%M'),
            'call': q.call,
            'band': q.band,
            'mode': q.mode,
            'error': q.lcr_error.replace('_', ' ').title(),
            'detail': q.lcr_detail,
            'operator': q.operator,
        })

    return {
        'total_errors': total_errors,
        'matched_errors': total_errors,  # all in this list are matched
        'type_rows': type_rows,
        'operator_rows': operator_rows,
        'error_qsos': error_detail,
    }
