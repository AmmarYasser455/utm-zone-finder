"""Build the utm-zone-finder showcase: UTM zones for Egypt's governorates.

Run from the repository root, offline:  python showcase/make_showcase.py

Reads showcase/data/egypt_governorates.geojson (Natural Earth, public domain),
runs utm_zone_finder on each governorate and writes map.geojson, map.png and
index.html into the showcase directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))  # work from a plain checkout, too

from utm_zone_finder import bbox_from_geojson, zone_for_bbox, zones_spanned  # noqa: E402

DATA = HERE / "data" / "egypt_governorates.geojson"
REPO_URL = "https://github.com/AmmarYasser455/utm-zone-finder"
CREDIT = "Data: Natural Earth (public domain). Zones: utm-zone-finder."
ZONE_COLORS = {35: "#4c78a8", 36: "#f58518", 37: "#54a24b"}  # categorical, one per zone

TITLE = "Which UTM zone fits each Egyptian governorate?"


def _signed_area(ring) -> float:
    """Shoelace area of a ring; only its sign (orientation) is used."""
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:])) / 2


def _orient_polygon(rings):
    """RFC 7946: exterior ring counter-clockwise, holes clockwise."""
    out = []
    for i, ring in enumerate(rings):
        ccw = _signed_area(ring) > 0
        out.append(ring if ccw == (i == 0) else ring[::-1])
    return out


def orient_geometry(geom: dict) -> dict:
    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": _orient_polygon(geom["coordinates"])}
    if geom["type"] == "MultiPolygon":
        return {"type": "MultiPolygon",
                "coordinates": [_orient_polygon(p) for p in geom["coordinates"]]}
    return geom


def build_result(data_path: Path = DATA) -> dict:
    """Run the tool on every feature; return a FeatureCollection in EPSG:4326 (lon, lat)."""
    with open(data_path, encoding="utf-8") as fh:
        src = json.load(fh)
    if not isinstance(src, dict) or src.get("type") != "FeatureCollection" \
            or not isinstance(src.get("features"), list):
        raise ValueError("input must be a GeoJSON FeatureCollection with a 'features' array")
    features = []
    for feat in src["features"]:
        if not isinstance(feat, dict) or not isinstance(feat.get("properties"), dict):
            raise ValueError("each feature must be a GeoJSON Feature object with properties")
        # bbox_from_geojson validates type, geometry and every coordinate
        # (null/empty geometry, NaN, wrong types and out-of-range values raise ValueError).
        min_lon, min_lat, max_lon, max_lat = bbox_from_geojson(feat)
        zone = zone_for_bbox(min_lon, min_lat, max_lon, max_lat)
        spanned = zones_spanned(min_lon, min_lat, max_lon, max_lat)
        props = dict(feat["properties"])
        props.update({
            "utm_zone": zone.name,
            "utm_zone_number": zone.number,
            "epsg": zone.epsg,
            "central_meridian": zone.central_meridian,
            "zones_spanned": [z.name for z in spanned],
            "spans_multiple_zones": len(spanned) > 1,
            "min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat,
        })
        features.append({"type": "Feature", "properties": props,
                         "geometry": orient_geometry(feat["geometry"])})
    features.sort(key=lambda f: (f["properties"]["utm_zone_number"], f["properties"]["name"]))
    return {"type": "FeatureCollection", "features": features}


def _rings(geom: dict):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for poly in polys:
        yield poly


def draw_png(result: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import math

    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath

    fig, ax = plt.subplots(figsize=(9.5, 9.0), dpi=150)
    for f in result["features"]:
        p = f["properties"]
        verts, codes = [], []
        for poly in _rings(f["geometry"]):
            for ring in poly:
                verts += [tuple(c) for c in ring]
                codes += [MPath.MOVETO] + [MPath.LINETO] * (len(ring) - 2) + [MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(verts, codes), facecolor=ZONE_COLORS[p["utm_zone_number"]],
                               edgecolor="white", linewidth=0.8, alpha=0.9))
        if p["spans_multiple_zones"]:  # outline the ones that cross a zone edge
            ax.add_patch(PathPatch(MPath(verts, codes), facecolor="none",
                                   edgecolor="black", linewidth=1.4, linestyle="--"))
    for lon in (30, 36):  # UTM zone edges (6 degree wide zones)
        ax.axvline(lon, color="0.3", linewidth=0.8, linestyle=":")
    ax.set_xlim(24.5, 37.2)
    ax.set_ylim(21.5, 32.0)
    ax.set_aspect(1 / math.cos(math.radians(27)))  # roughly equal scale at Egypt's latitude
    ax.set_xlabel("Longitude (degrees east, WGS84 / EPSG:4326)")
    ax.set_ylabel("Latitude (degrees north)")
    ax.grid(True, color="0.9", linewidth=0.5)
    ax.set_axisbelow(True)
    for name, lon, lat in (("Cairo", 31.24, 30.04), ("Alexandria", 29.92, 31.2),
                           ("Aswan", 32.9, 24.09)):
        ax.plot(lon, lat, "o", color="black", markersize=3.5)
        ax.annotate(name, (lon, lat), xytext=(4, 4), textcoords="offset points", fontsize=8)
    handles = [Line2D([], [], marker="s", linestyle="", markersize=10, color=c,
                      label=f"UTM zone {n}N (EPSG:{32600 + n})") for n, c in ZONE_COLORS.items()]
    handles.append(Line2D([], [], color="black", linestyle="--",
                          label="governorate spans more than one zone"))
    handles.append(Line2D([], [], color="0.3", linestyle=":", label="zone edge (30°E, 36°E)"))
    ax.legend(handles=handles, loc="lower left", fontsize=8.5, framealpha=0.95)
    ax.set_title(TITLE + "\nZone of each governorate's bounding-box centre", fontsize=12)
    ax.annotate("N ↑", (0.97, 0.97), xycoords="axes fraction", ha="right", va="top",
                fontsize=12, fontweight="bold")
    fig.text(0.99, 0.005, CREDIT, ha="right", va="bottom", fontsize=7, color="0.3")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  body { margin: 0; font-family: system-ui, sans-serif; }
  header { padding: 8px 14px; }
  h1 { font-size: 1.15rem; margin: 0 0 4px; }
  p { margin: 0; font-size: 0.9rem; }
  #map { height: calc(100vh - 100px); }
  .legend { background: #fff; padding: 6px 10px; line-height: 1.5; border-radius: 4px; }
  .legend i { display: inline-block; width: 12px; height: 12px; margin-right: 6px; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <p>Each governorate is coloured by the UTM zone utm-zone-finder returns for its bounding-box centre; dashed outlines span more than one zone.
  Click a governorate for its zone, EPSG code and spanned zones.
  Source and method: <a href="__REPO__">utm-zone-finder on GitHub</a>. Serve this folder over http (for example <code>python -m http.server</code>) so the page can load map.geojson.</p>
</header>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var colors = __COLORS__;
var map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors. Boundaries: Natural Earth.'
}).addTo(map);
function esc(s) { return String(s).replace(/[&<>"]/g, function (c) {
  return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
fetch('map.geojson').then(function (r) { return r.json(); }).then(function (data) {
  var layer = L.geoJSON(data, {
    style: function (f) {
      var p = f.properties;
      return {color: p.spans_multiple_zones ? '#000' : '#fff', weight: p.spans_multiple_zones ? 2 : 1,
              dashArray: p.spans_multiple_zones ? '5 4' : null,
              fillColor: colors[p.utm_zone_number], fillOpacity: 0.6};
    },
    onEachFeature: function (f, l) {
      var p = f.properties;
      l.bindPopup('<b>' + esc(p.name) + '</b> (' + esc(p.name_ar) + ')<br>UTM zone: ' + esc(p.utm_zone) +
        '<br>EPSG: ' + esc(p.epsg) + '<br>Central meridian: ' + esc(p.central_meridian) + '&deg;E' +
        '<br>Zones spanned: ' + esc(p.zones_spanned.join(', ')) +
        '<br>Longitude extent: ' + p.min_lon.toFixed(2) + ' to ' + p.max_lon.toFixed(2));
    }
  }).addTo(map);
  map.fitBounds(layer.getBounds());
  var legend = L.control({position: 'bottomleft'});
  legend.onAdd = function () {
    var d = L.DomUtil.create('div', 'legend');
    Object.keys(colors).forEach(function (n) {
      d.innerHTML += '<i style="background:' + colors[n] + '"></i>Zone ' + n + 'N (EPSG:' + (32600 + Number(n)) + ')<br>';
    });
    return d;
  };
  legend.addTo(map);
});
</script>
</body>
</html>
"""


def write_index(path: Path) -> None:
    html = (INDEX_HTML.replace("__TITLE__", TITLE).replace("__REPO__", REPO_URL)
            .replace("__COLORS__", json.dumps({str(k): v for k, v in ZONE_COLORS.items()})))
    path.write_text(html, encoding="utf-8")


def main(out_dir: Path | str = HERE, data_path: Path | str = DATA, png: bool = True) -> dict:
    """Write map.geojson, index.html and (if ``png``) map.png into ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = build_result(Path(data_path))
    with open(out / "map.geojson", "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    write_index(out / "index.html")
    if png:
        draw_png(result, out / "map.png")
    return result


if __name__ == "__main__":
    res = main()
    print(f"wrote {len(res['features'])} features to {HERE}")
