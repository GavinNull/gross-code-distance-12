"""Item 3: window lemma tests.
 (i)  (Wb)/(Wt) and finite-vs-bulk step-index equality for every deposit (writer instances 0..R-1, data errors at all
      half-integers in (0, last+1)), R = 1..3, using the evaluator's unroll start times;
 (ii) random legal deterministic schedules in u11's order class (same extended code, so the u11 lists apply);
 (iii) finite-R lifts vs bulk lifts on the w10(+1 flip) list (and a w11 sample) to see whether finite ⊆ bulk holds,
      and whether it breaks when the window conditions fail.

  uv run python -m search.theory.B_audit.window_test conds gross search/experiments/e032/u11_spec.json
  uv run python -m search.theory.B_audit.window_test random 40 <seed>
"""
from __future__ import annotations

import json
import math
import pickle
import random
import sys
from collections import Counter

from search.theory.B_audit.common import ROOT, Bulk, get_code, load_spec_dict
from search.theory.B_audit.delta import analyse
from search.theory.B_audit.lift import bulk_columns, finite_columns, solve_bulk, solve_finite
from search.theory.B_audit.template_check import build

W10 = {"Z": "results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl",
       "X": "results/E-032-gross-short-period/w10_Z_all_A1A2A3B3B1B2.pkl"}
W11 = {"Z": "results/E-032-gross-short-period/w11_X_all_A1A2A3B3B1B2.pkl",
       "X": "results/E-032-gross-short-period/w11_Z_all_A1A2A3B3B1B2.pkl"}


def conds(code, spec_d, Rmax=3):
    from evaluators import candidate as cand
    spec = cand.parse_schedule(spec_d)
    lay = cand.layout_for(code)
    D = spec.period
    out = {}
    for R in range(1, Rmax + 1):
        U = cand.unroll(spec, code, R)
        last = U.num_layers - 1
        for basis in ("Z", "X"):
            W, Rd = ((spec.x_checks, lay.x_anc), (spec.z_checks, lay.z_anc)) if basis == "Z" else \
                ((spec.z_checks, lay.z_anc), (spec.x_checks, lay.x_anc))
            reads = {}
            for z, (c, a) in enumerate(zip(*Rd)):
                dm, offs = c.offsets(D)
                for o, col in offs:
                    reads.setdefault(col, []).append(U.start[a] + o)
            wb = all(r - D <= 0 for l in reads.values() for r in l)
            wt = all(r + D * R > last for l in reads.values() for r in l)
            fin = lambda r, u: sum(1 for t in range(R) if r + D * t < u)
            blk = lambda r, u: math.floor((u - r) / D) + 1
            bad = 0
            for c, a in zip(*W):
                dm, offs = c.offsets(D)
                for j in range(R):
                    for o, col in offs:
                        u = U.start[a] + o + D * j
                        bad += sum(fin(r, u) != blk(r, u) for r in reads[col])
            for col, l in reads.items():
                for u2 in range(1, 2 * (last + 1) + 1, 2):
                    bad += sum(fin(r, u2 / 2) != blk(r, u2 / 2) for r in l)
            out[f"R{R}{basis}"] = {"Wb": wb, "Wt": wt, "index_mismatches": bad}
    return out


def lift_compare(code, spec_d, basis, R, lst, flips, limit=0):
    d = pickle.load(open(ROOT / lst, "rb"))
    L = d["keys"][:limit] if limit else d["keys"]
    B = Bulk(spec_d, code, basis)
    bc, _ = bulk_columns(B)
    fc, _, nz = finite_columns(spec_d, code, basis, R)
    bl = {i for i, S in enumerate(L) if solve_bulk(S, bc, flips) is not None}
    fl = {i for i, S in enumerate(L) if solve_finite(S, fc, nz, R, flips) is not None}
    return {"n": len(L), "bulk": len(bl), "finite": len(fl), "finite_not_bulk": len(fl - bl),
            "bulk_not_finite": len(bl - fl), "ex_finite_not_bulk": sorted(fl - bl)[:5]}


