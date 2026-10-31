"""E-042 audit, item 1: attack the bulk compression lemma on circuits that DO have lifts.

For circuit CNAME, basis, a list of extended logicals (H||L keys) and <= F readout flips (m = w + F faults):
  (a) bulk-liftable items: audited theory-B auditor solver (B_audit.lift.solve_bulk);
  (b) finite-liftable items at several R: my own CP-SAT over my own finite fault model (model.py, parsed from the stim
      circuit; equal to the DEM signature set, checked in premises.py);
  (c) constructive test of the proof: for each bulk-liftable item, a finite realisation at R_big with MAXIMAL index
      spread (CP-SAT objective) is compressed by the lemma's procedure (pair equal items per reader -> components ->
      shift each component by whole periods so that its minimum index is 1), and the result is checked at R* =
      s*m + 2 against the SD6 DEM of the R*-round circuit (every fault exists, finite items == shifted items, every
      (detectors, L) signature is a DEM term, XOR of detectors empty, L sum non-zero).
Lemma predicts: finite(R) subset bulk for all R (window lemma), and bulk subset finite(R*) (compression).

    uv run python -m search.experiments.e042_audit.lemma_test CNAME BASIS LIST F --Rs 1,2,3,13 [--limit N]
LIST: a pickle with "keys" (theory-B / E-0xx format) or "own:W" (own brute-force enumeration of weight W).
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
from collections import defaultdict

from ortools.sat.python import cp_model

from search.experiments.e042_audit.model import ROOT, SPECS, Model, dem_sigs, red

OUT = ROOT / "results/E-042-audit"


def groups(M):
    """image key -> list of (kind, ident, items, residual); flips separately."""
    g = defaultdict(list)
    flips = []
    z0 = M.image([])
    for f in M.finite_faults():
        kind, ident, its, res = f
        if kind == "f":
            flips.append(f)
            continue
        if not its and kind == "h" and ident[2] == 1:
            continue                       # k = 1: X_c deposited before the first CNOT = no fault
        k = M.image(res)
        if k == z0:
            raise AssertionError(f"zero-image non-flip fault {kind} {ident}")
        g[k].append(f)
    return g, flips


def solve(S, g, flips, F, spread=False):
    m = cp_model.CpModel()
    det = defaultdict(list)
    chosen = []
    allopts = []
    for key in S:
        bs = []
        for f in g.get(key, []):
            b = m.NewBoolVar("")
            bs.append(b)
            allopts.append((b, f))
            for it in f[2]:
                det[it].append(b)
        if not bs:
            return None
        m.AddExactlyOne(bs)
        chosen.append(bs)
    fl = []
    if F:
        for f in flips:
            b = m.NewBoolVar("")
            fl.append(b)
            allopts.append((b, f))
            for it in f[2]:
                det[it].append(b)
        m.Add(sum(fl) <= F)
    for it, lst in det.items():
        k = m.NewIntVar(0, len(lst), "")
        m.Add(sum(lst) == 2 * k)
    if spread:
        # hi = max over chosen options of their max index, lo = min over chosen of their min index (exact)
        BIG = 10 ** 4
        his, los = [], []
        for b, f in allopts:
            if f[2]:
                v = [x for _, x in f[2]]
                h = m.NewIntVar(0, BIG, "")
                m.Add(h == max(v)).OnlyEnforceIf(b)
                m.Add(h == 0).OnlyEnforceIf(b.Not())
                l_ = m.NewIntVar(0, BIG, "")
                m.Add(l_ == min(v)).OnlyEnforceIf(b)
                m.Add(l_ == BIG).OnlyEnforceIf(b.Not())
                his.append(h)
                los.append(l_)
        hi = m.NewIntVar(0, BIG, "hi")
        lo = m.NewIntVar(0, BIG, "lo")
        m.AddMaxEquality(hi, his)
        m.AddMinEquality(lo, los)
        m.Maximize(hi - lo)
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    if spread:
        s.parameters.max_time_in_seconds = 10
    st = s.Solve(m)
    if st == cp_model.INFEASIBLE:
        return None
    assert st in (cp_model.OPTIMAL, cp_model.FEASIBLE), s.StatusName(st)
    return [f for b, f in allopts if s.Value(b)]


def compress(sol, Mbig, Mr, D):
    """the lemma's procedure; returns (ok, info)."""
    P = Mbig.P
    # pair equal items per detector, union-find over faults
    par = list(range(len(sol)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    occ = defaultdict(list)
    for i, f in enumerate(sol):
        for it in f[2]:
            occ[it].append(i)
    for it, lst in occ.items():
        assert len(lst) % 2 == 0
        for a, b in zip(lst[::2], lst[1::2]):
            par[find(a)] = find(b)
    comp = defaultdict(list)
    for i in range(len(sol)):
        comp[find(i)].append(i)
    # spans
    span = lambda f: (max(x for _, x in f[2]) - min(x for _, x in f[2])) if f[2] else 0
    rstar_needed = sum(span(f) for f in sol) + 2
    fin = {(f[0], f[1]): f for f in Mr.finite_faults()}
    new = []
    for c, idx in comp.items():
        mn = min(x for i in idx for _, x in sol[i][2])
        sh = 1 - mn
        for i in idx:
            kind, ident, its, res = sol[i]
            if kind == "d":
                nid = (ident[0], ident[1] + sh * P)
            elif kind == "h":
                nid = (ident[0], ident[1] + sh, ident[2])
            else:
                nid = (ident[0], ident[1] + sh)
            shifted = frozenset((r, x + sh) for r, x in its)
            f2 = fin.get((kind, nid))
            if f2 is None:
                return False, {"missing": [kind, nid], "need": rstar_needed}
            if f2[2] != shifted:
                return False, {"index_mismatch": [kind, nid], "need": rstar_needed}
            if (f2[2], Mr.lobs(f2[3])) not in D:
                return False, {"not_in_dem": [kind, nid]}
            new.append(f2)
    acc = set()
    lo = set()
    for f in new:
        acc ^= set(f[2])
        lo ^= set(Mr.lobs(f[3]))
    allin = all(1 <= x <= Mr.R - 1 for f in new for _, x in f[2])
    return (not acc and bool(lo) and allin), {"components": len(comp), "sum_span": rstar_needed - 2,
                                               "orig_spread": max(x for f in sol for _, x in f[2]) - min(x for f in sol for _, x in f[2])}


def own_list(M, W):
    g, _ = groups(M)
    keys = sorted(g)
    import numpy as np
    nh = M.H.shape[0]
    vec = {k: np.frombuffer(k, dtype=np.uint8) for k in keys}
    out = []
    for S in itertools.combinations(keys, W):
        v = sum(vec[k].astype(np.int64) for k in S) % 2
        if not v[:nh].any() and v[nh:].any():
            out.append(list(S))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cname"); ap.add_argument("basis"); ap.add_argument("list"); ap.add_argument("F", type=int)
    ap.add_argument("--Rs", default="1,2,3")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--s", type=int, default=1, help="max per-fault span (from premises.py)")
    ap.add_argument("--only_bulk_lifted", action="store_true")
    a = ap.parse_args()
    from search.theory.B_audit.common import Bulk, get_code, load_spec_dict
    from search.theory.B_audit.lift import bulk_columns, check_bulk_solution, solve_bulk
    codename, sp = SPECS[a.cname]
    Rs = [int(x) for x in a.Rs.split(",")]
    M1 = Model(a.cname, 2, a.basis)
    if a.list.startswith("own:"):
        L = own_list(M1, int(a.list[4:]))
    else:
        L = pickle.load(open(ROOT / a.list, "rb"))["keys"]
    if a.limit:
        L = L[:a.limit]
    w = len(L[0])
    m_faults = w + a.F
    Rstar = a.s * m_faults + 2
    B = Bulk(load_spec_dict(sp), get_code(codename), a.basis)
    bcols, bzero = bulk_columns(B)
    bulk = set()
    for i, S in enumerate(L):
        r = solve_bulk(S, bcols, a.F)
        if r is not None:
            assert check_bulk_solution(r[0], r[1], a.F)
            bulk.add(i)
    res = {"circuit": a.cname, "basis": a.basis, "list": a.list, "n": len(L), "w": w, "F": a.F, "m": m_faults,
           "s": a.s, "R_star": Rstar, "bulk_lifted": len(bulk), "bulk_zero_key_hooks": len(bzero)}
    idxs = sorted(bulk) if a.only_bulk_lifted else range(len(L))
    fin = {}
    for R in sorted(set(Rs) | {Rstar}):
        M = Model(a.cname, R, a.basis)
        g, flips = groups(M)
        lifted = {i for i in idxs if solve(L[i], g, flips, a.F) is not None}
        fin[R] = lifted
        res[f"R{R}"] = {"lifted": len(lifted), "subset_of_bulk": lifted <= bulk,
                        "equal_bulk": lifted == (bulk & set(idxs))}
        print(json.dumps({"R": R, **res[f"R{R}"]}), flush=True)
    # constructive compression from maximally spread realisations at R_big
    Rbig = 2 * Rstar + 4
    Mb = Model(a.cname, Rbig, a.basis)
    gb, fb = groups(Mb)
    Mr = Model(a.cname, Rstar, a.basis)
    D = dem_sigs(Mr.circ)
    ok_c, fail_c, spreads, ncomp, excess = 0, [], [], [], []
    for i in sorted(bulk)[:120]:
        sol = solve(L[i], gb, fb, a.F, spread=True)
        if sol is None:
            fail_c.append((i, "no finite realisation at R_big"))
            continue
        ok, info = compress(sol, Mb, Mr, D)
        spreads.append(info.get("orig_spread"))
        excess.append(info.get("orig_spread", 0) - info.get("sum_span", 99))
        ncomp.append(info.get("components"))
        if ok:
            ok_c += 1
        else:
            fail_c.append((i, info))
    res["compress"] = {"R_big": Rbig, "tested": min(120, len(bulk)), "ok": ok_c, "fail": len(fail_c),
                       "fail_examples": fail_c[:5], "max_orig_spread": max(spreads, default=None),
                       "max_components": max(ncomp, default=None),
                       "max_spread_minus_sum_span": max(excess, default=None)}
    print(json.dumps(res), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "lemma_test.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
