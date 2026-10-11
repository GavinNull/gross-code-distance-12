"""E-025 method (b): exact decision of a SMALL logical set in a low-symmetry family.  Take a colour-symmetric UNSAT
core (orbit reps), keep only its G24 translates as logicals (dropping logicals is sound for UNSAT), encode each one
EXACTLY (explicit qubit-graph cycles, exact_cyc) on top of the TimeSAT base of the target family, and solve once.
UNSAT => every legal deterministic circuit of the family at period P has one of these logicals lifting in the bulk.
SAT   => the core is breakable in this family (the timing is checked with Bellman-Ford).

    PYTHONPATH=.:tests uv run python -m search.experiments.e025.exact_core CORE.json --P 10 --sub ""
"""
import argparse
import json
import time
from pathlib import Path

import search.experiments.e021.nwfull as NF
from search.experiments.e021.extgen import ext_general
from search.experiments.e021.mono import fig12_labels
from search.experiments.e025.cyc import rec_cycles, blocked
from search.experiments.e025.exact_cp import make_family
from search.experiments.e025.exact_cyc import ExactCyc

OUT = Path("results/E-025-gross12-perchk-period")


def core_translates(F, core_path):
    core = json.load(open(core_path))
    Fs = make_family("1,2;0,3")
    rs, _ = NF.prepare_full(Fs, "XZ")
    f12 = fig12_labels()
    orbit = {"X": set(), "Z": set()}
    for k in core["core"]:
        r = rs[k]
        E = ext_general(r["kind"], f12[r["kind"]])
        for Pm in E["perms"]:
            orbit[r["kind"]].add(tuple(sorted(int(Pm[j]) for j in r["S"])))
    recs, _ = NF.prepare_full(F, "XZ")
    return [r for r in recs if tuple(sorted(r["S"])) in orbit[r["kind"]]], len(core["core"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("core")
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--lazy", type=int, default=0, help="on SAT: add (exactly) up to this many lifting logicals of the "
                    "FULL modelled set per round and re-solve (exact lazy loop)")
    ap.add_argument("--max_sec", type=float, default=20000)
    a = ap.parse_args()
    t0 = time.time()
    F = make_family(a.sub)
    keep, nrep = core_translates(F, a.core)
    M = ExactCyc(F, a.P)
    base = M.ncl
    for k, r in enumerate(keep):
        M.add_logical(k, r)
    print(f"P={a.P} |H|={len(F.Hs)} core reps {nrep} -> logicals {len(keep)}; clauses base {base} total {M.ncl} "
          f"vars {M.pool.top} ({time.time() - t0:.0f}s)", flush=True)
    ts = time.time()
    t = M.solve([M.sel[k] for k in range(len(keep))])
    active = list(range(len(keep)))
    if a.lazy and t is not None:
        allr, _ = NF.prepare_full(F, "XZ")
        RCall = [rec_cycles(F, r) for r in allr]
        key = {(r["kind"], tuple(sorted(r["S"]))): k for k, r in enumerate(keep)}
        rnd = 0
        while t is not None and time.time() - t0 < a.max_sec:
            rnd += 1
            lif = [j for j, r in enumerate(allr) if not blocked(RCall[j], t, a.P)]
            print({"round": rnd, "lifting_full": len(lif), "active": len(active), "clauses": M.ncl,
                   "sec": round(time.time() - t0)}, flush=True)
            if not lif:
                break
            import random as _r
            _r.Random(rnd).shuffle(lif)
            for j in lif[:a.lazy]:
                r = allr[j]
                kk = key.setdefault((r["kind"], tuple(sorted(r["S"]))), len(keep))
                assert kk == len(keep), "active logical lifts: encoding error"
                keep.append(r); M.add_logical(kk, r); active.append(kk)
            t = M.solve([M.sel[k] for k in active])
    res = {"P": a.P, "sub": a.sub, "core": a.core, "logicals": len(keep), "clauses": M.ncl,
           "solve_sec": round(time.time() - ts, 1)}
    if t is None:
        res["status"] = "UNSAT"
    else:
        RC = [rec_cycles(F, r) for r in keep]
        ok = all(blocked(c, t, a.P) for c in RC)
        res.update(status="SAT", bf_check_all_blocked=ok, t=t)
    print("STATUS", {k: v for k, v in res.items() if k != "t"}, flush=True)
    (OUT / f"{a.tag}.json").write_text(json.dumps(res))


if __name__ == "__main__":
    main()
