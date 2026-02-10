"""Geographic utilities: Maidenhead grid conversion, Haversine distance, bearing.

Ported from TR4QT GeographicUtils.cpp.
"""

import math

EARTH_RADIUS_KM = 6371.0


def grid_to_latlon(grid: str) -> tuple[float, float] | None:
    """Convert Maidenhead grid (4 or 6 char) to (lat, lon) center point.

    Returns None if grid is invalid.
    """
    if len(grid) not in (4, 6):
        return None

    g = grid.upper()

    # Field characters (A-R)
    if not ('A' <= g[0] <= 'R' and 'A' <= g[1] <= 'R'):
        return None

    # Square characters (0-9)
    if not (g[2].isdigit() and g[3].isdigit()):
        return None

    lon = -180.0 + (ord(g[0]) - ord('A')) * 20.0 + int(g[2]) * 2.0
    lat = -90.0 + (ord(g[1]) - ord('A')) * 10.0 + int(g[3]) * 1.0

    if len(g) == 6:
        # Subsquare characters (a-x)
        s1 = g[4].lower()
        s2 = g[5].lower()
        if not ('a' <= s1 <= 'x' and 'a' <= s2 <= 'x'):
            return None
        lon += (ord(s1) - ord('a')) * (2.0 / 24.0)
        lat += (ord(s2) - ord('a')) * (1.0 / 24.0)
        # Center of subsquare
        lon += (2.0 / 24.0) / 2.0
        lat += (1.0 / 24.0) / 2.0
    else:
        # Center of 4-char square
        lon += 1.0
        lat += 0.5

    return (lat, lon)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km using Haversine formula."""
    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lat2_r = math.radians(lat2)
    lon2_r = math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_KM * c


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Forward azimuth bearing in degrees (0-360)."""
    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lat2_r = math.radians(lat2)
    lon2_r = math.radians(lon2)

    dlon = lon2_r - lon1_r

    y = math.sin(dlon) * math.cos(lat2_r)
    x = (math.cos(lat1_r) * math.sin(lat2_r) -
         math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon))

    bearing = math.degrees(math.atan2(y, x))
    return bearing % 360.0
