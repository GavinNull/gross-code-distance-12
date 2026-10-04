"""受速度预算限制的模拟退火：DecoderProblem + SolutionSpaceMutator，每次评估走评估器（search split，临时密钥）。"""
import argparse
import json
import sys
import time

from search.experiments.e007 import common as C

C.use_temp_secret()
from search.llm_evolve import AnnealingConfig, AnnealingSearch, SolutionSpaceMutator, best_so_far_curve  # noqa: E402
from search.llm_evolve.decoder_problem import DecoderProblem  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--max-evals", type=int, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    shots = C.SHOTS[a.task]
    t0, t1 = C.TEMPS[a.task]
    run_id = f"sa-restricted-{a.task.split('-')[0]}-s{a.seed}"
    problem = DecoderProblem(a.task, shots=shots, num_workers=3)
    mut = SolutionSpaceMutator(problem)
    if a.resume:
        s = AnnealingSearch.resume(run_id, problem, mut, results_dir=str(C.RESULTS), max_evals=a.max_evals)
    else:
        cfg = AnnealingConfig(run_id=run_id, seed=a.seed, results_dir=str(C.RESULTS), max_evals=a.max_evals,
                              t_start=t0, t_end=t1, checkpoint_every=5)
        s = AnnealingSearch(problem, mut, cfg)
    t = time.time()
    summ = s.run()
    print(json.dumps({k: summ[k] for k in ("stop_reason", "best_score", "n_evals", "proposals", "accepted")}),
          "wall_s", round(time.time() - t))


if __name__ == "__main__":
    main()
