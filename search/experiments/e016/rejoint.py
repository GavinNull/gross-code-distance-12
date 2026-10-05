"""E-016 阶段 D：在固定权重样本上补跑联合 Relay5。experimenter。

联合 Relay5 太贵（w=60 时 15 s/样本），不能对全部固定权重样本运行。对 fw/p{prior}/ 下每个批文件：
  * BP-OSD 或分 sector Relay5 在任一 sector 失败的样本：必跑（概率 1）；
  * 其余样本：按概率 --sub 随机抽样（种子由批文件名决定），Horvitz–Thompson 加权。
（直接采样 p=4e-3 中，联合 Relay5 的 5 次失败里 4 次同时有 BP-OSD 或分 sector Relay5 失败，所以“必跑”部分覆盖了大部分。）
样本的 detector / observable 由保存的故障集合重算（与 run_fw 相同），解码器对象与 run_direct 相同。
输出与原批文件同名加后缀 _rj.npz：rj_run, rj_pi, rj_fZ, rj_fX, rj_conv。

    PYTHONPATH=. uv run python -m search.experiments.e016.rejoint --prior 0.002 --sub 0.05 --workers 3
"""
from __future__ import annotations

import argparse
import time
import zlib
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from search.experiments.e016.common import OUT
from search.experiments.e016.run_direct import _setup
from search.experiments.e016.run_fw import full_matrices


def work(args):
    f, prior, sub = args
    out = f.with_name(f.stem + "_rj.npz")
    if out.exists():
        return f.name, None, 0
    t0 = time.process_time()
    z = np.load(f)
    circ = f.name.split("_w")[0]
    st = _setup(circ, prior, ("relay_j",))
    m = st["m"]
    Hf, Lf = full_matrices(m)
    sets = z["sets"].astype(np.int64)
    n, w = sets.shape
    must = z["bposd_fZ"] | z["bposd_fX"] | z["relay_s_fZ"] | z["relay_s_fX"]
    rng = np.random.default_rng(zlib.crc32(f.name.encode()))
    u = rng.random(n)
    run = must | (u < sub)
    pi = np.where(must, 1.0, sub)
    rec = {"rj_run": run, "rj_pi": pi, "rj_fZ": np.zeros(n, bool), "rj_fX": np.zeros(n, bool),
           "rj_conv": np.ones(n, bool)}
    idx = np.flatnonzero(run)
    if len(idx):
        E = sp.csr_matrix((np.ones(len(idx) * w, np.int32), (np.repeat(np.arange(len(idx)), w), sets[idx].ravel())),
                          shape=(len(idx), len(m.priors)))
        dets = ((E @ Hf).toarray() % 2).astype(np.uint8)
        obs = ((E @ Lf).toarray() % 2).astype(np.uint8)
        for k, i in enumerate(idx):
            d, tr = dets[k], obs[k]
            if d.any():
                r = st["relay_j"].decode_detailed(d)
                pred = (st["Lj"] @ np.asarray(r.decoding, dtype=np.uint8)) % 2
                rec["rj_conv"][i] = bool(r.success)
            else:
                pred = np.zeros_like(tr)
            rec["rj_fZ"][i] = bool((pred[:m.oz] != tr[:m.oz]).any())
            rec["rj_fX"][i] = bool((pred[m.oz:] != tr[m.oz:]).any())
    cpu = time.process_time() - t0
    np.savez_compressed(out, **rec, cpu=cpu, sub=sub)
    return f.name, cpu, int(run.sum())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prior", type=float, default=0.002)
    ap.add_argument("--sub", type=float, default=0.05)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--wmax", type=int, default=999, help="只补跑 w <= wmax 的批")
    a = ap.parse_args(argv)
    assert a.workers <= 3
    files = sorted(f for f in (OUT / "fw" / f"p{a.prior}").glob("*.npz") if not f.stem.endswith("_rj")
                   and int(f.stem.split("_w")[1][:3]) <= a.wmax)
    t0 = time.time()
    with get_context("spawn").Pool(a.workers) as pool:
        for name, cpu, nrun in pool.imap_unordered(work, [(f, a.prior, a.sub) for f in files]):
            print(f"{time.time() - t0:7.0f}s {name} ran {nrun} cpu={cpu if cpu is None else round(cpu)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
