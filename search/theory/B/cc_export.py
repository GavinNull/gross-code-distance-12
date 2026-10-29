"""Export the evaluator SD6 DEM of a schedule as an E-029 ccsearch instance (project tool, unchanged; only the
torus size of bb108 is added to its lookup table at run time).
  uv run python -m search.theory.B.cc_export SPEC TASK L M BASIS R OUT
"""
import sys
from search.theory.B.bulk import ROOT
sys.path.insert(0, str(ROOT / "search/experiments/e029"))
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import export  # noqa: E402
spec, task, l, m, basis, R, out = sys.argv[1:8]
export.LM[task] = (int(l), int(m))
export.main(["dem", spec, task, basis, R, out])
