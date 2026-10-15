"""A7: upper bound d_circ <= 10 for every R, both bases: a weight-10 data logical applied as 10 reset-flip faults
(X_ERROR after the data R in Z basis / Z_ERROR after RX in X basis -- SD6 fault locations) gives no detector event and
flips an observable.  Checked on the own (noiseless) encoder with the faults inserted at probability 1."""
import sys, json
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
import numpy as np, stim
from alib import *
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

HX, HZ, LX, LZ = code_with_logicals()
def min_logical(H, Lg, W=10):
    n = N; top = n; cls = []
    def chain(vs):
        nonlocal top, cls
        cur = vs[0]
        for v in vs[1:]:
            top += 1; y = top
            cls += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
            cur = y
        return cur
    for r in H: cls.append([-chain([int(j)+1 for j in np.nonzero(r)[0]])])
    cls.append([chain([int(j)+1 for j in np.nonzero(r)[0]]) for r in Lg])
    cls += CardEnc.atmost(list(range(1, n+1)), W, top_id=top, encoding=EncType.totalizer).clauses
    with Solver(name="cd15", bootstrap_with=cls) as s:
        assert s.solve(); m = s.get_model()
        return [j for j in range(n) if m[j] > 0]
spec = load_spec(sys.argv[1])
out = {}
for basis, H, Lg, err in (("Z", HZ, LZ, "X_ERROR"), ("X", HX, LX, "Z_ERROR")):
    lg = min_logical(H, Lg)
    for R in (1, 2, 3, 6, 10, 13):
        c = memory_circuit(spec, basis, R, noise=False)
        # insert after the first instruction (data reset)
        c2 = stim.Circuit()
        first = True
        for inst in c:
            c2.append(inst)
            if first:
                c2.append(err, lg, 1.0); first = False
        s = c2.compile_detector_sampler().sample(4, append_observables=True)
        nd = c2.num_detectors
        out[f"{basis}R{R}"] = {"weight": len(lg), "dets_fired": int(s[:, :nd].any(1).sum()), "obs_flipped": bool(s[:, nd:].any())}
print(json.dumps(out))
open("results/E-028-audit/a7_inject10.json", "w").write(json.dumps(out, indent=1))
