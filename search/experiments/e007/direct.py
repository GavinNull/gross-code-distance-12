"""不受评估器速度预算限制的对照：直接调官方 relay_bp 包（不经沙箱），在评估器同一批 shot 上（同一 split 根种子、同一 batch
划分、同样的 worker 分批顺序）打分。用途：区分“调参收益”与“多花算力的收益”。

只为保护本实验的 CPU 预算，加了一个宽松的安全上限 K_UNRES（默认 8）：每批每 sector 的累计 CPU 超过
K_UNRES x 基线(论文参数)平均 CPU/shot x 批大小 时，本批剩余 shot 记失败（与评估器的批预算同一机制，只是倍数更大）。
"""
from __future__ import annotations

import multiprocessing as mp
import time

import numpy as np

import os
K_UNRES = float(os.environ.get("E007_K_UNRES", "8"))
_STATE: dict = {}


def prepare(task_id: str, split: str, shots: int):
    """父进程：构建实例、采样好所有批（fork 后子进程共享）。"""
    from evaluators import decoder_problem as dp
    from evaluators.tasks import get_task
    task = get_task(task_id)
    inst = dp.build_instance(task)
    root = dp.split_root(task.task_id, task.hash(), split)
    bs = int(task.decoder["search"]["batch_size"]) if split != "holdout" else int(task.stop["batch_size"])
    nb = -(-shots // bs)
    batches = [dp.sample_batch(inst, root, b, bs) for b in range(nb)]
    _STATE.update(task=task, inst=inst, bs=bs, batches=batches, task_id=task_id)
    return task, inst, bs, nb


def _worker(w, nworkers, params, cap_per_shot, q, batch_ids):
    import relay_bp
    inst, batches, bs = _STATE["inst"], _STATE["batches"], _STATE["bs"]
    out = {}
    for s in ("Z", "X"):
        sp_ = inst.sectors[s]
        H, L = sp_.H.tocsr(), sp_.L
        dec = relay_bp.RelayDecoderF64(H, error_priors=np.asarray(sp_.priors, dtype=np.float64), alpha=params["alpha"],
                                       gamma0=params["gamma0"], pre_iter=params["pre_iter"],
                                       num_sets=params["num_sets"], set_max_iter=params["set_max_iter"],
                                       gamma_dist_interval=tuple(params["gamma_dist_interval"]),
                                       stop_nconv=params["stop_nconv"], seed=params["seed"])
        runner = relay_bp.ObservableDecoderRunner(dec, L.tocsc(), include_decode_result=False)
        for b in batch_ids[w::nworkers]:
            dets, obs = batches[b][s]
            n = dets.shape[0]
            fail = np.zeros(n, dtype=bool)
            cpu = np.zeros(n)
            budget = None if cap_per_shot is None else cap_per_shot[s] * n
            used = 0.0
            for i in range(n):
                if budget is not None and used > budget:
                    fail[i:] = True
                    break
                t = time.process_time()
                o = np.asarray(runner.decode_observables(dets[i].astype(np.uint8))).astype(bool)
                dt = time.process_time() - t
                cpu[i] = dt
                used += dt
                fail[i] = bool((o != obs[i]).any())
            out[(s, b)] = (fail, cpu)
    q.put((w, out))


def run(params: dict, nworkers: int = 3, cap_per_shot: dict | None = None, shots: int | None = None, batch_ids=None):
    """返回 dict：fail_Z, fail_X（逐 shot bool）, cpu_Z, cpu_X, n。"""
    if batch_ids is None:
        batch_ids = list(range(len(_STATE["batches"])))
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    ps = [ctx.Process(target=_worker, args=(w, nworkers, params, cap_per_shot, q, batch_ids)) for w in range(nworkers)]
    for p in ps:
        p.start()
    res = {}
    for _ in ps:
        w, o = q.get()
        res.update(o)
    for p in ps:
        p.join()
    cat = lambda s, k: np.concatenate([res[(s, b)][k] for b in batch_ids])  # noqa: E731
    r = {"fail_Z": cat("Z", 0), "fail_X": cat("X", 0), "cpu_Z": cat("Z", 1), "cpu_X": cat("X", 1)}
    if shots is not None:
        for k in r:
            r[k] = r[k][:shots]
    r["n"] = len(r["fail_Z"])
    return r
