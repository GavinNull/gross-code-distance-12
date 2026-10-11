"""E-025 method (c'): large-neighbourhood search with exact (CEGAR) sub-solves in the PER-CHECK-FREE family at period P
(positive direction: try to reach 0 modelled lifting logicals, then exact-lift).

State: a legal deterministic per-check timing t (TimeSAT base: legality, determinism, window <= P-3, Fig. 12 class).
Every modelled logical r has a selector s_r; its frame-model nogoods are added as (clause OR -s_r), so they stay in the
solver for the whole run (valid whenever r is required blocked) and are reused by later steps.
Step: pick a lifting logical l; neighbourhood N = checks of l's constraint graph (Z readers of its support + hook
check) plus checks of up to `extra` other lifting logicals sharing a check with N; free N's items, fix all other
items by assumptions; require T = {l} + every currently blocked logical touching N to be blocked (assume s_r, r in T);
CEGAR on T within a time limit.  SAT => accept the new timing (logicals not touching N keep their status, so the number
of lifting logicals strictly drops).  UNSAT => record (l, N) as stuck for now.
Start: per-check copy of the best (fewest lifting) colour-symmetric P timing seen in a symmetric CEGAR run, or a spec.

    PYTHONPATH=.:tests uv run python -m search.experiments.e025.lns --P 17 --max_sec 3600 --tag lns_P17
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import search.experiments.e021.nwfull as NF
from search.experiments.e024a.cegar import TimeSAT, bf_P, item_perms, spec_of, tighten
from search.experiments.e025.cegar_lib import Cegar
from search.experiments.e025.exact_cp import make_family

OUT = Path("results/E-025-gross12-perchk-period")


def checks_of(F, r):
    out = set()
    rd = r["rd"]
    qs = []
    for e in r["evs"]:
        if e[0] == "d":
            qs.append(e[1])
        else:
            qs += list(e[2])
            out.add((r["kind"], e[1]))
    for q in qs:
        for ty, c, lab in F.touch[q]:
            if ty == rd:
                out.add((ty, c))
    return out


def sym_start(P, seconds, seed):
    """best timing (fewest lifting reps) of a colour-symmetric CEGAR run at period P; returns unit times."""
    Fs = make_family("1,2;0,3")
    recs, _ = NF.prepare_full(Fs, "XZ")
    C = Cegar(Fs, P, recs, seed=seed)
    best = None
    t0 = time.time()
    while time.time() - t0 < seconds:
        t = C.M.solve()
        if t is None:
            break
        lif = C.lifting(t)
        if best is None or len(lif) < best[0]:
            best = (len(lif), t)
        if not lif:
            break
        C.add_nogoods(t, lif)
    return Fs, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--step_sec", type=float, default=60)
    ap.add_argument("--extra", type=int, default=2)
    ap.add_argument("--sym_sec", type=float, default=120)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rmax", type=int, default=6)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    T0 = time.time()
    P = a.P
    F = make_family("")
    recs, _ = NF.prepare_full(F, "XZ")
    rchecks = [checks_of(F, r) for r in recs]
    by_check = {}
    for k, cs in enumerate(rchecks):
        for c in cs:
            by_check.setdefault(c, []).append(k)
    M = TimeSAT(F, P)
    unit_of = [(it[0], it[1]) for it in F.items]
    sel = [M.pool.id(("sel", k)) for k in range(len(recs))]
    # start
    Fs, best = sym_start(P, a.sym_sec, a.seed)
    tsym = best[1]
    t = [tsym[Fs.item(ty, c, lab)] for (ty, c, lab) in F.items]
    assert M.solve([M.eq(i, t[i]) for i in range(len(t))]) is not None, "start not admitted"

    def lifting_set(tt):
        NF.bf_general = lambda cons, rank: bf_P(cons, tt, P)  # noqa: E731
        return {id(x[0]): x for x in NF.evaluate_full(F, recs, None)}

    idk = {id(r): k for k, r in enumerate(recs)}
    L = {idk[i]: v for i, v in lifting_set(t).items()}
    print(f"start: symmetric best {best[0]} reps -> per-check lifting {len(L)} ({time.time() - T0:.0f}s)", flush=True)
    log = {"P": P, "start_lifting": len(L), "steps": []}
    items_of = {}
    for i, (ty, c, lab) in enumerate(F.items):
        items_of.setdefault((ty, c), []).append(i)
    stuck = set()
    nng = 0
    while L and time.time() - T0 < a.max_sec:
        cand = [k for k in L if k not in stuck] or list(L)
        l = rng.choice(cand)
        N = set(rchecks[l])
        others = [k for k in L if k != l and rchecks[k] & N]
        rng.shuffle(others)
        for k in others[:a.extra]:
            N |= rchecks[k]
        free = set(i for c in N for i in items_of[c])
        fixed = [M.eq(i, t[i]) for i in range(len(t)) if i not in free]
        touching = set(k for c in N for k in by_check.get(c, []))
        Tset = [k for k in touching if k not in L] + [l] + [k for k in others[:a.extra]]
        Tset = sorted(set(Tset))
        ass = fixed + [sel[k] for k in Tset]
        ts = time.time()
        status, newt, its = "UNKNOWN", None, 0
        while time.time() - ts < a.step_sec:
            its += 1
            tt = M.solve(ass)
            if tt is None:
                status = "UNSAT"; break
            NF.bf_general = lambda cons, rank: bf_P(cons, tt, P)  # noqa: E731
            lif = NF.evaluate_full(F, [recs[k] for k in Tset], None)
            if not lif:
                status, newt = "SAT", tt; break
            for r_, cons, pi in lif:
                k = idk[id(r_)]
                pi, mins = tighten(cons, tt, P, unit_of, rng)
                lits = set()
                for ei, (u_, w_, kd, (i1, i2)) in enumerate(cons):
                    K = pi[u_] - pi[w_]
                    if K - 1 < mins[ei]:
                        continue
                    if kd in ("free", "hook+"):
                        lits.add(M.le_diff(i2, i1, (K - 1) * P - 1))
                    else:
                        lits.add(M.le_diff(i1, i2, K * P))
                M.add(sorted(lits) + [-sel[k]]); nng += 1
        rec = {"l": l, "N": len(N), "T": len(Tset), "status": status, "its": its, "sec": round(time.time() - ts, 1)}
        if status == "SAT":
            Lnew = {idk[i]: v for i, v in lifting_set(newt).items()}
            rec["lifting"] = len(Lnew)
            if len(Lnew) < len(L):
                t, L = newt, Lnew
                stuck = set()
        elif status == "UNSAT":
            stuck.add(l)
        rec["cur"] = len(L)
        log["steps"].append(rec)
        print(rec, f"total {time.time() - T0:.0f}s nogoods {nng}", flush=True)
        if len(stuck) >= len(L):
            a.extra += 1
            stuck = set()
            print("all stuck -> extra =", a.extra, flush=True)
    log.update(final_lifting=len(L), sec=round(time.time() - T0, 1))
    sp = OUT / f"{a.tag}_best.json"
    sp.write_text(json.dumps(spec_of(F, t, P)))
    if not L:
        from search.experiments.e021.liftscreen import screen
        r = screen(str(sp), a.rmax)
        log["exact"] = r
        print("exact:", r, flush=True)
    print(f"STATUS LNS P={P} final_lifting={len(L)} {log['sec']}s", flush=True)
    (OUT / f"{a.tag}.json").write_text(json.dumps(log))


if __name__ == "__main__":
    main()
