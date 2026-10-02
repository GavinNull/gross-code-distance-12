"""search/llm_evolve 端到端测试：MockClient + 玩具问题。绝不调用真实 API。"""

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from search.llm_evolve import (
    AnnealingConfig,
    AnnealingSearch,
    AnthropicClient,
    EvalResult,
    EvolutionConfig,
    EvolutionEngine,
    LLMConfigError,
    LLMRequest,
    MockClient,
    Problem,
    ProgramMutator,
    SolutionSpaceMutator,
    best_so_far_curve,
)
from search.llm_evolve.toy import (
    BAD_OUTPUT_PROGRAM,
    NEAREST_NEIGHBOR_PROGRAM,
    RAISING_PROGRAM,
    SEED_PROGRAM,
    TIMEOUT_PROGRAM,
    CircleTSPProblem,
)


@pytest.fixture(scope="module")
def problem():
    return CircleTSPProblem(timeout_s=1.0)


def _cfg(tmp_path, run_id, **kw):
    base = dict(run_id=run_id, results_dir=str(tmp_path), seed=7, num_islands=3, island_capacity=8,
                batch_size=3, concurrency=3, max_evals=30, token_budget=10_000_000, reset_interval=10,
                max_tokens_fast=2000, max_tokens_strong=4000)
    base.update(kw)
    return EvolutionConfig(**base)


def _records(run_dir, name):
    with open(Path(run_dir) / name) as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def _strip_volatile(recs):
    out = []
    for r in recs:
        if r.get("event") == "resumed":
            continue
        r = {k: v for k, v in r.items() if k != "timing"}
        for key in ("eval", None):
            d = r.get(key) if key else r
            if isinstance(d, dict) and isinstance(d.get("metrics"), dict):
                d["metrics"] = {k: v for k, v in d["metrics"].items() if k != "elapsed"}
        out.append(r)
    return out


# ----------------------------------------------------------------------------- 端到端
def test_end_to_end_mock_evolution_improves_and_logs(tmp_path, problem):
    client = MockClient(presets=[NEAREST_NEIGHBOR_PROGRAM, RAISING_PROGRAM, BAD_OUTPUT_PROGRAM], p_preset=0.15)
    eng = EvolutionEngine(problem, client, _cfg(tmp_path, "e2e", max_evals=40))
    summary = eng.run()
    run_dir = tmp_path / "e2e"
    seed_score = problem.evaluate(SEED_PROGRAM).score

    assert summary["stop_reason"] == "max_evals"
    assert summary["n_evals"] <= 40
    assert summary["best_score"] > seed_score

    calls = [r for r in _records(run_dir, "llm_calls.jsonl") if "call_index" in r]
    assert len(calls) == summary["usage"]["llm_calls"]
    for r in calls:  # 每条记录都有 prompt / 回复 / 程序 / 评估结果 / token
        assert {"prompt", "response", "program", "eval", "tokens", "model", "tier", "parents"} <= set(r)
        assert 1 <= len(r["parents"]) <= 3
    # 全局最优分数单调不降
    best = [r["best_score_after"] for r in calls]
    assert all(b2 >= b1 for b1, b2 in zip(best, best[1:]))
    # 曲线（按评估序号）也单调不降
    curve = best_so_far_curve(run_dir)
    assert [s for _, s in curve] == sorted(s for _, s in curve)

    # 缓存：评估日志里哈希唯一，且确有命中，命中的调用没有触发评估
    evals = _records(run_dir, "evaluations.jsonl")
    assert len(evals) == summary["n_evals"]
    assert len({e["hash"] for e in evals}) == len(evals)
    hits = [r for r in calls if r.get("cache_hit")]
    assert summary["n_cache_hits"] == len(hits) > 0
    assert all(r["eval_index"] is None for r in hits)

    # 抛异常 / 输出不合法的程序被标为 invalid，并带诊断
    invalid = [r for r in calls if r["eval"] and not r["eval"]["valid"]]
    assert any("ValueError: boom" in r["eval"]["diagnostics"] for r in invalid)
    assert any("not a permutation" in r["eval"]["diagnostics"] for r in invalid)
    assert all(not r.get("added_to_db") for r in invalid)

    # 产物齐全
    for f in ("config.json", "state.json", "summary.json", "best_program.py"):
        assert (run_dir / f).exists()
    # 岛重置发生过
    assert any(r.get("event") == "island_reset" for r in _records(run_dir, "llm_calls.jsonl"))
    # 快/强模型都用到了
    assert summary["usage"]["by_tier"]["fast"] > 0


def test_timeout_and_raising_programs_are_invalid(tmp_path, problem):
    client = MockClient(presets=[TIMEOUT_PROGRAM, RAISING_PROGRAM], p_preset=1.0)
    eng = EvolutionEngine(problem, client, _cfg(tmp_path, "bad", max_evals=3, batch_size=4))
    summary = eng.run()
    calls = [r for r in _records(tmp_path / "bad", "llm_calls.jsonl") if "call_index" in r]
    types = {r["eval"]["metrics"].get("error_type") for r in calls}
    assert {"Timeout", "ValueError"} <= types
    assert all(not r["eval"]["valid"] for r in calls)
    timeouts = [r for r in calls if r["eval"]["metrics"].get("error_type") == "Timeout" and not r["cache_hit"]]
    assert all(r["timing"]["eval_s"] < 5 for r in timeouts)  # 1 s 超时后被杀
    assert summary["db"]["best_score"] == pytest.approx(problem.evaluate(SEED_PROGRAM).score)


