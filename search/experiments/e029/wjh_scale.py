"""E-029: cost probe of the WJH pure-Python CCMW recursion (codeDistance, commit a4afe9c) on an instance:
time of the search rooted at column 0 for cluster sizes d = 2..DMAX (their CCMWRec, unchanged).

    uv run python search/experiments/e029/wjh_scale.py INSTANCE DMAX
"""
import sys, time, types
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
stub = types.ModuleType("gurobipy"); stub.GRB = types.SimpleNamespace(); sys.modules["gurobipy"] = stub
sys.path.insert(0, str(ROOT / "tools" / "wjh" / "codeDistancePYPI"))
from codedistance.distance import CCMWRec, bin2Set  # noqa: E402
lines = open(sys.argv[1]).read().split("\n")
nr, nc, nobs, norb = map(int, lines[0].split())
H = np.zeros((nr, nc), np.int8); L = np.zeros((nobs, nc), np.int8)
for c in range(nc):
    t = list(map(int, lines[1 + c].split())); k = t[0]; H[t[1:1 + k], c] = 1; m = t[1 + k]; L[t[2 + k:2 + k + m], c] = 1
HT = [set(bin2Set(c)) for c in H.T]; LT = [set(bin2Set(c)) for c in L.T]
HE = [set(bin2Set(r)) for r in H]
for d in range(2, int(sys.argv[2]) + 1):
    sList, lList = [set()] * nc, [set()] * nc
    sList[1] = HT[0]; lList[1] = LT[0]
    t0 = time.process_time()
    r = CCMWRec(HT, LT, HE, d, 1, 0, {0}, sList, lList, 0, True)
    print(f"d={d} root 0: found={r is not False} cpu {time.process_time() - t0:.2f}s", flush=True)
