"""E-033 timing: seconds per shot per (circ, model, decoder) at p = 3e-3, R = 12, Z basis, single process.
  uv run python -m search.experiments.e033.timing"""
import json, time
import numpy as np
from search.experiments.e026.decoders import sinter_decoders
from search.experiments.e033.common import OUT, noisy

decs = sinter_decoders()
res = {}
for c in ("ibm", "fig12", "u11"):
    for m in ("lam0", "lam1"):
        circ = noisy(c, "Z", 12, 3e-3, m)
        dem = circ.detector_error_model(decompose_errors=False)
        n = 40
        det, obs = circ.compile_detector_sampler(seed=33).sample(n, separate_observables=True)
        for dn, d in decs.items():
            cd = d.compile_decoder_for_dem(dem=dem)
            t = time.time()
            pred = cd.decode_shots_bit_packed(bit_packed_detection_event_data=np.packbits(det, axis=1, bitorder="little"))
            dt = (time.time() - t) / n
            fails = int((np.unpackbits(pred, axis=1, bitorder="little")[:, :obs.shape[1]] != obs).any(axis=1).sum())
            res[f"{c}_{m}_{dn}"] = dict(s_per_shot=round(dt, 4), fails=fails, n=n)
            print(c, m, dn, res[f"{c}_{m}_{dn}"], flush=True)
(OUT / "timing.json").write_text(json.dumps(res, indent=1))
