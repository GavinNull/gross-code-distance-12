"""E-030 step 1: c13 = c16 with the all-empty layers removed (generic: drop every time step mod P that carries no
prep / CNOT / meas of any check), legality (validate_schedule + L0 syntax/semantics, no distance), determinism,
and DEM signature subset vs the source circuit for R = 1..Rmax, both bases (SD6, p = 1e-3, decompose_errors=False).

    PYTHONPATH=.:tests uv run python -m search.experiments.e030.build search/experiments/e028/c16_spec.json \
        search/experiments/e030/c13_spec.json --Rmax 12
"""
import argparse
import json
import time
from pathlib import Path

from evaluators.candidate import build_circuits, parse_schedule, validate_schedule
from evaluators.l0 import L0Constraints, check_l0
from evaluators.noise import add_noise
from search.experiments.e028.common import css
from search.experiments.e029.export import dem_columns

OUT = Path("results/E-030-bb90-period-ler")


def compress(d):
    P = d["period"]
    used = set()
    for key in ("x_checks", "z_checks"):
        for c in d[key]:
            used.add(c["prep"] % P); used.add(c["meas"] % P)
            used.update(t % P for _, t in c["cnots"])
    keep = sorted(used)
    m = {t: i for i, t in enumerate(keep)}
    out = {"format": d["format"], "period": len(keep), "x_checks": [], "z_checks": []}
    for key in ("x_checks", "z_checks"):
        for c in d[key]:
            out[key].append({"prep": m[c["prep"]], "meas": m[c["meas"]], "cnots": [[q, m[t]] for q, t in c["cnots"]]})
    return out, sorted(set(range(P)) - used)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--Rmax", type=int, default=12)
    a = ap.parse_args()
    src = json.load(open(a.src))
    new, dropped = compress(src)
    Path(a.dst).write_text(json.dumps(new))
    code = css()
    s_old = parse_schedule(src).canonical(); s_new = parse_schedule(new).canonical()
    res = {"src": a.src, "dst": a.dst, "P_old": src["period"], "P_new": new["period"], "dropped": dropped}
    res["validate"] = validate_schedule(s_new, code)
    t0 = time.time()
    rep = check_l0(build_circuits(s_new, code, 3), code, "both", L0Constraints(rounds=3))
    res["L0"] = {c.name: c.status for c in rep.checks}
    res["L0_passed"] = all(c.status in ("pass", "skipped") for c in rep.checks)
    res["L0_sec"] = round(time.time() - t0, 1)
    print(json.dumps(res), flush=True)
    sub = {}
    for R in range(1, a.Rmax + 1):
        for b in "ZX":
            co = build_circuits(s_old, code, R)[b]; cn = build_circuits(s_new, code, R)[b]
            assert co.num_detectors == cn.num_detectors and co.num_observables == cn.num_observables
            cn.detector_error_model(allow_gauge_detectors=False)          # determinism (raises if not)
            _, Co = dem_columns(add_noise(co, "sd6", 1e-3)); _, Cn = dem_columns(add_noise(cn, "sd6", 1e-3))
            so, sn = set(Co), set(Cn)
            sub[f"{b}R{R}"] = {"n_old": len(so), "n_new": len(sn), "subset": sn <= so, "only_new": len(sn - so)}
            print(R, b, sub[f"{b}R{R}"], flush=True)
    res["dem_subset"] = sub
    res["all_subset"] = all(v["subset"] for v in sub.values())
    (OUT / f"build_{Path(a.dst).stem}.json").write_text(json.dumps(res, indent=1))
    print("ALL_SUBSET", res["all_subset"])


if __name__ == "__main__":
    main()
