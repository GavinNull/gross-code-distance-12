"""Optional: quick per-round LER comparison g10 vs u11 vs IBM depth 8 under SD6 (evaluator add_noise "sd6", idle noise
on, i.e. E-033's lam1), R = 12, Z and X bases sampled separately, BP-OSD with E-033/E-026's IBM parameters
(stimbposd, max_bp_iters 10000, min_sum, ms 0, osd_cs order 7).  PRESET shot counts (no adaptive stopping).
eps_round = 1 - (1 - eps_Z)^(1/R) + same for X (E-033 convention: eps = eps_Z + eps_X per round); Jeffreys 95%.

  uv run python -m search.experiments.e040_audit_circ.ler run --workers 1
  uv run python -m search.experiments.e040_audit_circ.ler summary
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")

from search.experiments.e040_audit_circ.common import OUT, gross, jdump, load

R = 12
SHOTS = {(0.002, "g10"): 15000, (0.002, "u11"): 15000, (0.002, "ibm"): 60000,
         (0.001, "g10"): 10000, (0.001, "u11"): 10000, (0.001, "ibm"): 10000}
CSV = OUT / "ler.csv"


def run(workers):
    import sinter
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    from search.experiments.e026.common import IBM_BPOSD
    from stimbposd import SinterDecoder_BPOSD
    code = gross()
    tasks = []
    for (p, c), n in SHOTS.items():
        sp = cand.parse_schedule(load(c))
        for b in ("Z", "X"):
            circ = add_noise(cand.memory_circuit(sp, code, b, R), "sd6", p)
            tasks.append(sinter.Task(circuit=circ, json_metadata=dict(circ=c, basis=b, p=p, R=R),
                                     collection_options=sinter.CollectionOptions(max_shots=n)))
    stats = sinter.collect(num_workers=workers, tasks=tasks, decoders=["bposd"],
                           custom_decoders={"bposd": SinterDecoder_BPOSD(**IBM_BPOSD)},
                           save_resume_filepath=str(CSV), max_errors=10**9)
    return stats


def jeffreys(k, n):
    from scipy.stats import beta
    lo = beta.ppf(0.025, k + 0.5, n - k + 0.5) if k > 0 else 0.0
    hi = beta.ppf(0.975, k + 0.5, n - k + 0.5) if k < n else 1.0
    return lo, hi


def per_round(x):
    return 1 - (1 - x) ** (1 / R)


def summary():
    import sinter
    agg = {}
    for s in sinter.read_stats_from_csv_files(str(CSV)):
        m = s.json_metadata
        a = agg.setdefault((m["p"], m["circ"], m["basis"]), [0, 0, 0.0])
        a[0] += s.shots
        a[1] += s.errors
        a[2] += s.seconds
    out = []
    for (p, c, b), (n, k, sec) in sorted(agg.items()):
        lo, hi = jeffreys(k, n)
        out.append({"p": p, "circ": c, "basis": b, "shots": n, "errors": k, "eps_round": per_round(k / n),
                    "lo": per_round(lo), "hi": per_round(hi), "sec": round(sec)})
    for r in out:
        jdump(r, "ler_summary.jsonl")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 1)
    else:
        summary()
