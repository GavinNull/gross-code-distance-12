"""Audit E-023 (c): BB108 direct-sampling throughput at p (Bernoulli over sector DEM columns, BP-OSD IBM / Relay5,
priors at 1e-3) -> cost of a direct test of a 2x effect.  args: prob p nshots seed"""
import sys, json, time
import numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, 'research/audits/2026-10-11-E-023-scripts')
from search.experiments.e023.common import sectors
from a3_decode_basis import decoders
prob, p, n, seed = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
rng = np.random.default_rng(seed)
out = dict(prob=prob, p=p, n=n)
for sec, secp in zip(sectors(prob, "sd6", 1e-3), sectors(prob, "sd6", p)):
    H = sec.H.toarray().astype(np.uint8); L = sec.L.toarray().astype(np.uint8)
    D = decoders(H, sec.q); print(prob, sec.label, "ndet", H.shape[0], "ncol", H.shape[1], "coldeg mean", H.sum(0).mean(), "max", H.sum(0).max(), "rowwt max", H.sum(1).max(), flush=True)
    B = rng.random((n, sec.ncol)) < secp.q[None, :]
    for dn, d in D.items():
        t0 = time.process_time(); k = 0
        for r in B:
            e = r.astype(np.uint8); s = (H @ e % 2).astype(np.uint8)
            if not s.any(): continue
            eh = d(s); k += int(((L @ eh) % 2 != (L @ e) % 2).any())
        out[f"{sec.label}_{dn}"] = dict(k=k, cpu_per_shot=(time.process_time() - t0) / n, lam=float(secp.q.sum()))
        print(prob, sec.label, dn, out[f"{sec.label}_{dn}"], flush=True)
json.dump(out, open(f"results/E-023-audit/a7_{prob}_p{p:.0e}.json", "w"), indent=1)
