"""E-008：Relay-BP 失败解剖。

对 Relay-BP 失败的每个 shot，用 CP-SAT MLE 求最可能错误，按四类归档：
  (i)  not_converged   Relay 没找到满足 syndrome 的解
  (ii) heavier_wrong   收敛到错误逻辑类，且 Relay 解比 MLE 解更不可能
  (iii) tie_wrong      收敛到错误逻辑类，与 MLE 解等可能（先验加权权重相同）
  (iv) mle_fails       MLE 也预测错（不可纠正）
另记录 (ii)/(iii) 中差向量 ê⊕e* 的先验加权权重与机制数，看它是否是“一次低权重逻辑翻转”。

    uv run python -m search.experiments.e008.anatomy --task bb72-dec-p3e-3 --shots 20000 --sector Z
分析用种子，不是评估器的保密种子；结果不上榜。
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import relay_bp
from ortools.sat.python import cp_model

from evaluators.decoder_problem import build_instance
from evaluators.tasks import get_task

RELAY_PARAMS = dict(alpha=None, gamma0=0.125, pre_iter=80, num_sets=300, set_max_iter=60,
                    gamma_dist_interval=(-0.24, 0.66), stop_nconv=5, seed=0)
SCALE = 1000.0


def mle(rows, w, syndrome, time_limit=60.0):
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{j}") for j in range(len(w))]
    for i, cols in enumerate(rows):
        t = m.NewIntVar(0, len(cols) // 2, f"t{i}")
        m.Add(sum(x[j] for j in cols) - 2 * t == int(syndrome[i]))
    m.Minimize(sum(int(round(SCALE * w[j])) * x[j] for j in range(len(w))))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.num_workers = 1
    s.parameters.random_seed = 0
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, False
    return np.array([s.Value(v) for v in x], dtype=np.uint8), st == cp_model.OPTIMAL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--shots", type=int, default=20000)
    ap.add_argument("--sector", default="Z")
    ap.add_argument("--seed", type=int, default=20261004)
    ap.add_argument("--out", default="results/E-008-relay-failure-anatomy")
    a = ap.parse_args()

    inst = build_instance(get_task(a.task))
    P = inst.sectors[a.sector]
    H = P.H.tocsr().astype(np.uint8)
    L = P.L.tocsr().astype(np.uint8)
    pri = np.clip(np.asarray(P.priors, dtype=np.float64), 1e-15, 0.5 - 1e-12)
    w = np.log((1 - pri) / pri)
    rows = [H.indices[H.indptr[i]:H.indptr[i + 1]].tolist() for i in range(H.shape[0])]
    dec = relay_bp.RelayDecoderF64(H, error_priors=pri, **RELAY_PARAMS)

    sampler = inst.circuit.compile_detector_sampler(seed=a.seed)
    dets, obs = sampler.sample(a.shots, separate_observables=True)
    nz, oz = inst.num_det_z, inst.num_obs_z
    if a.sector == "Z":
        dets, obs = dets[:, :nz], obs[:, :oz]
    else:
        dets, obs = dets[:, nz:], obs[:, oz:]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rec_path = out / f"{a.task}_{a.sector}_records.jsonl"
    counts = {"not_converged": 0, "heavier_wrong": 0, "tie_wrong": 0, "mle_fails": 0, "lighter_wrong": 0,
              "mle_unproved": 0}
    relay_fail = 0
    t0 = time.time()
    with rec_path.open("w") as f:
        for i in range(a.shots):
            syn = dets[i].astype(np.uint8)
            if not syn.any():
                if obs[i].any():
                    relay_fail += 1
                    counts["mle_fails"] += 1
                continue
            r = dec.decode_detailed(syn)
            e_r = np.asarray(r.decoding, dtype=np.uint8)
            pred = (L @ e_r) % 2
            if np.array_equal(pred.astype(bool), obs[i]):
                continue
            relay_fail += 1
            valid = np.array_equal((H @ e_r) % 2, syn)
            e_m, proved = mle(rows, w, syn)
            if e_m is None or not proved:
                counts["mle_unproved"] += 1
                continue
            mle_ok = np.array_equal(((L @ e_m) % 2).astype(bool), obs[i])
            wr = float(w[e_r.astype(bool)].sum())
            wm = float(w[e_m.astype(bool)].sum())
            diff = e_r ^ e_m
            if not mle_ok:
                cat = "mle_fails"
            elif not (r.success and valid):
                cat = "not_converged"
            elif abs(wr - wm) < 1e-6:
                cat = "tie_wrong"
            elif wr > wm:
                cat = "heavier_wrong"
            else:
                cat = "lighter_wrong"    # 不应出现（MLE 证明最优）；出现即说明建模不一致
            counts[cat] += 1
            f.write(json.dumps({"shot": i, "cat": cat, "relay_success": bool(r.success), "relay_valid": bool(valid),
                                "iters": int(r.iterations), "w_relay": wr, "w_mle": wm,
                                "n_relay": int(e_r.sum()), "n_mle": int(e_m.sum()), "n_diff": int(diff.sum()),
                                "w_diff": float(w[diff.astype(bool)].sum()),
                                "diff_logical": ((L @ diff) % 2).astype(int).tolist()}) + "\n")
            f.flush()
            if relay_fail % 10 == 0:
                print(f"[{time.time() - t0:7.0f}s] shot {i}/{a.shots} relay_fail={relay_fail} {counts}", flush=True)

    summary = {"task": a.task, "sector": a.sector, "shots": a.shots, "seed": a.seed, "relay_params": RELAY_PARAMS,
               "relay_fail": relay_fail, "counts": counts, "seconds": time.time() - t0}
    (out / f"{a.task}_{a.sector}_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
