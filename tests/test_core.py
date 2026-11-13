import json

import pytest

from utm_zone_finder import (
    bbox_from_geojson,
    zone_for_bbox,
    zone_for_geojson,
    zone_for_point,
    zones_spanned,
)
from utm_zone_finder.cli import main


def test_regular_points():
    assert zone_for_point(51.5, -0.1).epsg == 32630  # London
    assert zone_for_point(-33.9, 151.2).epsg == 32756  # Sydney
    assert zone_for_point(0, 0).epsg == 32631


def test_boundaries_and_antimeridian():
    assert zone_for_point(10, -180).number == 1
    assert zone_for_point(10, 180).number == 60
    assert zone_for_point(10, 6).number == 32
    assert zone_for_point(10, 5.999).number == 31


def test_norway_exception():
    assert zone_for_point(60, 5).number == 32  # Bergen
    assert zone_for_point(60, 2.9).number == 31
    assert zone_for_point(64, 5).number == 31  # just north of the exception
    assert zone_for_point(56, 3).number == 32
    assert zone_for_point(55.9, 5).number == 31


def test_svalbard_exceptions():
    assert zone_for_point(78, 15).number == 33  # Longyearbyen
    assert zone_for_point(78, 5).number == 31
    assert zone_for_point(78, 25).number == 35
    assert zone_for_point(78, 40).number == 37
    assert zone_for_point(75, 20.9).number == 33
    assert zone_for_point(75, 21).number == 35


def test_polar_flag_and_invalid_input():
    assert zone_for_point(85, 10).polar
    assert not zone_for_point(84, 10).polar
    with pytest.raises(ValueError):
        zone_for_point(91, 0)
    with pytest.raises(ValueError):
        zone_for_point(0, float("nan"))


def test_bbox():
    assert zone_for_bbox(-1, 50, 1, 52).epsg == 32631
    assert [z.number for z in zones_spanned(-1, 50, 1, 52)] == [30, 31]
    with pytest.raises(ValueError):
        zone_for_bbox(5, 0, 1, 1)


def test_geojson(tmp_path):
    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [30.0, 30.0]}},
            {"type": "Feature", "properties": {}, "geometry": None},
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [[[31, 31], [32, 31], [32, 32], [31, 31]]]},
            },
        ],
    }
    assert bbox_from_geojson(fc) == (30.0, 30.0, 32.0, 32.0)
    assert zone_for_geojson(fc).epsg == 32636
    p = tmp_path / "a.geojson"
    p.write_text(json.dumps(fc))
    assert zone_for_geojson(str(p)).number == 36
    with pytest.raises(ValueError):
        bbox_from_geojson({"type": "FeatureCollection", "features": []})


def test_cli(capsys, tmp_path):
    assert main(["point", "60", "5"]) == 0
    assert "EPSG:32632" in capsys.readouterr().out
    assert main(["bbox", "-1", "50", "1", "52"]) == 0
    assert "Spans zones" in capsys.readouterr().out
    assert main(["point", "100", "5"]) == 2
    assert main(["geojson", str(tmp_path / "missing.json")]) == 2
    capsys.readouterr()
    assert main(["point", "78", "15", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["epsg"] == 32633


@pytest.mark.parametrize(
    "doc",
    [
        {"type": "Point", "coordinates": [30]},
        None,
        [],
        {"type": "Point", "coordinates": "x"},
        {"type": "Point", "coordinates": [True, False]},
        {"type": "FeatureCollection", "features": [None]},
        {"type": "FeatureCollection", "features": 5},
        {"type": "FeatureCollection", "features": None},
        {"type": "FeatureCollection"},
        {"type": "FeatureCollection", "features": {"a": 1}},
        {"type": "GeometryCollection", "geometries": "x"},
        {"type": "Feature"},
        {"type": "Feature", "geometry": "x"},
        {"type": "Feature", "geometry": []},
        {"type": "Feature", "geometry": {"type": "Point"}},
        {"type": "Point", "coordinates": None},
        {"type": "Point", "coordinates": {"lon": 1, "lat": 2}},
        {"type": "Point", "coordinates": ["1", "2"]},
        {"type": "Point", "coordinates": [1, None]},
        {"type": "Point", "coordinates": [1, 2, "x"]},
        {"type": "Point", "coordinates": [float("nan"), 1]},
        {"type": "Point", "coordinates": [1, float("inf")]},
        {"type": "Point", "coordinates": [200, 1]},
        {"type": "Point", "coordinates": [1, -95]},
        {"type": "MultiPoint", "coordinates": [[0, 0], [float("nan"), 1]]},
        {"type": "MultiPoint", "coordinates": [[0, 0], [1, float("-inf")]]},
        {"type": "LineString", "coordinates": [[0, 0], [1, 2, float("nan")]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, None], [0, 0]]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], 5, [0, 0]]]},
        {"type": "Unknown", "coordinates": [0, 0]},
        # "type" of the wrong kind
        {"type": [], "coordinates": [0, 0]},
        {"type": {}, "coordinates": [0, 0]},
        {"type": None, "coordinates": [0, 0]},
        {"type": 1, "coordinates": [0, 0]},
        {"coordinates": [0, 0]},
        {"type": "FeatureCollection", "features": [{"type": []}]},
        # coordinate nesting that does not match the geometry type
        {"type": "Point", "coordinates": [[30, 30], [32, 32]]},
        {"type": "Point", "coordinates": []},
        {"type": "MultiPoint", "coordinates": [0, 0]},
        {"type": "MultiPoint", "coordinates": [[[0, 0]]]},
        {"type": "LineString", "coordinates": [0, 0]},
        {"type": "LineString", "coordinates": [[0, 0]]},
        {"type": "LineString", "coordinates": [[[0, 0], [1, 1]]]},
        {"type": "MultiLineString", "coordinates": [[0, 0], [1, 1]]},
        {"type": "MultiLineString", "coordinates": [[]]},
        {"type": "Polygon", "coordinates": [[0, 0], [1, 0], [1, 1], [0, 0]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]},
        {"type": "MultiPolygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        {"type": "MultiPolygon", "coordinates": [[[[[0, 0]]]]]},
        # collection members of the wrong object type
        {"type": "FeatureCollection", "features": [{"type": "Point", "coordinates": [0, 0]}]},
        {"type": "FeatureCollection", "features": [{"type": "FeatureCollection", "features": []}]},
        {"type": "GeometryCollection", "geometries": [{"type": "Feature", "geometry": None}]},
        {"type": "Feature", "geometry": {"type": "Feature", "geometry": None}},
        {"type": "Feature", "geometry": {"type": "FeatureCollection", "features": []}},
        "a string",
        42,
        True,
    ],
)
def test_malformed_geojson(doc, tmp_path, capsys):
    if not isinstance(doc, str):  # strings are treated as file paths by the API
        with pytest.raises(ValueError):
            bbox_from_geojson(doc)
    p = tmp_path / "bad.geojson"
    p.write_text(json.dumps(doc))  # json.dumps writes NaN/Infinity, which json.load accepts
    assert main(["geojson", str(p)]) == 2
    assert "error:" in capsys.readouterr().err


