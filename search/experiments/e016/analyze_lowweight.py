"""E-016 阶段 3b：由低权重逻辑错误的拆分得到“不可纠正”的低权重故障组合，并用实际解码器核对。experimenter。

读 lowweight.py 的闭包（每个电路、每个 sector 的权重 W 逻辑错误集合，sector 列下标；先验 p=1e-3 的模型）。
对 t（= 4、5）：所有 t 子集 S ⊂ L（|L| = W ∈ wset），S 的补集 S' = L \\ S 与 S 有相同 syndrome、相差一个非平凡逻辑。
  S “不可纠正”（MLE 在 S 上失败）⇔ 存在不同逻辑类、比 S 更可能的解；这里只用已找到的补集：
  failing(S) ⇔ max_L logodds(L \\ S) > logodds(S)（平局记 1/2）。这是**下界**（只用了找到的逻辑错误）。
贡献：C_t(p) = Σ_{failing S} Π_{i∈S} q_i(p) ≈ (p/1e-3)^t · C_t(1e-3)（sd6 下 q_i ∝ p）。
核对：随机抽 --nverify 个 failing S，注入 sector 列，跑 MILP-MLE、BP-OSD、分 sector Relay5，
统计实际失败。

    PYTHONPATH=. uv run python -m search.experiments.e016.analyze_lowweight --nverify 60
"""
from __future__ import annotations

import argparse
import itertools
import json
import time

import numpy as np

from search.experiments.e016.common import CIRCS, OUT, build_model


def failing_sets(sec, logicals, t):
    """向量化：对每个 t 子集 S 取 max_L logodds(L \\ S)，与 logodds(S) 比较。返回 (S 数组 (m, t), 失败权重 (m,), 总子集数)。"""
    lo = np.log(sec.priors) - np.log1p(-sec.priors)
    allS, allA, allC = [], [], []
    byw = {}
    for L in logicals:
        byw.setdefault(len(L), []).append(sorted(L))
    for W, Ls in byw.items():
        Ls = np.array(Ls, dtype=np.int64)
        lv = lo[Ls]
        tot = lv.sum(1)
        combos = np.array(list(itertools.combinations(range(W), t)), dtype=np.int64)
        for i0 in range(0, len(Ls), 2000):
            Lc, lvc, tc = Ls[i0:i0 + 2000], lv[i0:i0 + 2000], tot[i0:i0 + 2000]
            S = Lc[:, combos].reshape(-1, t)
            A = lvc[:, combos].sum(2).reshape(-1)
            C = (tc[:, None] - lvc[:, combos].sum(2)).reshape(-1)
            allS.append(S); allA.append(A); allC.append(C)
    S = np.concatenate(allS); A = np.concatenate(allA); C = np.concatenate(allC)
    order = np.lexsort(tuple(S[:, k] for k in range(t - 1, -1, -1)))
    S, A, C = S[order], A[order], C[order]
    new = np.ones(len(S), bool)
    new[1:] = (S[1:] != S[:-1]).any(1)
    gid = np.cumsum(new) - 1
    Cmax = np.full(gid[-1] + 1, -np.inf)
    np.maximum.at(Cmax, gid, C)
    Su, Au = S[new], A[new]
    fail = np.where(Cmax > Au + 1e-9, 1.0, np.where(np.abs(Cmax - Au) <= 1e-9, 0.5, 0.0))
    keep = fail > 0
    return Su[keep], fail[keep], len(Su)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--nverify", type=int, default=60)
    ap.add_argument("--seed", type=int, default=16316)
    ap.add_argument("--circs", default=",".join(CIRCS))
    a = ap.parse_args(argv)
    rng = np.random.default_rng(a.seed)
    out = {}
    from search.decoders import decoders as D
    for circ in a.circs.split(","):
        m = build_model(circ, 0.001)
        for s in "ZX":
            sec = m.sectors[s]
            f = OUT / "lowweight" / f"{circ}_{s}_logicals.json"
            if not f.exists():
                continue
            clo = [tuple(c) for c in json.loads(f.read_text())["closure"]]
            byw = {}
            for c in clo:
                byw.setdefault(len(c), []).append(c)
            wmin = min(byw)
            res = {"closure_by_w": {w: len(v) for w, v in sorted(byw.items())}, "w_min": wmin}
            decs = D.make(sec, ("bposd", "relay5"))
            ref = D.make_ref(sec)
            Hr = sec.H.tocsr()
            for t in (4, 5):
                wl = {4: (8, 9, 10), 5: (9, 10)}[t]
                logs = [L for w, v in byw.items() if w in wl for L in v]
                if not logs:
                    continue
                FS, FV, nsub = failing_sets(sec, logs, t)
                C = float((FV * np.prod(sec.priors[FS], axis=1)).sum()) if len(FS) else 0.0
                row = {"n_tsubsets_examined": nsub, "n_failing": float(FV.sum()),
                       "C_t_at_p1e-3": C, "from_weights": sorted({len(L) for L in logs})}
                # 核对
                ver = {"n": 0, "mle_fail": 0, "mle_nonopt": 0, "bposd_fail": 0, "relay5_fail": 0}
                t0 = time.process_time()
                for idx in rng.permutation(len(FS))[:a.nverify]:
                    S = tuple(FS[idx].tolist())
                    for tag, cols in (("", S),):
                        e = np.zeros(sec.H.shape[1], np.uint8)
                        e[list(cols)] = 1
                        syn = (Hr @ e) % 2
                        ob = (sec.L @ e) % 2
                        r = ref.decode(syn, time_limit=120)
                        ver["n"] += 1
                        ver["mle_nonopt"] += r.status != "OPTIMAL"
                        ver["mle_fail"] += bool(r.e is None or ((sec.L @ r.e) % 2 != ob).any())
                        for nm, dec in decs.items():
                            eh = dec.decode(syn)
                            ver[f"{nm}_fail"] += bool(((sec.L @ eh) % 2 != ob).any())
                ver["cpu"] = time.process_time() - t0
                row["verify"] = ver
                res[f"t{t}"] = row
                print(circ, s, f"t={t}", json.dumps(row), flush=True)
            out[f"{circ}_{s}"] = res
    (OUT / "lowweight_splits.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
