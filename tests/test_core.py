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
        zone_for_bbox(0, 5, 1, 1)


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


def test_bbox_crossing_antimeridian(capsys):
    # min_lon > max_lon means the box wraps over 180 (e.g. Fiji).
    assert [z.number for z in zones_spanned(170, -20, -170, -10)] == [1, 2, 59, 60]
    assert zone_for_bbox(178, 10, -170, 20).number == 1  # centre at -176
    assert zone_for_bbox(170, 10, -178, 20).number == 60  # centre at 176
    with pytest.raises(ValueError):
        zone_for_bbox(170, 20, -170, 10)  # lat order is still checked
    assert main(["bbox", "178", "-20", "-178", "-10"]) == 0
    out = capsys.readouterr().out
    assert "Spans zones: 1S (EPSG:32701), 60S (EPSG:32760)" in out


def _dense_spanned(min_lon, min_lat, max_lon, max_lat, step=0.1):
    """Reference: zone_for_point on a dense grid (edges of the box included)."""
    if min_lon > max_lon:
        max_lon += 360
    nlon = round((max_lon - min_lon) / step)
    nlat = round((max_lat - min_lat) / step)
    lons = [min_lon + i * (max_lon - min_lon) / nlon for i in range(nlon + 1)] if nlon else [min_lon]
    lats = [min_lat + i * (max_lat - min_lat) / nlat for i in range(nlat + 1)] if nlat else [min_lat]
    found = {}
    for lat in lats:
        for lon in lons:
            z = zone_for_point(lat, lon - 360 if lon > 180 else lon)
            found[z.name] = found.get(z.name, False) or z.polar
    return found


@pytest.mark.parametrize(
    "box",
    [
        (4.5, 57.9, 31.2, 71.2),  # mainland Norway (Norway exception, zones 32-36)
        (10.0, 76.4, 33.5, 80.8),  # Svalbard (odd zones only)
        (-1.0, 50.0, 1.0, 52.0),  # London area, across 0 degrees
        (29.5, -1.0, 35.0, 4.0),  # Lake Victoria region, across the equator
        (176.0, -20.0, -178.0, -15.0),  # Fiji, across the antimeridian
        (2.0, 83.0, 13.0, 85.0),  # across 84N, where Svalbard zones end and polar begins
        (5.5, 55.5, 12.5, 64.5),  # all four edges of the Norway exception
        (0.0, 10.0, 6.0, 11.0),  # ends exactly on the 6E zone edge
    ],
)
def test_zones_spanned_matches_dense_grid(box):
    got = {z.name: z.polar for z in zones_spanned(*box)}
    assert got == _dense_spanned(*box)


def test_zones_spanned_exact_edges():
    # The 6E meridian belongs to zone 32: ending there lists 32, starting there skips 31.
    assert [z.name for z in zones_spanned(0, 10, 6, 11)] == ["31N", "32N"]
    assert [z.name for z in zones_spanned(6, 10, 8, 11)] == ["32N"]
    # The equator belongs to the northern hemisphere.
    assert [z.name for z in zones_spanned(0, -1, 1, 0)] == ["31N", "31S"]
    # A degenerate box is a point.
    assert zones_spanned(5, 60, 5, 60) == [zone_for_point(60, 5)]
    # Bergen to just inside the 3E Norway edge: 32V only, 31 not touched.
    assert [z.name for z in zones_spanned(3.0, 59.0, 5.5, 61.0)] == ["32N"]
    # Just west of 3E at Norway latitudes is zone 31.
    assert [z.name for z in zones_spanned(2.999, 59.0, 5.5, 61.0)] == ["31N", "32N"]


def test_zones_spanned_whole_world():
    spanned = zones_spanned(-180, -90, 180, 90)
    assert len(spanned) == 120  # every zone in both hemispheres
    assert all(z.polar for z in spanned)  # each reaches beyond 84N or 80S
    assert [z.number for z in spanned[:3]] == [1, 2, 3]


def _count_point_calls(monkeypatch, box):
    import utm_zone_finder.core as core

    calls = []
    real = core.zone_for_point

    def counting(lat, lon):
        calls.append((lat, lon))
        return real(lat, lon)

    monkeypatch.setattr(core, "zone_for_point", counting)
    result = core.zones_spanned(*box)
    return result, len(calls)


