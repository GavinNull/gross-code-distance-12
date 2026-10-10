"""E-021 follow-up (3b): classical control with the same sampler as the CEGAR minus the logical nogoods.
Random legal + deterministic colour-symmetric non-wrapping frames in the Fig. 12 extended-code class from the
incremental SAT model (nwsat.Model + class constraints, as in nwenum.py) with random phases; each sample is excluded
afterwards (relation-pattern clause).  Per sample: modelled lifting count; exact lift (liftscreen) of every sample
whose model count is 0 and of a 10% random subset.

    PYTHONPATH=.:tests uv run python -m search.experiments.e021.randsat --sec 900 --seed 7
"""
import argparse
import itertools
import json
import random
import time
from pathlib import Path

from search.experiments.e021.lift21 import spec_from_ranks
from search.experiments.e021.liftscreen import screen
from search.experiments.e021.mono import fig12_labels
from search.experiments.e021.nwfull import evaluate_full, prepare_full
from search.experiments.e021.nwsat import Family, Model, bad_triples_all, parse_sub

OUT = Path("results/E-021-gross-new-orders")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sec", type=float, default=900)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    t0 = time.time()
    F = Family(parse_sub("1,2;0,3"))
    recs, _ = prepare_full(F, "XZ")
    M = Model(F, bad_triples_all())
    f12 = fig12_labels()
    for ty in "XZ":
        for k in range(F.nc):
            o = f12[ty][F.reps[k]]
            it_ = lambda lab: F.idx[(ty, k, lab)]  # noqa: E731
            rev = M.pool.id(("rev", ty, k))

            def first(U, guard):
                for x in U:
                    for y in range(6):
                        if y not in U:
                            M.S.add_clause(guard + [M.lt(it_(x), it_(y))])
            first(o[:2], [rev]); first(o[:3], [rev]); first(o[:4], [rev])
            first(o[4:], [-rev]); first(o[3:], [-rev]); first(o[2:], [-rev])
    rel = set()
    for q in range(144):
        rel.update(itertools.combinations(sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]}), 2))
    rel = sorted(rel)
    hist, exact, n = {}, [], 0
    while time.time() - t0 < a.sec:
        try:
            M.S.set_phases([v if rng.random() < 0.5 else -v for v in range(1, M.pool.top + 1)])
        except Exception:
            pass
        rank = M.solve()
        if rank is None:
            break
        n += 1
        k = len(evaluate_full(F, recs, rank))
        hist[k] = hist.get(k, 0) + 1
        if k == 0 or rng.random() < 0.1:
            sp = OUT / "randsat_tmp.json"
            sp.write_text(json.dumps(spec_from_ranks(F.cls, rank, F.items, len(F.items))))
            r = screen(str(sp), 6); r.update(model=k); exact.append(r)
        M.S.add_clause([(-M.lt(i, j) if rank[i] < rank[j] else M.lt(i, j)) for i, j in rel])
    s = {"samples": n, "model_hist": {str(k): v for k, v in sorted(hist.items())}, "exact": exact,
         "certified": sum(r["status"] == "CERTIFIED" for r in exact), "sec": round(time.time() - t0, 1)}
    (OUT / "randsat_summary.json").write_text(json.dumps(s, indent=1))
    print({k: v for k, v in s.items() if k != "exact"}, "exact checked", len(exact))


if __name__ == "__main__":
    main()
