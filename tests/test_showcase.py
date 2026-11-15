import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHOWCASE = ROOT / "showcase"


def _load():
    spec = importlib.util.spec_from_file_location("make_showcase", SHOWCASE / "make_showcase.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_map_geojson_is_not_stale(tmp_path):
    _load().main(tmp_path, png=False)
    assert _read(tmp_path / "map.geojson") == _read(SHOWCASE / "map.geojson")
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == (
        SHOWCASE / "index.html").read_text(encoding="utf-8")


def test_known_zones():
    props = {f["properties"]["name"]: f["properties"]
             for f in _read(SHOWCASE / "map.geojson")["features"]}
    # Cairo governorate sits at about 31.2-31.9 E: zone 36N. Matruh reaches 24.7 E: zone 35N.
    assert props["Al Qahirah"]["epsg"] == 32636
    assert props["Matruh"]["epsg"] == 32635
    assert props["Al Bahr al Ahmar"]["zones_spanned"] == ["36N", "37N"]
    assert props["Al Qahirah"]["spans_multiple_zones"] is False


def _vertices(fc):
    out = set()

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            out.add(tuple(c))
        else:
            for x in c:
                walk(x)

    for f in fc["features"]:
        walk(f["geometry"]["coordinates"])
    return out


def test_coordinates_keep_source_precision():
    src = _read(SHOWCASE / "data" / "egypt_governorates.geojson")
    out = _read(SHOWCASE / "map.geojson")
    src_v, out_v = _vertices(src), _vertices(out)
    # Output carries exactly the source vertices (only ring order may change).
    assert out_v == src_v
    # The committed source is not rounded to 3 decimals (about 100 m).
    assert any(round(v, 3) != v for xy in src_v for v in xy)
    # Every vertex is lon/lat inside Egypt (x = lon about 24-37 E, y = lat about 21-32 N).
    assert all(24 < x < 37.5 and 21 < y < 32 for x, y in src_v)


_SQ = [[[31.2, 30.0], [31.3, 30.0], [31.3, 30.1], [31.2, 30.1], [31.2, 30.0]]]


def _feat(geometry, properties=None):
    return {"type": "Feature", "properties": {"name": "x"} if properties is None else properties,
            "geometry": geometry}


@pytest.mark.parametrize("data", [
    None,
    [],
    "FeatureCollection",
    {"type": "Feature", "properties": {}, "geometry": None},
    {"type": "FeatureCollection"},
    {"type": "FeatureCollection", "features": None},
    {"type": "FeatureCollection", "features": {"a": 1}},
    {"type": "FeatureCollection", "features": [None]},
    {"type": "FeatureCollection", "features": ["feature"]},
    {"type": "FeatureCollection", "features": [_feat({"type": "Polygon", "coordinates": _SQ}, [])]},
    {"type": "FeatureCollection", "features": [_feat(None)]},
    {"type": "FeatureCollection", "features": [_feat({"type": "Polygon", "coordinates": []})]},
    {"type": "FeatureCollection", "features": [_feat({"type": "Polygon"})]},
    {"type": "FeatureCollection", "features": [_feat({"type": "Polygon", "coordinates": "x"})]},
    {"type": "FeatureCollection",
     "features": [_feat({"type": "Polygon", "coordinates": [[[float("nan"), 30.0]] * 4]})]},
    {"type": "FeatureCollection",
     "features": [_feat({"type": "Polygon", "coordinates": [[["31", "30"]] * 4]})]},
    {"type": "FeatureCollection",  # lat/lon swapped past 90: rejected, not silently used
     "features": [_feat({"type": "Point", "coordinates": [30.0, 131.2]})]},
    {"type": "FeatureCollection", "features": [_feat({"type": "Circle", "coordinates": [31, 30]})]},
])
def test_build_result_rejects_bad_input(tmp_path, data):
    path = tmp_path / "in.geojson"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        _load().build_result(path)


def test_build_result_empty_and_valid(tmp_path):
    mod = _load()
    path = tmp_path / "in.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
    assert mod.build_result(path) == {"type": "FeatureCollection", "features": []}
    # A small square in central Cairo (lon 31.2-31.3 E, lat 30.0-30.1 N): zone 36N.
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        _feat({"type": "Polygon", "coordinates": _SQ})]}), encoding="utf-8")
    (f,) = mod.build_result(path)["features"]
    assert f["properties"]["epsg"] == 32636
    assert f["properties"]["name"] == "x"
    assert _vertices({"features": [f]}) == {tuple(c) for c in _SQ[0]}


def test_notebook_executes_with_inline_map(tmp_path):
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    pytest.importorskip("matplotlib")
    pytest.importorskip("ipykernel")
    nb = nbformat.read(str(SHOWCASE / "showcase.ipynb"), as_version=4)
    # Run from the repository root so relative paths in the notebook resolve;
    # the executed copy is only kept in memory (nothing is written back).
    nbclient.NotebookClient(nb, timeout=300, resources={"metadata": {"path": str(ROOT)}}).execute()
    images = 0
    for cell in nb.cells:
        for out in cell.get("outputs", []):
            assert out.get("output_type") != "error"
            if "image/png" in out.get("data", {}):
                images += 1
    assert images >= 1


def test_png_is_produced(tmp_path):
    pytest.importorskip("matplotlib")
    _load().main(tmp_path)
    png = tmp_path / "map.png"
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
