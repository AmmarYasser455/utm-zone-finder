"""Core UTM zone logic (pure Python, no dependencies)."""

from __future__ import annotations

import json
import math
import numbers
from dataclasses import asdict, dataclass, replace

# Svalbard (lat 72-84N) uses only the odd zones 31, 33, 35 and 37.
_SVALBARD_EDGES = ((0, 9, 31), (9, 21, 33), (21, 33, 35), (33, 42, 37))


@dataclass(frozen=True)
class UTMZone:
    """A UTM zone: number (1-60), hemisphere ("N"/"S") and EPSG code."""

    number: int
    hemisphere: str
    epsg: int
    central_meridian: int
    polar: bool = False  # True when outside the UTM latitude range (80S-84N)

    @property
    def name(self) -> str:
        return f"{self.number}{self.hemisphere}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["name"] = self.name
        return d


def _num(v, what: str) -> float:
    """Convert a real number to float; reject bools, strings, None and non-finite values."""
    if isinstance(v, bool) or not isinstance(v, numbers.Real):
        raise ValueError(f"{what} must be a number, got {type(v).__name__}")
    try:
        f = float(v)
    except (OverflowError, TypeError, ValueError):
        raise ValueError(f"{what} is not a representable number") from None
    if not math.isfinite(f):
        raise ValueError(f"{what} must be a finite number")
    return f


def _check(lat, lon) -> tuple[float, float]:
    lat, lon = _num(lat, "latitude"), _num(lon, "longitude")
    if not -90 <= lat <= 90:
        raise ValueError(f"latitude {lat} out of range [-90, 90]")
    if not -180 <= lon <= 180:
        raise ValueError(f"longitude {lon} out of range [-180, 180]")
    return lat, lon


