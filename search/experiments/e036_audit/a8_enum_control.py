"""Audit claim 4: soundness stress test on a target that IS reachable.  CEGAR in enumeration mode for d_target with
S layers: every FOUND schedule is re-certified with my stim circuit + full SD6 DEM (no weight <= d-1 at R = 1..d,
both bases), stored, then blocked; every nogood ever produced is checked against every certified-good schedule
(including an external spec, e.g. E-036's q1863_p8) -- a nogood satisfied by a good schedule would be unsound."""
import argparse
import json

from pysat.solvers import Solver

from search.experiments.e036_audit.a3_cegar import Enc, find_cex
from search.experiments.e036_audit.core import min_weight_le, schedule_from_json, stim_circuit, stim_mechs


def holds(T, lits):
    return all(T[k1][a1] < T[k2][a2] for (k1, a1), (k2, a2) in lits)


def stim_ok(T, S, variant, d):
    for R in range(1, d + 1):
        for b in ("Z", "X"):
            w, _ = min_weight_le(stim_mechs(stim_circuit(T, S, variant, b, R)), d - 1)
            if w is not None:
                return False
    return True


def main(variant, S, d, n_found, ext):
    E = Enc(variant, S)
    s = Solver(name="g4", bootstrap_with=E.cl)
    ptr = len(E.cl)
    good = []
    if ext:
        Te, Se = schedule_from_json(ext, variant)
        assert Se == S and stim_ok(Te, S, variant, d)
        good.append(Te)
    nogoods = []
    bad = 0
    it = 0
    while len(good) < n_found + (1 if ext else 0):
        it += 1
        if not s.solve():
            print("exhausted")
            break
        T = E.decode(s.get_model())
        cex = find_cex(T, variant, d, range(1, d + 1))
        if not cex:
            assert stim_ok(T, S, variant, d), "Sym says good but stim disagrees"
            good.append(T)
            bad += sum(holds(T, ng) for ng in nogoods)
            block = [-E.x[((k, a), T[k][a])] for k in T for a in range(6)]
            E.cl.append(block)
        else:
            for R, b, w, lits in cex:
                E.cl.append([-E.lt(e1, e2) for e1, e2 in sorted(lits)])
                nogoods.append(lits)
                bad += sum(holds(G, lits) for G in good)
        for c_ in E.cl[ptr:]:
            s.add_clause(c_)
        ptr = len(E.cl)
        if it % 100 == 0:
            print(json.dumps({"it": it, "good": len(good), "nogoods": len(nogoods), "violations": bad}), flush=True)
    res = {"variant": variant, "S": S, "d": d, "iters": it, "good_certified": len(good), "nogoods": len(nogoods),
           "nogood_vs_good_violations": bad, "external": ext}
    print(json.dumps(res))
    with open("results/E-036-audit/a8_enum_control.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("S", type=int)
    ap.add_argument("--d", type=int, default=3)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--ext", default=None)
    a = ap.parse_args()
    main(a.variant, a.S, a.d, a.n, a.ext)
