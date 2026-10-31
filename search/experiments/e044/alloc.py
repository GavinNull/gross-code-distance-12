"""E-044 phase B shot allocation (fixed before phase B; uses NO failure counts -- deviation from the yaml rule, which
needed pilot f-hat, but the pilot gave 0 failures below k ~ 40 for the IBM circuits, so f-hat was unusable).
Rule: n_k prop. to max_{p in TARGET} P_p(K = k) * (k / 10)^3 / sqrt(c_k) for k in [KLO, KHI] (k^3 ~ sqrt of an
assumed f_k ~ k^6; c_k = measured pilot decode seconds per shot at k, interpolated), scaled so that
sum n_k c_k = the task's CPU allotment; floor 200 per k.
  uv run python -m search.experiments.e044.alloc <circ> <basis> <model> <cpu_seconds>  -> alloc/main_<...>.json"""
import json
import sys

import numpy as np

from search.experiments.e044.analysis import pk
from search.experiments.e044.common import OUT

TARGET = (1e-3, 7e-4, 5e-4)


def main(circ, basis, model, sec):
    KLO, KHI = (5, 40) if circ in ("g10", "u11", "ibm") else (4, 32)
    t = {}
    for ln in (OUT / "strat" / f"{circ}_{basis}_{model}_pdec0.001.jsonl").read_text().splitlines():
        r = json.loads(ln)
        a = t.setdefault(r["k"], [0, 0.0])
        a[0] += r["n"]; a[1] += r["sec_dec"]
    kk = np.array(sorted(t)); cc = np.array([t[k][1] / t[k][0] for k in kk])
    ks = np.arange(KLO, KHI + 1)
    c = np.exp(np.interp(np.log(ks), np.log(kk), np.log(np.maximum(cc, 1e-4))))
    P = np.max([pk(circ, basis, model, p)[ks] for p in TARGET], axis=0)
    w = P * (ks / 10.0) ** 3 / np.sqrt(c)
    n = w / np.sum(w * c) * sec
    n = np.maximum(200, np.round(n / 100) * 100).astype(int)
    alloc = {int(k): int(x) for k, x in zip(ks, n)}
    f = OUT / "alloc" / f"main_{circ}_{basis}_{model}.json"
    f.write_text(json.dumps(alloc))
    print(circ, basis, model, "expected sec", round(float(np.sum(n * c))), "total shots", int(n.sum()),
          {k: alloc[k] for k in list(alloc)[::5]})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]))
