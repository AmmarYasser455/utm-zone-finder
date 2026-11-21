import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "brand"
ORANGE = "#f2552c"
INK = {"logo.svg": "#121417", "logo-dark.svg": "#f3eee4"}


def test_logos_are_valid_and_on_palette():
    for name, ink in INK.items():
        path = BRAND / name
        assert path.exists()
        root = ET.parse(path).getroot()
        assert root.get("viewBox") == "0 0 100 100"
        assert root.get("width") == "100" and root.get("height") == "100"
        text = path.read_text(encoding="utf-8").lower()
        colours = set(re.findall(r"#[0-9a-f]{3,8}\b", text))
        assert colours == {ink, ORANGE}
        for banned in ("opacity", "gradient", "filter", "<text", "<image", "stroke"):
            assert banned not in text


def test_readme_header_and_openterra():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "assets/brand/logo-dark.svg" in readme
    assert "[OpenTerra](https://github.com/AmmarYasser455)" in readme