@pytest.mark.parametrize(
    "box, max_calls",
    [
        # 15 latitude samples x 129 longitude samples; a 0.5 degree grid needs 361 x 721.
        ((-180, -90, 180, 90), 1935),
        # One zone, no edge inside: 3 x 3 samples whatever the box size (was 81 x 5).
        ((0.5, 10.0, 2.5, 50.0), 9),
        # Fiji across the antimeridian: only the 180 edge is inside, 3 x 5 (was 11 x 13).
        ((176.0, -20.0, -178.0, -15.0), 15),
    ],
)
def test_zones_spanned_work_is_bounded_by_edges(monkeypatch, box, max_calls):
    result, n = _count_point_calls(monkeypatch, box)
    assert result == zones_spanned(*box)
    assert n <= max_calls


# Suva (178.44E) and Lakeba (178.8W), Fiji: two islands on either side of 180.
_FIJI = [[178.44, -18.14], [-178.8, -18.2]]


def test_declared_bbox_crossing_antimeridian(tmp_path, capsys):
    pts = {"type": "MultiPoint", "coordinates": _FIJI}
    # Without a bbox the plain min/max spans most of the globe (centre near 0).
    assert bbox_from_geojson(pts) == (-178.8, -18.2, 178.44, -18.14)
    assert zone_for_geojson(pts).number == 30
    # The declared RFC 7946 bbox wraps over 180 and gives the right zone.
    doc = dict(pts, bbox=[177, -19, -178, -16])
    assert bbox_from_geojson(doc) == (177, -19, -178, -16)
    assert zone_for_geojson(doc).epsg == 32760
    six = dict(pts, bbox=[177, -19, 0, -178, -16, 100])
    assert bbox_from_geojson(six) == (177, -19, -178, -16)
    # A line cut at the antimeridian (RFC 7946 3.1.9); -180 and 180 are the same meridian.
    cut = {"type": "Feature", "properties": {}, "bbox": [178, -18, -179, -16], "geometry": {
        "type": "MultiLineString", "coordinates": [[[178, -17], [180, -17]], [[-180, -17], [-179, -17]]]}}
    assert zone_for_geojson(cut).number == 60
    edge = {"type": "Point", "coordinates": [180, 0], "bbox": [-180, 0, -179, 0]}
    assert bbox_from_geojson(edge) == (-180, 0, -179, 0)
    # "bbox": null is treated as absent.
    assert bbox_from_geojson(dict(pts, bbox=None)) == (-178.8, -18.2, 178.44, -18.14)
    p = tmp_path / "fiji.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "bbox": [177, -19, -178, -16], "features": [
        {"type": "Feature", "properties": {}, "geometry": pts}]}), encoding="utf-8")
    assert main(["geojson", str(p)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("UTM zone 60S  EPSG:32760")
    assert "1S (EPSG:32701)" in out and "30S" not in out


_LINE = {"type": "LineString", "coordinates": [[10, 50], [12, 52]]}


@pytest.mark.parametrize(
    "doc",
    [
        # malformed bbox members
        dict(_LINE, bbox=[10, 50, 12]),
        dict(_LINE, bbox=[10, 50, 12, 52, 0]),
        dict(_LINE, bbox=[]),
        dict(_LINE, bbox="10,50,12,52"),
        dict(_LINE, bbox={"west": 10}),
        dict(_LINE, bbox=True),
        dict(_LINE, bbox=5),
        dict(_LINE, bbox=[10, 50, "12", 52]),
        dict(_LINE, bbox=[10, 50, None, 52]),
        dict(_LINE, bbox=[10, 50, True, 52]),
        dict(_LINE, bbox=[10, float("nan"), 12, 52]),
        dict(_LINE, bbox=[10, 50, float("inf"), 52]),
        dict(_LINE, bbox=[10, 50, 10**400, 52]),
        dict(_LINE, bbox=[10, 50, 200, 52]),
        dict(_LINE, bbox=[-181, 50, 12, 52]),
        dict(_LINE, bbox=[10, 52, 12, 50]),
        dict(_LINE, bbox=[10, 50, 12, 91]),
        dict(_LINE, bbox=[10, 50, 5, 12, 52, 0]),
        # a bbox without valid GeoJSON around it
        {"bbox": [0, 0, 1, 1]},
        {"type": "Point", "bbox": [0, 0, 1, 1]},
        {"type": "FeatureCollection", "features": [], "bbox": [0, 0, 1, 1]},
        # a bbox that does not contain the geometry
        dict(_LINE, bbox=[10, 50, 11, 52]),
        dict(_LINE, bbox=[10, 51, 12, 52]),
        dict(_LINE, bbox=[12, 50, 10, 52]),
        {"type": "MultiPoint", "coordinates": _FIJI, "bbox": [178, -19, -179, -16]},
        # the edge between the vertices runs through 0 in lon/lat space
        {"type": "LineString", "coordinates": [[-170, 0], [170, 0]], "bbox": [170, 0, -170, 0]},
        {"type": "Polygon", "bbox": [170, 0, -170, 1],
         "coordinates": [[[170, 0], [-170, 0], [-170, 1], [170, 1], [170, 0]]]},
        {"type": "Feature", "bbox": [170, 0, -170, 0], "geometry": {"type": "GeometryCollection",
         "geometries": [{"type": "LineString", "coordinates": [[-170, 0], [170, 0]]}]}},
    ],
)
def test_invalid_declared_bbox(doc, tmp_path, capsys):
    with pytest.raises(ValueError):
        bbox_from_geojson(doc)
    with pytest.raises(ValueError):
        zone_for_geojson(doc)
    p = tmp_path / "bad.geojson"
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["geojson", str(p)]) == 2
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize(
    "name,lat,lon,epsg",
    [
        ("Tromso", 69.65, 18.96, 32634),
        ("Longyearbyen", 78.22, 15.65, 32633),
        ("Ny-Alesund", 78.92, 11.93, 32633),
        ("Nordaustlandet", 79.9, 23.0, 32635),
        ("Kvitoya", 80.15, 31.5, 32635),
        ("Oslo", 59.91, 10.75, 32632),
        ("Stavanger", 58.97, 5.73, 32632),
        ("Santiago", -33.45, -70.67, 32719),
    ],
)
def test_real_places(name, lat, lon, epsg):
    assert zone_for_point(lat, lon).epsg == epsg, name


def test_cli_text_output_matches_readme(capsys):
    assert main(["point", "60", "5"]) == 0
    assert capsys.readouterr().out == "UTM zone 32N  EPSG:32632  central meridian 9\n"
    assert main(["bbox", "-1", "50", "1", "52"]) == 0
    assert capsys.readouterr().out == (
        "UTM zone 31N  EPSG:32631  central meridian 3\n"
        "Spans zones: 30N (EPSG:32630), 31N (EPSG:32631)\n"
    )


def test_cli_geojson_stdin(monkeypatch, capsys):
    import io

    # Bergen, Norway (lon 5.32, lat 60.39): zone 32 by the Norway exception
    gj = '{"type": "Point", "coordinates": [5.32, 60.39]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(gj))
    assert main(["geojson", "-"]) == 0
    assert "EPSG:32632" in capsys.readouterr().out
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert main(["geojson", "-"]) == 2
    assert capsys.readouterr().err.startswith("error:")


@pytest.mark.parametrize(
    "text",
    [
        "",  # empty
        "   \n",  # whitespace only
        "not json",
        "{",
        "null",
        "true",
        "42",
        "NaN",
        '"area.geojson"',  # a string is not treated as a path
        "[]",
        '[{"type": "Point", "coordinates": [5.32, 60.39]}]',
        "{}",
        '{"type": null}',
        '{"type": "Point"}',
        '{"type": "Point", "coordinates": null}',
        '{"type": "Point", "coordinates": [NaN, 60]}',
        '{"type": "Point", "coordinates": [5, Infinity]}',
        '{"type": "Point", "coordinates": ["5", 60]}',
        '{"type": "Point", "coordinates": [5, 91]}',
        '{"type": "FeatureCollection", "features": {}}',
        '{"type": "FeatureCollection", "features": []}',
        "[" * 100000 + "]" * 100000,  # nested too deeply
        '{"a":' * 100000 + "1" + "}" * 100000,
    ],
)
def test_cli_stdin_rejects_invalid_input(text, monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert main(["geojson", "-"]) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert captured.out == ""


def test_cli_stdin_json_string_is_not_a_path(monkeypatch, capsys, tmp_path):
    import io
    import json

    f = tmp_path / "p.geojson"
    f.write_text('{"type": "Point", "coordinates": [5.32, 60.39]}')
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(str(f))))
    assert main(["geojson", "-"]) == 2
    assert capsys.readouterr().err.startswith("error:")


def test_cli_polar_note_and_southern_hemisphere(capsys):
    # Near the North Pole (beyond 84N) a zone is returned and flagged as polar.
    assert main(["point", "89", "0"]) == 0
    assert capsys.readouterr().out == (
        "UTM zone 31N  EPSG:32631  central meridian 3  (outside UTM range, polar)\n"
    )
    # Sydney (33.87 S, 151.21 E): zone 56 south, EPSG 327xx.
    assert main(["point", "-33.87", "151.21"]) == 0
    assert capsys.readouterr().out == "UTM zone 56S  EPSG:32756  central meridian 153\n"


def test_cli_bbox_json_has_zone_and_spanned(capsys):
    assert main(["bbox", "-1", "50", "1", "52", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["zone"]["epsg"] == 32631
    assert [z["epsg"] for z in data["spanned"]] == [32630, 32631]
