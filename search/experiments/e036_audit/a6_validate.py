"""Audit claim 4: empirical soundness test of MY nogood extraction against a different fault model.
For random legal schedules: take Sym witnesses (weight <= d-1) and their literal sets; then find OTHER legal
schedules satisfying all literals (SAT with the literals + random layer assumptions) and check with my stim
circuit + full SD6 DEM (both detector types) that an undetectable logical of weight <= w exists at the same R.
Any failure = unsound nogood."""
import argparse
import json
import random

from pysat.solvers import Solver

from search.experiments.e036_audit.a3_cegar import Enc, find_cex
from search.experiments.e036_audit.core import legal, min_weight_le, stim_circuit, stim_mechs


def rand_model(E, s, rng, base_assume, tries=30):
    for _ in range(tries):
        extra = []
        for e in rng.sample(E.ev, 8):
            extra.append(E.x[(e, rng.randint(1, E.S))])
        if s.solve(assumptions=base_assume + extra):
            return E.decode(s.get_model())
    if s.solve(assumptions=base_assume):
        return E.decode(s.get_model())
    return None


def main(variant, S, d, n_sched, per, seed):
    rng = random.Random(seed)
    E = Enc(variant, S)
    # create all lt vars that might be needed lazily -> push clauses each time
    s = Solver(name="m22", bootstrap_with=E.cl)
    ptr = len(E.cl)
    tested = fails = 0
    for it in range(n_sched):
        T = rand_model(E, s, rng, [])
        cex = find_cex(T, variant, d, range(1, d + 1), per_case=per)
        for R, b, w, lits in cex:
            assume = [E.lt(e1, e2) for e1, e2 in lits]
            for c_ in E.cl[ptr:]:
                s.add_clause(c_)
            ptr = len(E.cl)
            T2 = rand_model(E, s, rng, assume)
            assert T2 is not None
            assert legal(T2, variant, S)[0]
            nsame = getattr(main, "nsame", 0) + (T2 == T); main.nsame = nsame
            w2, _ = min_weight_le(stim_mechs(stim_circuit(T2, S, variant, b, R)), w)
            ok = w2 is not None and w2 <= w
            tested += 1
            fails += (not ok)
            if not ok:
                print("UNSOUND?", json.dumps({"R": R, "b": b, "w": w, "lits": [list(map(str, l)) for l in lits]}))
        print(json.dumps({"sched": it, "tested": tested, "fails": fails, "same_as_source": getattr(main, "nsame", 0)}), flush=True)
    res = {"variant": variant, "S": S, "d": d, "tested": tested, "fails": fails, "seed": seed, "same_as_source": getattr(main, "nsame", 0)}
    print(json.dumps(res))
    with open("results/E-036-audit/a6_validate.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("S", type=int)
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--per", type=int, default=6)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    main(a.variant, a.S, a.d, a.n, a.per, a.seed)