def test_valid_geometry_shapes_accepted():
    ring = [[10, 50], [11, 50], [11, 51], [10, 50]]
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": {"type": "GeometryCollection", "geometries": [
            {"type": "Point", "coordinates": [10, 50, 100]},
            {"type": "MultiPoint", "coordinates": []},
            {"type": "LineString", "coordinates": [[10, 50], [12, 52]]},
            {"type": "MultiLineString", "coordinates": [[[10, 50], [11, 51]]]},
            {"type": "Polygon", "coordinates": [ring]},
            {"type": "MultiPolygon", "coordinates": [[ring], [ring]]},
            {"type": "GeometryCollection", "geometries": []},
        ]}},
        {"type": "Feature", "geometry": None},
    ]}
    assert bbox_from_geojson(doc) == (10, 50, 12, 52)


@pytest.mark.parametrize("text", ["", "{", "not json", "[" * 100000 + "]" * 100000])
def test_unreadable_geojson_file(text, tmp_path, capsys):
    p = tmp_path / "bad.geojson"
    p.write_text(text)
    with pytest.raises(ValueError):
        bbox_from_geojson(p)
    assert main(["geojson", str(p)]) == 2
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize(
    "lat, lon",
    [
        (None, 0),
        (0, None),
        ("10", 0),
        (0, "x"),
        (True, 0),
        (0, [1]),
        ({"a": 1}, 0),
        (float("nan"), 0),
        (0, float("inf")),
        (10**400, 0),
        (-90.1, 0),
        (0, 180.1),
    ],
)
def test_invalid_point_and_bbox_inputs(lat, lon):
    with pytest.raises(ValueError):
        zone_for_point(lat, lon)
    with pytest.raises(ValueError):
        zone_for_bbox(lon, lat, 10, 10)
    with pytest.raises(ValueError):
        zones_spanned(-10, -10, lon, lat)


@pytest.mark.parametrize("argv", [["point", "nan", "0"], ["point", "0", "inf"], ["bbox", "0", "0", "nan", "1"]])
def test_cli_rejects_non_finite(argv, capsys):
    assert main(argv) == 2
    assert "error:" in capsys.readouterr().err


def test_polar_flag_across_80s():
    spanned = zones_spanned(0, -85, 0, -75)
    assert [(z.name, z.polar) for z in spanned] == [("31S", True)]
    assert zone_for_bbox(0, -85, 0, -75).polar
    assert not zone_for_bbox(0, -79, 0, -75).polar
    assert zone_for_bbox(10, 80, 12, 85).polar
    # Only the part of the box that is actually polar marks a zone polar.
    assert [(z.name, z.polar) for z in zones_spanned(-1, 50, 1, 52)] == [("30N", False), ("31N", False)]
