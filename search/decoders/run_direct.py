"""E-006 method (a): direct sampling. For each shot (joint X/Z, stim DEM sampler with return_errors) decode both
sectors with BP-OSD (IBM), BP-LSD, serial BP-OSD, [pymatching for surface codes], and the exact MLE reference
(MILP) on: every shot where BP-OSD or Relay-BP-5 fails in any sector + a random subsample (rate --sub) of the other shots.

Batches are deterministic: batch b uses stim seed SeedSequence([seed, b]); results per batch in
results/E-006-decoder-headroom/direct/<tag>/batch_<b>.npz (resumable; existing batches are skipped).

uv run python -m search.decoders.run_direct --code bb72 --p 0.004 --batches 40 --batch-size 100 --sub 0.25 --workers 6
"""
from __future__ import annotations

import argparse
import json
import time
from multiprocessing import get_context
from pathlib import Path

import numpy as np

from search.decoders.common import RESULTS, build_model, sample_dem, sector_truth

_M = {}


def _setup(code, p, rounds, names):
    key = (code, p, rounds)
    if key not in _M:
        from search.decoders import decoders as D
        m = build_model(code, p, rounds)
        decs = {s: D.make(m.sectors[s], names) for s in "ZX"}
        refs = {s: D.make_ref(m.sectors[s]) for s in "ZX"}
        pm = D.pymatching_sector_decoders(m) if code.startswith("surf") else None
        _M.clear()
        _M[key] = (m, decs, refs, pm)
    return _M[key]


def run_batch(args):
    code, p, rounds, seed, b, shots, sub, names, outdir, tlim = args
    out = Path(outdir) / f"batch_{b:05d}.npz"
    if out.exists():
        return b, None
    t0 = time.process_time()
    m, decs, refs, pm = _setup(code, p, rounds, names)
    s_seed = int(np.random.SeedSequence([seed, b]).generate_state(1, dtype=np.uint32)[0])
    dets, obs, E = sample_dem(m, shots, s_seed)
    rng = np.random.default_rng([seed, b, 7])
    insub = rng.random(shots) < sub
    rec = {"nfaults": E.sum(1).astype(np.int16), "insub": insub}
    fail = {}
    td = {}
    for s in "ZX":
        sec = m.sectors[s]
        syn, ob, e = sector_truth(m, s, dets, obs, E)
        rec[f"{s}_Wtrue"] = (e.astype(bool) * sec.weights[None, :]).sum(1)
        rec[f"{s}_trivial"] = ~syn.any(1)
        for n, dec in decs[s].items():
            f = np.zeros(shots, bool)
            W = np.zeros(shots)
            conv = np.ones(shots, bool)
            t1 = time.process_time()
            for i in range(shots):
                if not syn[i].any():
                    f[i] = ob[i].any()
                    continue
                eh = dec.decode(syn[i])
                conv[i] = bool(dec.converge)
                f[i] = ((sec.L @ eh) % 2 != ob[i]).any()
                W[i] = sec.weights[eh.astype(bool)].sum()
            td[f"{s}_{n}"] = time.process_time() - t1
            rec[f"{s}_{n}_fail"], rec[f"{s}_{n}_W"], rec[f"{s}_{n}_conv"] = f, W, conv
            fail[(s, n)] = f
        if pm is not None:
            pred = pm[s].decode(syn.astype(bool))
            rec[f"{s}_pm_fail"] = (pred != ob).any(1)
        rec[f"{s}_ob"] = ob
        # keep sector data for the reference pass
        rec[f"_{s}"] = (syn, ob)
    do_ref = insub.copy()
    for n in ("bposd", "relay5"):
        if ("Z", n) in fail:
            do_ref |= fail[("Z", n)] | fail[("X", n)]
    rec["ref_done"] = do_ref
    for s in "ZX":
        sec = m.sectors[s]
        syn, ob = rec.pop(f"_{s}")
        f = np.zeros(shots, bool)
        W = np.full(shots, np.nan)
        st = np.zeros(shots, np.int8)          # 1 optimal, 2 feasible/timeout, 3 invalid/unknown, 0 not run
        tt = np.zeros(shots)
        t1 = time.process_time()
        for i in np.flatnonzero(do_ref):
            if not syn[i].any():
                f[i] = ob[i].any(); W[i] = 0.0; st[i] = 1
                continue
            r = refs[s].decode(syn[i], time_limit=tlim)
            tt[i] = r.seconds
            if r.e is None or r.status in ("UNKNOWN", "INVALID"):
                st[i] = 3
                continue
            st[i] = 1 if r.status == "OPTIMAL" else 2
            f[i] = ((sec.L @ r.e) % 2 != ob[i]).any()
            W[i] = r.objective
        td[f"{s}_ref"] = time.process_time() - t1
        rec[f"{s}_ref_fail"], rec[f"{s}_ref_W"], rec[f"{s}_ref_status"], rec[f"{s}_ref_sec"] = f, W, st, tt
    cpu = time.process_time() - t0
    np.savez_compressed(out, stim_seed=s_seed, cpu=cpu, sub=sub, timing=json.dumps(td), **rec)
    return b, cpu


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--p", type=float, required=True)
    ap.add_argument("--rounds", type=int, default=None)
    ap.add_argument("--seed", type=int, default=6006)
    ap.add_argument("--batches", type=int, required=True)
    ap.add_argument("--first-batch", type=int, default=0)
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--sub", type=float, default=0.25)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--decoders", default="bposd,lsd,relay5,relay1")
    ap.add_argument("--time-limit", type=float, default=300.0)
    ap.add_argument("--tag", default=None)
    a = ap.parse_args(argv)
    assert a.workers <= 6
    tag = a.tag or f"{a.code}_p{a.p}"
    outdir = RESULTS / "direct" / tag
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "args.json").write_text(json.dumps(vars(a), indent=1))
    names = tuple(a.decoders.split(","))
    tasks = [(a.code, a.p, a.rounds, a.seed, b, a.batch_size, a.sub, names, str(outdir), a.time_limit)
             for b in range(a.first_batch, a.first_batch + a.batches)]
    t0 = time.time()
    tot = 0.0
    with get_context("spawn").Pool(a.workers) as pool:
        for b, cpu in pool.imap_unordered(run_batch, tasks):
            if cpu is not None:
                tot += cpu
                print(f"batch {b} cpu {cpu:.0f}s  total cpu {tot/3600:.2f}h wall {time.time()-t0:.0f}s", flush=True)
    print("done", tag, f"cpu {tot/3600:.3f} h")


if __name__ == "__main__":
    main()
