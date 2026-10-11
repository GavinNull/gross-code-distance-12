"""E-024b step 1b: as dextsat.py, but the colouring is the coset partition of an arbitrary subgroup H of the 72
translations (given by generators), colours = cosets.  Translations permute cosets; survivors are blocked together
with all their translation images.  Assignments whose extended code equals an already-known d_ext >= 11 class
(column key set equality; e.g. Fig. 12 pulled back to a finer colouring) are recorded as 'known' and blocked
without a DFS (their d_ext is already proven).

    PYTHONPATH=. uv run python -m search.experiments.e024b.dextsat2 --kind X --sub "2,0;0,2" --workers 4
"""
from __future__ import annotations

import argparse
import json
import time

from pysat.formula import IDPool
from pysat.solvers import Cadical153

from search.experiments.e018 import common as C
from search.experiments.e024b.common import OUT, dfs, ext_general, key_of, name, realisations, resid_sets, \
    single_hooks, types

N2 = 72


def subgroup(gens):
    H = {(0, 0)}
    while True:
        N = H | {((h[0] + g[0]) % 12, (h[1] + g[1]) % 6) for h in H for g in gens}
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
        a, b = divmod(i, 6)
        for h in H:
            col[((a + h[0]) % 12) * 6 + (b + h[1]) % 6] = m
        m += 1
    perms = set()
    for ga in range(12):
        for gb in range(6):
            pr, _ = C.tr(ga, gb)
            p = [None] * m
            for i in range(N2):
                c, d = col[i], col[int(pr[i])]
                assert p[c] in (None, d)
                p[c] = d
            perms.add(tuple(p))
    return col, m, sorted(perms), len(H)


def known_keysets(kind):
    out = []
    p = OUT / "known_classes.jsonl"
    if p.exists():
        for line in p.read_text().splitlines():
            r = json.loads(line)
            if r["kind"] == kind:
                out.append(r)
    return out


def keyset(E):
    return frozenset(E["He"][:, j].tobytes() + E["Le"][:, j].tobytes() for j in range(E["N"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--sub", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max_sec", type=float, default=36000)
    a = ap.parse_args()
    kind = a.kind
    gens = [tuple(int(v) for v in g.split(",")) for g in a.sub.split(";")]
    colv, m, perms, hs = cosets(gens)
    TY = types(kind)
    nt = len(TY)
    RS = [resid_sets(o) for o in TY]
    real = realisations(kind)
    # known classes: (key set, description)
    known = []
    from search.experiments.e024b.common import labord as _lab  # noqa: F401
    for r in known_keysets(kind):
        from search.experiments.e024b.w11 import parse_orders
        col = tuple(r["col"])
        from search.experiments.e024b.common import labord
        E0 = ext_general(kind, labord(col, parse_orders(r["orders"])))
        known.append((keyset(E0), r["orders"]))
    pool = IDPool()
    S = Cadical153()
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
        clauses = set()
        for ga in range(12):
            for gb in range(6):
                _, pc = C.tr(ga, gb)
                ks = [key_of(kind, [int(pc[q]) for q in s_]) for s_ in sups]
                clauses.add(tuple(sorted({-present(k) for k in ks})))
        for cl in clauses:
            S.add_clause(list(cl))
        return len(sups), len(clauses)

    def block(assign):
        for p in perms:
            S.add_clause([-x[p[c]][assign[c]] for c in range(m)])

    tag = f"dext2_{kind}_" + a.sub.replace(";", "_").replace(",", "")
    outp = OUT / f"{tag}.jsonl"
    T0 = time.time()
    ncalls = nsurv = nknown = 0
    if outp.exists():
        for line in outp.read_text().splitlines():
            r = json.loads(line)
            assign = tuple(r["assign"])
            if r.get("survivor") or r.get("known"):
                block(assign)
                nsurv += bool(r.get("survivor")); nknown += bool(r.get("known"))
            else:
                E = ext_general(kind, [TY[assign[colv[i]]] for i in range(N2)])
                add_witness_clauses(E, r["witness"])
            ncalls += 1
        print(f"replayed {ncalls}", flush=True)
    status = "TIMEOUT"
    print(f"|H|={hs} colours={m} perms={len(perms)} known={len(known)}", flush=True)
    while time.time() - T0 < a.max_sec:
        if not S.solve():
            status = "COMPLETE"; break
        md = set(l for l in S.get_model() if l > 0)
        assign = tuple(next(t for t in range(nt) if x[c][t] in md) for c in range(m))
        lab = [TY[assign[colv[i]]] for i in range(N2)]
        E = ext_general(kind, lab)
        rec = {"kind": kind, "sub": a.sub, "assign": list(assign), "orders": [name(TY[t]) for t in assign],
               "group": len(E["group"]), "orbits": len(E["reps"]), "N": E["N"],
               "single_hooks": [single_hooks(kind, TY[t]) for t in assign]}
        ks = keyset(E)
        kn = [d for k, d in known if k == ks]
        if kn:
            rec["known"] = kn[0]; nknown += 1
            block(assign)
        else:
            t1 = time.time()
            sols, nodes, complete = dfs(E, 10, stopfirst=1, workers=a.workers)
            ncalls += 1
            rec.update(nodes=nodes, sec=round(time.time() - t1, 1))
            if sols:
                rec["witness"] = list(sols[0])
                rec["n_hooks"] = add_witness_clauses(E, sols[0])[0]
            else:
                assert complete
                rec["survivor"] = True; nsurv += 1
                block(assign)
                print("SURVIVOR", json.dumps(rec), flush=True)
        with open(outp, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if ncalls % 50 == 0:
            print(f"calls {ncalls} survivors {nsurv} known {nknown} {time.time() - T0:.0f}s", flush=True)
    summ = {"kind": kind, "sub": a.sub, "H": hs, "colours": m, "status": status, "calls": ncalls,
            "survivors": nsurv, "known": nknown, "sec": round(time.time() - T0, 1)}
    print("DONE", json.dumps(summ), flush=True)
    with open(OUT / "dext_summary.jsonl", "a") as f:
        f.write(json.dumps(summ) + "\n")


if __name__ == "__main__":
    main()
