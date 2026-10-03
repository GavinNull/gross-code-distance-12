"""解码器问题（H-005）：把评估器的解码器任务接入 LLM 进化框架。

只通过评估器的**公开入口**交互：
  - `evaluators.decoder_eval.evaluate_decoder(task_id, src, split="search", ...)` 给搜索集打分（永远不写榜）；
  - `evaluators.decoder_refs.program_for(name, params)` 取参考程序源码作为种子 / 退火的程序模板。
候选程序在评估器的沙箱里运行（每个 sector 一个子进程，sandbox-exec + audit hook），这里不执行候选代码。

两种接口（由任务决定）：
  - program：候选是完整程序 `make_decoder(H, L, priors, info) -> decode(syndrome)`。“BP + 后处理”只是这里给 LLM 的
    一个模板（`BP_POSTPROCESS_TEMPLATE`），评估器始终接收完整程序。
  - mp_rule：候选是局部更新规则（`check_rule` / `var_rule` / `SCHEDULE`），评估器的引擎执行并强制迭代上限。

分数（越大越好）= −P_any（搜索集）。超时 / 异常 / 输出格式错误的 shot 按失败计，所以已经含在分数里。
模拟退火对照（`SolutionSpace`）：在 Relay-BP 类参数空间上（每段迭代数、γ 分布、段数、S、γ0）退火，
解经 `solution_to_program` 变成同一个评估入口的程序，评估次数口径相同（CLAUDE.md 铁律 5）。
注意：速度预算按 CPU 时间判定，机器负载会让个别 shot 的超时判定有抖动，所以 evaluate 不是严格确定性的
（缓存按源码哈希，同一源码只评一次）。
"""
from __future__ import annotations

import math
import random
import threading
from typing import Any

from .problem import EvalResult, Problem

BP_POSTPROCESS_TEMPLATE = '''\
import numpy as np
import relay_bp


def make_decoder(H, L, priors, info):
    """Template: a BP stage (official Relay-BP package) followed by an optional post-processing hook."""
    bp = relay_bp.RelayDecoderF64(H.tocsr(), error_priors=np.asarray(priors, dtype=np.float64), alpha=None,
                                  gamma0=0.125, pre_iter=80, num_sets=300, set_max_iter=60,
                                  gamma_dist_interval=(-0.24, 0.66), stop_nconv=5, seed=0)
    Hr = H.tocsr()
    Lr = L.tocsr()

    def postprocess(syndrome, e):
        return e                       # e.g. local search on the residual syndrome, cluster repair, ...

    def decode(syndrome):
        e = np.asarray(bp.decode(syndrome), dtype=np.uint8)
        e = postprocess(syndrome, e)
        return (Lr @ e) % 2

    return decode
'''

_PARAM_SPACE = {
    "gamma0": (0.0, 0.6, float), "lo": (-0.8, 0.4, float), "width": (0.1, 1.6, float),
    "pre_iter": (10, 400, int), "set_max_iter": (10, 300, int), "num_sets": (5, 600, int),
    "stop_nconv": (1, 20, int),
}


