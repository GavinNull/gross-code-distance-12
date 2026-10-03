"""Three-colour tiled left-right circuits (cf. arXiv:2603.05481 v2 App. H, Prop. 6 and Fig. 11/12), depth 8.

Circuit family (LRC form, Sec. III.A, written in the 8-slot convention of schedules.py):
  X check: prep 0, its three A-term CNOTs (L data) in slots 1..3, its three B-term CNOTs (R data) in 4..6, meas 7.
  Z check: prep 4, its three B-term CNOTs (L data) in slots 5..7, its three A-term CNOTs (R data) in 0..2 of the next
           cycle, meas 3.
  Every data qubit has its X CNOTs and Z CNOTs in disjoint slot sets, so the circuit is non-interleaved by
  construction (Z round r strictly before X round r on every shared qubit, X round r before Z round r+1) as long as
  the CNOT slots inside each block form a proper edge colouring (no data qubit used twice in a slot).  This makes
  the X side and the Z side independent: d_ext = min(d^X(X orders), d^Z(Z orders)).
Colouring of checks: a group homomorphism h: G -> Z_3 (h(x^i y^j) = alpha*i + beta*j mod 3); checks of colour c
all use the same block orders (pi_c on the A block, sigma_c on the B block), as in Prop. 6.

Pipeline for one kind (X or Z) and one target T:
  1. block orders (36 = S3 x S3) whose single-check bound (stage `single`) is >= T;
  2. for each colour class c and order o: residuals of class-c checks only; MILP feasibility with cap T-1
     (infeasible => class tiling keeps d >= T; a witness <= T-1 kills (c, o) for every combination: Thm. 1 Eq. (10));
  3. all triples (o_0, o_1, o_2) of surviving orders that are proper colourings -> full decision with cap T-1.

  PYTHONPATH=. uv run python -m search.noninterleaved.colour_search --code "[[90,8,10]]" --kind X --target 9
"""
from __future__ import annotations

import argparse
import itertools
import json
import time

from search.noninterleaved.ext import residual_supports
from search.noninterleaved.run import HL, OUT, dump, get_code, neighbours, run_jobs, tag
from search.noninterleaved.uniform_search import classes, single_values

S3 = list(itertools.permutations(range(3)))


def homomorphisms(code):
    """Distinct 3-colourings of checks from nontrivial homomorphisms G = Z_l x Z_m -> Z_3 (up to c -> 2c)."""
    l, m = code_lm(code)
    out, seen = [], set()
    for a in range(3):
        for b in range(3):
            if (a, b) == (0, 0) or (l * a) % 3 or (m * b) % 3:
                continue
            col = tuple((a * (g // m) + b * (g % m)) % 3 for g in range(l * m))
            key = min(col, tuple((2 * c) % 3 for c in col))
            if key in seen:
                continue
            seen.add(key)
            out.append({"alpha": a, "beta": b, "colour": col})
    return out


def code_lm(code):
    g = code.group
    if getattr(g, "abelian_lm", None):
        return g.abelian_lm
    raise ValueError("need an abelian Z_l x Z_m group")


def order_terms(kind, pi, sigma):
    """Term order of one check: X = A block (terms 0..2 permuted by pi) then B block; Z = B block then A block."""
    A = [pi[k] for k in range(3)]
    B = [3 + sigma[k] for k in range(3)]
    return A + B if kind == "X" else B + A


def proper(code, kind, colour, orders_by_class) -> bool:
    """No data qubit receives two CNOTs of this kind in the same slot."""
    used = {}
    for i in range(code.n2):
        o = orders_by_class[colour[i]]
        for k, t in enumerate(o):
            d = neighbours(code, kind, i, t)
            key = (d, k)                       # slot index k within the 6 consecutive slots of this kind
            if key in used:
                return False
            used[key] = i
    return True


def run(name, kind, target, workers, tl, homs=None):
    code, css = get_code(name)
    H, L = HL(css, kind)
    sv = single_values(name)[kind]
    rep = classes(code, css, kind)
    blocks = [(pi, sg) for pi in S3 for sg in S3]
    ok_blocks = [b for b in blocks if (sv[rep[tuple(order_terms(kind, *b))]][1] or 99) >= target]
    out = {"code": name, "kind": kind, "target": target, "time_limit": tl,
           "num_block_orders": len(blocks), "block_orders_passing_single": len(ok_blocks), "homs": []}
    t0 = time.time()
    HM = homomorphisms(code)
    if homs is not None:
        HM = [HM[i] for i in homs]
    for hm in HM:
        col = hm["colour"]
        rec = {"alpha": hm["alpha"], "beta": hm["beta"]}
        # step 2: one colour class tiled
        jobs = []
        for c in range(3):
            for b in ok_blocks:
                o = order_terms(kind, *b)
                sups = [s for i in range(code.n2) if col[i] == c
                        for s in residual_supports([neighbours(code, kind, i, t) for t in o])]
                jobs.append({"H": H, "L": L, "sups": sups, "cap": target - 1, "tl": tl, "solver": "feas",
                             "key": [c, list(b[0]), list(b[1])]})
        res = run_jobs(jobs, workers)
        surv = {c: [] for c in range(3)}
        for r in res:
            c, pi, sg = r["key"]
            if r["upper"] is None:          # infeasible (proved >= target) or undecided
                surv[c].append((tuple(pi), tuple(sg)))
        rec["class_tests"] = [{k: r[k] for k in ("key", "status", "upper", "seconds")} for r in res]
        rec["survivors_per_class"] = {c: len(v) for c, v in surv.items()}
        # step 3: proper triples
        triples = []
        for b0 in surv[0]:
            for b1 in surv[1]:
                for b2 in surv[2]:
                    obc = {c: order_terms(kind, *b) for c, b in enumerate((b0, b1, b2))}
                    if proper(code, kind, col, obc):
                        triples.append((b0, b1, b2))
        rec["proper_triples"] = len(triples)
        jobs = []
        for tr in triples:
            obc = {c: order_terms(kind, *b) for c, b in enumerate(tr)}
            sups = [s for i in range(code.n2) for s in residual_supports([neighbours(code, kind, i, t)
                                                                          for t in obc[col[i]]])]
            jobs.append({"H": H, "L": L, "sups": sups, "cap": target - 1, "tl": tl, "solver": "feas",
                         "key": [[list(x) for x in b] for b in tr]})
        res3 = run_jobs(jobs, workers) if jobs else []
        rec["triple_tests"] = [{k: r[k] for k in ("key", "status", "upper", "seconds")} for r in res3]
        rec["achieving"] = [r["key"] for r in res3 if r["status"] == "infeasible_under_cap"]
        rec["undecided"] = [r["key"] for r in res3 if r["upper"] is None and r["status"] != "infeasible_under_cap"]
        print(f"h=({hm['alpha']},{hm['beta']}) survivors {rec['survivors_per_class']} proper triples {len(triples)} "
              f"achieving {len(rec['achieving'])} undecided {len(rec['undecided'])}", flush=True)
        out["homs"].append(rec)
        out["seconds"] = time.time() - t0
        dump(OUT / f"colour_{tag(name)}_{kind}_T{target}.json", out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="[[90,8,10]]")
    ap.add_argument("--kind", default="X")
    ap.add_argument("--target", type=int, required=True)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--time-limit", type=float, default=300)
    ap.add_argument("--homs", type=int, nargs="*", default=None)
    a = ap.parse_args()
    run(a.code, a.kind, a.target, a.workers, a.time_limit, a.homs)


if __name__ == "__main__":
    main()
