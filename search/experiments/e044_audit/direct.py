"""E-044 audit: direct sinter sampling (independent of the stratified estimator) at an intermediate p.
Circuits from e044.common.noisy (evaluator template, read-only), decoder stimbposd SinterDecoder_BPOSD with IBM
parameters (prior at the sampled p, as in every earlier direct run).  Preset max_shots, no stopping on errors.
  PYTHONPATH=.:tests uv run python -m search.experiments.e044_audit.direct gross_lam1 3
  PYTHONPATH=.:tests uv run python -m search.experiments.e044_audit.direct bb90_lam0 2
  ... summary <set>"""
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
import sinter

from search.experiments.e044.common import IBM_BPOSD, ROOT, noisy

OUT = ROOT / "results" / "E-044-audit"
OUT.mkdir(parents=True, exist_ok=True)
SETS = {
    "gross_lam1": [("ibm", b, 1.2e-3, "lam1", 4_000_000) for b in "ZX"] + [("g10", b, 1.2e-3, "lam1", 2_500_000) for b in "ZX"],
    "ibm90_lam0": [("ibm90", b, 1.2e-3, "lam0", 1_000_000) for b in "ZX"],
    "bb90_lam0": [("c11", b, 1.2e-3, "lam0", 4_000_000) for b in "ZX"] + [("ibm90", b, 1.2e-3, "lam0", 2_500_000) for b in "ZX"],
}


def run(name, workers):
    from stimbposd import SinterDecoder_BPOSD
    tasks = [sinter.Task(circuit=noisy(c, b, p, m), json_metadata=dict(circ=c, basis=b, p=p, noise=m, exp="E-044-audit"),
                         collection_options=sinter.CollectionOptions(max_shots=n)) for c, b, p, m, n in SETS[name]]
    sinter.collect(num_workers=workers, tasks=tasks, decoders=["bposd"],
                   custom_decoders={"bposd": SinterDecoder_BPOSD(**IBM_BPOSD)},
                   save_resume_filepath=str(OUT / f"direct_{name}.csv"), max_errors=10**9, max_batch_size=20000)


def summary(name):
    for s in sinter.read_stats_from_csv_files(str(OUT / f"direct_{name}.csv")):
        m = s.json_metadata
        print(m["circ"], m["basis"], m["noise"], m["p"], s.shots, s.errors, round(s.seconds))


if __name__ == "__main__":
    if sys.argv[1] == "summary":
        summary(sys.argv[2])
    else:
        run(sys.argv[1], int(sys.argv[2]))
