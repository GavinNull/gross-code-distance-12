"""DecoderProblem 接入进化框架：MockClient 端到端 + Relay-BP 参数空间上的模拟退火对照。绝不调用真实 API。

用自检任务 selftest-surface-d5-dec 的公开 split（不需要密钥），每次评估 500 shot、1 个 worker。
"""
import json
import random

import pytest

from search.llm_evolve import (AnnealingConfig, AnnealingSearch, EvolutionConfig, EvolutionEngine, MockClient,
                               SolutionSpaceMutator)
from search.llm_evolve.decoder_problem import DecoderProblem


@pytest.fixture(scope="module")
def problem():
    return DecoderProblem("selftest-surface-d5-dec", shots=500, num_workers=1, split="public")


def test_description_and_seeds(problem):
    d = problem.description()
    assert "make_decoder" in d and "Relay-BP" in d and "held-out" in d
    res = problem.evaluate(problem.seed_programs()[0])
    assert res.valid and res.score <= 0
    assert "reference Relay-BP" in res.diagnostics and "overlap with Relay-BP failures" in res.diagnostics
    assert "failing-shot features" in res.diagnostics and "CPU/shot" in res.diagnostics
    assert res.metrics["counts"]["shots"] == 500


def test_bad_programs_are_invalid_with_diagnostics(problem):
    bad, boom = problem.mock_presets()[2:4]
    r1 = problem.evaluate(bad)
    assert r1.valid and r1.metrics["counts"]["fail_any"] == 500          # 格式错误：全部按失败计
    r2 = problem.evaluate(boom)
    assert not r2.valid and "boom" in r2.diagnostics


def test_mock_client_end_to_end(problem, tmp_path):
    cfg = EvolutionConfig(run_id="dec-mock", seed=0, results_dir=str(tmp_path), max_evals=6, batch_size=2,
                          concurrency=1, num_islands=2, token_budget=10_000_000)
    summary = EvolutionEngine(problem, MockClient(presets=problem.mock_presets(), p_preset=0.4), cfg).run()
    assert summary["n_evals"] >= 4
    run = tmp_path / "dec-mock"
    evals = [json.loads(x) for x in (run / "evaluations.jsonl").read_text().splitlines()]
    assert any(e["valid"] for e in evals) and any(e["context"].get("origin") != "seed" for e in evals)
    assert (run / "best_program.py").exists()
    assert summary["best_score"] <= 0


def test_annealing_control_on_relay_parameter_space(problem, tmp_path):
    rng = random.Random(0)
    s0 = problem.initial_solution(rng)
    s1 = problem.neighbor(s0, rng)
    assert s1 != s0 and set(s1) == set(s0)
    cfg = AnnealingConfig(run_id="dec-sa", seed=0, results_dir=str(tmp_path), max_evals=3)
    summary = AnnealingSearch(problem, SolutionSpaceMutator(problem), cfg).run()
    assert summary["n_evals"] == 3 and summary["best_score"] is not None
