"""E-004: run evaluators.l2.sample_l2 on one candidate with a named decoder preset.

  PYTHONPATH=. uv run python -m search.proxy.run_l2 --cand G-ibm --decoder full --seed 1 \
      --min-sector-errors 300 --max-shots 20000 --workers 4 [--rounds-mult 2] [--tag ...]

Writes results/E-004-proxy-fidelity/l2/<tag>.json (L2Result.to_dict() + candidate meta + per-batch counts) and keeps
the per-batch files (with per-shot failure bits) under results/E-004-proxy-fidelity/batches/<tag>/ for bootstrap.
Uses only the public evaluator entry point sample_l2.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from evaluators.l2 import DecoderConfig, StopRule, sample_l2
from search.proxy import candidates as C

OUT = Path("results/E-004-proxy-fidelity")

DECODERS = {
    "full": {},                                                   # E-002 / IBM: max_iter 10000, osd_cs 7
    "osd0_it100": dict(max_iter=100, osd_method="osd0", osd_order=0),
    "osd0_it200": dict(max_iter=200, osd_method="osd0", osd_order=0),
    "cs1_it100": dict(max_iter=100, osd_method="osd_cs", osd_order=1),
    "cs2_it200": dict(max_iter=200, osd_method="osd_cs", osd_order=2),
    "cs2_it100": dict(max_iter=100, osd_method="osd_cs", osd_order=2),
    "cs7_it200": dict(max_iter=200, osd_method="osd_cs", osd_order=7),
    "cs7_it1000": dict(max_iter=1000, osd_method="osd_cs", osd_order=7),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--decoder", default="full", choices=sorted(DECODERS))
    ap.add_argument("--p", type=float, default=0.004)
    ap.add_argument("--rounds", type=int, default=None, help="default: code distance d")
    ap.add_argument("--rounds-mult", type=int, default=1, help="rounds = mult * d (if --rounds not given)")
    ap.add_argument("--boundary", default="paper")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--min-sector-errors", type=int, default=300)
    ap.add_argument("--max-shots", type=int, default=20000)
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    C.load_bad(OUT / "bad_schedules.json")
    css, circuits, dq, cand = C.build(a.cand)
    rounds = a.rounds or a.rounds_mult * cand.d
    tag = a.tag or f"{a.cand}__{a.decoder}__r{rounds}__{a.boundary}__s{a.seed}"
    bdir = OUT / "batches" / tag
    if bdir.exists():
        shutil.rmtree(bdir)
    bdir.parent.mkdir(parents=True, exist_ok=True)
    (OUT / "l2").mkdir(parents=True, exist_ok=True)
    stop = StopRule(max_shots=a.max_shots, max_errors=a.min_sector_errors, min_sector_errors=a.min_sector_errors,
                    batch_size=a.batch_size)
    t0 = time.time()
    res = sample_l2(css, circuits, dq, p=a.p, rounds=rounds, noise_model="sd6", boundary=a.boundary,
                    decoder=DecoderConfig("bposd", DECODERS[a.decoder]), seed=a.seed, stop=stop,
                    num_workers=a.workers, work_dir=bdir, keep_batches=True)
    d = res.to_dict()
    per_batch = []
    for f in sorted(bdir.glob("batch_*.json")):
        r = json.loads(f.read_text())
        per_batch.append({k: r[k] for k in ("index", "shots", "fail_Z", "fail_X", "fail_any", "fail_both", "cpu_s")})
    used = d["counts"]["batches_used"]
    cpu_used = sum(b["cpu_s"] for b in per_batch if b["index"] < used)
    d["e004"] = {"candidate": {**cand.__dict__, "Q": cand.Q, "kd2_n": cand.kd2_n}, "decoder_preset": a.decoder,
                 "tag": tag, "rounds": rounds, "wall_s": round(time.time() - t0, 1),
                 "cpu_s_per_shot_used": cpu_used / max(1, d["counts"]["shots"]),
                 "cpu_s_all_batches": sum(b["cpu_s"] for b in per_batch),
                 "B_per_logical_per_round": d["per_round"]["P_any"]["best"] / cand.k,
                 "per_batch": per_batch}
    (OUT / "l2" / f"{tag}.json").write_text(json.dumps(d, indent=1, default=str))
    print(res.summary())
    print(json.dumps({k: d["e004"][k] for k in ("tag", "wall_s", "cpu_s_per_shot_used", "cpu_s_all_batches",
                                                  "B_per_logical_per_round")}))


if __name__ == "__main__":
    main()
