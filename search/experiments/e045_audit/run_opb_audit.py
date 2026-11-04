"""E-045 audit: the E-037 audit's OPB semantic checker (opb_audit.py) against MY projected Tesseract DEM
(tess:gross:B:12 source of run_tess_mincc.py).  auditor.

  uv run python search/experiments/e045_audit/run_opb_audit.py OPB tess:gross:Z:12 9 --runs RUNS.jsonl
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "search/experiments/e037_audit"))
sys.path.insert(0, str(HERE))
import run_tess_mincc  # noqa: E402,F401  (patches mydem.load)
import opb_audit  # noqa: E402

if __name__ == "__main__":
    opb_audit.main()
