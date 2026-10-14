"""E-026b: seconds per shot per (model, circ, decoder) at a few p, single process, Z basis, R = 12.
  uv run python -m search.experiments.e026b.timing --models lam0,lam0.3 --ps 0.003,0.0015 --shots 20"""
import argparse, json, time
import numpy as np
from search.experiments.e026b.common import OUT, noisy
from search.experiments.e026.decoders import sinter_decoders

ap = argparse.ArgumentParser()
ap.add_argument("--models", default="lam0"); ap.add_argument("--ps", default="0.003")
ap.add_argument("--circs", default="p18,fig12,ibm"); ap.add_argument("--shots", type=int, default=20)
a = ap.parse_args()
decs = sinter_decoders(); res = []
for m in a.models.split(","):
    for p in map(float, a.ps.split(",")):
        for c in a.circs.split(","):
            circ = noisy(c, "Z", 12, p, m)
            dem = circ.detector_error_model(decompose_errors=False)
            det, obs = circ.compile_detector_sampler(seed=7).sample(a.shots, separate_observables=True)
            for dn, d in decs.items():
                t = time.process_time()
                cd = d.compile_decoder_for_dem(dem=dem)
                t1 = time.process_time()
                pred = cd.decode_shots_bit_packed(bit_packed_detection_event_data=np.packbits(det, axis=1, bitorder="little"))
                t2 = time.process_time()
                pred = np.unpackbits(pred, axis=1, bitorder="little")[:, :obs.shape[1]]
                fails = int((pred != obs).any(1).sum())
                r = dict(model=m, p=p, circ=c, dec=dn, s_per_shot=(t2 - t1) / a.shots, compile_s=t1 - t, fails=fails, shots=a.shots)
                res.append(r); print(json.dumps(r), flush=True)
(OUT / "timing.json").write_text(json.dumps(res, indent=1))
