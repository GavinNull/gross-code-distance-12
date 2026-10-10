"""E-022: print a predicted witness (from pred_<key>_<basis>_<half>.json) with forward / backward propagation."""
import json, sys
import numpy as np
from search.experiments.e022.ext import Ext
from search.experiments.e022.newcodes import load_random, register
register(load_random())
key, basis, half = sys.argv[1], sys.argv[2], sys.argv[3]
o = json.load(open(f"/Users/ephemeral/Desktop/qec-ai-search/results/E-022-morphing-criterion/pred_{key}_{basis}_{half}.json"))
E = Ext(key, basis)
idx = {(f[0], f[1], tuple(f[2])): i for i, f in enumerate(E.faults)}
A = np.zeros(E.N, np.uint8); B = np.zeros(E.N, np.uint8)
for w in o["witness"]:
    i = idx[(w[0], w[1], tuple(w[2]))]
    nz = lambda v: np.nonzero(v)[0].tolist()
    print(f"  {w[0]}@{w[1]} q={w[2]} a={nz(E.a[i])} r={nz(E.r[i])} | b={nz(E.b[i])} rho={nz(E.rho[i])}")
    A ^= E.a[i]; B ^= E.b[i]
print("  sum a", np.nonzero(A)[0].tolist(), "sum b", np.nonzero(B)[0].tolist(), "d_end", o["d_end"])
