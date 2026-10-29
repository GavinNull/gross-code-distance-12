"""Lift of listed extended logicals on the TIME CIRCLE of N rounds (bulk model with step indices mod N).

Projection lemma: a bulk undetected fault set maps to an undetected fault set on every time circle (indices mod N),
with the same columns, so 'no lift on the N-circle' implies 'no bulk lift', hence (window lemma) no lift at any R.
N = 1 is the extended code itself (every extended logical lifts).  Exact meet-in-the-middle over XOR signatures,
independent of the union-find solver in bulk.py.

  uv run python -m search.theory.B.circle --code gross --spec search/experiments/e032/u11_spec.json --basis Z \
      --N 2 --list results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl --flips 1
"""
from __future__ import annotations

import argparse
import json
import pickle
import time

from search.theory.B.bulk import ROOT, Sched, code_mats, load_spec
from search.theory.B.check_lists import enum_logicals


def circle_mechs(sch, cols, N):
    ids = {}

    def bit(z, t):
        k = (z, t % N)
        if k not in ids:
            ids[k] = len(ids)
        return 1 << ids[k]
    M = {}
    for key, reals in cols.items():
        sigs = set()
        for r in reals:
            for o in sch.options(r):
                for s in range(N):
                    v = 0
                    for z, offs in o.items():
                        for x in offs:
                            v ^= bit(z, s + x)
                    sigs.add(v)
        M[key] = sorted(sigs)
    zero = set()
    for z in range(len(sch.readers)):
        for t in range(N):
            zero.add(bit(z, t) ^ bit(z, t + 1))
    zero.discard(0)
    return M, zero


def lifts(S, M, zero=None, nflip=0):
    h = len(S) // 2

    def reach(part):
        st = {0}
        for k in part:
            st = {x ^ s for x in st for s in M[k]}
        return st
    A, B = reach(S[:h]), reach(S[h:])
    if A & B:
        return True
    if nflip and zero:
        return any((x ^ z) in B for x in A for z in zero)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--N", type=int, default=2)
    ap.add_argument("--list", required=True)
    ap.add_argument("--flips", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    sch = Sched(load_spec(a.spec), code_mats(a.code), a.basis)
    cols, zero_h = sch.ext()
    assert not zero_h, "zero-image hooks present: add them as zero mechanisms"
    if a.list.startswith("enum:"):
        L = enum_logicals(sch, cols, int(a.list[5:]))
    else:
        d = pickle.load(open(ROOT / a.list, "rb"))
        L = d["keys"]
        assert set(d["colset"]) == set(cols)
    t0 = time.time()
    M, zero = circle_mechs(sch, cols, a.N)
    lifted = [i for i, S in enumerate(L) if lifts(S, M, zero, a.flips)]
    res = {"spec": a.spec, "basis": a.basis, "N": a.N, "list": a.list, "n": len(L), "w": len(L[0]) if L else 0,
           "flips": a.flips, "circle_lifted": len(lifted), "first": lifted[:10], "sec": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    if a.out:
        with open(ROOT / a.out, "a") as f:
            f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
