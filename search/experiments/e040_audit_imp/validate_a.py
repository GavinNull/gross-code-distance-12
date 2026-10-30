"""E-040 impossibility audit: the independent bulk detector model (bulk_a.dets_one) vs stim on RANDOM fault sets
(1-4 random data / hook / measurement faults within 2 instances) on random canonical schedules: the stim-fired detector
set, mapped to (check, instance), must equal the model's set exactly.
   PYTHONPATH=.:tests uv run python -m search.experiments.e040_audit_imp.validate_a bb90 8 X 50 [seed]"""
import json
import random
import sys

import numpy as np

from search.experiments.e040_audit_imp.codes_a import code
from search.experiments.e040_audit_imp.inject_a import check


def main():
    name, P, sector, n = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
    seed = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    rng = random.Random(seed)
    C = code(name)
    z = np.load(f"results/E-040-audit-imp/canon_P{P}.npz")
    TX, TZ = z["TX"], z["TZ"]
    rk = "Z" if sector == "X" else "X"
    agree = tot = 0
    for _ in range(n):
        i = rng.randrange(len(TX))
        tX, tZ = TX[i].astype(int).tolist(), TZ[i].astype(int).tolist()
        tH = tX if sector == "X" else tZ
        order = sorted(range(6), key=lambda m: tH[m])
        fs = []
        for _ in range(rng.randint(1, 4)):
            u = rng.random()
            if u < 0.4:
                q = rng.randrange(C["NQ"])
                b = [bb for c in range(C["N2"]) for bb in range(6) if C["T"][rk][c][bb] == q][rng.randrange(3)]
                fs.append(("d", q, b, rng.randint(0, 1)))
            elif u < 0.8:
                k = rng.randint(1, 5)
                fs.append(("h", rng.randrange(C["N2"]), order[k:], rng.randint(0, 1)))
            else:
                fs.append(("m", rng.randrange(C["N2"]), rng.randint(0, 1)))
        nf, ob, same = check(C, sector, tX, tZ, P, fs)
        tot += 1
        agree += bool(same)
        if not same:
            print("MISMATCH", i, fs, flush=True)
    print(json.dumps({"code": name, "P": P, "sector": sector, "tests": tot, "agree": agree}), flush=True)


if __name__ == "__main__":
    main()
