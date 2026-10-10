"""E-021 step 2c: timing+order CEGAR in the "Fig. 12 extended-code class" (orders whose extended code equals Fig. 12's:
per class, within-pair swaps of positions 1-2 and 5-6 and/or reversal) with ALL weight-11 extended logicals
(E-018 stage a lists, 4224 per kind = 176 orbits of the 24 colour-preserving translations) in the bulk frame model.

Column realisations: data column -> free data error.  Hook column with residual support U of check a: the ancilla
fault after CNOT (6-|U|) equals errors on the qubits of U at their own CNOT times (forward) and also errors on the
qubits of a\\U at their own CNOT times (backward: the ancilla fault at preparation is trivial), so the column is
modelled as V = the smaller of U, a\\U pinned at a's CNOT times; this does not depend on which of the class's
admissible orders is used (U is a prefix or a suffix in all of them).  One realisation per column => the model is
a sufficient condition for lifting (enough for nogoods; candidates are decided by the exact lift, lift21.py).
Logicals whose realised qubit sets overlap are not modelled (counted).  |Q∩c| > 2: pairing enumeration (lifts if
any pairing is feasible); a nogood is generated from the feasible pairing.

    PYTHONPATH=. uv run python -m search.experiments.e021.nwfull --sub "1,2;0,3"
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

from search.experiments.e018 import common as C
from search.experiments.e021.extgen import ext_general
from search.experiments.e021.mono import LAB, fig12_labels
from search.experiments.e021.nwsat import Family, Model, bad_triples_all, class_orders, parse_sub

OUT = Path("results/E-021-gross-new-orders")
N2 = 72


def pairings(lst):
    if not lst:
        yield []
        return
    for k in range(1, len(lst)):
        for p in pairings(lst[1:k] + lst[k + 1:]):
            yield [(lst[0], lst[k])] + p


def column_real(F, kind, E, j):
    """('d', q) or ('h', a, V) with V = pinned qubits."""
    sups = E["col_sups"][j]
    for s in sups:
        if len(s) == 1:
            return ("d", s[0])
    s = set(sups[0])
    for a in range(N2):
        qa = set(int(q) for q in F.T[kind][a])
        if s <= qa:
            V = s if len(s) <= 3 else qa - s
            return ("h", a, tuple(sorted(V)))
    raise AssertionError


def prepare_full(F, kinds, orbit_reps=True):
    recs, skipped = [], 0
    for kind in kinds:
        rd = "Z" if kind == "X" else "X"
        f12 = fig12_labels()
        E = ext_general(kind, f12[kind])
        assert (E["He"] == C.ext(kind)["He"]).all() and (E["Le"] == C.ext(kind)["Le"]).all(), "column indexing"
        sols = C.load_logicals(kind)
        if orbit_reps:
            # reps of Hs-orbits: Hs <= 24-group; use E-018 perms restricted to Hs
            Hs = set(F.Hs)
            perms = [P for g, P in zip(E["group"], E["perms"]) if tuple(g) in Hs]
            seen, reps = set(), []
            for S in sols:
                if S in seen:
                    continue
                for P in perms:
                    seen.add(tuple(sorted(int(P[j]) for j in S)))
                reps.append(S)
            sols = reps
        for S in sols:
            evs = [column_real(F, kind, E, j) for j in S]
            qs = []
            for e in evs:
                qs += [e[1]] if e[0] == "d" else list(e[2])
            if len(set(qs)) != len(qs):
                skipped += 1
                continue
            rc = {}
            for q in qs:
                for ty, c, lab in F.touch[q]:
                    if ty == rd:
                        rc.setdefault(c, []).append(q)
            assert all(len(v) % 2 == 0 for v in rc.values())
            recs.append({"kind": kind, "S": tuple(int(j) for j in S), "evs": evs, "rc": rc, "rd": rd})
    return recs, skipped


def skeleton(F, r, cls):
    """constraints for a pairing choice cls: (c, q) -> node."""
    kind, rd = r["kind"], r["rd"]
    cons = []
    for e in r["evs"]:
        if e[0] == "d":
            q = e[1]
            rds = [(cls[(c, q)], F.item(rd, c, lab)) for ty, c, lab in F.touch[q] if ty == rd]
            for (nc, ic), (nd, idd) in itertools.permutations(rds, 2):
                cons.append((nc, nd, "free", (ic, idd)))
        else:
            a = e[1]
            Fn = ("F", a)
            for q in e[2]:
                ia = F.item(kind, a, F.label_of(kind, a, q))
                for ty, c, lab in F.touch[q]:
                    if ty != rd:
                        continue
                    ic = F.item(rd, c, lab)
                    cons.append((cls[(c, q)], Fn, "hook+", (ic, ia)))
                    cons.append((Fn, cls[(c, q)], "hook-", (ic, ia)))
    return cons


def bf_general(cons, rank):
    from search.experiments.e021.nwsat import bf
    return bf(cons, rank)


def evaluate_full(F, recs, rank):
    out = []
    for r in recs:
        rc = r["rc"]
        multi = [c for c, l in rc.items() if len(l) > 2]
        for choice in itertools.product(*[list(pairings(sorted(rc[c]))) for c in multi]):
            cls = {}
            for c, l in rc.items():
                if len(l) == 2:
                    cls[(c, l[0])] = cls[(c, l[1])] = ("c", c, 0)
            for c, prs in zip(multi, choice):
                for k, (x, y) in enumerate(prs):
                    cls[(c, x)] = cls[(c, y)] = ("c", c, k)
            cons = skeleton(F, r, cls)
            pi = bf_general(cons, rank)
            if pi is not None:
                out.append((r, cons, pi))
                break
    return out


def nogood_full(M, cons, pi):
    lits = []
    for u, w, kd, (i1, i2) in cons:
        K = pi[u] - pi[w]
        if kd in ("free", "hook+") and K == 1:
            lits.append(-M.lt(i1, i2))
        elif kd == "hook-" and K == 0:
            lits.append(M.lt(i1, i2))
    M.S.add_clause(sorted(set(lits)))
    M.nnogood += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default="1,2;0,3")
    ap.add_argument("--kinds", default="XZ")
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--exact_fig12", type=int, default=0, help="pin exact Fig. 12 orders (control)")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    t0 = time.time()
    F = Family(parse_sub(a.sub))
    recs, skipped = prepare_full(F, a.kinds)
    M = Model(F, bad_triples_all())
    f12 = fig12_labels()
    for ty in "XZ":
        for k in range(F.nc):
            o = f12[ty][F.reps[k]]
            for i in range(N2):
                assert F.cls[i] != k or f12[ty][i] == o
            it_ = lambda lab: F.idx[(ty, k, lab)]  # noqa: E731
            if a.exact_fig12:
                for i in range(5):
                    M.S.add_clause([M.lt(it_(o[i]), it_(o[i + 1]))])
                continue
            rev = M.pool.id(("rev", ty, k))

            def first(U, guard):
                for x in U:
                    for y in range(6):
                        if y not in U:
                            M.S.add_clause(guard + [M.lt(it_(x), it_(y))])
            first(o[:2], [rev]); first(o[:3], [rev]); first(o[:4], [rev])
            first(o[4:], [-rev]); first(o[3:], [-rev]); first(o[2:], [-rev])
    print(f"|Hs|={len(F.Hs)} modelled reps={len(recs)} skipped(overlap)={skipped} {time.time() - t0:.1f}s", flush=True)
    tag = a.tag or f"nwfull_H{len(F.Hs)}_{a.sub.replace(';', '_').replace(',', '')}{'_exact' if a.exact_fig12 else ''}"
    log = {"sub": a.sub, "reps": len(recs), "skipped": skipped, "iters": []}
    status, it, best = "UNKNOWN", 0, None
    while time.time() - t0 < a.max_sec:
        it += 1
        rank = M.solve()
        if rank is None:
            status = "UNSAT"; break
        lif = evaluate_full(F, recs, rank)
        if best is None or len(lif) < best[0]:
            best = (len(lif), rank)
        if not lif:
            status = "CANDIDATE"; break
        for r, cons, pi in lif:
            nogood_full(M, cons, pi)
        rec = {"it": it, "lifting": len(lif), "nogoods": M.nnogood, "sec": round(time.time() - t0, 1)}
        log["iters"].append(rec)
        if it % 20 == 0 or it < 4:
            print(rec, flush=True)
    log.update(status=status, iterations=it, sec=round(time.time() - t0, 1), best_lifting=best[0] if best else None)
    if best:
        log["candidate_rank"] = best[1]
        log["candidate_orders"] = {f"{k[0]},{k[1]}": list(v) for k, v in class_orders(F, best[1]).items()}
    print(f"STATUS {status} it={it} nogoods={M.nnogood} best={log['best_lifting']} {log['sec']}s", flush=True)
    (OUT / f"{tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
