"""E-041 pattern-CEGAR on an offset-range subclass (rng_enc.EncRange) with static complete pattern types and lazy
patterns for the rest (every witness of every SAT model -> its pattern clause, e038.cegar.PatternEncoder; sound global
nogoods).  SAT model with no bulk weight <= 3 witness (e038.model.bulk_min, W = 6 and 12, both bases) -> FOUND.
UNSAT -> the final CNF (static + lazy clauses) is dumped for an independent CaDiCaL DRAT / drat-trim run.
The built encoder is cached as a pickle next to the CNF.
usage: uv run python -m search.experiments.e041.rcegar --cls W --P 9 --lo -1 --hi 1 --types HH,HHM,DDH,DHH --tag W9_r1"""
import argparse
import json
import os
import pickle
import random
import sys
import time

from pysat.solvers import Solver

from search.experiments.e038.cegar import pattern_of
from search.experiments.e038.model import bulk_min
from search.experiments.e041.rng_enc import build

OUT = "results/E-041-bb18-p9"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cls", default="W")
    ap.add_argument("--P", type=int, default=9)
    ap.add_argument("--lo", type=int, default=-1)
    ap.add_argument("--hi", type=int, default=1)
    ap.add_argument("--types", default="HH,HHM,DDH,DHH")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--solver", default="cadical195")
    ap.add_argument("--shuffle", type=int, default=None)
    ap.add_argument("--hours", type=float, default=10)
    ap.add_argument("--starts", default=None, help="fix all 14 window starts (comma list, values -1..P-1 mod P)")
    ap.add_argument("--share", action="store_true",
                    help="also harvest witness patterns of every model in rcegar_<tag>_models.jsonl (shared by runs)")
    ap.add_argument("--C", type=int, default=8, help="reversal constant for *R ansatz")
    ap.add_argument("--sym", default=None, help="symmetric ansatz (sym.py): p, s1, s2, pR, s1R, s2R")
    a = ap.parse_args()
    sys.setrecursionlimit(100000)
    pk = f"{OUT}/{a.tag}_enc.pkl"
    t0 = time.time()
    if os.path.exists(pk):
        E, PE, pats = pickle.load(open(pk, "rb"))
    else:
        lo = [0] + [a.lo] * 13
        hi = [0] + [a.hi] * 13
        E, PE = build(a.cls, a.P, lo, hi, a.types.split(","))
        pats = set()
        pickle.dump((E, PE, pats), open(pk, "wb"))
    nosave = a.shuffle is not None or a.sym is not None or a.starts is not None
    if a.starts:
        st = [int(x) for x in a.starts.split(",")]
        for k, v in zip(E.ks, st):
            lo_, hi_ = E.pi[k].lo, E.pi[k].hi
            vv = [x for x in (v, v - a.P, v + a.P) if lo_ <= x <= hi_]
            assert len(vv) == 1, (k, v, lo_, hi_)
            E.add([E.pi[k].eq(vv[0])])
    nsym = 0
    if a.sym:
        from search.experiments.e041.sym import add_symmetry
        nsym = add_symmetry(E, a.sym, C=a.C)
    log = open(f"{OUT}/rcegar_{a.tag}{'' if a.shuffle is None else f'_sh{a.shuffle}'}"
               f"{'' if a.sym is None else '_sym' + a.sym}{'' if a.C == 8 else f'_C{a.C}'}.log", "a")

    def w(d):
        log.write(json.dumps(d) + "\n")
        log.flush()
        print(json.dumps(d), flush=True)
    w({"start": vars(a), "sym_clauses": nsym, "vars": E.nv, "clauses": len(E.cl), "lazy_patterns": len(pats),
       "build_or_load_sec": round(time.time() - t0, 1)})
    cl = list(E.cl)
    if a.shuffle is not None:
        random.Random(a.shuffle).shuffle(cl)
    s = Solver(name=a.solver, bootstrap_with=cl)
    ptr = len(E.cl)
    it = 0
    seen = 0
    mpath = f"{OUT}/rcegar_{a.tag}_models.jsonl"

    def harvest():
        nonlocal seen
        if not (a.share and os.path.exists(mpath)):
            return 0
        from search.experiments.e038.model import Sched
        lines = open(mpath).read().splitlines()
        n = 0
        for line in lines[seen:]:
            try:
                sch2 = Sched.from_json(json.loads(line)["sched"])
            except Exception:
                break
            seen += 1
            _, wits2 = bulk_min(sch2, 3, W=6, want_all=True, limit=2000)
            for b2, tags2 in wits2:
                pat2 = pattern_of(b2, tags2)
                if pat2 in pats:
                    continue
                pats.add(pat2)
                n += 1
                for c in PE.clauses(pat2):
                    E.add(c)
        return n
    nh = harvest()
    if nh:
        w({"harvested_at_start": nh, "models_seen": seen})
    while time.time() - t0 < a.hours * 3600:
        for c in E.cl[ptr:]:
            s.add_clause(c)
        ptr = len(E.cl)
        ts = time.time()
        sat = s.solve()
        tsolve = time.time() - ts
        if not sat:
            w({"result": "UNSAT", "iters": it, "lazy_patterns": len(pats), "vars": E.nv, "clauses": len(E.cl),
               "sec": round(time.time() - t0, 1)})
            path = f"{OUT}/{a.tag}_final.cnf"
            with open(path, "w") as f:
                f.write(f"p cnf {E.nv} {len(E.cl)}\n")
                for c in E.cl:
                    f.write(" ".join(map(str, c)) + " 0\n")
            break
        sch = E.decode(s.get_model())
        wmin, wits = bulk_min(sch, 3, W=6, want_all=True, limit=2000)
        if wmin is None:
            wmin, wits = bulk_min(sch, 3, W=12, want_all=True, limit=2000)
            if wmin is None:
                json.dump(sch.to_json(), open(f"{OUT}/found_{a.tag}_{a.sym}_{a.C}_{a.shuffle}.json", "w"))
                w({"result": "FOUND", "iters": it, "sec": round(time.time() - t0, 1)})
                break
        new = 0
        types = {}
        for b, tags in wits:
            pat = pattern_of(b, tags)
            if pat in pats:
                continue
            pats.add(pat)
            new += 1
            t = b + "".join(sorted(x[0] for x in pat[1]))
            types[t] = types.get(t, 0) + 1
            for c in PE.clauses(pat):
                E.add(c)
        if new == 0:
            raise RuntimeError("no new pattern")
        with open(mpath, "a") as fm:
            fm.write(json.dumps({"it": it, "nwit": len(wits), "sched": sch.to_json()}) + "\n")
        nh = harvest()
        w({"it": it, "w": wmin, "nwit": len(wits), "new": new, "harvested": nh, "patterns": len(pats), "types": types, "solve_sec": round(tsolve, 1),
           "sec": round(time.time() - t0, 1), "starts": [sch.pi[k] for k in E.ks]})
        it += 1
        if it % 20 == 0 and not nosave:
            pickle.dump((E, PE, pats), open(pk, "wb"))
    else:
        w({"result": "TIMEOUT", "iters": it, "sec": round(time.time() - t0, 1)})
    if not nosave:
        pickle.dump((E, PE, pats), open(pk, "wb"))


if __name__ == "__main__":
    main()
