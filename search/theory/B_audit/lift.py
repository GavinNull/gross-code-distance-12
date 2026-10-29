"""Items 4/5: independent exact lift solver (OR-tools CP-SAT, single thread).

Columns of the extended code are grouped by image key (H-syndrome || L-image of the residual data error); a column's
realisations are data errors on q (P cut patterns) and hooks (writer c, k = 2..6).  Zero-key hooks are reported.

bulk mode: every realisation has an integer shift x (round of the fault); item value = base + x.  Undetected <=> for
every reader the multiset of item values pairs up (perfect matching of equal values), plus up to F flips, each adding
{t, t+1} at one reader (each matched to a real item).  Shift domain [-K, K] (K generous, checked a posteriori).
finite mode (R): concrete faults of the evaluator's unrolled R-round circuit (unroll start times; writer instances
0..R-1, data errors at half-integers in (0, last+1)); undetected <=> XOR of item sets (detectors) is empty.

  uv run python -m search.theory.B_audit.lift gross search/experiments/e032/u11_spec.json Z \
        results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl --flips 1
"""
from __future__ import annotations

import argparse
import json
import pickle
import time
from collections import defaultdict

from ortools.sat.python import cp_model

from search.theory.B_audit.common import ROOT, Bulk, get_code, load_spec_dict, reduce_items


# ----------------------------------------------------------------------------------- realisations
def bulk_columns(B: Bulk):
    cols = defaultdict(list)       # key -> list of item-tuples (reduced, base values, shift 0)
    zero = []
    z0 = B.key([])
    for q in range(B.n):
        for pat in B.data_patterns(q):
            cols[B.key([q])].append(("d", q, pat))
    for c in range(len(B.wr)):
        for k in range(2, 7):
            items, suf = B.hook_items(c, k)
            kk = B.key(suf)
            if kk == z0:
                zero.append((c, k))
                continue
            cols[kk].append(("h", (c, k), reduce_items(items)))
    return dict(cols), zero


def finite_columns(spec_d, code, basis, R):
    from evaluators import candidate as cand
    spec = cand.parse_schedule(spec_d)
    U = cand.unroll(spec, code, R)
    lay = cand.layout_for(code)
    D = spec.period
    last = U.num_layers - 1
    B = Bulk(spec_d, code, basis)
    W, Rd = ((spec.x_checks, lay.x_anc), (spec.z_checks, lay.z_anc)) if basis == "Z" else \
        ((spec.z_checks, lay.z_anc), (spec.x_checks, lay.x_anc))
    reads = defaultdict(list)
    for z, (c, a) in enumerate(zip(*Rd)):
        dm, offs = c.offsets(D)
        for o, col in offs:
            reads[col].append((z, [U.start[a] + o + D * t for t in range(R)]))

    def items(q, u):
        return [(z, sum(1 for x in ts if x < u)) for z, ts in reads[q]]
    cols = defaultdict(list)
    for q in range(B.n):
        seen = set()
        for u2 in range(1, 2 * (last + 1) + 1, 2):
            it = reduce_items(items(q, u2 / 2))
            if it not in seen:
                seen.add(it)
                cols[B.key([q])].append(("d", (q, u2 / 2), it))
    for c, (ch, a) in enumerate(zip(*W)):
        dm, offs = ch.offsets(D)
        for j in range(R):
            for k in range(2, 7):
                suf = offs[k - 1:]
                its = []
                for o, col in suf:
                    its += items(col, U.start[a] + o + D * j)
                kk = B.key([col for _, col in suf])
                cols[kk].append(("h", (c, k, j), reduce_items(its)))
    nz = len(Rd[0])
    return dict(cols), B, nz


# ----------------------------------------------------------------------------------- solvers
def solve_bulk(S, cols, flips=0, K=60, want_solution=False):
    m = cp_model.CpModel()
    readers = defaultdict(list)     # z -> [(option boolean, value expr, item id, column index)]
    xs, opts = [], []
    for ci, key in enumerate(S):
        x = m.NewIntVar(-K, K, f"x{ci}")
        xs.append(x)
        bs = []
        for oi, (_, _, items) in enumerate(cols[key]):
            b = m.NewBoolVar(f"o{ci}_{oi}")
            bs.append(b)
            for (z, base) in items:
                readers[z].append((b, x, base, ci))
        m.AddExactlyOne(bs)
        opts.append(bs)
    if xs:
        m.Add(xs[0] == 0)
    fl = []
    for z, its in readers.items():
        part = defaultdict(list)
        for a in range(len(its)):
            for b in range(a + 1, len(its)):
                ba, xa, oa, ca = its[a]
                bb, xb, ob, cb = its[b]
                if ca == cb:
                    continue          # same column: same shift -> equal only if same base (already reduced)
                v = m.NewBoolVar("")
                m.AddImplication(v, ba)
                m.AddImplication(v, bb)
                m.Add(xa + oa == xb + ob).OnlyEnforceIf(v)
                part[a].append(v)
                part[b].append(v)
        if flips:
            f = m.NewBoolVar(f"f{z}")
            fl.append(f)
            t = m.NewIntVar(-K - 10, K + 10, "")
            fa, fb = [], []
            for a, (ba, xa, oa, ca) in enumerate(its):
                for which, lst in ((0, fa), (1, fb)):
                    v = m.NewBoolVar("")
                    m.AddImplication(v, ba)
                    m.AddImplication(v, f)
                    m.Add(xa + oa == t + which).OnlyEnforceIf(v)
                    part[a].append(v)
                    lst.append(v)
            m.Add(sum(fa) == f)
            m.Add(sum(fb) == f)
        for a, (ba, *_r) in enumerate(its):
            m.Add(sum(part[a]) == ba)
    if flips:
        m.Add(sum(fl) <= flips)
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    st = s.Solve(m)
    assert st in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE), s.StatusName(st)
    if st == cp_model.INFEASIBLE:
        return None
    sol = []
    for ci, key in enumerate(S):
        oi = [i for i, b in enumerate(opts[ci]) if s.Value(b)][0]
        sol.append((cols[key][oi], s.Value(xs[ci])))
    nfl = sum(s.Value(f) for f in fl)
    return sol, nfl


