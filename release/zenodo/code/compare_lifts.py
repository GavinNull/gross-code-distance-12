"""Run the three lift implementations side by side and compare them logical by logical (SM S13, S18).

  CP-SAT  code/gross12/ext.py (lift.py)
  DP      code/lift_independent.py (frontier dynamic programming)
  MITM    code/lift_independent.py (meet in the middle, no solver)
For each (circuit, basis, R) the set of lifting logicals must be the same for all methods: empty for circuit A,
all 4224 for the Fig. 12 positive control.

    python code/compare_lifts.py                      # circuit A, R = 1..3, and Fig. 12, R = 1, both bases
    python code/compare_lifts.py --circuit A --R 1-6 --methods cpsat dp
"""
import argparse
import time

from common_cli import Verdict, circuit, load_code, parse_range
from gross12 import ext as GE
import lift_independent as LI
from sat.common import ext_general

ap = argparse.ArgumentParser()
ap.add_argument("--circuit", nargs="+", default=None)
ap.add_argument("--R", default=None)
ap.add_argument("--methods", nargs="+", default=["cpsat", "dp", "mitm"])
a = ap.parse_args()
cases = [(c, parse_range(a.R)) for c in a.circuit] if a.circuit else [("A", [1, 2, 3]), ("fig12", [1])]
code = load_code()
V = Verdict()
for name, Rs in cases:
    spec = circuit(name).canonical()
    lo = LI.label_orders(spec)
    for basis in "ZX":
        kind = LI.KIND_OF_BASIS[basis]
        keys = GE.ext_keys_from_file(code, basis)
        cp_lists = [[keys[j] for j in S] for S in GE.load_w11(basis)]
        E = ext_general(kind, lo[kind])
        k2j = {E["He"][:, j].tobytes() + E["Le"][:, j].tobytes(): j for j in range(E["N"])}
        ind_lists = [[k2j[k] for k in S] for S in cp_lists]
        for R in Rs:
            res, tm = {}, {}
            if "cpsat" in a.methods:
                t0 = time.time()
                groups, _ = GE.dem_groups(spec, code, R, basis)
                res["cpsat"] = frozenset(i for i, S in enumerate(cp_lists) if GE.lift(S, groups))
                tm["cpsat"] = time.time() - t0
            if "dp" in a.methods or "mitm" in a.methods:
                t0 = time.time()
                g2, _ = LI.build_groups(spec, R, basis, E, code)
                tb = time.time() - t0
                for meth, f in (("dp", LI.dp_lift), ("mitm", LI.mitm_lift)):
                    if meth in a.methods:
                        t0 = time.time()
                        res[meth] = frozenset(i for i, S in enumerate(ind_lists) if f(S, g2))
                        tm[meth] = time.time() - t0 + tb
            vals = set(res.values())
            n = len(next(iter(res.values())))
            V(len(vals) == 1, f"[{name}] basis {basis} R={R}: " + ", ".join(
                f"{m} {len(v)}/4224 ({tm[m]:.1f} s)" for m, v in res.items())
              + (" -- identical sets of lifting logicals" if len(vals) == 1 else " -- MISMATCH"))
            want = 0 if name == "A" or name in ("B", "C") else 4224
            V(n == want, f"[{name}] basis {basis} R={R}: {n} lifting logicals (expected {want})")
V.exit()
