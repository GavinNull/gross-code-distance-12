"""Exact finite-R lift of listed extended logicals, directly on the evaluator's finite circuit (step model with the
finite step index, validated against the stim DEM by validate.py).  Frontier DP over columns: the set of reachable
partial detector syndromes.  Used to compare finite-R lifts with bulk lifts.

  uv run python -m search.theory.B.finite --code gross --spec search/experiments/e032/ctl_p10_spec.json --basis Z \
      --R 1 --list results/E-032-gross-short-period/w11_X_all_A1A2A3B3B1B2.pkl
"""
from __future__ import annotations

import argparse
import json
import pickle
from collections import defaultdict

import numpy as np

from search.theory.B.bulk import ROOT, Sched, code_mats, load_spec
from search.theory.B.check_lists import colopts_for
from search.theory.B.window import get_code


def finite_mechs(code, spec, basis, R, H, L):
    """key (H,L image bytes) -> set of detector signatures (frozensets of (z, s)); plus zero-image signatures."""
    from evaluators import candidate as cand
    U = cand.unroll(spec, code, R)
    lay = cand.layout_for(code)
    D = spec.period
    last = U.num_layers - 1
    W, Rd = ((spec.x_checks, lay.x_anc), (spec.z_checks, lay.z_anc)) if basis == "Z" else \
        ((spec.z_checks, lay.z_anc), (spec.x_checks, lay.x_anc))
    reads = {}
    for z, (c, a) in enumerate(zip(*Rd)):
        dm, offs = c.offsets(D)
        for o, col in offs:
            reads.setdefault(col, []).append((z, U.start[a] + o))

    def sf(r, u):
        for t in range(R):
            if r + D * t > u:
                return t
        return R

    def key(qs):
        qs = list(qs)
        return (H[:, qs].sum(1) % 2).astype(np.uint8).tobytes() + (L[:, qs].sum(1) % 2).astype(np.uint8).tobytes()

    def sig(items):
        s = set()
        for it in items:
            s ^= {it}
        return frozenset(s)
    M = defaultdict(set)
    for q, lst in reads.items():
        for u2 in range(1, 2 * (last + 1), 2):
            M[key([q])].add(sig([(z, sf(r, u2 / 2)) for z, r in lst]))
    for c, a in zip(*W):
        dm, offs = c.offsets(D)
        for j in range(R):
            for k in range(2, 7):
                suf = offs[k - 1:]
                items = []
                for o, col in suf:
                    items += [(z, sf(r, U.start[a] + o + D * j)) for z, r in reads[col]]
                M[key([col for _, col in suf])].add(sig(items))
    zero = set()
    for z in range(len(Rd[0])):
        for t in range(R):
            zero.add(frozenset({(z, t), (z, t + 1)}))
    return M, zero


def to_bits(M, zero):
    ids = {}
    def b(fs):
        v = 0
        for d in fs:
            if d not in ids:
                ids[d] = len(ids)
            v |= 1 << ids[d]
        return v
    return {k: sorted({b(s) for s in v}) for k, v in M.items()}, {b(s) for s in zero}


def lifts(S, M, zero=None):
    """M: key -> list of int signatures.  Meet in the middle: first half states vs second half states."""
    h = len(S) // 2
    def reach(part):
        st = {0}
        for k in part:
            st = {x ^ s for x in st for s in M[k]}
        return st
    A, B = reach(S[:h]), reach(S[h:])
    if A & B:
        return True
    if zero:
        return any((x ^ z) in B for x in A for z in zero)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--basis", default="Z")
    ap.add_argument("--R", type=int, default=1)
    ap.add_argument("--list", required=True)
    ap.add_argument("--flips", type=int, default=0)
    ap.add_argument("--compare-bulk", action="store_true")
    a = ap.parse_args()
    from evaluators import candidate as cand
    from search.theory.B.bulk import bulk_lift
    code = get_code(a.code)
    sd = load_spec(a.spec)
    spec = cand.parse_schedule(sd)
    sch = Sched(sd, code_mats(a.code), a.basis)
    M, zero = finite_mechs(code, spec, a.basis, a.R, sch.H, sch.L)
    M, zero = to_bits(M, zero)
    Lst = pickle.load(open(ROOT / a.list, "rb"))["keys"]
    fin = [i for i, S in enumerate(Lst) if lifts(S, M, zero if a.flips else None)]
    res = {"spec": a.spec, "basis": a.basis, "R": a.R, "n": len(Lst), "finite_lifted": len(fin)}
    if a.compare_bulk:
        cols, _ = sch.ext()
        blk = [i for i in fin if bulk_lift(colopts_for(Lst[i], cols, sch), flips=a.flips) is not None]
        res["finite_but_not_bulk"] = [i for i in fin if i not in set(blk)][:20]
        res["n_finite_not_bulk"] = len(fin) - len(blk)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
