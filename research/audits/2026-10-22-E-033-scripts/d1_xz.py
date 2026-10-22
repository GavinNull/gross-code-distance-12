"""Auditor E-033 claim 4: why does u11 fail ~2x more often in the X basis than in Z with BP-OSD at low p?
Own pipeline (s_sample.setup: own circuit/noise/logicals, ldpc BpOsdDecoder IBM parameters), lam 0, p given.
Per shot: BP converged?  On failure: weight & cost (sum log((1-q)/q)) of the TRUE error vs of the decoder output;
"suboptimal" = decoder output strictly costlier than the true error (a better decoder would have succeeded on it).
  uv run python d1_xz.py <circ> <p> <shots_per_basis> <seed>"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np
import s_sample as S
from mylib import memory_circuit, dem_terms, load_spec
circ, p, N, seed = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
basis = sys.argv[5] if len(sys.argv) > 5 else "ZX"
res = {}
for b in basis:
    dem, Lm, dec = S.setup(0.0, p, circ, b)
    terms, nd, no = dem_terms(memory_circuit(load_spec(S.SPECS[circ]), b, 12, p, 0.0))
    q = np.array([t[2] for t in terms]); w = np.log((1 - q) / q)
    det, obs, err = dem.compile_sampler(seed=seed).sample(N, return_errors=True)
    t0 = time.process_time()
    nconv = 0; fails = []
    for s in range(N):
        corr = dec.decode(det[s].astype(np.uint8))
        nconv += bool(dec.converge)
        if ((Lm @ corr) % 2 != obs[s]).any():
            e = err[s].astype(np.uint8)
            fails.append(dict(wt_true=int(e.sum()), wt_dec=int(corr.sum()), cost_true=float(w @ e), cost_dec=float(w @ corr),
                              conv=bool(dec.converge), wt_diff=int(((e ^ corr) & 1).sum())))
    sub = sum(f["cost_dec"] > f["cost_true"] + 1e-9 for f in fails)
    res[b] = dict(shots=N, fails=len(fails), bp_converged=nconv, suboptimal=sub,
                  fails_conv=sum(f["conv"] for f in fails), wt_true=sorted(f["wt_true"] for f in fails),
                  wt_diff=sorted(f["wt_diff"] for f in fails), cpu=time.process_time() - t0, detail=fails)
    print(b, {k: v for k, v in res[b].items() if k != "detail"}, flush=True)
json.dump(res, open(f"/Users/ephemeral/Desktop/qec-ai-search/results/E-033-audit/d1_{circ}_{p}_{seed}_{basis}.json", "w"), indent=1)
