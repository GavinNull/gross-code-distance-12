"""Small codes: enumerate all extended logicals of weight w <= d-1 and decide their bulk lift with d-1-w extra
zero-image faults (readout flips) allowed (Lemma 2 generalised: w distinct columns + z zero-image faults + c cancelling
pairs with w + z + 2c <= d-1; cancelling pairs are handled by allowing repeated columns, see --pairs).
  uv run python -m search.theory.B.small --code kunlun-bb18 --spec search/experiments/e038/bb18_n8_d4_spec.json --d 4
"""
import argparse, json
from search.theory.B.bulk import Sched, bulk_lift, code_mats, load_spec
from search.theory.B.check_lists import colopts_for
from search.theory.B.enum import enumerate_w

ap = argparse.ArgumentParser()
ap.add_argument("--code"); ap.add_argument("--spec"); ap.add_argument("--d", type=int)
ap.add_argument("--bases", default="ZX")
a = ap.parse_args()
mats = code_mats(a.code)
out = {"spec": a.spec}
for b in a.bases:
    sch = Sched(load_spec(a.spec), mats, b)
    cols, zero = sch.ext()
    assert not zero
    rows = {}
    for w in range(1, a.d):
        L = enumerate_w(sch, cols, w)
        if not L:
            continue
        lifted = []
        for S in L:
            co = colopts_for(S, cols, sch)
            # cancelling pairs: a repeated column = two faults with equal image; allowed if budget permits
            budget = a.d - 1 - w
            ok = bulk_lift(co, flips=budget) is not None
            if not ok and budget >= 2:
                for j in range(len(S)):
                    if bulk_lift(co + [co[j]], flips=budget - 2) is not None:
                        ok = True; break
            if ok:
                lifted.append(S)
        rows[w] = {"n": len(L), "lifted": len(lifted)}
    out[b] = {"ncols": len(cols), "pairing_violations": len(sch.pairing_ok()), "by_weight": rows}
print(json.dumps(out))
