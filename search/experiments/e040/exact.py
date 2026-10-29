"""E-040: exact finite-R lift test (E-032 lift10.test = audited frontier DP on the augmented stim DEM of the evaluator
template, generalised Lemma 2 with d_ext = w0: weight w0 list exactly, w0 list + one zero-image term, weight w0+1
list exactly) for a translation-invariant schedule given by its times; both bases; lists from this experiment
(complete DFS lists, list_*.pkl / list<w>_*.pkl).  0 lifts in a basis at R <=> no undetected logical of weight
<= w0 + 1 at R in that basis (needs d_ext = w0 exactly, i.e. no weight < w0 extended logical: asserted from
types_*.jsonl).

    PYTHONPATH=.:tests uv run python -m search.experiments.e040.exact --code gross --P 8 --tx .. --tz .. --R 1 2 3
"""
from __future__ import annotations

import argparse
import json
import pickle
import time

from evaluators.candidate import parse_schedule
from search.experiments.e040.bulk import Sector, spec_of
from search.experiments.e040.codes import MOD, OUT
from search.experiments.e040.lists import type_rep


def lists_for(code, kind, order, sym=False):
    C = MOD[code]
    t = type_rep(code, tuple(order))
    nm = C.name(t)
    base = pickle.load(open(OUT / f"list_{code}_{kind}_{nm}.pkl", "rb"))
    w0 = base["meta"]["dext"]
    nxt = pickle.load(open(OUT / f"list{w0 + 1}_{code}_{kind}_{nm}.pkl", "rb"))
    assert nxt["meta"]["complete"]
    E = C.ext_general(kind, [tuple(order)] * C.N2, group=[(0, 0)])
    if sym:
        # the schedule is translation invariant (every check the same times), so the circuit -- including the
        # temporal boundaries -- is invariant under the code's translations: x lifts iff its translate does.
        from search.experiments.e040.lists import orbit_reps
        a = orbit_reps(code, kind, t)[1]
        b = orbit_reps(code, kind, t, tag=f"list{w0 + 1}")[1]
        assert len(a) * C.N2 >= len(base["keys"]) and len(b) * C.N2 >= len(nxt["keys"])
        return w0, a, b, C.keyset(E)
    return w0, base["keys"], nxt["keys"], C.keyset(E)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--tx", required=True)
    ap.add_argument("--tz", required=True)
    ap.add_argument("--R", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--bases", default="ZX")
    ap.add_argument("--tag", default="exact")
    ap.add_argument("--sym", type=int, default=0, help="translation-orbit representatives only")
    a = ap.parse_args()
    C = MOD[a.code]
    if a.code == "gross":
        from search.experiments.e032 import lift10 as LM
    else:
        raise SystemExit("only gross wired")
    tx = [int(v) for v in a.tx.split(",")]
    tz = [int(v) for v in a.tz.split(",")]
    d = spec_of(a.code, tx, tz, a.P)
    spec = parse_schedule(d).canonical()
    for R in a.R:
        for b in a.bases:
            kind = "X" if b == "Z" else "Z"
            S = Sector(a.code, kind, tx, tz, a.P)
            w0, lA, lB, cs = lists_for(a.code, kind, S.order, sym=bool(a.sym))
            t0 = time.time()
            r = LM.test(spec, R, b, lA, lB, cs)
            r.update(sec=round(time.time() - t0, 1), w0=w0, sym=a.sym, tx=tx, tz=tz, P=a.P, order=C.name(S.order))
            print(json.dumps(r), flush=True)
            with open(OUT / f"{a.tag}.jsonl", "a") as f:
                f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
