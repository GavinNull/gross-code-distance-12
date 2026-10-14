"""E-026 timing: decode time per shot (single process).  uv run python -m search.experiments.e026.timing p R n"""
import sys, time, json
import numpy as np
from search.experiments.e026.common import CIRCS, noisy
from search.experiments.e026.decoders import sinter_decoders

p, R, n = float(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
decs = sinter_decoders()
for c in CIRCS:
    for b in "Z":
        circ = noisy(c, b, R, p)
        dem = circ.detector_error_model()
        dets, obs = circ.compile_detector_sampler(seed=26000).sample(n, separate_observables=True, bit_packed=True)
        for nm, D in decs.items():
            t = time.process_time()
            cd = D.compile_decoder_for_dem(dem=dem)
            t1 = time.process_time()
            pred = cd.decode_shots_bit_packed(bit_packed_detection_event_data=dets)
            t2 = time.process_time()
            print(c, b, nm, f"compile {t1-t:.2f}s decode {(t2-t1)/n*1000:.1f} ms/shot", flush=True)
