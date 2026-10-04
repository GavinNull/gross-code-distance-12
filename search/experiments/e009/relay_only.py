import time, json, numpy as np
from search.experiments.e009.joint import _setup
from search.decoders.common import sample_dem
st = _setup("bb72", 0.004); m = st["m"]; Hj, Lj, _ = st["joint"]; nz, oz = m.nz, m.oz
N = 6000
dets, obs, _ = sample_dem(m, N, 20261004)
fs = fj = both = 0; t0 = time.time()
for i in range(N):
    d = dets[i].astype(np.uint8); truth = obs[i].astype(np.uint8)
    if not d.any():
        fs += truth.any(); fj += truth.any(); both += truth.any(); continue
    pred = np.zeros_like(truth)
    for s, ds, sl in (("Z", d[:nz], slice(0, oz)), ("X", d[nz:], slice(oz, None))):
        if ds.any():
            pred[sl] = (m.sectors[s].L @ np.asarray(st[f"relay_{s}"].decode(ds), dtype=np.uint8)) % 2
    a = (pred != truth).any()
    b = ((((Lj @ np.asarray(st["relay_joint"].decode(d), dtype=np.uint8)) % 2).astype(np.uint8)) != truth).any()
    fs += a; fj += b; both += (a and b)
print(json.dumps({"code": "bb72", "p": 0.004, "shots": N, "relay_sector_fail": int(fs), "relay_joint_fail": int(fj),
                  "both_fail": int(both), "seconds": round(time.time() - t0)}))
