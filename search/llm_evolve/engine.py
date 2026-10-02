"""LLM 进化搜索主循环（FunSearch / AlphaEvolve 风格内循环）。

每个 batch：
  1. 规划：轮流选岛 → 选 2-3 个父代 → 按 strong_fraction 抽快/强模型 → 构造 prompt →
     预扣 token（prompt 估计 + max_tokens），超预算/超评估次数就停止规划；
  2. 并发调用 LLM；
  3. 提取程序 → 规范化哈希 → 批内去重、查缓存 → 并发评估未命中的程序；
  4. 按规划顺序（确定性地）写日志、更新数据库、按评估次数触发岛重置；
  5. 写断点。

确定性：所有随机决策来自引擎的 ``random.Random(seed)``；每次 LLM 调用拿到一个由它派生的
``request.seed``。用 MockClient 时，同种子的运行逐条记录完全一致，崩溃后续跑与不中断运行一致。
真实 API 不支持采样种子，可复现性依赖 llm_calls.jsonl 里完整记录的回复。
"""

from __future__ import annotations

import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .database import Program, ProgramDatabase
from .llm import LLMClient, LLMRequest, LLMResponse, estimate_cost_usd
from .problem import EvalResult, Problem
from .prompt import SYSTEM_PROMPT, build_prompt, extract_program
from .runlog import CachedEvaluator, JsonlLog, atomic_write_json, dumps, make_run_dir

STATE_VERSION = 1
BUDGET_FIELDS = ("token_budget", "max_evals", "max_llm_calls")


@dataclass
class EvolutionConfig:
    run_id: str
    seed: int = 0
    results_dir: str | None = None
    # 数据库 / 选择
    num_islands: int = 4
    island_capacity: int = 20
    parents_min: int = 2
    parents_max: int = 3
    selection_temperature: float = 0.3
    diversity_weight: float = 0.3
    reset_interval: int = 100          # 每多少次唯一评估重置一次最差岛
    num_reset: int | None = None       # 默认 num_islands // 2
    reset_elites: int = 1
    # LLM
    strong_fraction: float = 0.15      # 强模型调用比例
    max_tokens_fast: int = 16000
    max_tokens_strong: int = 16000
    max_diag_chars: int = 800
    extra_instructions: str = ""
    log_prompts: bool = True
    # 预算（续跑时可以调大）
    token_budget: int = 2_000_000      # 输入+输出 token 总量（含 thinking）
    max_evals: int = 500               # 唯一评估次数上限（含种子）
    max_llm_calls: int | None = None
    # 执行
    batch_size: int = 4
    concurrency: int = 4
    max_consecutive_llm_errors: int = 5
    chars_per_token_estimate: float = 2.5  # 预扣 prompt token 时的保守估计

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EvolutionConfig:
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


@dataclass
class _Plan:
    call_index: int
    island: int
    tier: str
    seed: int
    parents: list[Program]
    prompt: str
    reserved_tokens: int


