"""E-016：低权重逻辑错误的细节（各权重的个数、先验乘积之和、拆分平局比例）。experimenter。
    PYTHONPATH=. uv run python -m search.experiments.e016.lowweight_detail
"""
import json
import numpy as np
from search.experiments.e016.common import CIRCS, OUT, build_model
from search.experiments.e016.analyze_lowweight import failing_sets

out = {}
for c in CIRCS:
    m = build_model(c, 0.001)
    for s in "ZX":
        sec = m.sectors[s]
        clo = [tuple(x) for x in json.loads((OUT / "lowweight" / f"{c}_{s}_logicals.json").read_text())["closure"]]
        row = {}
        for W in sorted({len(x) for x in clo}):
            Ls = [x for x in clo if len(x) == W]
            P = np.array([np.prod(sec.priors[list(x)]) for x in Ls])
            row[W] = {"n": len(Ls), "sum_prod_q": float(P.sum()), "median_q": float(np.median(sec.priors[np.array(Ls)]))}
            for t in ((W // 2,) if W in (8, 10) else ()):
                FS, FV, nsub = failing_sets(sec, Ls, t)
                Ct = float((FV * np.prod(sec.priors[FS], axis=1)).sum())
                row[W][f"split_t{t}"] = {"n_failing": float(FV.sum()), "tie_fraction": float((FV == 0.5).mean()),
                                        "C": Ct}
        out[f"{c}_{s}"] = row
        print(c, s, json.dumps(row), flush=True)
print("median sector prior (p=1e-3):", {c: float(np.median(build_model(c, 0.001).sectors["Z"].priors)) for c in CIRCS})
(OUT / "lowweight_detail.json").write_text(json.dumps(out, indent=1))
