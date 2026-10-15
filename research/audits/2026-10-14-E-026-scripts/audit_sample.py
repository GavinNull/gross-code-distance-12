"""Auditor (E-026): independent direct sampling + decoder-optimality diagnostic.

Independent of the experimenter's pipeline except for the (frozen) evaluator template/noise:
  circuit  = evaluators.candidate.memory_circuit + evaluators.noise.add_noise('sd6')
  DEM      = own merge (columns keyed by (detectors, observables), probabilities XOR-combined)
  sampling = stim DEM sampler with return_errors=True (gives the true fault set per shot)
  decoder  = ldpc.BpOsdDecoder with IBM parameters (min-sum, 10000 iters, ms_scaling 0, OSD-CS 7)
For every failed shot we record  w(true) = sum_{i in e} log((1-q)/q)  and  w(corr)  (decoder output).
  w(corr) <= w(true) -> 'code-limited' failure (the decoder found an at-least-as-likely error in the wrong class;
                         a minimum-weight decoder would very likely also fail)
  w(corr) >  w(true) -> 'decoder-limited' failure (a better decoder could in principle succeed)
Optionally, failed shots are re-decoded with a stronger decoder (OSD-CS order --strong-order).

  PYTHONPATH=.:tests uv run python research/audits/2026-10-14-E-026-scripts/audit_sample.py \
      --circ p18 --basis Z --p 2e-3 --shots 300 --seed 9001 --R 12
"""
import argparse, json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1")
from pathlib import Path
import numpy as np
import scipy.sparse as sp
import stim

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from search.experiments.e026.common import spec, code  # schedule loading only (read-only)
from evaluators import candidate as cand
from evaluators.noise import add_noise

OUT = ROOT / "results" / "E-026-audit"


def build(circ, basis, R, p):
    c = add_noise(cand.memory_circuit(spec(circ), code(), basis, R), "sd6", p)
    dem = c.detector_error_model(decompose_errors=False)
    cols, colp, inst2col = {}, [], []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        pr = inst.args_copy()[0]
        ds = tuple(sorted(t.val for t in inst.targets_copy() if t.is_relative_detector_id()))
        os_ = tuple(sorted(t.val for t in inst.targets_copy() if t.is_logical_observable_id()))
        k = (ds, os_)
        if k not in cols:
            cols[k] = len(colp); colp.append(0.0)
        j = cols[k]
        colp[j] = colp[j] * (1 - pr) + pr * (1 - colp[j])
        inst2col.append(j)
    n = len(colp)
    H = sp.lil_matrix((dem.num_detectors, n), dtype=np.uint8)
    L = sp.lil_matrix((dem.num_observables, n), dtype=np.uint8)
    for (ds, os_), j in cols.items():
        for d in ds: H[d, j] = 1
        for o in os_: L[o, j] = 1
    return dem, H.tocsr(), L.tocsr(), np.array(colp), np.array(inst2col)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circ"); ap.add_argument("--basis"); ap.add_argument("--p", type=float)
    ap.add_argument("--R", type=int, default=12); ap.add_argument("--shots", type=int)
    ap.add_argument("--seed", type=int); ap.add_argument("--batch", type=int, default=2000)
    ap.add_argument("--strong-order", type=int, default=0)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    from ldpc import BpOsdDecoder
    dem, H, L, q, i2c = build(a.circ, a.basis, a.R, a.p)
    w = np.log((1 - q) / q)
    dec = BpOsdDecoder(H.tocsc(), error_channel=list(q), max_iter=10000, bp_method="minimum_sum",
                       ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)
    strong = None
    if a.strong_order:
        strong = BpOsdDecoder(H.tocsc(), error_channel=list(q), max_iter=10000, bp_method="minimum_sum",
                              ms_scaling_factor=0, osd_method="osd_cs", osd_order=a.strong_order)
    sampler = dem.compile_sampler(seed=a.seed)
    t0 = time.process_time()
    shots = fails = 0; recs = []; strong_fail = 0
    while shots < a.shots:
        nb = min(a.batch, a.shots - shots)
        det, obs, err = sampler.sample(nb, return_errors=True)
        for s in range(nb):
            syn = det[s].astype(np.uint8)
            if not syn.any():
                if obs[s].any():
                    fails += 1; recs.append(dict(trivial=True))
                continue
            corr = dec.decode(syn)
            if ((L @ corr) % 2 != obs[s]).any():
                fails += 1
                e = np.zeros(len(q), np.uint8)
                np.add.at(e, i2c[np.nonzero(err[s])[0]], 1); e %= 2
                assert not (((H @ e) % 2) != syn).any()
                r = dict(w_true=float(w[e == 1].sum()), w_corr=float(w[corr == 1].sum()),
                         n_true=int(e.sum()), n_corr=int(corr.sum()), conv=bool(dec.converge))
                if strong is not None:
                    c2 = strong.decode(syn)
                    r["strong_fail"] = bool(((L @ c2) % 2 != obs[s]).any())
                    r["w_strong"] = float(w[c2 == 1].sum())
                    strong_fail += r["strong_fail"]
                recs.append(r)
        shots += nb
    P = fails / shots
    res = dict(circ=a.circ, basis=a.basis, p=a.p, R=a.R, shots=shots, fails=fails, P_shot=P,
               per_round=1 - (1 - P) ** (1 / a.R) if P < 1 else 1.0, seed=a.seed, cpu=time.process_time() - t0,
               ncol=len(q), lam=float(q.sum()), strong_order=a.strong_order, strong_fail=strong_fail,
               n_code_limited=sum(1 for r in recs if "w_corr" in r and r["w_corr"] <= r["w_true"] + 1e-9),
               n_decoder_limited=sum(1 for r in recs if "w_corr" in r and r["w_corr"] > r["w_true"] + 1e-9),
               fail_records=recs)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"sample_{a.circ}_{a.basis}_p{a.p:g}_R{a.R}_s{a.seed}{a.tag}.json"
    f.write_text(json.dumps(res))
    print(json.dumps({k: v for k, v in res.items() if k != "fail_records"}), flush=True)


if __name__ == "__main__":
    main()
