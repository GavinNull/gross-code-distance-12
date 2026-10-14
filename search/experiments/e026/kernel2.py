"""E-026 stage C2: practical decoders on structural sub-kernels of the exactly enumerated minimum-weight logicals.
For a logical L (weight W) and t-subset S: inject S (syndrome = XOR of term detectors, true flip = XOR of term
observables), decode on the full R-round DEM (decoder priors at fw.P_DEC).  For t < W - t the ideal (most-likely)
decoder is correct, so any failure is the decoder's own ('masking distance').  For t = W - t (6|6) or t > W - t the
ideal decoder fails on the less likely side; we record the decoder's rate there for reference.
  uv run python -m search.experiments.e026.kernel2 --files fig12_Z_w11_R4,p18_Z_w11z_R3 --t 3,4,5,6 --n 1000"""
import argparse, json, time
from multiprocessing import get_context
import numpy as np
from search.experiments.e026.common import OUT
from search.experiments.e026.dem import get
from search.experiments.e026.fw import decoders, P_DEC

_C = {}


def run(args):
    name, t, n, seed, part = args
    circ, basis, mode, R = name.split("_"); R = int(R[1:])
    d = np.load(OUT / "lift" / f"{name}.npz")
    logs, tdets, toff, tobs, logq = d["logs"], d["tdets"], d["toff"], d["tobs"], d["logq"]
    key = (circ, basis, R)
    if key not in _C:
        _C.clear(); D = get(circ, basis, R, P_DEC); _C[key] = (D, decoders(D))
    D, decs = _C[key]
    rng = np.random.default_rng([seed, t, part, abs(hash(name)) % 10 ** 6])
    W = logs.shape[1]
    fails = {nm: 0 for nm in decs}; wfail = {nm: 0.0 for nm in decs}; wsum = 0.0; wideal = 0.0; ideal_fail = 0; t0 = time.process_time(); ex = {nm: [] for nm in decs}
    for _ in range(n):
        L = logs[rng.integers(len(logs))]
        S = rng.choice(L, t, replace=False); C = np.setdiff1d(L, S)
        syn = np.zeros(D.ndet, np.uint8); ob = 0
        for x in S:
            syn[tdets[toff[x]:toff[x + 1]]] ^= 1; ob ^= int(tobs[x])
        tr = np.array([(ob >> k) & 1 for k in range(D.Lr.shape[0])], np.uint8)
        sS, sC = logq[S].sum(), logq[C].sum()
        fi = 1 if sC > sS + 1e-12 else (0.5 if abs(sC - sS) <= 1e-12 else 0)
        ideal_fail += fi; wS = float(np.exp(sS)); wsum += wS; wideal += fi * wS
        for nm, f in decs.items():
            if ((D.Lr @ f(syn)) % 2 != tr).any():
                fails[nm] += 1; wfail[nm] += wS
                if len(ex[nm]) < 20:
                    ex[nm].append(S.tolist())
    return dict(name=name, t=t, W=W, n=n, part=part, fails=fails, ideal_fail=ideal_fail, wfail=wfail, wsum=wsum,
                wideal=wideal, nlog=int(len(logs)), examples=ex,
                cpu=time.process_time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", required=True); ap.add_argument("--t", default="4,5,6")
    ap.add_argument("--n", type=int, default=500); ap.add_argument("--parts", type=int, default=1)
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--seed", type=int, default=26401)
    a = ap.parse_args(); assert a.workers <= 6
    jobs = [(f, int(t), a.n, a.seed, k) for f in a.files.split(",") for t in a.t.split(",") for k in range(a.parts)]
    od = OUT / "kernel"; od.mkdir(parents=True, exist_ok=True)
    with get_context("spawn").Pool(a.workers) as pool:
        for r in pool.imap_unordered(run, jobs):
            (od / f"{r['name']}_t{r['t']}_p{r['part']}_s{a.seed}.json").write_text(json.dumps(r))
            print(r["name"], "W", r["W"], "t", r["t"], "dec fails", r["fails"], "ideal fails", r["ideal_fail"], "/", r["n"],
                  "cpu", round(r["cpu"]), flush=True)


if __name__ == "__main__":
    main()