def random_u11_class(rng, code_name="gross"):
    """random period, X/Z prep/meas and increasing CNOT times keeping u11's per-check term orders."""
    xo = ["A2", "A1", "A3", "B3", "B2", "B1"]
    zo = ["B1", "B2", "B3", "A3", "A1", "A2"]
    code = get_code(code_name)
    from evaluators import candidate as cand
    for _ in range(10000):
        P = rng.randint(8, 14)
        def one(order):
            span = rng.randint(7, P - 1 + 1)          # prep..meas offsets 0..span, span < P
            span = min(span, P - 1)
            offs = sorted(rng.sample(range(1, span), 6))
            p = rng.randrange(P)
            return (p, (p + span) % P, {k: (p + o) % P for k, o in zip(order, offs)})
        T = dict(P=P, X=one(xo), Z=one(zo))
        Pp, xs, zs = build(code_name, T)
        spec = {"format": "qec-schedule/v1", "period": Pp,
                "x_checks": [{"prep": p, "meas": m, "cnots": sorted(map(list, c))} for p, m, c in xs],
                "z_checks": [{"prep": p, "meas": m, "cnots": sorted(map(list, c))} for p, m, c in zs]}
        if cand.validate_schedule(cand.parse_schedule(spec), code):
            continue
        a = analyse(Bulk(spec, code, "Z"))
        if a["pairing_violations"]:
            continue                                    # non-deterministic
        return T, spec
    raise RuntimeError


def main():
    mode = sys.argv[1]
    if mode == "conds":
        code = get_code(sys.argv[2])
        print(json.dumps({"spec": sys.argv[3], **conds(code, load_spec_dict(sys.argv[3]))}), flush=True)
    elif mode == "compare":
        name, sp, basis, R, which, flips = sys.argv[2:8]
        limit = int(sys.argv[8]) if len(sys.argv) > 8 else 0
        lst = (W10 if which == "w10" else W11)[basis]
        code = get_code(name)
        print(json.dumps({"spec": sp, "basis": basis, "R": int(R), "list": which, "flips": int(flips),
                          **lift_compare(code, load_spec_dict(sp), basis, int(R), lst, int(flips), limit)}), flush=True)
    elif mode == "random":
        n, seed = int(sys.argv[2]), int(sys.argv[3])
        rng = random.Random(seed)
        code = get_code("gross")
        tally = Counter()
        for i in range(n):
            T, spec = random_u11_class(rng)
            c = conds(code, spec, Rmax=2)
            rec = {"i": i, "T": T, "conds": c}
            # finite vs bulk on the w10 list (+1 flip), R = 1, Z basis
            for basis in ("Z", "X"):
                ok = c[f"R1{basis}"]
                cmpres = lift_compare(code, spec, basis, 1, W10[basis], 1)
                rec[f"cmp_R1_{basis}"] = cmpres
                key = ("window" if ok["Wb"] and ok["Wt"] else "nowindow",
                       "mismatch0" if ok["index_mismatches"] == 0 else "mismatch>0",
                       "finite<=bulk" if cmpres["finite_not_bulk"] == 0 else "FINITE_NOT_BULK")
                tally[" ".join(key)] += 1
            print(json.dumps(rec), flush=True)
        print(json.dumps({"tally": dict(tally)}), flush=True)




