"""E-025 new method: HYBRID exact/lazy CEGAR.  For every (lazily activated) modelled logical r and pairing p:
      sel_r -> ( OR_{C in short cycles of (r,p)} neg_C )  OR  rho_{r,p}
  neg_C -> cycle C negative (exact small totalizer, e025.exact_cyc), short = at most `maxterms` terms;
  rho_{r,p} = 'blocked through some other (longer) cycle'.  When r lifts at a candidate through pairing p (then no short
  cycle of p is negative, so rho_{r,p} is true), add the frame-model nogood guarded by rho:  -rho_{r,p} OR pi-clause
  (valid: blocked => pi-clause, e024a/e020 nogood argument).  Exact and complete: a blocked logical either has a
  negative short cycle or makes rho true without violating any added clause.
  Rationale (cycle anatomy of the certified P = 18 circuits): most logicals are blocked by cycles with 4-6 terms, so the
  solver can 'choose' the blocking cycle directly instead of learning it through many potential cells.
UNSAT => every legal deterministic circuit of the family at period P has a modelled logical lifting in the bulk.

    PYTHONPATH=.:tests uv run python -m search.experiments.e025.hybrid --P 17 --sub "1,2;0,3"
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import search.experiments.e021.nwfull as NF
from search.experiments.e024a.cegar import bf_P, item_perms, spec_of, tighten
from search.experiments.e025.cyc import pairing_classes, cycles_of, cycle_sum
from search.experiments.e025.exact_cp import make_family
from search.experiments.e025.exact_cyc import ExactCyc

OUT = Path("results/E-025-gross12-perchk-period")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="1,2;0,3")
    ap.add_argument("--split", default="")
    ap.add_argument("--maxterms", type=int, default=5)
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--maxwin", type=int, default=None)
    ap.add_argument("--winunits", default="")
    ap.add_argument("--images", type=int, default=1, help="add G24 images of nogoods (only when the image logical "
                    "is the same record, i.e. symmetric-style families; per-check families map records)")
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    t0 = time.time()
    P = a.P
    F = make_family(a.sub, a.split)
    wu = {(x[0], int(x[1:])) for x in a.winunits.split(",")} if a.winunits else None
    tag = a.tag or f"hyb_P{P}_H{len(F.Hs)}_{a.sub.replace(';', '_').replace(',', '') or 'triv'}" + \
        (f"_m{a.split.replace(',', '')}" if a.split else "") + f"_k{a.maxterms}"
    recs, skipped = NF.prepare_full(F, "XZ")
    M = ExactCyc(F, P, maxwin=a.maxwin, winunits=wu)
    unit_of = [(it[0], it[1]) for it in F.items]
    rng = random.Random(a.seed)
    # translation images of nogoods: canonical form of a logical (data qubits + hooks), all Hs-translates -> rep
    from search.experiments.e018 import common as C18
    from search.experiments.e024a.cegar import G24
    perms = item_perms(F) if a.images else []
    trs = [C18.tr(*g) for g in G24]

    def canon(r, pr=None, pc=None):
        ev = []
        for e in r["evs"]:
            if e[0] == "d":
                ev.append(("d", int(pc[e[1]]) if pc is not None else e[1]))
            else:
                a_ = int(pr[e[1]]) if pr is not None else e[1]
                ev.append(("h", a_, tuple(sorted(int(pc[v]) if pc is not None else v for v in e[2]))))
        return (r["kind"], tuple(sorted(ev)))

    canon2k = {}
    Hset = set(tuple(h) for h in F.Hs)
    for k, r in enumerate(recs):
        for g, (pr, pc) in zip(G24, trs):
            if tuple(g) in Hset:
                canon2k[canon(r, pr, pc)] = k
    pair_cls = [list(pairing_classes(r)) for r in recs]
    cons_of = {}
    short = {}
    rho = {}
    active = set()

    def cons(k, p):
        if (k, p) not in cons_of:
            cons_of[(k, p)] = NF.skeleton(F, recs[k], pair_cls[k][p])
        return cons_of[(k, p)]

    def activate(k):
        if k in active:
            return
        active.add(k)
        g = M.pool.id(("sel", k))
        M.add([g])
        for p, cls in enumerate(pair_cls[k]):
            cs = [c for c in cycles_of(F, recs[k], cls) if len(c) <= a.maxterms]
            short[(k, p)] = cs
            lits = []
            for c in cs:
                n = M.new()
                if M.add_cycle(c, n):
                    lits.append(n)
            rr = M.new()
            rho[(k, p)] = rr
            M.add([-g, rr] + lits)

    def nogood(k, p, t, cns, pi):
        pi2, mins = tighten(cns, t, P, unit_of, rng)
        lits = set()
        for ei, (u_, w_, kd, (i1, i2)) in enumerate(cns):
            K = pi2[u_] - pi2[w_]
            if K - 1 < mins[ei]:
                continue
            if kd in ("free", "hook+"):
                lits.add((i2, i1, (K - 1) * P - 1))
            else:
                lits.add((i1, i2, K * P))
        return sorted(lits)

    log = {"P": P, "sub": a.sub, "split": a.split, "H": len(F.Hs), "reps": len(recs), "maxterms": a.maxterms,
           "iters": [], "lift": []}
    status, it, ncand, nng = "UNKNOWN", 0, 0, 0
    print(f"P={P} |H|={len(F.Hs)} items={len(F.items)} reps={len(recs)} skipped={skipped} base clauses={M.ncl} "
          f"{time.time() - t0:.0f}s", flush=True)
    while time.time() - t0 < a.max_sec:
        it += 1
        ts = time.time()
        t = M.solve()
        if t is None:
            status = "UNSAT"; break
        lif = []
        for k, r in enumerate(recs):
            for p in range(len(pair_cls[k])):
                pi = bf_P(cons(k, p), t, P)
                if pi is not None:
                    lif.append((k, p, pi)); break
        rec = {"it": it, "lifting": len(lif), "active": len(active), "clauses": M.ncl,
               "solve_sec": round(time.time() - ts, 1), "sec": round(time.time() - t0, 1)}
        log["iters"].append(rec)
        if it % 10 == 0 or it < 4:
            print(rec, f"nogoods {nng}", flush=True)
        if not lif:
            ncand += 1
            from search.experiments.e021.liftscreen import screen
            sp = OUT / f"{tag}_cand{ncand}.json"
            sp.write_text(json.dumps(spec_of(F, t, P)))
            rr = screen(str(sp), a.rmax)
            rr["it"] = it
            print("exact:", rr, flush=True)
            log["lift"].append(rr)
            if rr["status"] == "CERTIFIED":
                status = "CERTIFIED"; log["spec"] = str(sp); break
            M.add([-M.eq(i, t[i]) for i in range(len(t))])
            continue
        for k, p, pi in lif:
            newly = k not in active
            activate(k)
            if not newly:
                assert not any(cycle_sum(c, t, P) < 0 for c in short[(k, p)]), "encoding error"
            keys = nogood(k, p, t, cons(k, p), pi)
            M.add([-rho[(k, p)]] + sorted(set(M.le_diff(*x) for x in keys))); nng += 1
            if perms and len(pair_cls[k]) == 1:
                done = {k}
                for (pr, pc), pm in zip(trs, perms):
                    k2 = canon2k.get(canon(recs[k], pr, pc))
                    if k2 is None or k2 in done or len(pair_cls[k2]) != 1:
                        continue
                    done.add(k2)
                    activate(k2)
                    M.add([-rho[(k2, 0)]] + sorted(set(M.le_diff(pm[x], pm[y], v) for x, y, v in keys)))
                    nng += 1
    log.update(status=status, iterations=it, sec=round(time.time() - t0, 1), active=len(active), nogoods=nng,
               candidates=ncand)
    print(f"STATUS P={P} |H|={len(F.Hs)} {status} it={it} active={len(active)} nogoods={nng} {log['sec']}s",
          flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
