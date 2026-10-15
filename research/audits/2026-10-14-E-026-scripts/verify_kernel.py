"""Auditor (E-026): independent re-test of the 'decoder fails at weight 5 (fig12: 4)' kernel claim.
Inject t-subsets of enumerated minimum-weight logicals into an independently built DEM (audit_sample.build, priors at
P_DEC = 2e-3 as in E-026), decode with ldpc BP-OSD (IBM parameters), compare with the ideal rule
(complement more likely under the PE = 1e-3 term priors -> ideal fails; also evaluated with the decoder priors).
  PYTHONPATH=.:tests uv run python research/audits/2026-10-14-E-026-scripts/verify_kernel.py NAME R t n seed
"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_sample import build, ROOT, OUT

name, R, t, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
circ, b, mode = name.split("_")
d = np.load(ROOT / f"results/E-026-gross-ler/lift/{name}_R{R}.npz")
logs, lq, td, to, tob = d["logs"], d["logq"], d["tdets"], d["toff"], d["tobs"]
dem, H, L, q, _ = build(circ, b, R, 2e-3)
from ldpc import BpOsdDecoder
dec = BpOsdDecoder(H.tocsc(), error_channel=list(q), max_iter=10000, bp_method="minimum_sum", ms_scaling_factor=0,
                   osd_method="osd_cs", osd_order=7)
Hc, Lc = H.tocsc(), L.tocsc()
colkey = {}
for j in range(H.shape[1]):
    colkey[(tuple(Hc.indices[Hc.indptr[j]:Hc.indptr[j + 1]].tolist()),
            int(sum(1 << int(o) for o in Lc.indices[Lc.indptr[j]:Lc.indptr[j + 1]])))] = j
tcol = np.array([colkey[(tuple(sorted(td[to[k]:to[k + 1]].tolist())), int(tob[k]))] for k in range(len(lq))])
lqd = np.log(q)[tcol]
rng = np.random.default_rng(seed)
fails = ideal = ideal_dec = 0; ex = []
for _ in range(n):
    Lg = logs[rng.integers(len(logs))]
    S = rng.choice(Lg, t, replace=False); C = np.setdiff1d(Lg, S)
    e = np.zeros(H.shape[1], np.uint8); e[tcol[S]] ^= 1
    syn = (H @ e) % 2; tr = (L @ e) % 2
    ideal += lq[C].sum() > lq[S].sum() + 1e-12
    ideal_dec += lqd[C].sum() > lqd[S].sum() + 1e-12
    c = dec.decode(syn.astype(np.uint8))
    if ((L @ c) % 2 != tr).any():
        fails += 1
        if len(ex) < 10:
            ex.append(dict(S=S.tolist(), logw_S=float(-lqd[S].sum()), logw_corr=float(-np.log(q)[c == 1].sum()),
                           n_corr=int(c.sum())))
r = dict(name=name, R=R, t=t, n=n, seed=seed, bposd_fail=fails, ideal_fail_PE=int(ideal), ideal_fail_Pdec=int(ideal_dec),
         examples=ex)
(OUT / f"kernel_{name}_R{R}_t{t}_s{seed}.json").write_text(json.dumps(r))
print(json.dumps({k: v for k, v in r.items() if k != "examples"}), flush=True)
