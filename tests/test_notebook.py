import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "examples" / "demo.ipynb"


def test_notebook_runs(monkeypatch):
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert code
    assert all(c["outputs"] == [] and c["execution_count"] is None for c in code)
    monkeypatch.chdir(ROOT)
    ns = {"__name__": "__notebook__"}
    for cell in code:
        exec(compile("".join(cell["source"]), str(NOTEBOOK), "exec"), ns)
    assert ns["zones"]["Bergen"].epsg == 32632
    assert os.getcwd() == str(ROOT)
