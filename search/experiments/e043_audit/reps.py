"""Orbit-representative sublists (B_audit pickle format) of the auditor's lists, for the second bulk solver
(theory B's Bellman-Ford dc.py, not E-043 code).
  uv run python -m search.experiments.e043_audit.reps g9 Z 10"""
import pickle
import sys

from search.experiments.e043_audit.common import OUT
from search.experiments.e043_audit.lists import build

name, basis, w = sys.argv[1], sys.argv[2], int(sys.argv[3])
B, cols, zero, keys, colperm = build(name, basis)
kidx = {k: i for i, k in enumerate(keys)}
d = pickle.load(open(OUT / f"list_{name}_{basis}_w{w}.pkl", "rb"))
seen, reps = set(), []
for S in d["keys"]:
    t = tuple(sorted(kidx[k] for k in S))
    if t in seen:
        continue
    reps.append(S)
    for pm in colperm:
        seen.add(tuple(sorted(pm[j] for j in t)))
assert len(seen) == len(d["keys"])
pickle.dump({"keys": reps, "colset": keys}, open(OUT / f"reps_{name}_{basis}_w{w}.pkl", "wb"))
print(len(reps), "of", len(d["keys"]))
