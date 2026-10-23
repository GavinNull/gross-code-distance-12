"""E-035 sensitivity stage with a CPU cap per block (yaml amendment 2): each block is run in shot levels
(step = max(50, N/8)); after each level, if the block's cumulative sinter seconds >= its allowance, the block stops;
it also stops at N.  The stop depends only on CPU seconds and the level, never on failure counts.  Global stop when
main + sens sinter seconds reach 48 h.  Same csv (direct/sens.csv), sinter resume counts existing shots.
  PYTHONPATH=.:tests uv run python -m search.experiments.e035.sens_capped --workers 6"""
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")

import sinter

from search.experiments.e026.decoders import sinter_decoders
from search.experiments.e035.common import OUT, na_noisy, rounds_of
from search.experiments.e035.plan import MAIN, blocks

GLOBAL_CAP_S = 48 * 3600


def secs(path):
    tot = defaultdict(float)
    if not Path(path).exists():
        return tot
    for s in sinter.read_stats_from_csv_files(str(path)):
        m = s.json_metadata
        tot[(m["fam"], m["model"], s.decoder)] += s.seconds
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    assert a.workers <= 6
    shots = json.loads((Path(__file__).parent / "shots.json").read_text())
    sens = OUT / "direct" / "sens.csv"
    main_s = sum(secs(OUT / "direct" / "main.csv").values())
    log = []
    for fam, model, dec, A, cs in blocks():
        if model in MAIN:
            continue
        N = shots[f"{fam}|{model}|{dec}"]["N"]
        step = max(50, N // 8)
        level = 0
        while level < N:
            used = secs(sens)
            if used[(fam, model, dec)] >= A:
                log.append(dict(block=[fam, model, dec], stopped="allowance", level=level, sec=used[(fam, model, dec)]))
                break
            if main_s + sum(used.values()) >= GLOBAL_CAP_S:
                log.append(dict(block=[fam, model, dec], stopped="global cap", level=level))
                break
            level = min(N, level + step)
            ts = [sinter.Task(circuit=na_noisy(c, b, rounds_of(c), model), decoder=dec,
                              json_metadata=dict(circ=c, basis=b, R=rounds_of(c), model=model, fam=fam),
                              collection_options=sinter.CollectionOptions(max_shots=level, max_errors=10 ** 9))
                  for c in cs for b in "ZX"]
            sinter.collect(num_workers=a.workers, tasks=ts, custom_decoders=sinter_decoders(),
                           save_resume_filepath=str(sens), print_progress=False)
        else:
            log.append(dict(block=[fam, model, dec], stopped="N reached", level=level, sec=secs(sens)[(fam, model, dec)]))
        print(log[-1], flush=True)
    (OUT / "sens_capped_log.json").write_text(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
