"""Audit E-021 (b4): brute-force meet-in-the-middle cross-check of b3 (no solver): for each weight-11 extended
logical S, enumerate all XORs of one term per column for the first 5 columns and for the last 6, intersect.
Detector sets as numpy multi-word uint64 rows.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-10-E-021-scripts/b4_mitm.py cand|fig12 basis R
"""
import json, sys, time
sys.path.insert(0, "research/audits/2026-10-10-E-021-scripts")
from b_common import *

which, basis, R = sys.argv[1], sys.argv[2], int(sys.argv[3])
kind = {"Z": "X", "X": "Z"}[basis]
spec = load_spec() if which == "cand" else parse_schedule(A1.SPEC.to_dict())
lists, kb = audit018_lists(kind)
groups, st = dem_groups(spec, R, basis)
nd = st["detectors"]; W = (nd + 63) // 64
def vec(ds):
    v = np.zeros(W, np.uint64)
    for d in ds:
        v[d // 64] |= np.uint64(1) << np.uint64(d % 64)
    return v
G = {k: np.array([vec(ds) for ds in v]) for k, v in groups.items()}
def xorall(keys):
    acc = np.zeros((1, W), np.uint64)
    for k in keys:
        g = G[k]
        acc = (acc[:, None, :] ^ g[None, :, :]).reshape(-1, W)
    return acc
t0 = time.time(); hits = []
for i, S in enumerate(lists):
    S = sorted(S, key=lambda k: len(G[k]))
    a = xorall(S[0::2]); b = xorall(S[1::2])          # interleave to balance sizes
    sa = {r.tobytes() for r in a}
    if any(r.tobytes() in sa for r in b):
        hits.append(i)
rec = {"which": which, "basis": basis, "R": R, "lifting": len(hits), "of": len(lists), **st,
       "sec": round(time.time() - t0, 1), "hits_first": hits[:20]}
print(rec, flush=True)
json.dump(rec, open(f"{OUT}/b4_{which}_{basis}_R{R}.json", "w"), indent=1)
