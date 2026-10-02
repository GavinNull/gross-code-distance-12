"""L2 验证：gross code [[144,12,12]] + IBM depth-8 调度，boundary="paper"，与 auditor（E-002 审计，
joint_xz.py paper1 变体：每轮 pL 0.0537）和论文拟合（arXiv:2308.07915 Table 6 拟合，p=0.006 时 0.0511）比较。

    uv run python scripts/validate_l2_gross.py --p 0.006 --shots 1000 --workers 4 --seed 20261002

只写 results/l2-validation/，不上 leaderboard。本脚本可以 import baselines（评估器自身不能）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from baselines.bb_code import gross_code
from baselines.circuit import memory_circuit
from baselines.schedule import ibm_depth8
from evaluators.codes import CSSCode
from evaluators.l2 import (
    DecoderConfig,
    StopRule,
    build_joint_circuit,
    sample_l2,
)
from evaluators.noise import add_noise

AUDITOR_PAPER1 = {"pL_either": 0.05370219985141578, "boot95": [0.04593759191451163, 0.06276763018006792],
                  "shots": 320, "errors_either": 155, "PZ": 0.296875, "PX": 0.3125,
                  "source": "research/audits/2026-10-02-E-002-scripts/joint_paper1_stdout.txt"}


def paper_fit(p):
    return p ** 5 * np.exp(18.04 + 1337 * p - 96007 * p ** 2)


def setup(rounds):
    bb = gross_code()
    sched = ibm_depth8(bb)
    code = CSSCode.from_checks(bb.HX, bb.HZ, name="gross[[144,12,12]]")
    circs = {"Z": memory_circuit(sched, bb.HX, bb.HZ, bb.logical_z(), rounds, "Z", 0.0),
             "X": memory_circuit(sched, bb.HX, bb.HZ, bb.logical_x(), rounds, "X", 0.0)}
    return code, circs, list(sched.data), bb, sched


def noise_equivalence(bb, sched, circs, p, rounds):
    """sd6 on the noiseless IBM circuit vs. E-002's built-in noise: compare per-basis DEMs."""
    out = {}
    for b in "ZX":
        L = bb.logical_z() if b == "Z" else bb.logical_x()
        e002 = memory_circuit(sched, bb.HX, bb.HZ, L, rounds, b, p).detector_error_model()
        ours = add_noise(circs[b], "sd6", p).detector_error_model()

        def as_dict(dem):
            d = {}
            for inst in dem.flattened():
                if inst.type != "error":
                    continue
                pr = inst.args_copy()[0]
                key = tuple(sorted(str(t) for t in inst.targets_copy()))
                q = d.get(key, 0.0)
                d[key] = q * (1 - pr) + pr * (1 - q)
            return d
        a, c = as_dict(e002), as_dict(ours)
        keys = set(a) | set(c)
        out[b] = {"mechanisms_e002": len(a), "mechanisms_sd6": len(c),
                  "max_abs_prob_diff": max(abs(a.get(k, 0) - c.get(k, 0)) for k in keys)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p", type=float, default=0.006)
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--shots", type=int, default=1000)
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261002)
    ap.add_argument("--out", default=str(ROOT / "results" / "l2-validation"))
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    code, circs, data, bb, sched = setup(a.rounds)
    t0 = time.time()
    jc = build_joint_circuit(code, circs, data, p=a.p, boundary="paper")
    dem = jc.circuit.detector_error_model()
    check = {"joint_build_and_dem_s": round(time.time() - t0, 2), "joint_info": jc.info,
             "num_detectors": dem.num_detectors, "num_errors": dem.num_errors,
             "noise_sd6_vs_e002": noise_equivalence(bb, sched, circs, a.p, a.rounds)}
    print(json.dumps(check, indent=1), flush=True)
    if a.check_only:
        return
    res = sample_l2(code, circs, data, p=a.p, rounds=a.rounds, noise_model="sd6", boundary="paper",
                    decoder=DecoderConfig("bposd"), seed=a.seed,
                    stop=StopRule(max_shots=a.shots, batch_size=a.batch_size), num_workers=a.workers)
    d = res.to_dict()
    pl = d["per_round"]["P_any"]
    fit = float(paper_fit(a.p))
    d["validation"] = {
        "check": check,
        "auditor_paper1": AUDITOR_PAPER1,
        "paper_fit_pL": fit,
        "ours_pL_any": pl["best"],
        "ours_pL_any_interval": [pl["low"], pl["high"]],
        "ratio_to_paper_fit": pl["best"] / fit,
        "ratio_to_auditor": pl["best"] / AUDITOR_PAPER1["pL_either"],
        "command": " ".join(sys.argv),
    }
    tag = f"gross_paper_p{a.p}_r{a.rounds}_seed{a.seed}"
    (out / f"{tag}.json").write_text(json.dumps(d, indent=1, default=float))
    print(res.summary())
    print(json.dumps(d["validation"], indent=1, default=float))


if __name__ == "__main__":
    main()
