"""不受速度预算限制的退火对照：同一个参数空间、同一个 SA（同温度、同种子），评估改为直接调官方包（direct.py）。"""
import argparse
import json
import math
import time

import numpy as np

from search.experiments.e007 import common as C

C.use_temp_secret()
from search.experiments.e007 import direct  # noqa: E402
from search.llm_evolve import AnnealingConfig, AnnealingSearch, EvalResult, SolutionSpaceMutator  # noqa: E402
from search.llm_evolve.decoder_problem import DecoderProblem  # noqa: E402


class UnrestrictedProblem(DecoderProblem):
    """同样的解空间；evaluate 直接跑官方包，无评估器速度预算（只有 direct.K_UNRES 的安全上限）。"""

    def __init__(self, task_id, shots):
        super().__init__(task_id, shots=shots, num_workers=3)
        self.base_cpu = None          # 论文参数的 CPU/shot（逐 sector），第一次评估后设定
        direct.prepare(task_id, "search", shots)

    def fingerprint(self):
        return {**super().fingerprint(), "unrestricted": True, "K_UNRES": direct.K_UNRES}

    def evaluate(self, program_src: str) -> EvalResult:
        raise RuntimeError("use evaluate_solution")

    # AnnealingSearch 只经 mutator.to_program → evaluate(src)；这里把参数 JSON 当作“程序”传递
    def solution_to_program(self, sol):
        return json.dumps(self._params(sol), sort_keys=True)

    def _params(self, sol):
        return {"gamma0": float(sol["gamma0"]), "pre_iter": int(sol["pre_iter"]), "set_max_iter": int(sol["set_max_iter"]),
                "gamma_dist_interval": [float(sol["lo"]), float(sol["lo"] + sol["width"])],
                "stop_nconv": int(sol["stop_nconv"]), "alpha": None, "seed": 0, "num_sets": int(sol["num_sets"])}

    def seed_programs(self):
        return [json.dumps(self._params(self.initial_solution(None)), sort_keys=True)]


def _eval(self, program_src):
    params = json.loads(program_src)
    t = time.time()
    cap = None if self.base_cpu is None else {s: direct.K_UNRES * self.base_cpu[s] for s in ("Z", "X")}
    r = direct.run(params, 3, cap)
    n = r["n"]
    fz, fx = r["fail_Z"], r["fail_X"]
    pany = float((fz | fx).sum()) / n
    cpu = {s: float(r[f"cpu_{s}"].sum()) for s in ("Z", "X")}
    if self.base_cpu is None:
        self.base_cpu = {s: cpu[s] / n for s in ("Z", "X")}
    ratio = sum(cpu.values()) / (n * sum(self.base_cpu.values()))
    m = {"counts": {"Z": int(fz.sum()), "X": int(fx.sum()), "any": int((fz | fx).sum()), "n": n},
         "speed": {"cpu_per_shot_ms": 1e3 * sum(cpu.values()) / n, "ratio_to_paper_params": ratio,
                   "cpu_total_s": sum(cpu.values())},
         "wall_s": time.time() - t, "params": params}
    return EvalResult(valid=True, score=-pany, metrics=m, diagnostics=f"P_any={pany:.5f} ratio={ratio:.2f}")


UnrestrictedProblem.evaluate = _eval


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--max-evals", type=int, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    shots = C.SHOTS[a.task]
    t0, t1 = C.TEMPS[a.task]
    run_id = f"sa-unrestricted-{a.task.split('-')[0]}-s{a.seed}"
    problem = UnrestrictedProblem(a.task, shots)
    mut = SolutionSpaceMutator(problem)
    if a.resume:
        raise SystemExit("resume not supported for the unrestricted control (base_cpu state); rerun")
    cfg = AnnealingConfig(run_id=run_id, seed=a.seed, results_dir=str(C.RESULTS), max_evals=a.max_evals,
                          t_start=t0, t_end=t1, checkpoint_every=5)
    s = AnnealingSearch(problem, mut, cfg)
    t = time.time()
    summ = s.run()
    print(json.dumps({k: summ[k] for k in ("stop_reason", "best_score", "n_evals", "proposals", "accepted")}),
          "wall_s", round(time.time() - t))


if __name__ == "__main__":
    main()