class DecoderProblem(Problem):
    def __init__(self, task_id: str = "bb72-dec-p3e-3", shots: int | None = None, num_workers: int = 3,
                 use_os_sandbox: bool | None = None, split: str = "search"):
        from evaluators.tasks import get_task
        self.task_id = task_id
        self.task = get_task(task_id)
        if self.task.kind != "decoder":
            raise ValueError(f"{task_id} is not a decoder task")
        self.interface = self.task.decoder["interface"]
        self.name = f"decoder:{task_id}"
        self.function_name = "make_decoder" if self.interface == "program" else "check_rule"
        self.shots = shots
        self.num_workers = num_workers
        self.use_os_sandbox = use_os_sandbox
        if split not in ("search", "public"):
            raise ValueError("DecoderProblem only uses the search split (or public for self-test tasks)")
        self.split = split
        self._lock = threading.Lock()     # 评估本身已用 num_workers 个进程；串行化，避免超过 CPU 配额

    def fingerprint(self) -> dict[str, Any]:
        return {**super().fingerprint(), "task_id": self.task_id, "task_hash": self.task.hash(),
                "shots": self.shots, "split": self.split}

    # ------------------------------------------------------------------
    def description(self) -> str:
        t = self.task
        sp = t.decoder["speed"]
        n = self.shots or t.decoder["search"]["shots"]
        common = (
            f"Decoding task {t.task_id}: {t.description}\n\n"
            "Setting: a memory experiment of a CSS code under circuit-level noise. The X and Z sectors are decoded "
            "separately; each sector gets its own decoder instance (in its own sandboxed process) and sees only "
            "its own syndrome. Per sector you get the detector error model as matrices:\n"
            "  H: scipy.sparse.csc_matrix (num_detectors x num_mechanisms, uint8) - which detectors each fault "
            "mechanism flips;\n  L: scipy.sparse.csr_matrix (k x num_mechanisms, uint8) - which logical observables "
            "it flips;\n  priors: numpy float64 array (num_mechanisms,) - independent fault probabilities;\n"
            "  info: dict with 'sector', 'rounds', 'p', 'num_detectors', 'num_observables', 'detector_coords' "
            "(per detector [check row, round, type]) and 'code' (n, k, check supports).\n"
            f"Score = -(fraction of {n} fixed search shots where the X or the Z sector predicts a wrong logical "
            "observable); higher is better. The reference is Relay-BP (arXiv:2506.01779, official relay_bp "
            "package). Speed budget per shot and sector: "
            f"{sp['K']} x max(Relay-BP CPU time on that shot, Relay-BP mean, {sp['min_shot_cap_s'] * 1e3:.0f} ms); "
            f"total per batch {sp['K']} x Relay-BP's; building the decoder at most {sp['build_cpu_s']:.0f} CPU s. "
            "Shots over budget, exceptions and malformed outputs count as failures. The final ranking uses a "
            "separate secret held-out set, so do not try to memorise the search shots.\n"
            "Available libraries: numpy, scipy, ldpc (BpOsdDecoder, BpLsdDecoder, ...), relay_bp "
            "(RelayDecoderF64(check_matrix, error_priors, alpha, gamma0, pre_iter, num_sets, set_max_iter, "
            "gamma_dist_interval, stop_nconv, seed) with .decode(syndrome) -> error vector, MinSumBPDecoderF64, "
            "ObservableDecoderRunner), pymatching, and the standard library. No files, network, subprocesses, "
            "threads pools or ctypes.\n")
        if self.interface == "program":
            return common + (
                "Write a complete program defining\n\n    def make_decoder(H, L, priors, info):\n        ...\n"
                "        return decode   # decode(syndrome: numpy uint8 array (num_detectors,)) -> k bits\n\n"
                "decode must return a list / numpy array of exactly k entries, each 0 or 1 (the predicted flip of "
                "each logical observable). A useful template is 'BP + post-processing':\n\n"
                + BP_POSTPROCESS_TEMPLATE)
        mp = self.task.decoder["mp"]
        return common + (
            f"Message-passing interface: you only supply LOCAL update rules; the evaluator's engine runs them with a "
            f"hard cap of {mp['max_total_iters']} total iterations per shot (FPGA-style). Rules are restricted "
            "Python: assignments and return only; numpy calls np.<f>(...) from a whitelist (elementwise: abs, sign, "
            "minimum, maximum, where, exp, log, log1p, expm1, tanh, arctanh, sqrt, square, clip, logaddexp, floor, "
            "ceil, zeros_like, ones_like, full_like; row-wise: sum/min/max/prod/mean/argmin/argmax with axis=1, "
            "keepdims=True; sort/cumsum/cumprod with axis=1; take_along_axis(x, i, axis=1); rowkth(x, k) = k-th "
            "smallest per row as a column). No indexing, loops or other names.\n"
            "Define SCHEDULE = {'first_iters', 'leg_iters', 'max_legs', 'gamma0', 'gamma_low', 'gamma_high', "
            "'stop_solutions', 'reset_messages'}, check_rule(m, sgn) -> out (m: (C, D) incoming variable-to-check "
            "LLRs padded with +1e30, sgn: (C, 1) +-1 syndrome sign) and var_rule(prior, inc, gamma, prev) -> "
            "(marg, out) (prior (V,1) LLR, inc (V, D') incoming check-to-variable messages padded with 0, gamma "
            "(V,1) memory strength of the leg, prev (V,1) previous marginal). Example = Relay-BP:\n\n"
            + _relay_rules())

    def seed_programs(self) -> list[str]:
        from evaluators.decoder_refs import program_for
        ref = self.task.decoder["reference"]
        if self.interface == "mp_rule":
            return [program_for("mp_relay", ref["params"])]
        weaker = dict(ref["params"], stop_nconv=1, num_sets=30)
        return [program_for("relay_bp", ref["params"]), program_for("relay_bp", weaker)]

    def mock_presets(self) -> list[str]:
        """MockClient 的预设回复（离线测试用）：参考程序的变体、一个格式错误的程序、一个抛异常的程序。"""
        from evaluators.decoder_refs import program_for
        if self.interface == "mp_rule":
            return [program_for("mp_relay", dict(self.task.decoder["reference"]["params"], stop_nconv=1))]
        p = dict(self.task.decoder["reference"]["params"])
        return [program_for("relay_bp", dict(p, gamma0=0.2)),
                program_for("relay_bp", dict(p, stop_nconv=2, num_sets=60)),
                "def make_decoder(H, L, priors, info):\n    return lambda s: [2] * L.shape[0]\n",
                "def make_decoder(H, L, priors, info):\n    raise ValueError('boom')\n"]

    # ------------------------------------------------------------------
    def evaluate(self, program_src: str) -> EvalResult:
        from evaluators.decoder_eval import evaluate_decoder
        with self._lock:
            try:
                rep = evaluate_decoder(self.task_id, program_src, split=self.split, shots=self.shots, submit=False,
                                       num_workers=self.num_workers, use_os_sandbox=self.use_os_sandbox)
            except Exception as e:  # noqa: BLE001 —— 评估器异常（参考失败等）
                return EvalResult.invalid(f"evaluator error: {type(e).__name__}: {e}", evaluator_error=True)
        metrics = {"status": rep.status, "counts": rep.counts, "reference_counts": rep.reference.get("counts"),
                   "speed": rep.speed, "overlap": rep.overlap, "program_hash": rep.program_hash,
                   "sectors": {s: {k: v for k, v in st.items() if k != "build_cpu_s"}
                               for s, st in rep.sectors.items()}}
        if rep.status != "searched":
            return EvalResult.invalid(rep.to_text(), **metrics)
        return EvalResult(valid=True, score=-rep.rates["P_any"]["best"], metrics=metrics, diagnostics=rep.to_text())

    # ---- SolutionSpace：Relay-BP 类参数空间上的模拟退火对照 ----
    def initial_solution(self, rng: random.Random) -> dict:
        p = self.task.decoder["reference"]["params"]
        lo, hi = p["gamma_dist_interval"]
        return {"gamma0": p["gamma0"], "lo": lo, "width": hi - lo, "pre_iter": p["pre_iter"],
                "set_max_iter": p["set_max_iter"], "num_sets": p.get("num_sets", 8), "stop_nconv": p["stop_nconv"]}

    def neighbor(self, sol: dict, rng: random.Random) -> dict:
        s = dict(sol)
        k = rng.choice(sorted(_PARAM_SPACE))
        lo, hi, typ = _PARAM_SPACE[k]
        if typ is int:
            step = max(1, int(abs(s[k]) * 0.3))
            d = rng.randint(-step, step) or rng.choice((-1, 1))
            s[k] = int(min(hi, max(lo, s[k] + d)))
        else:
            s[k] = round(min(hi, max(lo, s[k] + rng.gauss(0, 0.15 * (hi - lo)))), 4)
        return s

    def solution_to_program(self, sol: dict) -> str:
        from evaluators.decoder_refs import program_for
        params = {"gamma0": float(sol["gamma0"]), "pre_iter": int(sol["pre_iter"]),
                  "set_max_iter": int(sol["set_max_iter"]),
                  "gamma_dist_interval": [float(sol["lo"]), float(sol["lo"] + sol["width"])],
                  "stop_nconv": int(sol["stop_nconv"]), "alpha": None, "seed": 0}
        if self.interface == "mp_rule":
            mp = self.task.decoder["mp"]
            legs = max(1, min(int(mp["max_legs"]), int(sol["num_sets"]) + 1))
            return program_for("mp_relay", dict(params, max_legs=legs))
        return program_for("relay_bp", dict(params, num_sets=int(sol["num_sets"])))


def _relay_rules() -> str:
    from evaluators.decoder_refs import program_for
    from evaluators.tasks import get_task
    return program_for("mp_relay", get_task("bb72-mp-p3e-3").decoder["reference"]["params"])


def score_to_ler(score: float) -> float:
    return -score if math.isfinite(score) else float("nan")
