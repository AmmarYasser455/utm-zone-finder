"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys

from .core import bbox_from_geojson, zone_for_bbox, zone_for_point, zones_spanned


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="utm-zone-finder",
        description="Find the UTM zone and EPSG code for a point, bbox or GeoJSON file.",
    )
    sub = p.add_subparsers(dest="command", required=True)
    pt = sub.add_parser("point", help="latitude and longitude")
    pt.add_argument("lat", type=float)
    pt.add_argument("lon", type=float)
    bb = sub.add_parser("bbox", help="bounding box")
    bb.add_argument("min_lon", type=float)
    bb.add_argument("min_lat", type=float)
    bb.add_argument("max_lon", type=float)
    bb.add_argument("max_lat", type=float)
    gj = sub.add_parser("geojson", help="GeoJSON file")
    gj.add_argument("path")
    for s in (pt, bb, gj):
        s.add_argument("--json", action="store_true", help="print JSON")
    return p


def _line(z) -> str:
    note = "  (outside UTM range, polar)" if z.polar else ""
    return f"UTM zone {z.name}  EPSG:{z.epsg}  central meridian {z.central_meridian}{note}"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "point":
            zone, spanned = zone_for_point(args.lat, args.lon), None
        else:
            if args.command == "bbox":
                box = (args.min_lon, args.min_lat, args.max_lon, args.max_lat)
            else:
                box = bbox_from_geojson(args.path)
            zone, spanned = zone_for_bbox(*box), zones_spanned(*box)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        out = zone.to_dict()
        if spanned is not None:
            out = {"zone": out, "spanned": [z.to_dict() for z in spanned]}
        print(json.dumps(out, indent=2))
    else:
        print(_line(zone))
        if spanned is not None and len(spanned) > 1:
            print("Spans zones: " + ", ".join(f"{z.name} (EPSG:{z.epsg})" for z in spanned))
    return 0


if __name__ == "__main__":
    sys.exit(main())
