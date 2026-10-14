"""E-026 stage A: direct sinter sampling, R-round memory, both bases, BP-OSD (IBM) and Relay-BP (relay5).

  uv run python -m search.experiments.e026.direct --circs p18,fig12,ibm --ps 0.005,0.004 --rounds 12 \
      --decoders bposd,relay5 --max-errors 100 --max-shots 2000 --workers 6 --tag a1

Resumable: results/E-026-gross-ler/direct/<tag>.csv (sinter resume file).  sinter 'seconds' = decoder-process CPU-ish
wall time per worker, summed (used as the CPU ledger)."""
import argparse
import sinter
from search.experiments.e026.common import OUT, noisy
from search.experiments.e026.decoders import sinter_decoders


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circs", default="p18,fig12,ibm")
    ap.add_argument("--bases", default="Z,X")
    ap.add_argument("--ps", required=True)
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--decoders", default="bposd,relay5")
    ap.add_argument("--max-errors", type=int, default=100)
    ap.add_argument("--max-shots", type=int, default=10000)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--idle", default="sd6", help="sd6 | noidle (uniform_depolarizing idle=False, sensitivity only)")
    a = ap.parse_args()
    assert a.workers <= 6
    tasks = []
    for c in a.circs.split(","):
        for b in a.bases.split(","):
            for p in map(float, a.ps.split(",")):
                if a.idle == "sd6":
                    circ = noisy(c, b, a.rounds, p)
                else:
                    from evaluators.noise import add_noise
                    from search.experiments.e026.common import noiseless
                    circ = add_noise(noiseless(c, b, a.rounds), "uniform_depolarizing", p, idle=False)
                tasks.append(sinter.Task(circuit=circ, json_metadata=dict(circ=c, basis=b, p=p, R=a.rounds,
                                                                           noise=a.idle)))
    d = OUT / "direct"
    d.mkdir(parents=True, exist_ok=True)
    stats = sinter.collect(num_workers=a.workers, tasks=tasks, decoders=a.decoders.split(","),
                           custom_decoders=sinter_decoders(), max_errors=a.max_errors, max_shots=a.max_shots,
                           save_resume_filepath=str(d / f"{a.tag}.csv"), print_progress=False)
    for s in stats:
        print(s.json_metadata, s.decoder, s.shots, s.errors, round(s.seconds), flush=True)


if __name__ == "__main__":
    main()
