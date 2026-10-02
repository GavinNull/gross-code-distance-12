"""命令行入口。

    uv run python -m search.llm_evolve.cli llm    --problem search.llm_evolve.toy:CircleTSPProblem --client mock --run-id toy-mock --max-evals 200
    uv run python -m search.llm_evolve.cli anneal --problem search.llm_evolve.toy:CircleTSPProblem --mutator program --run-id toy-sa --max-evals 200
    uv run python -m search.llm_evolve.cli llm    --problem ... --run-id toy-mock --resume --max-evals 400
    uv run python -m search.llm_evolve.cli compare results/toy-mock results/toy-sa --at 50 100 200

``--client anthropic`` 会真实调用 API 并产生费用；需要环境变量 ANTHROPIC_API_KEY。
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys

from .baseline import (
    AnnealingConfig,
    AnnealingSearch,
    ProgramMutator,
    SolutionSpaceMutator,
)
from .engine import EvolutionConfig, EvolutionEngine
from .llm import AnthropicClient, MockClient
from .runlog import best_at, best_so_far_curve


def load_problem(spec: str, kwargs_json: str | None):
    mod, _, attr = spec.partition(":")
    factory = getattr(importlib.import_module(mod), attr)
    return factory(**(json.loads(kwargs_json) if kwargs_json else {}))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="llm_evolve")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--problem", required=True, help="module:Factory")
        p.add_argument("--problem-kwargs", default=None, help="JSON kwargs for the factory")
        p.add_argument("--run-id", required=True)
        p.add_argument("--results-dir", default=None)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--max-evals", type=int, default=200)
        p.add_argument("--resume", action="store_true")

    p_llm = sub.add_parser("llm")
    common(p_llm)
    p_llm.add_argument("--client", choices=["mock", "anthropic"], default="mock")
    p_llm.add_argument("--token-budget", type=int, default=2_000_000)
    p_llm.add_argument("--max-llm-calls", type=int, default=None)
    p_llm.add_argument("--strong-fraction", type=float, default=0.15)
    p_llm.add_argument("--islands", type=int, default=4)
    p_llm.add_argument("--batch-size", type=int, default=4)
    p_llm.add_argument("--concurrency", type=int, default=4)
    p_llm.add_argument("--reset-interval", type=int, default=100)

    p_sa = sub.add_parser("anneal")
    common(p_sa)
    p_sa.add_argument("--mutator", choices=["program", "solution"], default="program")
    p_sa.add_argument("--t-start", type=float, default=0.05)
    p_sa.add_argument("--t-end", type=float, default=1e-4)

    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("run_dirs", nargs="+")
    p_cmp.add_argument("--at", type=int, nargs="+", default=[25, 50, 100, 200])

    a = ap.parse_args(argv)
    if a.cmd == "compare":
        for d in a.run_dirs:
            c = best_so_far_curve(d)
            print(d, " ".join(f"@{n}={best_at(c, n):.4f}" for n in a.at), f"(total evals {len(c)})")
        return 0

    problem = load_problem(a.problem, a.problem_kwargs)
    if a.cmd == "llm":
        if a.client == "mock":
            presets = []
            if hasattr(problem, "mock_presets"):
                presets = problem.mock_presets()
            client = MockClient(presets=presets)
        else:
            client = AnthropicClient()
        if a.resume:
            eng = EvolutionEngine.resume(a.run_id, problem, client, results_dir=a.results_dir,
                                         max_evals=a.max_evals, token_budget=a.token_budget,
                                         max_llm_calls=a.max_llm_calls)
        else:
            eng = EvolutionEngine(problem, client, EvolutionConfig(
                run_id=a.run_id, seed=a.seed, results_dir=a.results_dir, max_evals=a.max_evals,
                token_budget=a.token_budget, max_llm_calls=a.max_llm_calls,
                strong_fraction=a.strong_fraction, num_islands=a.islands, batch_size=a.batch_size,
                concurrency=a.concurrency, reset_interval=a.reset_interval))
        summary = eng.run()
    else:
        mut = ProgramMutator(problem) if a.mutator == "program" else SolutionSpaceMutator(problem)
        if a.resume:
            s = AnnealingSearch.resume(a.run_id, problem, mut, results_dir=a.results_dir, max_evals=a.max_evals)
        else:
            s = AnnealingSearch(problem, mut, AnnealingConfig(
                run_id=a.run_id, seed=a.seed, results_dir=a.results_dir, max_evals=a.max_evals,
                t_start=a.t_start, t_end=a.t_end))
        summary = s.run()
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
