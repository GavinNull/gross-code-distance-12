"""E-028 step 1: d_ext >= 9 type assignments for [[90,8,10]] under the coset colouring of a translation subgroup H
(port of e024b/dextsat2.py; audited method 2026-10-11).  Colours = cosets of H; each colour picks one of the 54
allowed extended-code types (single-check value 9; singles.py).  Lazy loop: SAT proposes an assignment; oracle =
complete W=8 DFS on its extended code; a witness gives, for each of the 45 translations, the clause "not all of the
witness's (translated) hook columns are present" (presence of a column key <=> some check whose colour's type realises
that label set as a residual).  Survivors (no weight <= 8) are blocked with all their translation images.
UNSAT => the survivors listed are all d_ext >= 9 assignments of that colouring (mod translation).

DFS cases: every extended logical of weight <= 8 contains a hook column (data-only logicals have weight >= d = 10), so
only orbit cases of hook columns are run, with orbits renumbered hooks-first (complete for weight <= 8).

    PYTHONPATH=.:tests uv run python -m search.experiments.e028.dext --kind X --sub "0,1" --workers 4
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
from pysat.formula import IDPool
from pysat.solvers import Solver

from search.experiments.e028 import common as C

N2 = C.N2


def subgroup(gens):
    H = {(0, 0)}
    while True:
        N = H | {((h[0] + g[0]) % C.L_, (h[1] + g[1]) % C.M_) for h in H for g in gens}
        if N == H:
            return sorted(H)
        H = N


def cosets(gens):
    H = subgroup(gens)
    col = [-1] * N2
    m = 0
    for i in range(N2):
        if col[i] >= 0:
            continue
        a, b = divmod(i, C.M_)
        for h in H:
            col[C.idx(a + h[0], b + h[1])] = m
        m += 1
    perms = set()
    for ga, gb in C.GROUP:
        pr, _ = C.tr(ga, gb)
        p = [None] * m
        for i in range(N2):
            c, d = col[i], col[int(pr[i])]
            assert p[c] in (None, d)
            p[c] = d
        perms.add(tuple(p))
    return col, m, sorted(perms), len(H)


def types(kind):
    d = json.loads((C.OUT / "singles.json").read_text())
    out = [o for o in C.all_types() if d[f"{kind}:{C.name(o)}"]["value_le"] == 9]
    assert len(out) == 54
    return out


def hooks_first(E):
    """orbit numbering with hook-column orbits first; returns (orbit, reps, n_hook_orbits)."""
    ishook = [not any(len(s) == 1 for s in E["col_sups"][j]) for j in range(E["N"])]
    old = E["orbit"]
    ho = sorted({int(old[j]) for j in range(E["N"]) if ishook[j]})
    do = sorted({int(old[j]) for j in range(E["N"]) if not ishook[j]})
    assert not set(ho) & set(do)
    ren = {o: k for k, o in enumerate(ho + do)}
    orb = np.array([ren[int(old[j])] for j in range(E["N"])])
    reps = [E["reps"][o] for o in ho + do]
    return orb, reps, len(ho)


def dext_dfs(E, W, stopfirst=1, workers=4, split=1, log=None):
    orb, reps, nh = hooks_first(E)
    return C.dfs(E, W, stopfirst=stopfirst, workers=workers, split=split, log=log, cases=range(nh),
                 orbit=orb, reps=reps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--sub", required=True, help="generators a,b;a,b  ('45' = trivial subgroup: 0,0)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max_sec", type=float, default=36000)
    ap.add_argument("--nsol", type=int, default=1, help="witnesses collected per oracle call (per DFS case)")
    ap.add_argument("--tag", default="")
    ap.add_argument("--solver", default="cadical153")
    ap.add_argument("--replay", default="", help="jsonl of an earlier run: re-add its clauses first")
    a = ap.parse_args()
    kind = a.kind
    gens = [tuple(int(v) for v in g.split(",")) for g in a.sub.split(";")]
    colv, m, perms, hs = cosets(gens)
    TY = types(kind)
    nt = len(TY)
    RS = [C.resid_sets(o) for o in TY]
    real = C.realisations(kind)
    pool = IDPool()
    S = Solver(name=a.solver)
    x = [[pool.id(("x", c, t)) for t in range(nt)] for c in range(m)]
    for c in range(m):
        S.add_clause(x[c])
        for t1 in range(nt):
            for t2 in range(t1 + 1, nt):
                S.add_clause([-x[c][t1], -x[c][t2]])
    pres = {}

    def present(k):
        if k not in pres:
            p = pool.id(("p", k))
            for a_, U in real.get(k, []):
                c = colv[a_]
                for t in range(nt):
                    if U in RS[t]:
                        S.add_clause([-x[c][t], p])
            pres[k] = p
        return pres[k]

    def add_witness_clauses(E, w):
        sups = [E["col_sups"][j][0] for j in w if not any(len(s_) == 1 for s_ in E["col_sups"][j])]
        assert sups
        clauses = set()
        for ga, gb in C.GROUP:
            _, pc = C.tr(ga, gb)
            ks = [C.key_of(kind, [int(pc[q]) for q in s_]) for s_ in sups]
            clauses.add(tuple(sorted({-present(k) for k in ks})))
        for cl in clauses:
            S.add_clause(list(cl))
        return len(sups)

    def block(assign):
        for p in perms:
            S.add_clause([-x[p[c]][assign[c]] for c in range(m)])

    tag = f"dext_{kind}_" + a.sub.replace(";", "_").replace(",", "") + a.tag
    outp = C.OUT / f"{tag}.jsonl"
    if outp.exists():
        outp.unlink()
    T0 = time.time()
    ncalls = nsurv = 0
    if a.replay:
        for line in open(a.replay):
            r = json.loads(line)
            assign = tuple(r["assign"])
            if r.get("survivor"):
                block(assign); nsurv += 1
            else:
                E = C.ext_general(kind, [TY[assign[colv[i]]] for i in range(N2)])
                for w_ in r.get("witnesses", [r["witness"]]):
                    add_witness_clauses(E, w_)
            ncalls += 1
        print(f"replayed {ncalls} {time.time() - T0:.0f}s", flush=True)
    status = "TIMEOUT"
    print(f"|H|={hs} colours={m} perms={len(perms)} types={nt}", flush=True)
    while time.time() - T0 < a.max_sec:
        if not S.solve():
            status = "COMPLETE"; break
        md = set(l for l in S.get_model() if l > 0)
        assign = tuple(next(t for t in range(nt) if x[c][t] in md) for c in range(m))
        lab = [TY[assign[colv[i]]] for i in range(N2)]
        E = C.ext_general(kind, lab)
        rec = {"kind": kind, "sub": a.sub, "assign": list(assign), "orders": [C.name(TY[t]) for t in assign],
               "group": len(E["group"]), "orbits": len(E["reps"]), "N": E["N"]}
        t1 = time.time()
        sols, nodes, complete = dext_dfs(E, 8, stopfirst=a.nsol, workers=a.workers)
        ncalls += 1
        rec.update(nodes=nodes, sec=round(time.time() - t1, 2))
        if sols:
            C.verify_logicals(E, sols)
            rec["witness"] = list(sols[0]); rec["wt"] = len(sols[0])
            rec["n_hooks"] = add_witness_clauses(E, sols[0])
            for w_ in sols[1:]:
                add_witness_clauses(E, w_)
            rec["n_wit"] = len(sols)
            rec["witnesses"] = [list(w_) for w_ in sols]
        else:
            assert complete
            rec["survivor"] = True; nsurv += 1
            block(assign)
            print("SURVIVOR", json.dumps(rec), flush=True)
        with open(outp, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if ncalls % 50 == 0:
            print(f"calls {ncalls} survivors {nsurv} {time.time() - T0:.0f}s", flush=True)
    summ = {"kind": kind, "sub": a.sub, "H": hs, "colours": m, "status": status, "calls": ncalls,
            "survivors": nsurv, "sec": round(time.time() - T0, 1)}
    print("DONE", json.dumps(summ), flush=True)
    with open(C.OUT / "dext_summary.jsonl", "a") as f:
        f.write(json.dumps(summ) + "\n")


if __name__ == "__main__":
    main()
