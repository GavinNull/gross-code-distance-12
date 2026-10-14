"""E-026b stage A/V: direct sinter sampling with the post-processed noise models (lam<x>, si1000cx).
  uv run python -m search.experiments.e026b.direct --model lam0 --circs p18,fig12,ibm --ps 0.004,0.003 \
      --decoders bposd,relay5 --max-errors 60 --max-shots 20000 --workers 4 --tag A_lam0_hi
Resumable: results/E-026b-idle-sensitivity/direct/<tag>.csv."""
import argparse
import sinter
from search.experiments.e026b.common import OUT, noisy
from search.experiments.e026.decoders import sinter_decoders


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--circs", default="p18,fig12,ibm")
    ap.add_argument("--bases", default="Z,X")
    ap.add_argument("--ps", required=True)
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--decoders", default="bposd,relay5")
    ap.add_argument("--max-errors", type=int, default=60)
    ap.add_argument("--max-shots", type=int, default=10000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    assert a.workers <= 4
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