def zone_for_point(lat: float, lon: float) -> UTMZone:
    """Return the UTM zone for a WGS84 point, honouring Norway and Svalbard."""
    lat, lon = _check(lat, lon)
    number = min(int((lon + 180) // 6) + 1, 60)  # lon == 180 belongs to zone 60
    if 56 <= lat < 64 and 3 <= lon < 12:
        number = 32  # southwest Norway
    elif 72 <= lat <= 84:
        for lo, hi, n in _SVALBARD_EDGES:
            if lo <= lon < hi:
                number = n
                break
    north = lat >= 0
    return UTMZone(
        number=number,
        hemisphere="N" if north else "S",
        epsg=(32600 if north else 32700) + number,
        central_meridian=number * 6 - 183,
        polar=lat < -80 or lat > 84,
    )


# Every longitude/latitude where zone_for_point can change its answer: the
# 6 degree meridians, the Norway/Svalbard edges, the equator and the UTM limits.
_LON_EDGES = sorted(set(range(-180, 181, 6)) | {3, 9, 12, 21, 33, 42})
_LAT_EDGES = (-80, 0, 56, 64, 72, 84)


def _samples(lo: float, hi: float, edges) -> list[float]:
    """One value per piece of [lo, hi] on which zone_for_point is constant.

    The pieces are the edges inside [lo, hi] and the open gaps between them, so
    the edges themselves plus the midpoint of every gap cover all of them.
    """
    cuts = sorted({lo, hi} | {e for e in edges if lo < e < hi})
    mids = [(a + b) / 2 for a, b in zip(cuts, cuts[1:])]
    return sorted(cuts + mids)


def _check_bbox(min_lon, min_lat, max_lon, max_lat) -> tuple[float, float, float, float]:
    min_lat, min_lon = _check(min_lat, min_lon)
    max_lat, max_lon = _check(max_lat, max_lon)
    if min_lat > max_lat:
        raise ValueError("bbox must be min_lon, min_lat, max_lon, max_lat with min_lat <= max_lat")
    return min_lon, min_lat, max_lon, max_lat


def _wrap(lon: float) -> float:
    """Bring a longitude in (-180, 540] back into [-180, 180]."""
    return lon - 360 if lon > 180 else lon


def zones_spanned(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> list[UTMZone]:
    """All zones a bounding box touches, edges included.

    The box is checked at every zone edge it contains and between them, so no
    zone is missed however narrow its part of the box is.
    A zone is flagged ``polar`` if any part of the box inside it lies outside 80S-84N.
    If ``min_lon > max_lon`` the box is taken to cross the antimeridian (RFC 7946).
    """
    min_lon, min_lat, max_lon, max_lat = _check_bbox(min_lon, min_lat, max_lon, max_lat)
    lon_edges = _LON_EDGES
    if min_lon > max_lon:
        max_lon += 360  # work in [min_lon, max_lon + 360] and wrap back
        lon_edges = _LON_EDGES + [e + 360 for e in _LON_EDGES]
    found: dict[int, UTMZone] = {}
    for lat in _samples(min_lat, max_lat, _LAT_EDGES):
        for lon in _samples(min_lon, max_lon, lon_edges):
            z = zone_for_point(lat, _wrap(lon))
            prev = found.get(z.epsg)
            if prev is None:
                found[z.epsg] = z
            elif z.polar and not prev.polar:
                found[z.epsg] = replace(prev, polar=True)
    return sorted(found.values(), key=lambda z: (z.hemisphere != "N", z.number))


def zone_for_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> UTMZone:
    """Zone of the bounding box centre (the usual choice for projecting it).

    ``polar`` is set if any part of the box lies outside 80S-84N. If
    ``min_lon > max_lon`` the box is taken to cross the antimeridian.
    """
    min_lon, min_lat, max_lon, max_lat = _check_bbox(min_lon, min_lat, max_lon, max_lat)
    if min_lon > max_lon:
        max_lon += 360
    z = zone_for_point((min_lat + max_lat) / 2, _wrap((min_lon + max_lon) / 2))
    if min_lat < -80 or max_lat > 84:
        z = replace(z, polar=True)
    return z


# Array nesting depth of "coordinates" for each geometry type (0 = a single position).
_GEOMETRY_DEPTH = {
    "Point": 0, "MultiPoint": 1, "LineString": 1,
    "MultiLineString": 2, "Polygon": 2, "MultiPolygon": 3,
}
_GEOMETRIES = frozenset(_GEOMETRY_DEPTH) | {"GeometryCollection"}
_ANY = _GEOMETRIES | {"Feature", "FeatureCollection"}
# Minimum positions per line string / linear ring (RFC 7946 sections 3.1.4 and 3.1.6).
_MIN_POSITIONS = {"LineString": 2, "MultiLineString": 2, "Polygon": 4, "MultiPolygon": 4}


def _position(p, out: list) -> None:
    """A position: [lon, lat, (alt, ...)], every element a finite number."""
    if not isinstance(p, list) or len(p) < 2:
        raise ValueError("invalid GeoJSON: a position must be an array of at least two numbers")
    for v in p[2:]:
        _num(v, "GeoJSON position value")
    lat, lon = _check(p[1], p[0])
    out.append((lon, lat))


def _coords(c, depth: int, t: str, out: list, segs: list, top: bool = True) -> None:
    """Validate ``c`` as an array nested exactly ``depth`` levels deep for type ``t``.

    Positions go to ``out``; the edges of lines and rings go to ``segs``.
    """
    if depth == 0:
        _position(c, out)
        segs.append((out[-1], out[-1]))  # a lone position is a zero-length edge
        return
    if not isinstance(c, list):
        raise ValueError(f"invalid GeoJSON: {t} coordinates are not nested correctly")
    start = len(out)
    if depth == 1 and (c or not top):  # an empty top-level array is an empty geometry
        need = _MIN_POSITIONS.get(t, 0)
        if len(c) < need:
            raise ValueError(f"invalid GeoJSON: each {t} line/ring needs at least {need} positions")
    for item in c:
        _coords(item, depth - 1, t, out, segs, top=False)
    if depth == 1 and t in _MIN_POSITIONS:
        line = out[start:]
        segs.extend(zip(line, line[1:]))
        if t.endswith("Polygon") and line and line[0] != line[-1]:
            segs.append((line[-1], line[0]))  # an unclosed ring still closes


def _members(obj: dict, key: str) -> list:
    items = obj.get(key)
    if not isinstance(items, list):
        raise ValueError(f"invalid GeoJSON: {key!r} must be an array")
    return items


def _collect(obj, out: list, segs: list, allowed: frozenset = _ANY) -> None:
    if not isinstance(obj, dict):
        raise ValueError("invalid GeoJSON: expected an object")
    t = obj.get("type")
    if not isinstance(t, str):
        raise ValueError(f"invalid GeoJSON: 'type' must be a string, got {type(t).__name__}")
    if t not in _ANY:
        raise ValueError(f"unsupported GeoJSON object type: {t!r}")
    if t not in allowed:
        raise ValueError(f"invalid GeoJSON: a {t} is not allowed here")
    if t == "FeatureCollection":
        for f in _members(obj, "features"):
            _collect(f, out, segs, frozenset({"Feature"}))
    elif t == "Feature":
        if "geometry" not in obj:
            raise ValueError("invalid GeoJSON: Feature has no 'geometry' member")
        if obj["geometry"] is not None:
            _collect(obj["geometry"], out, segs, _GEOMETRIES)
    elif t == "GeometryCollection":
        for g in _members(obj, "geometries"):
            _collect(g, out, segs, _GEOMETRIES)
    else:
        if "coordinates" not in obj:
            raise ValueError(f"invalid GeoJSON: {t} has no 'coordinates' member")
        _coords(obj["coordinates"], _GEOMETRY_DEPTH[t], t, out, segs)


_TOL = 1e-9  # degrees


def _declared_bbox(obj) -> tuple[float, float, float, float] | None:
    """The top-level RFC 7946 ``bbox`` member as (west, south, east, north), or None."""
    if not isinstance(obj, dict) or obj.get("bbox") is None:
        return None
    b = obj["bbox"]
    if not isinstance(b, list) or len(b) not in (4, 6):
        raise ValueError("invalid GeoJSON: 'bbox' must be an array of 4 or 6 numbers")
    vals = [_num(v, "GeoJSON bbox value") for v in b]
    if len(vals) == 6:
        west, south, low, east, north, high = vals
        if low > high:
            raise ValueError("invalid GeoJSON: bbox minimum altitude exceeds maximum altitude")
    else:
        west, south, east, north = vals
    try:
        return _check_bbox(west, south, east, north)
    except ValueError as exc:
        raise ValueError(f"invalid GeoJSON bbox: {exc}") from None


def _lon_ranges(west: float, east: float) -> list[tuple[float, float]]:
    """Longitude intervals covered by a bbox; -180 and 180 are the same meridian."""
    if west > east:  # crosses the antimeridian
        return [(west, 180.0), (-180.0, east)]
    ranges = [(west, east)]
    if west <= -180 + _TOL:
        ranges.append((180.0, 180.0))
    if east >= 180 - _TOL:
        ranges.append((-180.0, -180.0))
    return ranges


def _check_contains(box, segs: list) -> None:
    """Every edge, taken as a straight line in lon/lat space, must lie inside ``box``."""
    west, south, east, north = box
    ranges = _lon_ranges(west, east)
    for (lon1, lat1), (lon2, lat2) in segs:
        lo, hi = min(lon1, lon2), max(lon1, lon2)
        lon_ok = any(a - _TOL <= lo and hi <= b + _TOL for a, b in ranges)
        lat_ok = south - _TOL <= min(lat1, lat2) and max(lat1, lat2) <= north + _TOL
        if not (lon_ok and lat_ok):
            raise ValueError(
                f"invalid GeoJSON: declared bbox {list(box)} does not contain the geometry "
                f"between ({lon1}, {lat1}) and ({lon2}, {lat2})"
            )


def bbox_from_geojson(data) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) of a GeoJSON dict or file path.

    If the top-level object has an RFC 7946 ``bbox`` member it is validated,
    checked to contain every edge of the geometry and returned as declared, so
    ``min_lon > max_lon`` means the extent crosses the antimeridian. Without
    one, the plain min/max of the coordinates is returned.
    """
    if isinstance(data, (str, bytes)) or hasattr(data, "__fspath__"):
        with open(data, encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except RecursionError:
                raise ValueError("invalid GeoJSON: nested too deeply") from None
    pts: list = []
    segs: list = []
    try:
        _collect(data, pts, segs)
    except RecursionError:
        raise ValueError("invalid GeoJSON: nested too deeply") from None
    if not pts:
        raise ValueError("GeoJSON contains no coordinates")
    declared = _declared_bbox(data)
    if declared is not None:
        _check_contains(declared, segs)
        return declared
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    return min(lons), min(lats), max(lons), max(lats)


def zone_for_geojson(data) -> UTMZone:
    """Zone of the centre of a GeoJSON object's bounding box."""
    return zone_for_bbox(*bbox_from_geojson(data))
