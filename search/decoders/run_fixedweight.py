"""E-006 method (b): fixed-weight fault sampling.

For a target p, the joint DEM (sd6 at p) has independent mechanisms with priors q_i. Stratify by the number w of
fired mechanisms:  LER(p) = sum_w pi_w(p) f_w(p),  pi_w = P(|E| = w) (Poisson-binomial, exact DP),
f_w = P(fail | |E| = w).  Given |E| = w the fired set S has P(S) ∝ prod_{i in S} q_i/(1-q_i) (exact rejection
sampler in common.sample_fixed_weight).  Each sampled S is decoded in both sectors (decoders at the same p's priors);
the exact MLE reference runs on every sample where BP-OSD or Relay-BP-5 fails, plus a random subsample (rate sub_w).

uv run python -m search.decoders.run_fixedweight --code bb72 --p 0.001 --w 3:16 --n 2000 --sub 1.0 --workers 6
"""
from __future__ import annotations

import argparse
import json
import time
from multiprocessing import get_context
from pathlib import Path

import numpy as np

from search.decoders.common import RESULTS, build_model, sample_fixed_weight, sector_truth, sets_to_E

_M = {}


def _setup(code, p, names):
    key = (code, p)
    if key not in _M:
        from search.decoders import decoders as D
        m = build_model(code, p)
        _M.clear()
        _M[key] = (m, {s: D.make(m.sectors[s], names) for s in "ZX"}, {s: D.make_ref(m.sectors[s]) for s in "ZX"})
    return _M[key]


def run_batch(args):
    code, p, w, b, n, sub, names, outdir, seed, tlim, trigger, ftag = args
    out = Path(outdir) / f"w{w:03d}_b{ftag}{b:04d}.npz"
    if out.exists():
        return w, b, None
    t0 = time.process_time()
    m, decs, refs = _setup(code, p, names)
    rng = np.random.default_rng([seed, w, b])
    sets = sample_fixed_weight(m.priors, w, n, rng)
    E = sets_to_E(sets, len(m.priors))
    insub = rng.random(n) < sub
    rec = {"sets": sets.astype(np.int32), "insub": insub}
    trig = insub.copy()
    secdata = {}
    for s in "ZX":
        sec = m.sectors[s]
        syn, ob, e = sector_truth(m, s, None, None, E, check=False)
        secdata[s] = (syn, ob)
        rec[f"{s}_Wtrue"] = (e.astype(bool) * sec.weights[None, :]).sum(1)
        rec[f"{s}_ncols"] = e.sum(1).astype(np.int16)
        for nm, dec in decs[s].items():
            f = np.zeros(n, bool)
            conv = np.ones(n, bool)
            WD = np.zeros(n)
            for i in range(n):
                if not syn[i].any():
                    f[i] = ob[i].any()
                    continue
                eh = dec.decode(syn[i])
                conv[i] = bool(getattr(dec, "converge", True))
                f[i] = ((sec.L @ eh) % 2 != ob[i]).any()
                WD[i] = sec.weights[eh.astype(bool)].sum()
            rec[f"{s}_{nm}_fail"] = f
            rec[f"{s}_{nm}_conv"] = conv
            rec[f"{s}_{nm}_W"] = WD
            if nm in trigger:
                trig |= f
    rec["ref_done"] = trig
    for s in "ZX":
        sec = m.sectors[s]
        syn, ob = secdata[s]
        f = np.zeros(n, bool)
        W = np.full(n, np.nan)
        st = np.zeros(n, np.int8)
        for i in np.flatnonzero(trig):
            if not syn[i].any():
                f[i] = ob[i].any(); W[i] = 0.0; st[i] = 1
                continue
            r = refs[s].decode(syn[i], time_limit=tlim)
            if r.e is None or r.status in ("UNKNOWN", "INVALID"):
                st[i] = 3
                continue
            st[i] = 1 if r.status == "OPTIMAL" else 2
            f[i] = ((sec.L @ r.e) % 2 != ob[i]).any()
            W[i] = r.objective
        rec[f"{s}_ref_fail"], rec[f"{s}_ref_W"], rec[f"{s}_ref_status"] = f, W, st
    cpu = time.process_time() - t0
    np.savez_compressed(out, cpu=cpu, w=w, sub=sub, trigger=",".join(trigger), **rec)
    return w, b, cpu


def parse_w(s):
    out = []
    for part in s.split(","):
        if ":" in part:
            a, b = part.split(":")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--p", type=float, required=True)
    ap.add_argument("--w", required=True, help="e.g. 3:12,14,16")
    ap.add_argument("--n", type=int, default=1000, help="samples per weight")
    ap.add_argument("--n-low", default="", help="override n for some weights: 'w=n,w=n'")
    ap.add_argument("--batch", type=int, default=250)
    ap.add_argument("--sub", type=float, default=0.2)
    ap.add_argument("--sub-low", type=float, default=1.0, help="ref subsample rate for w <= --low-w")
    ap.add_argument("--low-w", type=int, default=0)
    ap.add_argument("--seed", type=int, default=6106)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--decoders", default="bposd,relay5,relay1")
    ap.add_argument("--time-limit", type=float, default=300.0)
    ap.add_argument("--trigger", default="bposd,relay5", help="decoders whose failures always trigger the reference")
    ap.add_argument("--file-tag", default="", help="extra batch-file label (use with a new --seed to add samples)")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args(argv)
    assert a.workers <= 6
    tag = a.tag or f"{a.code}_p{a.p}"
    outdir = RESULTS / "fixedweight" / tag
    outdir.mkdir(parents=True, exist_ok=True)
    prev = {}
    if (outdir / "args.json").exists():
        prev = json.loads((outdir / "args.json").read_text())
    prev.setdefault("runs", []).append(vars(a))
    (outdir / "args.json").write_text(json.dumps(prev, indent=1))
    nover = {int(k): int(v) for k, v in (x.split("=") for x in a.n_low.split(",") if x)}
    names = tuple(a.decoders.split(","))
    tasks = []
    for w in parse_w(a.w):
        n = nover.get(w, a.n)
        sub = a.sub_low if w <= a.low_w else a.sub
        for b in range((n + a.batch - 1) // a.batch):
            tasks.append((a.code, a.p, w, b, min(a.batch, n - b * a.batch), sub, names, str(outdir), a.seed,
                          a.time_limit, tuple(a.trigger.split(",")), a.file_tag))
    t0 = time.time()
    tot = 0.0
    with get_context("spawn").Pool(a.workers) as pool:
        for w, b, cpu in pool.imap_unordered(run_batch, tasks):
            if cpu is not None:
                tot += cpu
                print(f"w {w} b {b} cpu {cpu:.0f}s total {tot/3600:.2f}h wall {time.time()-t0:.0f}s", flush=True)
    print("done", tag, f"cpu {tot/3600:.3f} h")


if __name__ == "__main__":
    main()
