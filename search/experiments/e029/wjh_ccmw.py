"""E-029: run the Webster-Jacob-Higgott pure-Python connected-cluster routine (CCMW, codeDistance package,
tools/wjh/codeDistancePYPI, commit a4afe9c) on one of our instance files, as a third-party implementation check.
gurobipy (not installed; only needed by their Gurobi method) is stubbed so that the module imports.

    uv run python search/experiments/e029/wjh_ccmw.py INSTANCE
"""
import sys
import time
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
stub = types.ModuleType("gurobipy")
stub.GRB = types.SimpleNamespace()
sys.modules["gurobipy"] = stub
sys.path.insert(0, str(ROOT / "tools" / "wjh" / "codeDistancePYPI"))
from codedistance.distance import CCMW  # noqa: E402

lines = open(sys.argv[1]).read().split("\n")
nr, nc, nobs, norb = map(int, lines[0].split())
H = np.zeros((nr, nc), np.int8)
L = np.zeros((nobs, nc), np.int8)
for c in range(nc):
    t = list(map(int, lines[1 + c].split()))
    k = t[0]
    H[t[1:1 + k], c] = 1
    m = t[1 + k]
    L[t[2 + k:2 + k + m], c] = 1
t0 = time.process_time()
d, lo, prog = CCMW(H, L)
print("WJH CCMW d =", d, "support", np.nonzero(lo)[0].tolist(), f"cpu {time.process_time() - t0:.1f}s")
print(prog)
