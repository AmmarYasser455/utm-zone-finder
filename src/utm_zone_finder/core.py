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


def _steps(lo: float, hi: float, step: float = 0.5) -> list[float]:
    n = int(math.ceil((hi - lo) / step))
    return [lo + i * step for i in range(n)] + [hi]


def _check_bbox(min_lon, min_lat, max_lon, max_lat) -> tuple[float, float, float, float]:
    min_lat, min_lon = _check(min_lat, min_lon)
    max_lat, max_lon = _check(max_lat, max_lon)
    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError("bbox must be min_lon, min_lat, max_lon, max_lat with min <= max")
    return min_lon, min_lat, max_lon, max_lat


def zones_spanned(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> list[UTMZone]:
    """All zones a bounding box touches (sampled on a 0.5 degree grid).

    A zone is flagged ``polar`` if any part of the box inside it lies outside 80S-84N.
    """
    min_lon, min_lat, max_lon, max_lat = _check_bbox(min_lon, min_lat, max_lon, max_lat)
    found: dict[int, UTMZone] = {}
    for lat in _steps(min_lat, max_lat):
        for lon in _steps(min_lon, max_lon):
            z = zone_for_point(lat, lon)
            prev = found.get(z.epsg)
            if prev is None:
                found[z.epsg] = z
            elif z.polar and not prev.polar:
                found[z.epsg] = replace(prev, polar=True)
    return sorted(found.values(), key=lambda z: (z.hemisphere != "N", z.number))


def zone_for_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> UTMZone:
    """Zone of the bounding box centre (the usual choice for projecting it).

    ``polar`` is set if any part of the box lies outside 80S-84N.
    """
    min_lon, min_lat, max_lon, max_lat = _check_bbox(min_lon, min_lat, max_lon, max_lat)
    z = zone_for_point((min_lat + max_lat) / 2, (min_lon + max_lon) / 2)
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


def _coords(c, depth: int, t: str, out: list, top: bool = True) -> None:
    """Validate ``c`` as an array nested exactly ``depth`` levels deep for type ``t``."""
    if depth == 0:
        _position(c, out)
        return
    if not isinstance(c, list):
        raise ValueError(f"invalid GeoJSON: {t} coordinates are not nested correctly")
    if depth == 1 and (c or not top):  # an empty top-level array is an empty geometry
        need = _MIN_POSITIONS.get(t, 0)
        if len(c) < need:
            raise ValueError(f"invalid GeoJSON: each {t} line/ring needs at least {need} positions")
    for item in c:
        _coords(item, depth - 1, t, out, top=False)


def _members(obj: dict, key: str) -> list:
    items = obj.get(key)
    if not isinstance(items, list):
        raise ValueError(f"invalid GeoJSON: {key!r} must be an array")
    return items


def _collect(obj, out: list, allowed: frozenset = _ANY) -> None:
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
            _collect(f, out, frozenset({"Feature"}))
    elif t == "Feature":
        if "geometry" not in obj:
            raise ValueError("invalid GeoJSON: Feature has no 'geometry' member")
        if obj["geometry"] is not None:
            _collect(obj["geometry"], out, _GEOMETRIES)
    elif t == "GeometryCollection":
        for g in _members(obj, "geometries"):
            _collect(g, out, _GEOMETRIES)
    else:
        if "coordinates" not in obj:
            raise ValueError(f"invalid GeoJSON: {t} has no 'coordinates' member")
        _coords(obj["coordinates"], _GEOMETRY_DEPTH[t], t, out)


def bbox_from_geojson(data) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) of a GeoJSON dict or file path."""
    if isinstance(data, (str, bytes)) or hasattr(data, "__fspath__"):
        with open(data, encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except RecursionError:
                raise ValueError("invalid GeoJSON: nested too deeply") from None
    pts: list = []
    try:
        _collect(data, pts)
    except RecursionError:
        raise ValueError("invalid GeoJSON: nested too deeply") from None
    if not pts:
        raise ValueError("GeoJSON contains no coordinates")
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    return min(lons), min(lats), max(lons), max(lats)


def zone_for_geojson(data) -> UTMZone:
    """Zone of the centre of a GeoJSON object's bounding box."""
    return zone_for_bbox(*bbox_from_geojson(data))