class EvolutionEngine:
    def __init__(self, problem: Problem, client: LLMClient, config: EvolutionConfig):
        self.problem = problem
        self.client = client
        self.config = config
        self.run_dir: Path = make_run_dir(config.run_id, config.results_dir)
        self.rng = random.Random(config.seed)
        self.db = ProgramDatabase(config.num_islands, config.island_capacity,
                                  config.selection_temperature, config.diversity_weight)
        self.eval_log = JsonlLog(self.run_dir / "evaluations.jsonl")
        self.call_log = JsonlLog(self.run_dir / "llm_calls.jsonl")
        self.evaluator = CachedEvaluator(problem, self.eval_log)
        self.usage = {"input_tokens": 0, "output_tokens": 0, "llm_calls": 0, "llm_errors": 0,
                      "extract_failures": 0, "cost_usd_est": 0.0, "by_tier": {"fast": 0, "strong": 0}}
        self.consecutive_errors = 0
        self.call_index = 0
        self.batch_index = 0
        self.next_reset_at = config.reset_interval
        self.stop_reason: str | None = None
        self.initialized = False

    # ------------------------------------------------------------------ 公共入口
    @classmethod
    def resume(cls, run_id: str, problem: Problem, client: LLMClient, *,
               results_dir: str | None = None, **budget_overrides: Any) -> EvolutionEngine:
        """从 ``results/<run_id>/state.json`` 续跑。只允许覆盖预算字段（以及 concurrency/batch_size）。"""
        run_dir = make_run_dir(run_id, results_dir, must_exist=True)
        state = _load_json(run_dir / "state.json")
        cfg = state["config"]
        allowed = set(BUDGET_FIELDS) | {"concurrency"}
        bad = set(budget_overrides) - allowed
        if bad:
            raise ValueError(f"cannot override {sorted(bad)} on resume (allowed: {sorted(allowed)})")
        cfg.update(budget_overrides)
        if results_dir is not None:
            cfg["results_dir"] = results_dir
        eng = cls(problem, client, EvolutionConfig.from_dict(cfg))
        eng._load_state(state)
        return eng

    def run(self) -> dict[str, Any]:
        """运行直到预算耗尽。返回摘要。异常（含 KeyboardInterrupt）时保留上一个断点。"""
        if not self.initialized:
            if (self.run_dir / "state.json").exists():
                raise FileExistsError(f"{self.run_dir} already has a checkpoint; use EvolutionEngine.resume()")
            self._write_config()
            self._init_seeds()
            self._checkpoint()
        self.stop_reason = None
        with ThreadPoolExecutor(max_workers=max(1, self.config.concurrency)) as pool:
            while self.stop_reason is None:
                plans, reason = self._plan_batch()
                if not plans:
                    self.stop_reason = reason
                    break
                self._run_batch(plans, pool)
                self.batch_index += 1
                if self.consecutive_errors >= self.config.max_consecutive_llm_errors:
                    self.stop_reason = "too_many_consecutive_llm_errors"
                self._checkpoint()
        self._checkpoint()
        return self._write_summary()

    # ------------------------------------------------------------------ 初始化
    def _write_config(self) -> None:
        atomic_write_json(self.run_dir / "config.json", {
            "kind": "llm_evolve", "config": self.config.to_dict(),
            "problem": self.problem.fingerprint(), "client": self.client.describe(),
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    def _init_seeds(self) -> None:
        seeds = self.problem.seed_programs()
        if not seeds:
            raise ValueError("problem provided no seed programs")
        n_valid = 0
        for i, src in enumerate(seeds):
            h, res, hit, idx = self.evaluator.evaluate(src, {"origin": "seed", "seed_index": i})
            if res.valid and not hit:
                n_valid += 1
                self.db.add_to_all(Program(hash=h, src=src, score=res.score, metrics=res.metrics,
                                           diagnostics=res.diagnostics, eval_index=idx or 0, origin="seed"))
        if n_valid == 0:
            raise ValueError("no valid seed program; diagnostics: " +
                             "; ".join(EvalResult.from_dict(v).diagnostics[:300] for v in self.evaluator.cache.values()))
        self.initialized = True

    # ------------------------------------------------------------------ 规划
    def _tokens_used(self) -> int:
        return self.usage["input_tokens"] + self.usage["output_tokens"]

    def _plan_batch(self) -> tuple[list[_Plan], str | None]:
        cfg = self.config
        plans: list[_Plan] = []
        reserved = 0
        reason = None
        for _ in range(cfg.batch_size):
            if self.evaluator.n_evals + len(plans) >= cfg.max_evals:
                reason = "max_evals"
                break
            if cfg.max_llm_calls is not None and self.usage["llm_calls"] + len(plans) >= cfg.max_llm_calls:
                reason = "max_llm_calls"
                break
            rng_state = self.rng.getstate()
            island = self.call_index % cfg.num_islands
            k = self.rng.randint(cfg.parents_min, cfg.parents_max)
            parents = self.db.sample_parents(island, k, self.rng)
            tier = "strong" if self.rng.random() < cfg.strong_fraction else "fast"
            seed = self.rng.getrandbits(32)
            prompt = build_prompt(self.problem.description(), self.problem.function_name, parents,
                                  max_diag_chars=cfg.max_diag_chars, extra_instructions=cfg.extra_instructions)
            max_tokens = cfg.max_tokens_strong if tier == "strong" else cfg.max_tokens_fast
            est = math.ceil((len(SYSTEM_PROMPT) + len(prompt)) / cfg.chars_per_token_estimate) + max_tokens
            if self._tokens_used() + reserved + est > cfg.token_budget:
                self.rng.setstate(rng_state)  # 未执行的规划不消耗随机数
                reason = "token_budget"
                break
            reserved += est
            plans.append(_Plan(self.call_index, island, tier, seed, parents, prompt, est))
            self.call_index += 1
        return plans, reason

    # ------------------------------------------------------------------ 执行
    def _call_llm(self, plan: _Plan) -> tuple[LLMResponse | None, str | None, float]:
        max_tokens = self.config.max_tokens_strong if plan.tier == "strong" else self.config.max_tokens_fast
        t0 = time.perf_counter()
        try:
            resp = self.client.complete(LLMRequest(prompt=plan.prompt, tier=plan.tier,
                                                   max_tokens=max_tokens, seed=plan.seed))
            return resp, None, time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001 —— 网络/限流等错误：记录后继续
            return None, f"{type(e).__name__}: {e}"[:1000], time.perf_counter() - t0

    def _run_batch(self, plans: list[_Plan], pool: ThreadPoolExecutor) -> None:
        cfg = self.config
        llm_results = list(pool.map(self._call_llm, plans))

        # 提取程序 + 批内去重 + 查缓存
        extracted: list[tuple[str | None, str | None]] = []  # (src, hash)
        to_eval: dict[str, str] = {}
        for resp, _err, _lat in llm_results:
            src = extract_program(resp.text, self.problem.function_name) if resp is not None else None
            if src is None:
                extracted.append((None, None))
                continue
            h, cached = self.evaluator.lookup(src)
            extracted.append((src, h))
            if cached is None and h not in to_eval:
                to_eval[h] = src
        hashes = list(to_eval)
        eval_out = dict(zip(hashes, pool.map(self.evaluator.raw_evaluate, [to_eval[h] for h in hashes])))

        # 按规划顺序确定性地整合
        recorded: set[str] = set()
        for plan, (resp, err, latency), (src, h) in zip(plans, llm_results, extracted):
            rec: dict[str, Any] = {
                "call_index": plan.call_index, "batch": self.batch_index, "island": plan.island,
                "tier": plan.tier, "request_seed": plan.seed,
                "parents": [{"hash": p.hash, "score": p.score} for p in plan.parents],
                "reserved_tokens": plan.reserved_tokens,
            }
            if cfg.log_prompts:
                rec["prompt"] = plan.prompt
            self.usage["llm_calls"] += 1
            self.usage["by_tier"][plan.tier] += 1
            if resp is None:
                self.usage["llm_errors"] += 1
                self.consecutive_errors += 1
                rec.update(error=err, model=None, response=None, tokens=None)
            else:
                self.consecutive_errors = 0
                self.usage["input_tokens"] += resp.input_tokens
                self.usage["output_tokens"] += resp.output_tokens
                cost = estimate_cost_usd(resp.model, resp.input_tokens, resp.output_tokens)
                if cost is not None:
                    self.usage["cost_usd_est"] += cost
                rec.update(error=None, model=resp.model, response=resp.text, stop_reason=resp.stop_reason,
                           tokens={"input": resp.input_tokens, "output": resp.output_tokens},
                           cost_usd_est=cost, llm_extra=resp.extra)
            rec["program"] = src
            rec["program_hash"] = h
            eval_s = None
            if resp is not None and src is None:
                self.usage["extract_failures"] += 1
                rec.update(cache_hit=False, eval_index=None,
                           eval=EvalResult.invalid("no program defining "
                                                   f"`{self.problem.function_name}` found in the reply").to_dict())
            elif src is not None:
                if h in eval_out and h not in recorded:
                    res, eval_s = eval_out[h]
                    idx = self.evaluator.record(h, src, res, eval_s, {
                        "origin": f"llm:{plan.tier}", "call_index": plan.call_index,
                        "parents": [p.hash for p in plan.parents]})
                    recorded.add(h)
                    rec.update(cache_hit=False, eval_index=idx, eval=res.to_dict())
                    if res.valid:
                        self.db.add(Program(hash=h, src=src, score=res.score, metrics=res.metrics,
                                            diagnostics=res.diagnostics, island=plan.island, eval_index=idx,
                                            parents=[p.hash for p in plan.parents],
                                            origin=f"llm:{plan.tier}"), plan.island)
                    rec["added_to_db"] = res.valid
                else:
                    self.evaluator.n_cache_hits += 1
                    rec.update(cache_hit=True, eval_index=None,
                               eval=self.evaluator.cache[h])
                    rec["added_to_db"] = False
            rec["best_score_after"] = self.db.best.score if self.db.best else None
            rec["n_evals_after"] = self.evaluator.n_evals
            rec["timing"] = {"llm_s": round(latency, 3), "eval_s": None if eval_s is None else round(eval_s, 4)}
            self.call_log.append(rec)

            if self.evaluator.n_evals >= self.next_reset_at:
                n = self.config.num_reset if self.config.num_reset is not None else self.config.num_islands // 2
                reset = self.db.reset_worst_islands(n, self.config.reset_elites)
                self.call_log.append({"event": "island_reset", "after_evals": self.evaluator.n_evals,
                                      "reset_islands": reset, "db": self.db.summary()})
                while self.next_reset_at <= self.evaluator.n_evals:
                    self.next_reset_at += self.config.reset_interval

    # ------------------------------------------------------------------ 断点
    def _checkpoint(self) -> None:
        atomic_write_json(self.run_dir / "state.json", {
            "version": STATE_VERSION,
            "config": self.config.to_dict(),
            "problem": self.problem.fingerprint(),
            "rng_state": _rng_to_json(self.rng.getstate()),
            "usage": self.usage,
            "consecutive_errors": self.consecutive_errors,
            "call_index": self.call_index,
            "batch_index": self.batch_index,
            "next_reset_at": self.next_reset_at,
            "stop_reason": self.stop_reason,
            "evaluator": self.evaluator.state_dict(),
            "db": self.db.state_dict(),
            "log_offsets": {"evaluations": self.eval_log.offset(), "llm_calls": self.call_log.offset()},
        })

    def _load_state(self, state: dict[str, Any]) -> None:
        if state.get("version") != STATE_VERSION:
            raise ValueError(f"unsupported state version {state.get('version')}")
        if state["problem"] != self.problem.fingerprint():
            raise ValueError(f"problem fingerprint mismatch: checkpoint {state['problem']} "
                             f"vs current {self.problem.fingerprint()}")
        self.rng.setstate(_rng_from_json(state["rng_state"]))
        self.usage = state["usage"]
        self.consecutive_errors = state["consecutive_errors"]
        self.call_index = state["call_index"]
        self.batch_index = state["batch_index"]
        self.next_reset_at = state["next_reset_at"]
        ev = state["evaluator"]
        self.evaluator = CachedEvaluator(self.problem, self.eval_log, ev["cache"], ev["n_evals"], ev["n_cache_hits"])
        self.db = ProgramDatabase.from_state(state["db"])
        # 丢弃崩溃前未进入断点的日志行
        self.eval_log.truncate(state["log_offsets"]["evaluations"])
        self.call_log.truncate(state["log_offsets"]["llm_calls"])
        self.initialized = True
        self.call_log.append({"event": "resumed", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                              "budget": {k: getattr(self.config, k) for k in BUDGET_FIELDS}})

    def _write_summary(self) -> dict[str, Any]:
        best = self.db.best
        summary = {
            "kind": "llm_evolve", "run_id": self.config.run_id, "stop_reason": self.stop_reason,
            "best_score": None if best is None else best.score,
            "best_hash": None if best is None else best.hash,
            "best_metrics": None if best is None else best.metrics,
            "n_evals": self.evaluator.n_evals, "n_cache_hits": self.evaluator.n_cache_hits,
            "usage": self.usage, "tokens_used": self._tokens_used(),
            "budget": {k: getattr(self.config, k) for k in BUDGET_FIELDS},
            "db": self.db.summary(),
        }
        atomic_write_json(self.run_dir / "summary.json", summary)
        if best is not None:
            (self.run_dir / "best_program.py").write_text(
                f"# score={best.score!r} hash={best.hash} eval_index={best.eval_index}\n{best.src}\n")
        return summary


def _rng_to_json(state: tuple) -> list:
    version, internal, gauss = state
    return [version, list(internal), gauss]


def _rng_from_json(d: list) -> tuple:
    return (d[0], tuple(d[1]), d[2])


def _load_json(path: Path) -> Any:
    import json

    with open(path) as f:
        return json.load(f)


__all__ = ["EvolutionConfig", "EvolutionEngine", "dumps"]
