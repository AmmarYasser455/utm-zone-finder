"""Build docs/demo.geojson: utm-zone-finder run on examples/cities.geojson.

Run from the repository root, offline:  python examples/make_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))  # work from a plain checkout, too

from utm_zone_finder import zone_for_point  # noqa: E402

DATA = HERE / "cities.geojson"
OUT = HERE.parent / "docs" / "demo.geojson"


def build_result(data_path: Path = DATA) -> dict:
    """Add the UTM zone of every point (CRS: WGS84, x = lon, y = lat, degrees)."""
    with open(data_path, encoding="utf-8") as fh:
        src = json.load(fh)
    features = []
    for feat in src["features"]:
        lon, lat = feat["geometry"]["coordinates"][:2]
        zone = zone_for_point(lat, lon)  # the API takes (lat, lon)
        props = dict(feat["properties"])
        props.update({"utm_zone": zone.name, "epsg": zone.epsg,
                      "central_meridian": zone.central_meridian, "polar": zone.polar})
        features.append({"type": "Feature", "properties": props, "geometry": feat["geometry"]})
    return {"type": "FeatureCollection", "features": features}


def main(out_path: Path | str = OUT) -> dict:
    result = build_result()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return result


if __name__ == "__main__":
    print(f"wrote {len(main()['features'])} features to {OUT}")
