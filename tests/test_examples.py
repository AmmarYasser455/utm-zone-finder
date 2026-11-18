import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
DOCS = ROOT / "docs"


def _load():
    spec = importlib.util.spec_from_file_location("make_demo", EXAMPLES / "make_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_known_zones_of_real_cities():
    props = {f["properties"]["name"]: f["properties"] for f in _load().build_result()["features"]}
    # Norway exception: Bergen (5.3 E) is zone 32, not 31. Svalbard: 11.9 E and 15.6 E are 33.
    assert props["Bergen"]["epsg"] == 32632
    assert props["Ny-Ålesund"]["epsg"] == 32633
    assert props["Longyearbyen"]["epsg"] == 32633
    assert props["Tromsø"]["epsg"] == 32634
    assert props["London"]["epsg"] == 32630
    assert props["Reykjavik"]["epsg"] == 32627
    assert props["Cairo"]["epsg"] == 32636
    assert props["Quito"]["epsg"] == 32717  # just south of the equator: S zone
    assert props["Sydney"]["epsg"] == 32756
    assert props["Wellington"]["epsg"] == 32760


def test_demo_geojson_is_not_stale(tmp_path):
    _load().main(tmp_path / "demo.geojson")
    assert _read(tmp_path / "demo.geojson") == _read(DOCS / "demo.geojson")


def test_demo_page_and_example_size():
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "leaflet@1.9.4/dist/leaflet.js" in html
    assert "OpenStreetMap" in html
    assert "https://github.com/AmmarYasser455/utm-zone-finder" in html
    assert sum(p.stat().st_size for p in EXAMPLES.glob("*.geojson")) < 100_000
