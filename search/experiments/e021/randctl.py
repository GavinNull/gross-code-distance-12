"""E-021 follow-up (3): classical control.  Random colour-symmetric non-wrapping frame circuits in the Fig. 12
extended-code class (per unit a uniformly random admissible order out of 8; a uniformly random interleaving of the
six unit sequences), rejected unless deterministic.  For each accepted sample: number of lifting modelled weight-11
logicals in the bulk frame model (nwfull reps, as the CEGAR sees them); exact lift (R = 1..6 both bases,
liftscreen) for every sample whose model count is 0 and for a random 5% calibration subset (R = 1 Z count).

    PYTHONPATH=.:tests uv run python -m search.experiments.e021.randctl --sec 1800 --seed 20261010
"""
import argparse
import itertools
import json
import random
import time
from pathlib import Path

from search.experiments.e021.lift21 import spec_from_ranks
from search.experiments.e021.liftscreen import screen
from search.experiments.e021.mono import fig12_labels, table
from search.experiments.e021.nwfull import evaluate_full, prepare_full
from search.experiments.e021.nwsat import Family, parse_sub
from search.experiments.e021.p8class import class_orders

OUT = Path("results/E-021-gross-new-orders")
N2 = 72


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sec", type=float, default=1800)
    ap.add_argument("--seed", type=int, default=20261010)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    F = Family(parse_sub("1,2;0,3"))
    recs, _ = prepare_full(F, "XZ")
    T = table()
    f12 = fig12_labels()
    units = [(ty, k) for ty in "XZ" for k in range(F.nc)]
    copts = {u: class_orders(f12[u[0]][F.reps[u[1]]]) for u in units}
    det_pairs = []
    for ia in range(N2):
        qa = set(int(x) for x in T["X"][ia])
        for ic in range(N2):
            ov = sorted(qa & set(int(x) for x in T["Z"][ic]))
            if ov:
                det_pairs.append([(F.item("X", ia, F.label_of("X", ia, q)), F.item("Z", ic, F.label_of("Z", ic, q)))
                                  for q in ov])
    t0 = time.time()
    stats = {"samples": 0, "det": 0, "model_hist": {}, "exact": [], "best_model": None}
    outp = OUT / "randctl.jsonl"
    while time.time() - t0 < a.sec:
        stats["samples"] += 1
        orders = {u: rng.choice(copts[u]) for u in units}
        seq = [u for u in units for _ in range(6)]
        rng.shuffle(seq)
        rank = [0] * len(F.items)
        pos = {u: 0 for u in units}
        for r, u in enumerate(seq):
            lab = orders[u][pos[u]]; pos[u] += 1
            rank[F.idx[(u[0], u[1], lab)]] = r
        if any((rank[p[0][0]] < rank[p[0][1]]) != (rank[p[1][0]] < rank[p[1][1]]) for p in det_pairs):
            continue
        stats["det"] += 1
        n = len(evaluate_full(F, recs, rank))
        stats["model_hist"][n] = stats["model_hist"].get(n, 0) + 1
        if stats["best_model"] is None or n < stats["best_model"]:
            stats["best_model"] = n
        if n == 0 or rng.random() < 0.05:
            d = spec_from_ranks(F.cls, rank, F.items, len(F.items))
            sp = OUT / "randctl_tmp.json"
            sp.write_text(json.dumps(d))
            r = screen(str(sp), 6)
            r.update(model=n)
            stats["exact"].append(r)
            with open(outp, "a") as f:
                f.write(json.dumps(r) + "\n")
    stats["sec"] = round(time.time() - t0, 1)
    stats["model_hist"] = {str(k): v for k, v in sorted(stats["model_hist"].items())}
    stats["certified"] = sum(1 for r in stats["exact"] if r["status"] == "CERTIFIED")
    (OUT / "randctl_summary.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps({k: v for k, v in stats.items() if k != "exact"}))


if __name__ == "__main__":
    main()
