"""E-035 timing: decode-time per shot for every pre-registered task.  Records ONLY seconds per shot (no failure counts:
observables are discarded).  seed 35.  4 worker processes."""
import json
import os
import time
from multiprocessing import Pool

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from search.experiments.e035.common import OUT, na_noisy, rounds_of
from search.experiments.e035.plan import blocks

NSHOT = {"bposd": 24, "relay5": 48}


def one(args):
    circ, basis, model, dec = args
    from search.experiments.e026.decoders import sinter_decoders
    c = na_noisy(circ, basis, rounds_of(circ), model)
    dem = c.detector_error_model(decompose_errors=False)
    d = sinter_decoders()[dec].compile_decoder_for_dem(dem=dem)
    smp = c.compile_detector_sampler(seed=35)
    det, _obs = smp.sample(NSHOT[dec], bit_packed=True, separate_observables=True)
    del _obs  # never looked at
    d.decode_shots_bit_packed(bit_packed_detection_event_data=det[:2])  # warm-up
    t0 = time.process_time()
    d.decode_shots_bit_packed(bit_packed_detection_event_data=det[2:])
    t = (time.process_time() - t0) / (NSHOT[dec] - 2)
    return f"{circ}|{basis}|{model}|{dec}", t


def main():
    tasks = sorted({(c, b, m, dec) for fam, m, dec, A, cs in blocks() for c in cs for b in "ZX"})
    with Pool(4) as pool:
        res = dict(pool.imap_unordered(one, tasks))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "timing.json").write_text(json.dumps(res, indent=1, sort_keys=True))
    for k in sorted(res):
        print(k, round(res[k], 4))


if __name__ == "__main__":
    main()
