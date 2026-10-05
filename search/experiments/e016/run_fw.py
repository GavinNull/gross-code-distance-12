"""E-016 阶段 2：固定权重法。experimenter。

与 E-006 方法 (b) 相同（search/decoders/common.sample_fixed_weight / weight_distribution，只读复用）：
LER(p) = Σ_w π_w(p) f_w(p)，π_w = P(|E| = w)（联合 DEM 独立机制的 Poisson-二项分布，精确 DP），
f_w = P(失败 | |E| = w)，给定 |E| = w 时 P(S) ∝ Π r_i（精确拒绝抽样）。解码器先验用同一 p 的 DEM。
每个样本：由联合 DEM 的完整矩阵算出 detector / observable（与 stim 采样器同一定义），交给 bposd、relay_s、relay_j
（与 run_direct 相同的解码器对象）。参考解码器（分 sector 精确 MLE，HiGHS MILP，search/decoders/exact.py）
在任一解码器失败的 sector 上必跑，另按 --sub 随机抽样跑其余 sector（Horvitz–Thompson 加权）。

    PYTHONPATH=. uv run python -m search.experiments.e016.run_fw --p 0.001 --w 6:30:2 --n 1000 --batch 100 --workers 3
"""
from __future__ import annotations

import argparse
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from search.decoders.common import sample_fixed_weight
from search.experiments.e016.common import CIRCS, OUT
from search.experiments.e016.run_direct import _setup

NAMES = ("bposd", "relay_s", "relay_j")
_F = {}


def full_matrices(m):
    """联合 DEM 的完整矩阵（含无探测器机制），机制顺序 = m.priors 的顺序。"""
    key = id(m)
    if key in _F:
        return _F[key]
    rows, cols, orows, ocols = [], [], [], []
    j = 0
    for inst in m.dem.flattened():
        if inst.type != "error":
            continue
        d, o = set(), set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        rows += sorted(d); cols += [j] * len(d)
        orows += sorted(o); ocols += [j] * len(o)
        j += 1
    assert j == len(m.priors)
    Hf = sp.csr_matrix((np.ones(len(rows), np.int32), (cols, rows)), shape=(j, m.circuit.num_detectors))
    Lf = sp.csr_matrix((np.ones(len(orows), np.int32), (ocols, orows)), shape=(j, m.circuit.num_observables))
    _F.clear()
    _F[key] = (Hf, Lf)
    return Hf, Lf


def decode_all(st, names, d, tr, rec, i):
    m = st["m"]
    nz, oz = m.nz, m.oz
    for nm in names:
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
        rec[f"{nm}_fZ"][i] = bool((pred[:oz] != tr[:oz]).any())
        rec[f"{nm}_fX"][i] = bool((pred[oz:] != tr[oz:]).any())


