"""E-026 stage C1: fixed-weight sampling.  f_w = P(decoder fails | exactly w merged DEM columns fire), columns drawn
with P(S) ∝ prod q/(1-q) (exact), priors of the R-round DEM at P_DEC.  Decoders: BP-OSD (IBM parameters, ldpc) and
Relay-BP (relay5), priors fixed at P_DEC.  Per-batch npz, resumable.

  uv run python -m search.experiments.e026.fw --circ ibm --basis Z --w 2:8 --n 400 --R 12 --workers 6 --tag fw
"""
import argparse, time
from multiprocessing import get_context
import numpy as np
from search.experiments.e026.common import OUT, CIRCS, IBM_BPOSD, RELAY5
from search.experiments.e026.dem import get, sample_fixed_weight

P_DEC = 2e-3
_C = {}


def decoders(D):
    from ldpc import BpOsdDecoder
    import relay_bp
    kw = dict(IBM_BPOSD); kw["max_iter"] = kw.pop("max_bp_iters")
    bp = BpOsdDecoder(D.H, error_channel=list(D.q), **kw)
    rl = relay_bp.RelayDecoderF64(D.Hr, error_priors=D.q, seed=20261003, **RELAY5)
    return {"bposd": lambda s: bp.decode(s), "relay5": lambda s: np.asarray(rl.decode(s), np.uint8)}


def run(args):
    circ, basis, R, w, b, n, seed, outdir, cols_list = args
    out = outdir / f"{circ}_{basis}_R{R}_w{w:03d}_b{b:03d}.npz"
    if out.exists():
        return str(out), None
    t0 = time.process_time()
    key = (circ, basis, R)
    if key not in _C:
        _C.clear(); D = get(circ, basis, R, P_DEC); _C[key] = (D, decoders(D))
    D, decs = _C[key]
    rng = np.random.default_rng([seed, CIRCS.index(circ), "ZX".index(basis), R, w, b])
    samples = sample_fixed_weight(D.q, w, n, rng)
    rec = {nm: np.zeros(n, bool) for nm in decs}
    for i, S in enumerate(samples):
        e = np.zeros(D.ncol, np.uint8); e[S] = 1
        syn = (D.Hr @ e) % 2; tr = (D.Lr @ e) % 2
        for nm, f in decs.items():
            eh = f(syn.astype(np.uint8))
            rec[nm][i] = bool(((D.Lr @ eh) % 2 != tr).any())
    fail_sets = {nm: [samples[i].tolist() for i in np.nonzero(rec[nm])[0]] for nm in decs}
    np.savez_compressed(out, **{f"fail_{k}": v for k, v in rec.items()}, cpu=time.process_time() - t0, n=n, w=w,
                        fail_sets=np.array(str(fail_sets)))
    return str(out), time.process_time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circ", default="p18,fig12,ibm"); ap.add_argument("--basis", default="Z,X")
    ap.add_argument("--w", required=True); ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--batches", type=int, default=1); ap.add_argument("--R", type=int, default=12)
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--seed", type=int, default=26201)
    ap.add_argument("--tag", default="fw")
    a = ap.parse_args(); assert a.workers <= 6
    ws = [int(x) for x in a.w.split(",")] if "," in a.w else list(range(*[int(x) for x in a.w.split(":")]))
    od = OUT / a.tag; od.mkdir(parents=True, exist_ok=True)
    jobs = [(c, bs, a.R, w, b, a.n, a.seed, od, None) for b in range(a.batches) for w in ws
            for c in a.circ.split(",") for bs in a.basis.split(",")]
    with get_context("spawn").Pool(a.workers) as pool:
        for o, cpu in pool.imap_unordered(run, jobs):
            print(o.split("/")[-1], cpu if cpu is None else round(cpu), flush=True)


if __name__ == "__main__":
    main()
