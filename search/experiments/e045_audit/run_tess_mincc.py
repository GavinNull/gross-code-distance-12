"""E-045 audit: the E-037 audit's constraint-free exhaustive search (mincc.c, run_mincc.py) run directly on MY projected
Tesseract DEM (results/E-045-audit/tess_proj_BASIS.json from tess_audit.py), with the translation group re-verified by
run_mincc.group.  Independent of VeriPB, of E-045's code and of the isomorphism.  auditor.

  uv run python search/experiments/e045_audit/run_tess_mincc.py tess:gross:Z:12 9 --sym --out results/E-045-audit/mincc_tess.jsonl
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "search/experiments/e037_audit"))
import mydem  # noqa: E402
import run_mincc  # noqa: E402

_orig = mydem.load


def load(src):
    if src.startswith("tess:"):
        b = src.split(":")[2]
        T = json.loads((ROOT / f"results/E-045-audit/tess_proj_{b}.json").read_text())
        D = [tuple(c[0]) for c in T["cols"]]; L = [tuple(c[1]) for c in T["cols"]]
        co = [((int(c[0]) // 2) * 6 + int(c[1]) // 2, int(round(c[2]))) for c in T["coords"]]
        assert len(set(co)) == len(co)
        return dict(D=D, L=L, ndet=len(co), nobs=T["nobs"], coords=co, l=12, m=6)
    return _orig(src)


mydem.load = load
run_mincc.mydem.load = load

if __name__ == "__main__":
    run_mincc.main()
