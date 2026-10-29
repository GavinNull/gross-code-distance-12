"""Theory A: stim validation of bulk witnesses (uses the E-040 injector, which inserts the faults as deterministic
Pauli errors into the noiseless evaluator memory circuit and runs stim; independent of my detector arithmetic).

    PYTHONPATH=.:tests uv run python search/theory/A/stimcheck.py --code bb90 --P 9 --n 30
"""
from __future__ import annotations

import argparse
import pickle
import random
import sys

sys.path.insert(0, "search/theory/A")
from common import Code  # noqa: E402
from lift import OUT, Bulk  # noqa: E402
from search.experiments.e040.inject import check  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    C = Code(a.code)
    R = pickle.load(open(OUT / f"lift_{a.code}_P{a.P}.pkl", "rb"))
    idx = [i for i, b in enumerate(R["res"]) if b and b[0] <= C.d - 1]
    random.seed(1)
    ok = n = 0
    for i in random.sample(idx, min(a.n, len(idx))):
        tot, kind, Sname, Lw = R["res"][i]
        tx, tz = R["times"][i]
        sig = R["surv"][i]
        order = sig[0] if kind == "X" else sig[1]
        tH, tR = (tx, tz) if kind == "X" else (tz, tx)
        bk = Bulk(C, kind, list(tH), list(tR), a.P)
        found = None
        for S in (frozenset(order[4:]), frozenset(order[2:]), frozenset(order[3:])):
            for T in (S, frozenset(range(6)) - S):
                Tq = {int(bk.Hk[0][s]) for s in T}
                if not Tq <= set(Lw):
                    continue
                data = [q for q in Lw if q not in Tq]
                out = bk.solve(sorted(S), data, C.d - 1 - (len(data) + 1), want=True)
                if out and len(data) + 1 + out[0] == tot:
                    found = out[1]
                    break
            if found:
                break
        good, nd, no, Rr = check(a.code, kind, list(tx), list(tz), a.P, found)
        ok += bool(good)
        n += 1
        print(i, kind, Sname, "faults", len(found), "stim dets", nd, "obs", no, "R", Rr, "OK" if good else "FAIL",
              flush=True)
    print("validated", ok, "of", n)


if __name__ == "__main__":
    main()
