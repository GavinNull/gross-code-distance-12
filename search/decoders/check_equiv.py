"""E-006 sanity checks: (1) our sector BP-OSD == evaluators.l2 BP-OSD (same predictions shot by shot);
(2) DEM sampling with return_errors reproduces the sector syndromes / observables (asserted in sector_truth);
(3) the circuit-level LER from the evaluator's own sampler path agrees with DEM sampling (same decoder).
uv run python -m search.decoders.check_equiv --code bb72 --p 0.004 --shots 300"""
import argparse, json
import numpy as np
from evaluators.l2 import DecoderConfig, _BatchRunner
from search.decoders.common import RESULTS, build_model, sample_dem, sector_truth
from search.decoders import decoders as D

ap = argparse.ArgumentParser()
ap.add_argument("--code", default="bb72"); ap.add_argument("--p", type=float, default=0.004)
ap.add_argument("--shots", type=int, default=300)
a = ap.parse_args()
m = build_model(a.code, a.p)
br = _BatchRunner(m.circuit, m.nz, m.oz, DecoderConfig("bposd"))
dets, obs, E = sample_dem(m, a.shots, 99)
out = {}
for s in "ZX":
    sec = m.sectors[s]
    syn, ob, e = sector_truth(m, s, dets, obs, E)
    mine = D.make(sec, ("bposd",))["bposd"]
    pm = np.zeros_like(ob)
    for i in range(a.shots):
        if syn[i].any():
            pm[i] = (sec.L @ mine.decode(syn[i])) % 2
    d0 = dets[:, :m.nz] if s == "Z" else dets[:, m.nz:]
    pe = br.decoders[s].decode(d0)
    out[s] = {"shots": a.shots, "pred_identical": bool(np.array_equal(pm.astype(bool), pe)),
              "n_cols_ours": int(sec.H.shape[1]), "n_cols_l2": int(br.decoders[s].num_mechanisms),
              "fails": int((pm.astype(bool) != ob).any(1).sum())}
# circuit sampler (evaluator path) vs DEM sampler, same decoder: failure rate comparison
r = br.run(1234, 0, a.shots)
out["circuit_sampler_fail_any"] = r["fail_any"]; out["circuit_sampler_shots"] = a.shots
print(json.dumps(out, indent=1))
(RESULTS / f"check_equiv_{a.code}_p{a.p}.json").write_text(json.dumps(out, indent=1))
