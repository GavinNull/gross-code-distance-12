"""E-021 follow-up (2d): enumerate many model candidates of nwfull (colour-symmetric non-wrapping frames, Fig. 12
extended-code class, all modelled weight-11 logicals blocked in the bulk model), compress each (compress.py: the
minimal frame depth for its relative order), and keep the shortest periods.  Each found candidate is excluded by a
clause over its "related" relations (pairs of class-label items sharing a data qubit or an ancilla), so the next
candidate has a different gate DAG.  A depth bound can be imposed lazily: candidates whose compressed period exceeds
--pmax are excluded the same way (the search then continues).

    PYTHONPATH=.:tests uv run python -m search.experiments.e021.nwenum --n 200 --sec 1800
"""
import argparse
import itertools
import json
import time
from pathlib import Path

from search.experiments.e021.compress import compress
from search.experiments.e021.lift21 import spec_from_ranks
from search.experiments.e021.mono import fig12_labels
from search.experiments.e021.nwfull import evaluate_full, nogood_full, prepare_full
from search.experiments.e021.nwsat import Family, Model, bad_triples_all, parse_sub

OUT = Path("results/E-021-gross-new-orders")
N2 = 72


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--sec", type=float, default=1800)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    t0 = time.time()
    F = Family(parse_sub("1,2;0,3"))
    recs, skipped = prepare_full(F, "XZ")
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
    # related item pairs
    rel = set()
    for q in range(144):
        its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
        rel.update(itertools.combinations(its, 2))
    for ty in "XZ":
        for k in range(F.nc):
            rel.update(itertools.combinations(sorted(F.idx[(ty, k, l)] for l in range(6)), 2))
    rel = sorted(rel)
    import random
    rng = random.Random(a.seed)
    found = []
    outp = OUT / "nwenum.jsonl"
    while time.time() - t0 < a.sec and len(found) < a.n:
        # randomise the search a little via phases
        try:
            M.S.set_phases([v if rng.random() < 0.5 else -v for v in range(1, M.pool.top + 1)])
        except Exception:
            pass
        rank = M.solve()
        if rank is None:
            print("exhausted", flush=True)
            break
        lif = evaluate_full(F, recs, rank)
        if lif:
            for r, cons, pi in lif:
                nogood_full(M, cons, pi)
            continue
        sd = spec_from_ranks(F.cls, rank, F.items, len(F.items))
        sdc, _, Pc = compress(sd)
        found.append(Pc)
        rec = {"n": len(found), "P": Pc, "rank": rank, "sec": round(time.time() - t0, 1)}
        with open(outp, "a") as f:
            f.write(json.dumps(rec) + "\n")
        (OUT / f"nwenum_spec{len(found)}.json").write_text(json.dumps(sdc))
        if len(found) % 10 == 0:
            print(len(found), "min P", min(found), f"{time.time() - t0:.0f}s", flush=True)
        # exclude this relation pattern
        M.S.add_clause([(-M.lt(i, j) if rank[i] < rank[j] else M.lt(i, j)) for i, j in rel])
    print("done", len(found), "min P", min(found) if found else None, flush=True)


if __name__ == "__main__":
    main()