def hunt(n, seed):
    """random u11-order-class schedules: keep those whose bulk w10 lifting (no flip, Z and X) is partial, report
    window status and finite R=1,2 lifts vs bulk lifts (looking for finite-not-bulk when the window fails)."""
    rng = random.Random(seed)
    code = get_code("gross")
    for i in range(n):
        T, spec = random_u11_class(rng)
        rec = {"i": i, "T": T}
        c = conds(code, spec, Rmax=1)
        for basis in ("Z", "X"):
            d = pickle.load(open(ROOT / W10[basis], "rb"))
            B = Bulk(spec, code, basis)
            bc, _ = bulk_columns(B)
            bl = {k for k, S in enumerate(d["keys"]) if solve_bulk(S, bc, 1) is not None}
            rec[basis] = {"bulk_w10f1": len(bl), "window": c[f"R1{basis}"]}
            if len(bl) < 144:
                for R in (1, 2):
                    fc, _, nz = finite_columns(spec, code, basis, R)
                    fl = {k for k, S in enumerate(d["keys"]) if solve_finite(S, fc, nz, R, 1) is not None}
                    rec[basis][f"R{R}"] = {"finite": len(fl), "finite_not_bulk": len(fl - bl)}
        print(json.dumps(rec), flush=True)


def near_u11(rng, code):
    from evaluators import candidate as cand
    xo = ["A2", "A1", "A3", "B3", "B2", "B1"]
    zo = ["B1", "B2", "B3", "A3", "A1", "A2"]
    X0, Z0 = [1, 2, 3, 4, 5, 9], [1, 5, 6, 7, 8, 9]
    for _ in range(100000):
        P = 11 + rng.choice([0, 0, 1, 2])
        def pert(o0):
            o = [x + rng.choice([-1, 0, 0, 1, 2 * (P - 11)]) for x in o0]
            if any(b <= a for a, b in zip(o, o[1:])) or o[0] < 1:
                return None
            mo = o[-1] + rng.choice([1, 1, 2])
            return (o, mo) if mo < P else None
        x, z = pert(X0), pert(Z0)
        if not x or not z:
            continue
        phi = (10 + rng.choice([-1, 0, 0, 1])) % P
        T = dict(P=P, X=(0, x[1] % P, {k: o % P for k, o in zip(xo, x[0])}),
                 Z=(phi, (phi + z[1]) % P, {k: (phi + o) % P for k, o in zip(zo, z[0])}))
        Pp, xs, zs = build("gross", T)
        spec = {"format": "qec-schedule/v1", "period": Pp,
                "x_checks": [{"prep": p_, "meas": m_, "cnots": sorted(map(list, c_))} for p_, m_, c_ in xs],
                "z_checks": [{"prep": p_, "meas": m_, "cnots": sorted(map(list, c_))} for p_, m_, c_ in zs]}
        if cand.validate_schedule(cand.parse_schedule(spec), code):
            continue
        if analyse(Bulk(spec, code, "Z"))["pairing_violations"]:
            continue
        return T, spec
    raise RuntimeError


def hunt_near(n, seed):
    rng = random.Random(seed)
    code = get_code("gross")
    seen = set()
    for i in range(n):
        T, spec = near_u11(rng, code)
        key = json.dumps(T, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        rec = {"i": i, "T": T}
        c = conds(code, spec, Rmax=1)
        for basis in ("Z", "X"):
            d = pickle.load(open(ROOT / W10[basis], "rb"))
            B = Bulk(spec, code, basis)
            bc, _ = bulk_columns(B)
            bl = {k for k, S in enumerate(d["keys"]) if solve_bulk(S, bc, 1) is not None}
            w = c[f"R1{basis}"]
            rec[basis] = {"bulk_w10f1": len(bl), "window": w}
            if len(bl) < 144 and not (w["Wb"] and w["Wt"]):
                for R in (1, 2):
                    fc, _, nz = finite_columns(spec, code, basis, R)
                    fl = {k for k, S in enumerate(d["keys"]) if solve_finite(S, fc, nz, R, 1) is not None}
                    rec[basis][f"R{R}"] = {"finite": len(fl), "finite_not_bulk": len(fl - bl),
                                           "ex": sorted(fl - bl)[:3]}
        print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "hunt_near":
        hunt_near(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1] == "hunt":
        hunt(int(sys.argv[2]), int(sys.argv[3]))
    else:
        main()