def check_bulk_solution(sol, flips_used, flips_allowed):
    """independent verification of a bulk solution: count values per reader; odd counts must be explained by flips."""
    cnt = defaultdict(int)
    for (kind, ident, items), x in sol:
        for z, base in items:
            cnt[(z, base + x)] ^= 1
    odd = defaultdict(list)
    for (z, v), p in cnt.items():
        if p:
            odd[z].append(v)
    nf = 0
    for z, vs in odd.items():
        vs.sort()
        if len(vs) != 2 or vs[1] - vs[0] != 1:
            return False
        nf += 1
    return nf <= flips_allowed


def solve_finite(S, cols, nz, R, flips=0):
    m = cp_model.CpModel()
    det = defaultdict(list)
    opts = []
    for ci, key in enumerate(S):
        bs = []
        for oi, (_, _, items) in enumerate(cols[key]):
            b = m.NewBoolVar("")
            bs.append(b)
            for it in items:
                det[it].append(b)
        m.AddExactlyOne(bs)
        opts.append(bs)
    fl = []
    if flips:
        for z in range(nz):
            for t in range(R):
                f = m.NewBoolVar("")
                fl.append(f)
                det[(z, t)].append(f)
                det[(z, t + 1)].append(f)
        m.Add(sum(fl) <= flips)
    for it, lst in det.items():
        k = m.NewIntVar(0, len(lst), "")
        m.Add(sum(lst) == 2 * k)
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    st = s.Solve(m)
    assert st in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE)
    if st == cp_model.INFEASIBLE:
        return None
    return [cols[key][[i for i, b in enumerate(opts[ci]) if s.Value(b)][0]] for ci, key in enumerate(S)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    ap.add_argument("spec")
    ap.add_argument("basis")
    ap.add_argument("list")
    ap.add_argument("--flips", type=int, default=0)
    ap.add_argument("--R", type=int, default=0, help="0 = bulk; else finite R-round evaluator circuit")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    code = get_code(a.code)
    spec = load_spec_dict(a.spec)
    if a.R:
        cols, B, nz = finite_columns(spec, code, a.basis, a.R)
        zero = []
    else:
        B = Bulk(spec, code, a.basis)
        cols, zero = bulk_columns(B)
    d = pickle.load(open(ROOT / a.list, "rb"))
    L = d["keys"]
    colset_ok = set(d["colset"]) == set(cols)
    assert colset_ok, (len(d["colset"]), len(cols))
    if a.limit:
        L = L[:a.limit]
    t0 = time.time()
    lifted, maxshift = [], 0
    for i, S in enumerate(L):
        assert len(set(S)) == len(S)
        if a.R:
            r = solve_finite(S, cols, nz, a.R, a.flips)
        else:
            r = solve_bulk(S, cols, a.flips)
            if r is not None:
                sol, nfl = r
                assert check_bulk_solution(sol, nfl, a.flips), "solution failed independent check"
                maxshift = max(maxshift, max(abs(x) for _, x in sol))
        if r is not None:
            lifted.append(i)
    res = {"code": a.code, "spec": a.spec, "basis": a.basis, "list": a.list, "R": a.R or "bulk", "n": len(L),
           "weight": len(L[0]) if L else None, "flips<=": a.flips, "ncols": len(cols), "zero_key_hooks": len(zero),
           "colset_equal": colset_ok, "lifted": len(lifted), "first_lifted": lifted[:10], "max_abs_shift": maxshift,
           "sec": round(time.time() - t0, 1)}
    print(json.dumps(res), flush=True)
    if a.out:
        with open(ROOT / a.out, "a") as f:
            f.write(json.dumps(res) + "\n")
        with open(ROOT / (a.out + ".lifted.json"), "a") as f:
            f.write(json.dumps({"spec": a.spec, "basis": a.basis, "list": a.list, "R": a.R, "flips": a.flips,
                                "lifted": lifted}) + "\n")


if __name__ == "__main__":
    main()