def test_extraction_failure_is_logged_not_evaluated(tmp_path, problem):
    client = MockClient(p_garbage=1.0)
    eng = EvolutionEngine(problem, client, _cfg(tmp_path, "garbage", max_llm_calls=4, batch_size=2))
    s = eng.run()
    assert s["stop_reason"] == "max_llm_calls"
    assert s["usage"]["extract_failures"] == 4 and s["n_evals"] == 1  # 只有种子


def test_token_budget_stops_gracefully(tmp_path, problem):
    eng = EvolutionEngine(problem, MockClient(), _cfg(tmp_path, "tok", token_budget=12_000, max_evals=1000))
    s = eng.run()
    assert s["stop_reason"] == "token_budget"
    assert 0 < s["tokens_used"] <= 12_000
    state = json.loads((tmp_path / "tok" / "state.json").read_text())
    assert state["stop_reason"] == "token_budget"
    # 续跑不加预算 -> 立即停止，不再调用
    eng2 = EvolutionEngine.resume("tok", problem, MockClient(), results_dir=str(tmp_path))
    s2 = eng2.run()
    assert s2["usage"]["llm_calls"] == s["usage"]["llm_calls"]
    # 加预算 -> 继续
    s3 = EvolutionEngine.resume("tok", problem, MockClient(), results_dir=str(tmp_path), token_budget=30_000).run()
    assert s3["usage"]["llm_calls"] > s["usage"]["llm_calls"] and s3["tokens_used"] <= 30_000


def test_max_evals_and_resume_with_larger_budget(tmp_path, problem):
    s1 = EvolutionEngine(problem, MockClient(), _cfg(tmp_path, "ev", max_evals=12)).run()
    assert s1["stop_reason"] == "max_evals" and s1["n_evals"] <= 12
    s2 = EvolutionEngine.resume("ev", problem, MockClient(), results_dir=str(tmp_path), max_evals=25).run()
    assert 12 < s2["n_evals"] <= 25
    assert s2["best_score"] >= s1["best_score"]
    with pytest.raises(FileExistsError):
        EvolutionEngine(problem, MockClient(), _cfg(tmp_path, "ev")).run()
    with pytest.raises(ValueError):
        EvolutionEngine.resume("ev", problem, MockClient(), results_dir=str(tmp_path), num_islands=9)


class _CrashingClient(MockClient):
    """第 crash_at 次调用时模拟进程被中断（KeyboardInterrupt 不会被引擎当作普通 LLM 错误吞掉）。"""

    def __init__(self, crash_at, **kw):
        super().__init__(**kw)
        self.crash_at = crash_at

    def complete(self, request):
        if self.calls + 1 >= self.crash_at:
            self.calls += 1
            raise KeyboardInterrupt("simulated crash")
        return super().complete(request)


def test_crash_and_resume_matches_uninterrupted_run(tmp_path, problem):
    kw = dict(presets=[NEAREST_NEIGHBOR_PROGRAM, RAISING_PROGRAM], p_preset=0.2)
    full = EvolutionEngine(problem, MockClient(**kw), _cfg(tmp_path, "full", max_evals=30)).run()

    with pytest.raises(KeyboardInterrupt):
        EvolutionEngine(problem, _CrashingClient(crash_at=11, **kw), _cfg(tmp_path, "crash", max_evals=30)).run()
    crashed_state = json.loads((tmp_path / "crash" / "state.json").read_text())
    assert 0 < crashed_state["usage"]["llm_calls"] < full["usage"]["llm_calls"]
    # 崩溃时最后一个 batch 未提交：日志里可能有断点之后的残留行，续跑时会被截断
    resumed = EvolutionEngine.resume("crash", problem, MockClient(**kw), results_dir=str(tmp_path)).run()

    for k in ("best_score", "best_hash", "n_evals", "n_cache_hits", "tokens_used"):
        assert resumed[k] == full[k], k
    for name in ("llm_calls.jsonl", "evaluations.jsonl"):
        a = _strip_volatile(_records(tmp_path / "full", name))
        b = _strip_volatile(_records(tmp_path / "crash", name))
        assert a == b, name


def test_same_seed_is_reproducible_different_seed_differs(tmp_path, problem):
    runs = {}
    for rid, seed in (("a", 1), ("b", 1), ("c", 2)):
        EvolutionEngine(problem, MockClient(), _cfg(tmp_path, rid, seed=seed, max_evals=15)).run()
        runs[rid] = _strip_volatile(_records(tmp_path / rid, "llm_calls.jsonl"))
    assert runs["a"] == runs["b"]
    assert runs["a"] != runs["c"]


