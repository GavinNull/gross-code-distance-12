"""E-024a soundness check of the bulk frame model as used for UNSAT claims (e021.nwfull realisations, wrap weights):
for random legal deterministic circuits of a family at period P, every logical the MODEL says lifts must really lift
in the exact augmented DEM (lift21.build_groups + e018 DP) at a moderately large R (both bases).  A model-lifting
logical that does not lift exactly at R would mean the model is unsound (or needs more rounds than R).

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.modelcheck P "sub" ncircuits R
"""
import json
import random
import sys
import time

import search.experiments.e021.nwfull as NF
from evaluators.candidate import parse_schedule
from search.experiments.e018 import common as C18
from search.experiments.e018.lift import solve
from search.experiments.e021.extgen import ext_general
from search.experiments.e021.lift21 import KIND_OF_BASIS, build_groups, label_orders, w11_from_fig12
from search.experiments.e021.nwsat import Family, parse_sub
from search.experiments.e024a.cegar import TimeSAT, bf_P, spec_of


def main():
    P = int(sys.argv[1]); sub = sys.argv[2]; nc = int(sys.argv[3]); R = int(sys.argv[4])
    F = Family(parse_sub(sub) if sub else [(0, 0)])
    recs, _ = NF.prepare_full(F, "XZ")
    M = TimeSAT(F, P)
    rng = random.Random(11)
    tot_model = tot_ok = 0
    bad = []
    for k in range(nc):
        M.S.set_phases([rng.choice([1, -1]) * v for v in range(1, M.pool.top + 1)])
        t = M.solve()
        NF.bf_general = lambda cons, rank: bf_P(cons, t, P)  # noqa: E731
        lif = NF.evaluate_full(F, recs, None)
        spec = parse_schedule(spec_of(F, t, P)).canonical()
        lo = label_orders(spec)
        for kind in "XZ":
            basis = {"X": "Z", "Z": "X"}[kind]
            E = ext_general(kind, lo[kind])
            new = w11_from_fig12(kind, E)
            pos = {S: i for i, S in enumerate(C18.load_logicals(kind))}
            groups, _ = build_groups(spec, R, basis, E)
            for r, cons, pi in lif:
                if r["kind"] != kind:
                    continue
                tot_model += 1
                S = new[pos[tuple(sorted(r["S"]))]] if tuple(sorted(r["S"])) in pos else new[pos[r["S"]]]
                ch, _ = solve(S, groups)
                if ch is not None:
                    tot_ok += 1
                else:
                    bad.append({"circuit": k, "kind": kind, "S": list(r["S"])})
        print(f"circuit {k}: model-lifting {len(lif)}; cumulative exact-confirmed {tot_ok}/{tot_model}", flush=True)
    print(json.dumps({"P": P, "sub": sub, "R": R, "model_lifting": tot_model, "exact_confirmed": tot_ok,
                      "unconfirmed": bad[:20]}))


if __name__ == "__main__":
    main()
