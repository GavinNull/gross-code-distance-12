"""E-025 step 1 (structure): deletion-based minimal core of modelled logicals (orbit reps of the family) for which
blocking is impossible under the given restriction (e.g. colour-symmetric, P = 24, window of unit X0 <= 14).
Each test = a fresh in-process nogood CEGAR (cegar_lib) on the subset (UNSAT keeps the removal).  Result is
minimal w.r.t. single deletions (each remaining rep was tested for removal and the rest became MODEL_SAT).

    PYTHONPATH=.:tests uv run python -m search.experiments.e025.core --P 24 --maxwin 14 --winunits X0 --tag core_w14X0
"""
import argparse
import json
import time
from pathlib import Path

import search.experiments.e021.nwfull as NF
from search.experiments.e025.cegar_lib import Cegar
from search.experiments.e025.exact_cp import make_family

OUT = Path("results/E-025-gross12-perchk-period")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=int, required=True)
    ap.add_argument("--sub", default="1,2;0,3")
    ap.add_argument("--maxwin", type=int, default=None)
    ap.add_argument("--winunits", default="")
    ap.add_argument("--max_sec", type=float, default=900)
    ap.add_argument("--start", default="", help="json file with a starting UNSAT subset")
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    F = make_family(a.sub)
    recs, _ = NF.prepare_full(F, "XZ")
    wu = {(x[0], int(x[1:])) for x in a.winunits.split(",")} if a.winunits else None
    t0 = time.time()
    ntest = [0]

    def test(keep):
        ntest[0] += 1
        C = Cegar(F, a.P, [recs[k] for k in keep], maxwin=a.maxwin, winunits=wu)
        st, t, info = C.run(a.max_sec)
        return st, info

    keep = json.load(open(a.start)) if a.start else list(range(len(recs)))
    st, info = test(keep)
    print("full:", len(keep), st, info, flush=True)
    assert st == "UNSAT"
    chunk = max(1, len(keep) // 4)
    while True:
        i = 0
        while i < len(keep):
            trial = keep[:i] + keep[i + chunk:]
            st, info = test(trial)
            print(f"size {len(keep)} chunk {chunk} rm [{i}:{i + chunk}] -> {st} it={info['it']} "
                  f"({time.time() - t0:.0f}s)", flush=True)
            if st == "UNSAT":
                keep = trial
            else:
                i += chunk
        if chunk == 1:
            break
        chunk = max(1, chunk // 2)
    out = {"P": a.P, "sub": a.sub, "maxwin": a.maxwin, "winunits": a.winunits, "core": keep, "tests": ntest[0],
           "sec": round(time.time() - t0), "recs": [{"kind": recs[k]["kind"], "S": list(recs[k]["S"]),
                                                    "evs": [[str(x) for x in e] for e in recs[k]["evs"]]} for k in keep]}
    (OUT / f"{a.tag}.json").write_text(json.dumps(out))
    print("CORE", len(keep), keep, flush=True)


if __name__ == "__main__":
    main()
