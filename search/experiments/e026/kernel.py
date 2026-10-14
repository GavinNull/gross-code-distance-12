"""E-026 stage C2: decoders on structural sub-kernels: t-subsets (t < ceil(d/2), where the ideal decoder is correct
because the complement is heavier) of enumerated bulk minimum-weight logicals, decoded on the RE-round DEM with
decoder priors at fw.P_DEC.  A failure = the practical decoder fails on t faults although t < d_circ/2.
  uv run python -m search.experiments.e026.kernel --t 4,5 --n 1500 --workers 6"""
import argparse, json, itertools, time
from multiprocessing import get_context
import numpy as np
from search.experiments.e026.common import OUT, CIRCS, DCIRC
from search.experiments.e026.enum import RE, ENUM
from search.experiments.e026.dem import get
from search.experiments.e026.fw import decoders, P_DEC

_C = {}


def run(args):
    c, b, t, n, seed, part = args
    key = (c, b)
    if key not in _C:
        _C.clear(); D = get(c, b, RE, P_DEC); _C[key] = (D, decoders(D))
    D, decs = _C[key]
    logs = [tuple(x) for x in json.loads((ENUM / f"bulk_{c}_{b}.json").read_text())]
    dmin = min(len(L) for L in logs)
    logs = [L for L in logs if len(L) == dmin]
    rng = np.random.default_rng([seed, CIRCS.index(c), "ZX".index(b), t, part])
    t0 = time.process_time()
    fails = {nm: [] for nm in decs}
    for _ in range(n):
        L = logs[rng.integers(len(logs))]
        S = sorted(rng.choice(L, t, replace=False).tolist())
        e = np.zeros(D.ncol, np.uint8); e[S] = 1
        syn = ((D.Hr @ e) % 2).astype(np.uint8); tr = (D.Lr @ e) % 2
        for nm, f in decs.items():
            if ((D.Lr @ f(syn)) % 2 != tr).any():
                fails[nm].append(S)
    return dict(circ=c, basis=b, t=t, n=n, part=part, dmin=dmin, fails=fails, cpu=time.process_time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circ", default="p18,fig12,ibm"); ap.add_argument("--basis", default="Z,X")
    ap.add_argument("--t", default="3,4,5"); ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--parts", type=int, default=1); ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed", type=int, default=26301)
    a = ap.parse_args(); assert a.workers <= 6
    jobs = [(c, b, int(t), a.n, a.seed, k) for c in a.circ.split(",") for b in a.basis.split(",")
            for t in a.t.split(",") for k in range(a.parts)]
    od = OUT / "kernel"; od.mkdir(parents=True, exist_ok=True)
    with get_context("spawn").Pool(a.workers) as pool:
        for r in pool.imap_unordered(run, jobs):
            (od / f"{r['circ']}_{r['basis']}_t{r['t']}_p{r['part']}_s{a.seed}.json").write_text(json.dumps(r))
            print(r["circ"], r["basis"], "t", r["t"], "d", r["dmin"], {k: len(v) for k, v in r["fails"].items()},
                  "/", r["n"], round(r["cpu"]), flush=True)


if __name__ == "__main__":
    main()
