"""E-016 阶段 1：直接采样。experimenter。

每批：联合 DEM 采样（stim 种子 SeedSequence([seed, circ_id, b])），同一批 syndrome 交给
  bposd    分 sector BP-OSD（E-002 / IBM 设置，与评估器 _SectorDecoder 相同参数与矩阵）
  relay_s  分 sector Relay-BP-5（E-006 relay5 参数，seed 20261003）
  relay_j  联合 DEM 上的 Relay-BP-5（E-009 的做法，同参数）
记录每 shot、每个解码器的 Z / X sector 失败位（联合解码器按 observable 拆成 Z、X 两部分），以及 BP-OSD / Relay 是否收敛。
每批一个 npz（已存在则跳过，可断点续跑）。

    PYTHONPATH=. uv run python -m search.experiments.e016.run_direct --p 0.004 --batches 0:40 --batch 50 --workers 3
"""
from __future__ import annotations

import argparse
import time
from multiprocessing import get_context

import numpy as np

from search.experiments.e016.common import CIRCS, OUT, build_model, joint_matrices

DEC_ALL = ("bposd", "relay_s", "relay_j")
_S = {}


def _setup(circ, p, names):
    key = (circ, p, names)
    if key not in _S:
        import relay_bp
        from ldpc import BpOsdDecoder
        from search.decoders.common import IBM_BPOSD
        from search.decoders.decoders import RELAY
        m = build_model(circ, p)
        st = {"m": m}
        if "relay_j" in names:
            Hj, Lj, pj, _, _ = joint_matrices(m)
            st["Lj"] = Lj.tocsr()
            st["relay_j"] = relay_bp.RelayDecoderF64(Hj, error_priors=pj, seed=20261003, **RELAY["relay5"])
        for s in "ZX":
            sec = m.sectors[s]
            if "bposd" in names:
                st[f"bposd_{s}"] = BpOsdDecoder(sec.H, error_channel=list(sec.priors), **IBM_BPOSD)
            if "relay_s" in names:
                st[f"relay_s_{s}"] = relay_bp.RelayDecoderF64(sec.H.tocsr(), error_priors=sec.priors, seed=20261003,
                                                              **RELAY["relay5"])
        _S.clear()
        _S[key] = st
    return _S[key]


def run_batch(args):
    circ, p, b, bs, seed, names, outdir = args
    out = outdir / f"{circ}_b{b:04d}.npz"
    if out.exists():
        return circ, b, None
    t0 = time.process_time()
    st = _setup(circ, p, names)
    m = st["m"]
    nz, oz = m.nz, m.oz
    cid = CIRCS.index(circ)
    s_seed = int(np.random.SeedSequence([seed, cid, b]).generate_state(1, dtype=np.uint32)[0])
    sampler = m.dem.compile_sampler(seed=s_seed)
    dets, obs, _ = sampler.sample(bs, return_errors=False)
    rec = {}
    tdec = {}
    for nm in names:
        rec[f"{nm}_fZ"] = np.zeros(bs, bool)
        rec[f"{nm}_fX"] = np.zeros(bs, bool)
        rec[f"{nm}_conv"] = np.ones(bs, bool)
        tdec[nm] = 0.0
    for i in range(bs):
        d = dets[i].astype(np.uint8)
        tr = obs[i].astype(np.uint8)
        for nm in names:
            ta = time.process_time()
            if nm == "relay_j":
                if d.any():
                    r = st["relay_j"].decode_detailed(d)
                    pred = (st["Lj"] @ np.asarray(r.decoding, dtype=np.uint8)) % 2
                    rec[f"{nm}_conv"][i] = bool(r.success)
                else:
                    pred = np.zeros_like(tr)
            else:
                pred = np.zeros_like(tr)
                for s, ds, sl in (("Z", d[:nz], slice(0, oz)), ("X", d[nz:], slice(oz, None))):
                    if not ds.any():
                        continue
                    dec = st[f"{nm}_{s}"]
                    if nm == "relay_s":
                        r = dec.decode_detailed(ds)
                        eh = np.asarray(r.decoding, dtype=np.uint8)
                        rec[f"{nm}_conv"][i] &= bool(r.success)
                    else:
                        eh = dec.decode(ds)
                        rec[f"{nm}_conv"][i] &= bool(dec.converge)
                    pred[sl] = (m.sectors[s].L @ eh) % 2
            tdec[nm] += time.process_time() - ta
            rec[f"{nm}_fZ"][i] = bool((pred[:oz] != tr[:oz]).any())
            rec[f"{nm}_fX"][i] = bool((pred[oz:] != tr[oz:]).any())
    rec["ndet"] = dets.sum(1).astype(np.int32)
    cpu = time.process_time() - t0
    np.savez_compressed(out, **rec, cpu=cpu, **{f"t_{k}": v for k, v in tdec.items()}, seed=s_seed, shots=bs)
    return circ, b, cpu


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--p", type=float, required=True)
    ap.add_argument("--batches", default="0:20", help="a:b 批编号范围")
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--seed", type=int, default=16016)
    ap.add_argument("--circs", default=",".join(CIRCS))
    ap.add_argument("--decoders", default=",".join(DEC_ALL))
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    assert a.workers <= 3
    names = tuple(a.decoders.split(","))
    outdir = OUT / "direct" / f"p{a.p}"
    outdir.mkdir(parents=True, exist_ok=True)
    lo, hi = map(int, a.batches.split(":"))
    jobs = [(c, a.p, b, a.batch, a.seed, names, outdir) for b in range(lo, hi) for c in a.circs.split(",")]
    t0 = time.time()
    with get_context("spawn").Pool(a.workers) as pool:
        for circ, b, cpu in pool.imap_unordered(run_batch, jobs):
            print(f"{time.time() - t0:7.0f}s {circ} b{b} cpu={cpu if cpu is None else round(cpu)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