def test_llm_errors_are_logged_and_stop_after_too_many(tmp_path, problem):
    class Failing(MockClient):
        def complete(self, request):
            raise ConnectionError("network down")

    s = EvolutionEngine(problem, Failing(), _cfg(tmp_path, "fail", max_consecutive_llm_errors=4,
                                                 batch_size=2)).run()
    assert s["stop_reason"] == "too_many_consecutive_llm_errors"
    calls = [r for r in _records(tmp_path / "fail", "llm_calls.jsonl") if "call_index" in r]
    assert all("network down" in r["error"] for r in calls)


# ----------------------------------------------------------------------------- 问题接口的边界
class _BrokenEvaluator(Problem):
    name = "broken"
    function_name = "solve"

    def description(self):
        return "x"

    def seed_programs(self):
        return ["def solve():\n    return 1\n", "def solve():\n    return 2\n"]

    def evaluate(self, program_src):
        if "return 2" in program_src:
            raise RuntimeError("evaluator bug")
        return EvalResult(valid=True, score=1.0)


def test_evaluator_exception_is_contained(tmp_path):
    eng = EvolutionEngine(_BrokenEvaluator(), MockClient(), _cfg(tmp_path, "brk", max_evals=2))
    eng.run()
    evals = _records(tmp_path / "brk", "evaluations.jsonl")
    bad = [e for e in evals if not e["valid"]]
    assert bad and bad[0]["metrics"]["evaluator_error"] and "evaluator bug" in bad[0]["diagnostics"]


def test_no_valid_seed_raises(tmp_path):
    class NoSeed(_BrokenEvaluator):
        def evaluate(self, program_src):
            return EvalResult.invalid("nope")

    with pytest.raises(ValueError, match="no valid seed"):
        EvolutionEngine(NoSeed(), MockClient(), _cfg(tmp_path, "noseed")).run()


def test_nonfinite_score_is_invalid():
    assert not EvalResult(valid=True, score=float("nan")).valid
    assert not EvalResult(valid=True, score=math.inf).valid


# ----------------------------------------------------------------------------- 经典基线
@pytest.mark.parametrize("kind", ["program", "solution"])
def test_annealing_baseline_same_eval_budget(tmp_path, problem, kind):
    mut = ProgramMutator(problem) if kind == "program" else SolutionSpaceMutator(problem)
    s = AnnealingSearch(problem, mut, AnnealingConfig(run_id=f"sa-{kind}", results_dir=str(tmp_path),
                                                      max_evals=30, seed=3)).run()
    assert s["stop_reason"] == "max_evals" and s["n_evals"] == 30
    evals = _records(tmp_path / f"sa-{kind}", "evaluations.jsonl")
    assert len(evals) == 30 and len({e["hash"] for e in evals}) == 30
    curve = best_so_far_curve(tmp_path / f"sa-{kind}")
    assert [v for _, v in curve] == sorted(v for _, v in curve)
    if kind == "program":
        assert s["best_score"] >= problem.evaluate(SEED_PROGRAM).score


def test_annealing_resume(tmp_path, problem):
    mut = SolutionSpaceMutator(problem)
    s1 = AnnealingSearch(problem, mut, AnnealingConfig(run_id="sar", results_dir=str(tmp_path), max_evals=15)).run()
    s2 = AnnealingSearch.resume("sar", problem, mut, results_dir=str(tmp_path), max_evals=30).run()
    assert s1["n_evals"] == 15 and s2["n_evals"] == 30 and s2["best_score"] >= s1["best_score"]
    assert len(_records(tmp_path / "sar", "evaluations.jsonl")) == 30


# ----------------------------------------------------------------------------- Anthropic 客户端（无网络）
def test_anthropic_client_requires_env_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMConfigError):
        AnthropicClient()


def test_anthropic_client_request_shape_and_usage(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_FAST", "fast-model-x")
    monkeypatch.delenv("LLM_MODEL_STRONG", raising=False)
    captured = {}

    def create(**kw):
        captured.update(kw)
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking=""),
                     SimpleNamespace(type="text", text="```python\ndef solve(p):\n    return p\n```")],
            usage=SimpleNamespace(input_tokens=100, output_tokens=50, cache_creation_input_tokens=10,
                                  cache_read_input_tokens=5),
            stop_reason="end_turn", model=kw["model"], _request_id="req_1")

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
                           messages=SimpleNamespace(create=create))
    c = AnthropicClient(sdk_client=fake)
    assert c.models == {"fast": "fast-model-x", "strong": "claude-opus-5-5"}
    r = c.complete(LLMRequest(prompt="hello", tier="fast", max_tokens=123, seed=1))
    assert captured["model"] == "fast-model-x" and captured["max_tokens"] == 123
    assert captured["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["fallbacks"] == "default" and "temperature" not in captured
    assert r.input_tokens == 115 and r.output_tokens == 50 and "def solve" in r.text
    r2 = c.complete(LLMRequest(prompt="hi", tier="strong", max_tokens=5, seed=1))
    assert captured["model"] == "claude-opus-5-5" and r2.model == "claude-opus-5-5"