def run_batch(args):
    circ, p, w, b, n, sub, names, seed, outdir, tlim, pbo = args
    out = outdir / f"{circ}_w{w:03d}_b{b:04d}.npz"
    if out.exists():
        return circ, w, b, None
    t0 = time.process_time()
    st = _setup(circ, p, names)
    m = st["m"]
    nz, oz = m.nz, m.oz
    Hf, Lf = full_matrices(m)
    if "mle" not in st:
        from search.decoders.exact import MilpMLE
        st["mle"] = {s: MilpMLE(m.sectors[s].H, m.sectors[s].weights) for s in "ZX"}
    rng = np.random.default_rng([seed, CIRCS.index(circ), w, b])
    sets = sample_fixed_weight(m.priors, w, n, rng)
    E = sp.csr_matrix((np.ones(n * w, np.int32), (np.repeat(np.arange(n), w), sets.ravel())), shape=(n, len(m.priors)))
    dets = ((E @ Hf).toarray() % 2).astype(np.uint8)
    obs = ((E @ Lf).toarray() % 2).astype(np.uint8)
    rec = {"sets": sets.astype(np.int32)}
    for nm in names:
        rec[f"{nm}_fZ"] = np.zeros(n, bool)
        rec[f"{nm}_fX"] = np.zeros(n, bool)
        rec[f"{nm}_conv"] = np.ones(n, bool)
    for s in "ZX":
        rec[f"mle_{s}_run"] = np.zeros(n, bool)       # MLE 是否运行
        rec[f"mle_{s}_sub"] = np.zeros(n, bool)       # 是否属于随机子样本
        rec[f"mle_{s}_f"] = np.zeros(n, bool)         # MLE 失败（证明最优或可行解）
        rec[f"mle_{s}_opt"] = np.zeros(n, bool)       # MILP 证明最优
        rec[f"mle_{s}_Wt"] = np.full(n, np.nan)       # 真实 sector 错误的似然权重
        rec[f"mle_{s}_Wm"] = np.full(n, np.nan)       # MLE 解的似然权重
        rec[f"mle_{s}_pi"] = np.zeros(n)              # 该 sector 进入 MLE 的概率（HT 权重 = 1/pi）
    insub = {s: rng.random(n) < sub for s in "ZX"}
    ubo = {s: rng.random(n) for s in "ZX"}
    for i in range(n):
        decode_all(st, names, dets[i], obs[i], rec, i)
        for s in "ZX":
            # 进入 MLE：任一 Relay 失败 -> 必跑；只有 BP-OSD 失败 -> 概率 pbo；其余 -> 概率 sub
            relay_f = any(rec[f"{nm}_f{s}"][i] for nm in names if nm.startswith("relay"))
            bo_f = "bposd" in names and rec[f"bposd_f{s}"][i]
            if relay_f:
                pi = 1.0
            elif bo_f:
                pi = 1 - (1 - pbo) * (1 - sub)
            else:
                pi = sub
            rec[f"mle_{s}_pi"][i] = pi
            sel = relay_f or (bo_f and ubo[s][i] < pbo) or insub[s][i]
            if not sel:
                continue
            ds = dets[i, :nz] if s == "Z" else dets[i, nz:]
            ts = obs[i, :oz] if s == "Z" else obs[i, oz:]
            sec = m.sectors[s]
            e = np.zeros(sec.H.shape[1], np.uint8)
            cc = sec.j2c[sets[i]]
            np.add.at(e, cc[cc >= 0], 1)
            e %= 2
            rec[f"mle_{s}_run"][i] = True
            rec[f"mle_{s}_sub"][i] = insub[s][i]
            rec[f"mle_{s}_Wt"][i] = float(sec.weights[e.astype(bool)].sum())
            if not ds.any():
                rec[f"mle_{s}_f"][i] = bool(ts.any())
                rec[f"mle_{s}_opt"][i] = True
                rec[f"mle_{s}_Wm"][i] = 0.0
                continue
            r = st["mle"][s].decode(ds.astype(np.uint8), time_limit=tlim)
            rec[f"mle_{s}_opt"][i] = r.status == "OPTIMAL"
            if r.e is None:
                rec[f"mle_{s}_f"][i] = True
                continue
            rec[f"mle_{s}_Wm"][i] = r.objective
            rec[f"mle_{s}_f"][i] = bool((((sec.L @ r.e) % 2) != ts).any())
    cpu = time.process_time() - t0
    np.savez_compressed(out, **rec, cpu=cpu, sub=sub, n=n, w=w, p=p)
    return circ, w, b, cpu


def parse_w(s):
    out = []
    for part in s.split(","):
        if ":" in part:
            a = list(map(int, part.split(":")))
            out += list(range(a[0], a[1] + 1, a[2] if len(a) > 2 else 1))
        else:
            out.append(int(part))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--p", type=float, required=True)
    ap.add_argument("--w", required=True, help="如 6:30:2 或 4,5,6")
    ap.add_argument("--n", type=int, default=1000, help="每个 w 每个电路的样本数")
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--b0", type=int, default=0, help="起始批编号（追加样本时用新的批号）")
    ap.add_argument("--sub", type=float, default=0.02)
    ap.add_argument("--seed", type=int, default=16116)
    ap.add_argument("--circs", default=",".join(CIRCS))
    ap.add_argument("--decoders", default=",".join(NAMES))
    ap.add_argument("--tlim", type=float, default=120.0)
    ap.add_argument("--pbo", type=float, default=0.25, help="只有 BP-OSD 失败时运行 MLE 的概率")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    assert a.workers <= 3
    names = tuple(a.decoders.split(","))
    outdir = OUT / "fw" / f"p{a.p}"
    outdir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for w in parse_w(a.w):
        for b in range(a.b0, a.b0 + a.n // a.batch):
            for c in a.circs.split(","):
                jobs.append((c, a.p, w, b, a.batch, a.sub, names, a.seed, outdir, a.tlim, a.pbo))
    t0 = time.time()
    with get_context("spawn").Pool(a.workers) as pool:
        for circ, w, b, cpu in pool.imap_unordered(run_batch, jobs):
            print(f"{time.time() - t0:7.0f}s {circ} w{w} b{b} cpu={cpu if cpu is None else round(cpu)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
