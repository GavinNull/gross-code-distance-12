"""E-016 阶段 3：低权重层的“不可纠正”故障组合。experimenter。

对每个电路、每个 sector（10 轮模型，先验取 --p）：
 1) 随机 BP-OSD 搜索最低权重的不可检测逻辑错误（arXiv:2603.05481 Eq. 12，与 E-002/E-003 审计 lowweight_count 相同：
    随机 (a, b) 生成一行 eta = a L + b H，解 [H; eta] e = (0, 1)，BP min-sum 100 次 + OSD-CS 10，error_rate 0.01），
    保留权重 <= --wmax 的所有不同解（sector 列集合；一个 sector 列 = 一个电路故障，所以列数 = 故障数）。
 2) 时空平移闭包：BB 码的平移 (a, b) ∈ Z_9 × Z_6 作用在校验下标 i = x*6 + y 上，轮次平移 Δ 作用在 detector 的轮次上
    （sector detector d -> (r = d // 54, i = d % 54)）。一个解的平移像若每一列都映射到一个存在的列（detector 集合相同）
    且仍是逻辑错误，就加入集合。电路不在某个平移下对称时，像会因 detector 集合不存在而被拒绝（自动处理两色电路
    只在 y 偶数平移下对称的情形）；先打印每个平移下“能映射的列”的比例作为自检。
 3) 拆分：权重 W 的逻辑错误 L 的每个 t 子集 S 与补集 S' = L \\ S 有相同 syndrome、相差一个逻辑算符，所以任何解码器
    在 S 与 S' 中至少错一个。按似然（先验乘积）较小的一方计为“不可纠正”（MLE 在没有更好的第三种解时就错在这一方）。
    对 IBM：W = 8，t = 4；对两色：W = 10，t = 4（看 6 故障的补集是否可能比 4 故障更可能）与 t = 5。
 4) 对拆分得到的 t 子集抽样，用精确 MLE（分 sector，HiGHS MILP）与 bposd / relay_s 实际解码，核对。

    PYTHONPATH=. uv run python -m search.experiments.e016.lowweight --circ ibm --trials 4000 --wmax 9 --workers 3
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from multiprocessing import get_context

import numpy as np
import scipy.sparse as sp

from search.experiments.e016.common import OUT, build_model

NCHK, LL, MM = 54, 9, 6
_M = {}


def _model(circ, p):
    if (circ, p) not in _M:
        _M.clear()
        _M[(circ, p)] = build_model(circ, p)
    return _M[(circ, p)]


def search(args):
    circ, p, s, trials, seed, wmax, weighted = args
    from ldpc import BpOsdDecoder
    m = _model(circ, p)
    sec = m.sectors[s]
    D = sec.H.tocsr().astype(np.uint8)
    Lm = sec.L.tocsr().astype(np.uint8)
    rng = np.random.default_rng(seed)
    sols = {}
    t0 = time.process_time()
    for _ in range(trials):
        a = rng.integers(0, 2, Lm.shape[0])
        if not a.any():
            a[rng.integers(Lm.shape[0])] = 1
        b = rng.integers(0, 2, D.shape[0])
        eta = ((a @ Lm) + (b @ D)) % 2
        H = sp.vstack([D, sp.csr_matrix(eta.astype(np.uint8))]).tocsr()
        syn = np.zeros(H.shape[0], dtype=np.uint8)
        syn[-1] = 1
        if weighted:   # 按先验加权（偏向最可能的逻辑错误；先验统一放大到均值 0.01）
            ch = list(np.minimum(sec.priors * (0.01 / sec.priors.mean()), 0.4))
            dec = BpOsdDecoder(H, error_channel=ch, max_iter=100, bp_method="minimum_sum", osd_method="osd_cs",
                               osd_order=10)
        else:
            dec = BpOsdDecoder(H, error_rate=0.01, max_iter=100, bp_method="minimum_sum", osd_method="osd_cs",
                               osd_order=10)
        xi = dec.decode(syn)
        cols = tuple(np.nonzero(xi)[0].tolist())
        assert not ((D @ xi) % 2).any() and ((Lm @ xi) % 2).any()
        if len(cols) <= wmax:
            sols[cols] = sols.get(cols, 0) + 1
    return circ, s, seed, {"sols": [list(k) for k in sols], "hits": list(sols.values()),
                           "cpu": time.process_time() - t0}


def det_maps(sec):
    """每列的 detector 集合 -> 列下标。"""
    H = sec.H.tocsc()
    keys = [tuple(H.indices[H.indptr[j]:H.indptr[j + 1]].tolist()) for j in range(H.shape[1])]
    return keys, {k: j for j, k in enumerate(keys)}


def chk_perm(a, b):
    return np.array([((i // MM + a) % LL) * MM + (i % MM + b) % MM for i in range(NCHK)])


def translate_cols(cols, keys, kidx, perm, dt, ndet):
    out = []
    for j in cols:
        nd = []
        for d in keys[j]:
            r, i = divmod(d, NCHK)
            r2 = r + dt
            d2 = r2 * NCHK + perm[i]
            if r2 < 0 or d2 >= ndet:
                return None
            nd.append(d2)
        j2 = kidx.get(tuple(sorted(nd)))
        if j2 is None:
            return None
        out.append(j2)
    return tuple(sorted(out))


def closure(sec, sols, rmax=11):
    keys, kidx = det_maps(sec)
    ndet = sec.H.shape[0]
    L = sec.L.tocsc()
    H = sec.H.tocsc()
    allsets = set()
    sym_report = {}
    perms = {(a, b): chk_perm(a, b) for a in range(LL) for b in range(MM)}
    # 自检：每个空间平移下能映射的列所占比例（dt=0）
    for (a, b), pm in perms.items():
        ok = sum(translate_cols([j], keys, kidx, pm, 0, ndet) is not None for j in range(len(keys)))
        sym_report[f"{a},{b}"] = round(ok / len(keys), 4)
    good = [k for k, v in sym_report.items() if v > 0.9]
    for S in sols:
        for k in good:
            a, b = map(int, k.split(","))
            for dt in range(-rmax, rmax + 1):
                T = translate_cols(S, keys, kidx, perms[(a, b)], dt, ndet)
                if T is None or len(set(T)) != len(S):
                    continue
                e = np.zeros(H.shape[1], np.uint8)
                e[list(T)] = 1
                if ((H @ e) % 2).any() or not ((L @ e) % 2).any():
                    continue
                allsets.add(T)
    return allsets, sym_report


def split_stats(sec, L8, t):
    """所有 W 权重逻辑的 t | W-t 拆分；返回 {t 子集: (logP_S, logP_comp)}，只保留 t 子集一侧。"""
    lq = np.log(sec.priors) - np.log1p(-sec.priors)   # log odds
    out = {}
    for Lset in L8:
        Lset = tuple(Lset)
        tot = lq[list(Lset)].sum()
        for S in itertools.combinations(Lset, t):
            a = lq[list(S)].sum()
            prev = out.get(S)
            comp = tot - a
            if prev is None or comp > prev[1]:
                out[S] = (float(a), float(comp))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--circ", required=True)
    ap.add_argument("--p", type=float, default=0.001)
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--chunks", type=int, default=6)
    ap.add_argument("--wmax", type=int, default=9)
    ap.add_argument("--seed", type=int, default=16216)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--weighted", action="store_true", help="BP-OSD 用按先验加权的信道（找最可能的逻辑错误）")
    ap.add_argument("--merge", action="store_true", help="与已有 logicals.json 的 found 合并后再求闭包")
    a = ap.parse_args(argv)
    assert a.workers <= 3
    outdir = OUT / "lowweight"
    outdir.mkdir(parents=True, exist_ok=True)
    tasks = [(a.circ, a.p, s, a.trials // a.chunks, a.seed + 1000 * k + (0 if s == "Z" else 500), a.wmax,
              a.weighted)
             for s in "ZX" for k in range(a.chunks)]
    raw = {"Z": {}, "X": {}}
    cpu = 0.0
    t0 = time.time()
    with get_context("spawn").Pool(a.workers) as pool:
        for circ, s, seed, r in pool.imap_unordered(search, tasks):
            for c, h in zip(r["sols"], r["hits"]):
                raw[s][tuple(c)] = raw[s].get(tuple(c), 0) + h
            cpu += r["cpu"]
            print(f"{time.time() - t0:6.0f}s {s} seed {seed}: {len(r['sols'])} sols <= {a.wmax}, cpu {r['cpu']:.0f}",
                  flush=True)
    m = _model(a.circ, a.p)
    summ = {"args": vars(a), "search_cpu": cpu}
    for s in "ZX":
        sec = m.sectors[s]
        new = set(raw[s])
        prev = set()
        f = outdir / f"{a.circ}_{s}_logicals.json"
        if a.merge and f.exists():
            old = json.loads(f.read_text())
            prev = {tuple(c) for c in old["found"]}
            for c, h in zip(old["found"], old["hits"]):
                raw[s][tuple(c)] = raw[s].get(tuple(c), 0) + h
        summ.setdefault("new_not_in_previous_found", {})[s] = len(new - prev)
        found = list(raw[s])
        byw = {}
        for c in found:
            byw.setdefault(len(c), []).append(c)
        t1 = time.process_time()
        clo, symrep = closure(sec, found)
        cbyw = {}
        for c in clo:
            cbyw.setdefault(len(c), []).append(c)
        summ[s] = {"found_by_w": {w: len(v) for w, v in sorted(byw.items())},
                   "closure_by_w": {w: len(v) for w, v in sorted(cbyw.items())},
                   "sym_ok_fraction": symrep, "closure_cpu": time.process_time() - t1,
                   "min_w": min(byw) if byw else None}
        (outdir / f"{a.circ}_{s}_logicals.json").write_text(json.dumps(
            {"found": [list(c) for c in found], "hits": [raw[s][c] for c in found],
             "closure": [list(c) for c in sorted(clo)]}))
        print(s, json.dumps({k: v for k, v in summ[s].items() if k != "sym_ok_fraction"}), flush=True)
        print(s, "symmetry check (fraction of columns mapped):",
              {k: v for k, v in symrep.items() if v > 0.5}, flush=True)
    (outdir / f"{a.circ}_summary{'_merged' if a.merge else ''}.json").write_text(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
