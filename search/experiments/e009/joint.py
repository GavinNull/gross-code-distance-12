"""E-009：联合（X/Z）解码的提升空间。同一批 shot 上比较四个解码器：
  relay_sector  分 sector 的 Relay-BP（Z、X 各自解码）
  relay_joint   在完整联合 DEM 上运行的 Relay-BP
  mle_sector    分 sector 的精确 MLE（HiGHS MILP）
  mle_joint     联合 DEM 上的精确 MLE
失败 = 任一 observable 预测错。只考虑带探测器的机制；无探测器的 observable 翻转任何解码器都看不到，对所有解码器同样计为失败。

    uv run python -m search.experiments.e009.joint --code bb72 --p 0.004 --shots 2000 --workers 4
"""
import argparse
import json
import time
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import relay_bp
import scipy.sparse as sp

from search.decoders.common import build_model, sample_dem
from search.decoders.exact import MilpMLE

RELAY5 = dict(alpha=None, gamma0=0.1, pre_iter=80, num_sets=300, set_max_iter=60,
              gamma_dist_interval=(-0.24, 0.66), stop_nconv=5, seed=0)
_S = {}


def joint_matrices(m):
    """完整联合 DEM：只保留至少触发一个探测器的机制。"""
    rows, cols, orows, ocols, pri = [], [], [], [], []
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
        if not d:
            continue
        rows += sorted(d); cols += [j] * len(d)
        orows += sorted(o); ocols += [j] * len(o)
        pri.append(inst.args_copy()[0])
        j += 1
    H = sp.csc_matrix((np.ones(len(rows), np.uint8), (rows, cols)), shape=(m.circuit.num_detectors, j))
    L = sp.csr_matrix((np.ones(len(orows), np.uint8), (orows, ocols)), shape=(m.circuit.num_observables, j))
    return H, L, np.array(pri)


def _setup(code, p):
    m = build_model(code, p)
    Hj, Lj, pj = joint_matrices(m)
    st = {"m": m, "joint": (Hj.tocsr(), Lj.tocsr(), pj)}
    st["relay_joint"] = relay_bp.RelayDecoderF64(Hj.tocsr(), error_priors=pj, **RELAY5)
    st["mle_joint"] = MilpMLE(Hj, np.log((1 - pj) / pj))
    for s in "ZX":
        S = m.sectors[s]
        st[f"relay_{s}"] = relay_bp.RelayDecoderF64(S.H.tocsr(), error_priors=S.priors, **RELAY5)
        st[f"mle_{s}"] = MilpMLE(S.H, S.weights)
    return st


def work(args):
    code, p, seed, b, bs = args
    if (code, p) not in _S:
        _S.clear()
        _S[(code, p)] = _setup(code, p)
    st = _S[(code, p)]
    m = st["m"]
    nz, oz = m.nz, m.oz
    s_seed = int(np.random.SeedSequence([seed, b]).generate_state(1, dtype=np.uint32)[0])
    dets, obs, _ = sample_dem(m, bs, s_seed)
    Hj, Lj, _pj = st["joint"]
    out = []
    for i in range(bs):
        d = dets[i].astype(np.uint8)
        truth = obs[i].astype(np.uint8)
        rec = {"b": b, "i": i}
        if not d.any():
            for k in ("relay_sector", "relay_joint", "mle_sector", "mle_joint"):
                rec[k] = bool(truth.any())
            out.append(rec)
            continue
        dz, dx = d[:nz], d[nz:]
        # 分 sector Relay
        pred = np.zeros_like(truth)
        for s, ds, sl in (("Z", dz, slice(0, oz)), ("X", dx, slice(oz, None))):
            if ds.any():
                e = np.asarray(st[f"relay_{s}"].decode(ds), dtype=np.uint8)
                pred[sl] = (m.sectors[s].L @ e) % 2
        rec["relay_sector"] = bool((pred != truth).any())
        # 联合 Relay
        e = np.asarray(st["relay_joint"].decode(d), dtype=np.uint8)
        rec["relay_joint"] = bool((((Lj @ e) % 2).astype(np.uint8) != truth).any())
        # 分 sector MLE
        pred = np.zeros_like(truth)
        status = []
        for s, ds, sl in (("Z", dz, slice(0, oz)), ("X", dx, slice(oz, None))):
            if ds.any():
                r = st[f"mle_{s}"].decode(ds, time_limit=60.0)
                status.append(r.status)
                if r.e is not None:
                    pred[sl] = (m.sectors[s].L @ r.e) % 2
        rec["mle_sector"] = bool((pred != truth).any())
        rec["mle_sector_status"] = status
        # 联合 MLE
        r = st["mle_joint"].decode(d, time_limit=30.0)
        rec["mle_joint_status"] = r.status
        rec["mle_joint"] = True if r.e is None else bool((((Lj @ r.e) % 2).astype(np.uint8) != truth).any())
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="bb72")
    ap.add_argument("--p", type=float, default=0.004)
    ap.add_argument("--shots", type=int, default=2000)
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261004)
    ap.add_argument("--out", default="results/E-009-joint-decoding-headroom")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{a.code}_p{a.p}"
    rec_path = out / f"{tag}_records.jsonl"
    nb = a.shots // a.batch
    t0 = time.time()
    keys = ("relay_sector", "relay_joint", "mle_sector", "mle_joint")
    fails = dict.fromkeys(keys, 0)
    n = 0
    with get_context("spawn").Pool(a.workers) as pool, rec_path.open("w") as f:
        for recs in pool.imap_unordered(work, [(a.code, a.p, a.seed, b, a.batch) for b in range(nb)]):
            for r in recs:
                f.write(json.dumps(r) + "\n")
                n += 1
                for k in keys:
                    fails[k] += int(r[k])
            f.flush()
            print(f"[{time.time() - t0:6.0f}s] shots={n} fails={fails}", flush=True)
    summary = {"code": a.code, "p": a.p, "shots": n, "seed": a.seed, "relay_params": {**RELAY5,
               "gamma_dist_interval": list(RELAY5["gamma_dist_interval"])}, "fails": fails,
               "seconds": time.time() - t0}
    (out / f"{tag}_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
