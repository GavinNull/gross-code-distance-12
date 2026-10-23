"""E-035 direct sinter sampling under the neutral-atom model (na_noise), fixed pre-registered shot counts
(max_errors set huge so sinter stops only on max_shots), Z and X sampled separately, BP-OSD (IBM parameters) and
Relay-BP (relay5) from e026.decoders, identical for every circuit.  R: gross 12, [[90]] 10.

  uv run python -m search.experiments.e035.direct --circs u11,ibm --models cur --shots 2000 --workers 6 --tag t
Resumable: results/E-035-neutral-atom-ler/direct/<tag>.csv  (json_metadata carries circ, basis, R, model)."""
import argparse
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import sinter

from search.experiments.e026.decoders import sinter_decoders
from search.experiments.e035.common import OUT, na_noisy, rounds_of


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circs", required=True)
    ap.add_argument("--bases", default="Z,X")
    ap.add_argument("--models", required=True)
    ap.add_argument("--decoders", default="bposd,relay5")
    ap.add_argument("--shots", type=int, required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    assert a.workers <= 6
    tasks = []
    for m in a.models.split(","):
        for c in a.circs.split(","):
            for b in a.bases.split(","):
                R = rounds_of(c)
                tasks.append(sinter.Task(circuit=na_noisy(c, b, R, m),
                                         json_metadata=dict(circ=c, basis=b, R=R, model=m)))
    d = OUT / "direct"
    d.mkdir(parents=True, exist_ok=True)
    stats = sinter.collect(num_workers=a.workers, tasks=tasks, decoders=a.decoders.split(","),
                           custom_decoders=sinter_decoders(), max_errors=10 ** 9, max_shots=a.shots,
                           save_resume_filepath=str(d / f"{a.tag}.csv"), print_progress=False)
    for s in stats:
        print(s.json_metadata, s.decoder, s.shots, s.errors, round(s.seconds), flush=True)


if __name__ == "__main__":
    main()
