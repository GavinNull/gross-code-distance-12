"""E-035 sampling of every pre-registered task with the shot counts of shots.json (fixed max_shots, max_errors 1e9).
Main blocks first, then sensitivity blocks.  Resumable csv results/.../direct/{main,sens}.csv.
  PYTHONPATH=.:tests uv run python -m search.experiments.e035.run_all --workers 6 [--stage main|sens]"""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import sinter

from search.experiments.e026.decoders import sinter_decoders
from search.experiments.e035.common import OUT, na_noisy, rounds_of
from search.experiments.e035.plan import MAIN, blocks


def tasks(stage):
    shots = json.loads((Path(__file__).parent / "shots.json").read_text())
    out = []
    for fam, model, dec, A, cs in blocks():
        if (model in MAIN) != (stage == "main"):
            continue
        N = shots[f"{fam}|{model}|{dec}"]["N"]
        for c in cs:
            for b in "ZX":
                R = rounds_of(c)
                out.append(sinter.Task(circuit=na_noisy(c, b, R, model), decoder=dec,
                                       json_metadata=dict(circ=c, basis=b, R=R, model=model, fam=fam),
                                       collection_options=sinter.CollectionOptions(max_shots=N, max_errors=10 ** 9)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--stage", default="main,sens")
    a = ap.parse_args()
    assert a.workers <= 6
    d = OUT / "direct"
    d.mkdir(parents=True, exist_ok=True)
    for st in a.stage.split(","):
        ts = tasks(st)
        print("stage", st, len(ts), "tasks", flush=True)
        for s in sinter.collect(num_workers=a.workers, tasks=ts, custom_decoders=sinter_decoders(),
                                save_resume_filepath=str(d / f"{st}.csv"), print_progress=False):
            print(s.json_metadata, s.decoder, s.shots, s.errors, round(s.seconds), flush=True)


if __name__ == "__main__":
    main()
