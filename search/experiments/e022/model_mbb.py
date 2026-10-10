"""E-022: simplified 'midpoint + boundary' model: faults = single-qubit errors at the mid-cycle point (CNOT
components after Fd2), left data errors at the start and end of the half-cycle, reset and measurement flips.
usage: model_mbb.py <key> <basis> [Wmax]"""
import json, sys
import numpy as np
from search.experiments.e019.dfsrun import min_weight
from search.experiments.e022.ext import Ext
from search.experiments.e022.solve22 import instance
key, basis = sys.argv[1], sys.argv[2]
Wmax = int(sys.argv[3]) if len(sys.argv) > 3 else 9
E = Ext(key, basis)
keep = np.array([(kind != "cx") or (k == 3 and len(qs) == 1) for (kind, k, qs) in E.faults])
path, norb, groups, Hd, Ld, _ = instance(E, "start", keep=keep, tag="_mbb")
W, sol, log = min_weight(path, norb, Wmax, npar=1)
print(json.dumps(dict(key=key, basis=basis, d_mbb=W, cols=int(Hd.shape[1]),
                      wit=[E.faults[groups[c][0]][0] for c in sol] if sol else None)), flush=True)
