"""E-004 proxy (b): circuit-distance upper bound (evaluators.distance.upper_bound) + low-weight witness counts.

  PYTHONPATH=. uv run python -m search.proxy.distance_proxy --cand G-ibm --budget low --rounds 3

Budgets:  low     = graphlike + BP-OSD 200 trials + 8 LNS starts
          default = the L0 default (graphlike + stim_search 4/4 + BP-OSD 1500 trials + 96 LNS starts)
Single process (num_workers=1) so CPU time is measured cleanly (process_time of this process; no child pools).
Writes results/E-004-proxy-fidelity/distance/<cand>__<budget>__r<rounds>__s<seed>.json
"""
from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path

from evaluators.distance import upper_bound
from evaluators.noise import add_noise
from search.proxy import candidates as C

OUT = Path("results/E-004-proxy-fidelity")

BUDGETS = {
    "low": dict(methods=("graphlike", "bposd"), bposd_trials=200, lns_starts=8),
    "default": dict(methods=("graphlike", "stim_search", "bposd"), bposd_trials=1500, lns_starts=96),
}


def cpu_now() -> float:
    a = resource.getrusage(resource.RUSAGE_SELF)
    b = resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--budget", default="low", choices=sorted(BUDGETS))
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    C.load_bad(OUT / "bad_schedules.json")
    css, circuits, dq, cand = C.build(a.cand)
    (OUT / "distance").mkdir(parents=True, exist_ok=True)
    rec = {"cand": a.cand, "budget": a.budget, "rounds": a.rounds, "seed": a.seed, "params": BUDGETS[a.budget],
           "bases": {}}
    for basis in ("Z", "X"):
        c = add_noise(circuits(basis, a.rounds), "sd6", 1e-3)
        c0, t0 = cpu_now(), time.time()
        r = upper_bound(c, seed=a.seed, num_workers=1, **BUDGETS[a.budget])
        cpu = cpu_now() - c0
        hist = {}
        lns_final = []
        for m in r.methods:
            if m.method == "bposd":
                hist = m.extra.get("solution_weight_histogram", {})
            if m.method == "bposd_lns":
                lns_final = m.extra.get("final_weights", [])
        w = r.weight
        n_at_w = sum(v for kk, v in hist.items() if w is not None and int(kk) <= w)
        n_le_w1 = sum(v for kk, v in hist.items() if w is not None and int(kk) <= w + 1)
        rec["bases"][basis] = {"weight": w, "summary": r.summary(), "wall_s": round(time.time() - t0, 2),
                               "cpu_s": round(cpu, 2), "bposd_hist": hist, "lns_final_weights": lns_final,
                               "n_bposd_solutions_le_w": n_at_w, "n_bposd_solutions_le_w_plus1": n_le_w1,
                               "lns_hits_at_w": sum(1 for x in lns_final if w is not None and x <= w),
                               "witness": r.witness.describe() if r.witness is not None else None}
        print(a.cand, basis, w, r.summary(), f"cpu={cpu:.1f}s", flush=True)
    ws = [b["weight"] for b in rec["bases"].values()]
    rec["d_circ_ub"] = min(x for x in ws if x is not None) if all(x is not None for x in ws) else None
    rec["cpu_s_total"] = round(sum(b["cpu_s"] for b in rec["bases"].values()), 2)
    path = OUT / "distance" / f"{a.cand}__{a.budget}__r{a.rounds}__s{a.seed}.json"
    path.write_text(json.dumps(rec, indent=1, default=str))


if __name__ == "__main__":
    main()
