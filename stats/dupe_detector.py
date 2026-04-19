"""Duplicate QSO detection with configurable rules."""

from .contest_data import QSO


def find_dupes(qsos: list[QSO], rule: str = "per_band_mode") -> int:
    """Mark duplicate QSOs in-place. Returns dupe count.

    Rules:
      per_band_mode: Same callsign + band + mode_group = dupe (most contests)
      per_band: Same callsign + band = dupe (e.g., Field Day)
      all_band_mode: Same callsign = dupe regardless of band/mode (e.g., ARRL SS)
    """
    seen: dict[tuple, int] = {}  # key -> index of first QSO
    dupe_count = 0

    for i, qso in enumerate(qsos):
        if rule == "all_band_mode":
            base = (qso.call,)
        elif rule == "per_band":
            base = (qso.call, qso.band)
        else:
            base = (qso.call, qso.band, qso.mode_group)

        # POTA refs split the key: working the same station at a different
        # park (either side of the QSO) is not a dupe. Non-POTA logs have
        # empty refs so this is a no-op for them.
        key = base + (qso.pota_ref, qso.my_pota_ref)

        if key in seen:
            qso.is_dupe = True
            dupe_count += 1
        else:
            seen[key] = i

    return dupe_count
