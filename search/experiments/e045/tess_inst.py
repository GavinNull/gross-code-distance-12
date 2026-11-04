"""E-045: E-037's dem_inst.py (unchanged, imported) with one extra source  tess:gross:BASIS  = the projected DEM of
Crocker's Tesseract file bb144_BASIS.stim (search/experiments/e045/tess.py).  Same arguments as dem_inst.py.  experimenter.

    uv run python search/experiments/e045/tess_inst.py tess:gross:Z 9 OUT [--blocks F] [--sym formula]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "search/experiments/e037"))
import dem_inst  # noqa: E402
from search.experiments.e045 import tess  # noqa: E402

_orig = dem_inst.load_source


def load_source(s):
    if s.startswith("tess:"):
        _, code, basis = s.split(":")
        assert code == "gross"
        return tess.source(basis)
    return _orig(s)


dem_inst.load_source = load_source

if __name__ == "__main__":
    dem_inst.main()
