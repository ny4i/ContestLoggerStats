"""Grid-to-state and grid-to-DXCC mapping for cross-checking.

Data sources:
  grid.dat (WSJT-X) — US state mapping: 4-char grid → state(s)
  vuccgrids.dat (TQSL) — worldwide: 4-char grid → DXCC entity ID(s)
  cty.csv (AD1C) — maps primary prefix → DXCC entity number

Used to validate grid squares against exchanged state/DXCC before
trusting a QRZ-sourced grid for map plotting.
"""

import csv
import os
import re
import xml.etree.ElementTree as ET


def load_grid_state_map(filepath: str) -> dict[str, list[str]]:
    """Load grid.dat and return {4-char-grid: [state, ...]} mapping.

    Example: grid_map['FN20'] = ['PA', 'NJ', 'NY']
    """
    grid_map: dict[str, list[str]] = {}

    if not os.path.isfile(filepath):
        return grid_map

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    field = ''
    for line in content.splitlines():
        line = line.strip()
        # Field header: two uppercase letters followed by <
        m = re.match(r'^([A-Z]{2})<$', line)
        if m:
            field = m.group(1)
            continue

        if not field:
            continue

        # Square entry: digits:STATE[-STATE...][,>]
        m = re.match(r'^(\d{2}):([A-Z][A-Z0-9\-]+)[,>]?$', line)
        if m:
            square = m.group(1)
            states = [s.strip() for s in m.group(2).split('-') if s.strip()]
            grid_map[field + square] = states

        # End of block
        if line.endswith('>'):
            field = ''

    return grid_map


def grid_states(grid: str, grid_map: dict[str, list[str]]) -> list[str]:
    """Return list of states a grid square could be in, or empty list.

    Accepts 4 or 6 char grids (subsquare suffix is ignored).
    """
    if not grid or len(grid) < 4:
        return []
    key = grid[:2].upper() + grid[2:4]
    return grid_map.get(key, [])


# Standard US state abbreviations — grid.dat only covers US states.
# If the exchanged state is not in this set (e.g. Canadian province "ON"),
# grid.dat cannot validate it and we should not reject the grid.
_US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC',
}


def grid_matches_state(grid: str, state: str,
                       grid_map: dict[str, list[str]]) -> bool | None:
    """Check if a grid is consistent with a state.

    Returns:
        True  — grid covers this state
        False — grid does NOT cover this state (mismatch)
        None  — can't determine (grid not in map, or state is non-US)
    """
    if not grid or not state:
        return None
    # grid.dat only maps US states — can't validate provinces or DX
    if state.upper() not in _US_STATES:
        return None
    states = grid_states(grid, grid_map)
    if not states:
        return None  # Grid not in map
    return state.upper() in [s.upper() for s in states]


# ---------------------------------------------------------------------------
# Grid-to-DXCC mapping (vuccgrids.dat — TQSL, worldwide coverage)
# ---------------------------------------------------------------------------

def load_vucc_grid_map(filepath: str) -> tuple[dict[str, list[int]], str]:
    """Load vuccgrids.dat (XML) and return ({4-char-grid: [entity_id, ...]}, updatedate).

    XML format:
      <vuccgrids majorversion="1" minorversion="5" updatedate="2025-10-22">
        <vucc entity="1" pas="AB" grid="CO93" />
      </vuccgrids>
    """
    grid_map: dict[str, list[int]] = {}
    updatedate = ""

    if not os.path.isfile(filepath):
        return grid_map, updatedate

    try:
        tree = ET.parse(filepath)
    except ET.ParseError:
        return grid_map, updatedate

    root = tree.getroot()
    updatedate = root.get('updatedate', '')

    for elem in root.iter('vucc'):
        grid = elem.get('grid', '').strip().upper()
        entity_str = elem.get('entity', '').strip()
        if not grid or not entity_str:
            continue
        try:
            entity_id = int(entity_str)
        except ValueError:
            continue
        if grid not in grid_map:
            grid_map[grid] = []
        if entity_id not in grid_map[grid]:
            grid_map[grid].append(entity_id)

    return grid_map, updatedate


def grid_matches_dxcc(grid: str, dxcc: int,
                      grid_dxcc_map: dict[str, list[int]]) -> bool | None:
    """Check if a grid is consistent with a DXCC entity.

    Returns:
        True  — grid covers this DXCC entity
        False — grid does NOT cover this DXCC entity (mismatch)
        None  — grid not in map (can't determine)
    """
    if not grid or not dxcc:
        return None
    key = (grid[:2].upper() + grid[2:4]) if len(grid) >= 4 else ''
    if not key:
        return None
    entities = grid_dxcc_map.get(key)
    if entities is None:
        return None
    return dxcc in entities


# ---------------------------------------------------------------------------
# Primary prefix → DXCC entity number mapping (cty.csv from AD1C)
# ---------------------------------------------------------------------------

def load_prefix_dxcc_map(filepath: str) -> dict[str, int]:
    """Load cty.csv and return {primary_prefix: dxcc_entity_number}.

    CSV format (no header):
      prefix,name,dxcc_number,continent,cq_zone,itu_zone,lat,lon,gmt_offset,aliases;
    Example:
      K,United States,291,NA,5,8,37.53,97.80,-5.0,AA ... ;
    """
    prefix_map: dict[str, int] = {}

    if not os.path.isfile(filepath):
        return prefix_map

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip().rstrip(';')
            if not line:
                continue
            parts = line.split(',', 3)
            if len(parts) < 3:
                continue
            prefix = parts[0].strip()
            try:
                dxcc_num = int(parts[2].strip())
            except ValueError:
                continue
            prefix_map[prefix] = dxcc_num

    return prefix_map
