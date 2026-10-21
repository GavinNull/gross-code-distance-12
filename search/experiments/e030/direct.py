"""E-030 direct sinter sampling, R-round memory (default R = 10 = d, IBM's N_c), Z and X bases sampled separately,
BP-OSD (IBM parameters) and Relay-BP (relay5) -- identical decoders for every circuit; noise model lam<x>.

  uv run python -m search.experiments.e030.direct --circs c11,ibm --ps 0.004,0.003 --model lam1 \
      --max-errors 100 --max-shots 100000 --workers 6 --tag a1
Resumable: results/E-030-bb90-period-ler/direct/<tag>.csv."""
import argparse

import sinter

from search.experiments.e026.decoders import sinter_decoders
from search.experiments.e030.common import OUT, noisy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circs", required=True)
    ap.add_argument("--bases", default="Z,X")
    ap.add_argument("--ps", required=True)
    ap.add_argument("--model", default="lam1")
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--decoders", default="bposd,relay5")
    ap.add_argument("--max-errors", type=int, default=100)
    ap.add_argument("--max-shots", type=int, default=100000)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    assert a.workers <= 8
    tasks = []
    for m in a.model.split(","):
        for c in a.circs.split(","):
            for b in a.bases.split(","):
                for p in map(float, a.ps.split(",")):
                    tasks.append(sinter.Task(circuit=noisy(c, b, a.rounds, p, m),
                                             json_metadata=dict(circ=c, basis=b, p=p, R=a.rounds, noise=m)))
    d = OUT / "direct"
    d.mkdir(parents=True, exist_ok=True)
    stats = sinter.collect(num_workers=a.workers, tasks=tasks, decoders=a.decoders.split(","),
                           custom_decoders=sinter_decoders(), max_errors=a.max_errors, max_shots=a.max_shots,
                           save_resume_filepath=str(d / f"{a.tag}.csv"), print_progress=False)
    for s in stats:
        print(s.json_metadata, s.decoder, s.shots, s.errors, round(s.seconds), flush=True)


if __name__ == "__main__":
    main()
