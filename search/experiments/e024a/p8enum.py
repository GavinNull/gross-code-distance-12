"""E-024a: per-check-free P = 8 circuits in the Fig. 12 extended-code class (each check: start in Z_8, order in its
8-element class; at P = 8 the evaluator rule forces CNOT offsets 1..6 and measurement at 7).  Enumerate all legal
(data-collision-free) and deterministic assignments with the TimeSAT base encoding (X check 0's first CNOT fixed at
time 0 = global time shift), blocking each found assignment, up to a cap.  Optionally screen each by the exact lift
at small R (first lifting logical stops).

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.p8enum --cap 20000 --screen 0
"""
import argparse
import json
import time
from pathlib import Path

from search.experiments.e021.nwsat import Family
from search.experiments.e024a.cegar import TimeSAT, spec_of

OUT = Path("results/E-024a-gross12-period")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=20000)
    ap.add_argument("--max_sec", type=float, default=3600)
    ap.add_argument("--sub", default="")
    ap.add_argument("--tag", default="p8enum")
    a = ap.parse_args()
    P = 8
    t0 = time.time()
    gens = [tuple(int(v) for v in g.split(",")) for g in a.sub.split(";")] if a.sub else [(0, 0)]
    F = Family(gens)
    M = TimeSAT(F, P)
    print(f"base built {time.time() - t0:.0f}s vars {M.pool.top} clauses {M.ncl}", flush=True)
    n = 0
    status = "CAP"
    with open(OUT / f"{a.tag}.jsonl", "w") as f:
        while n < a.cap and time.time() - t0 < a.max_sec:
            t = M.solve()
            if t is None:
                status = "COMPLETE"; break
            n += 1
            f.write(json.dumps(t) + "\n")
            M.add([-M.eq(i, t[i]) for i in range(len(t))])
            if n % 100 == 0:
                print(n, f"{time.time() - t0:.0f}s", flush=True)
    if status == "CAP" and time.time() - t0 >= a.max_sec:
        status = "TIME"
    print(f"STATUS {status} n={n} {time.time() - t0:.0f}s", flush=True)
    json.dump({"status": status, "n": n, "sub": a.sub, "sec": round(time.time() - t0)},
              open(OUT / f"{a.tag}_summary.json", "w"))


if __name__ == "__main__":
    main()
