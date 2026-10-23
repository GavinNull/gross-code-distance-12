"""E-035 sanity: rotated surface-code memory (stim generated, noiseless) + the neutral-atom post-processor, decoded with
pymatching, compared with the d = 3 / d = 5 repeated-QEC numbers of Bluvstein et al. 2506.20661.
Timing set cur_slow (4 CX layers x 470 us + 2570 us readout = 4.45 ms per round, the surface-code round of 2506.20661).
  uv run python -m search.experiments.e035.surface_sanity --shots 200000 --workers 2"""
import argparse
import json
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import sinter
import stim

from search.experiments.e035.common import OUT
from search.experiments.e035.na_noise import apply, get_params


def circ(d, R, basis, tag):
    nl = stim.Circuit.generated(f"surface_code:rotated_memory_{basis.lower()}", distance=d, rounds=R)
    anc = set()
    for inst in nl.flattened():
        if inst.name in ("MR", "MRX"):
            anc.update(t.value for t in inst.targets_copy())
    return apply(nl, get_params(tag), None, anc_set=anc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", type=int, default=200000)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--models", default="cur_slow,cur")
    a = ap.parse_args()
    tasks = []
    for m in a.models.split(","):
        for d in (3, 5):
            for b in "ZX":
                tasks.append(sinter.Task(circuit=circ(d, d, b, m), json_metadata=dict(d=d, R=d, basis=b, model=m)))
    OUT.mkdir(parents=True, exist_ok=True)
    stats = sinter.collect(num_workers=a.workers, tasks=tasks, decoders=["pymatching"], max_shots=a.shots,
                           max_errors=10 ** 9, save_resume_filepath=str(OUT / "surface_sanity.csv"))
    for s in stats:
        print(s.json_metadata, s.shots, s.errors, flush=True)


if __name__ == "__main__":
    main()
