"""E-022: midpoint-local models (faults restricted to CNOT layers near the mid-cycle point).
  m34 : CNOT faults after Fd2 and after F0 (all components) -> midpoint errors of weight <= 2
  m2345: CNOT faults after Fd1, Fd2, F0, F1
  mid1: single-qubit midpoint errors only (= mid-code distance d_M)
usage: midlocal.py <key> <basis> <model> [Wmax]"""
import json, sys
import numpy as np
from search.experiments.e019.dfsrun import min_weight
from search.experiments.e022.ext import Ext
from search.experiments.e022.newcodes import load_random, register
from search.experiments.e022.solve22 import instance
register(load_random())
key, basis, model = sys.argv[1], sys.argv[2], sys.argv[3]
Wmax = int(sys.argv[4]) if len(sys.argv) > 4 else 12
E = Ext(key, basis)
if model == "m34":
    keep = [kind == "cx" and k in (3, 4) for (kind, k, qs) in E.faults]
elif model == "m2345":
    keep = [kind == "cx" and k in (2, 3, 4, 5) for (kind, k, qs) in E.faults]
elif model == "mid1":
    keep = [kind == "cx" and k == 3 and len(qs) == 1 for (kind, k, qs) in E.faults]
path, norb, groups, Hd, Ld, _ = instance(E, "start", keep=np.array(keep), tag="_" + model)
W, sol, log = min_weight(path, norb, Wmax, npar=1)
out = dict(key=key, basis=basis, model=model, d=W, cols=int(Hd.shape[1]))
json.dump(out, open(f"/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion/mid_{key}_{basis}_{model}.json", "w"))
print(json.dumps(out), flush=True)
