"""不用 LLM 的对照搜索器：模拟退火（同一个 ``Problem`` 接口、同一个评估入口、同样的评估次数口径）。

两种“状态空间”（``Mutator``）：
* ``ProgramMutator``  —— 状态是程序源码；邻域 = 随机改数值字面量 / 交换运算符（``mutation.py``）。
  对任何 Problem 都可用，是“经典启发式改程序”的对照。
* ``SolutionSpaceMutator`` —— 问题实现了 ``SolutionSpace`` 协议时，直接在解空间上退火，
  每个解经 ``solution_to_program`` 包装成程序再走 ``evaluate``。对调度问题就是“直接搜调度”的对照。

预算口径与 LLM 搜索相同：``max_evals`` 计**唯一**评估次数（含初始解），缓存命中不计；
另设 ``max_proposals`` 防止邻域退化时死循环。
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import asdict, dataclass, fields
from typing import Any, Protocol

from .mutation import mutate_program
from .problem import Problem, SolutionSpace
from .runlog import CachedEvaluator, JsonlLog, atomic_write_json, make_run_dir


class Mutator(Protocol):
    name: str

    def initial_states(self, rng: random.Random) -> list[Any]: ...

    def neighbor(self, state: Any, rng: random.Random) -> Any: ...

    def to_program(self, state: Any) -> str: ...


class ProgramMutator:
    name = "program_literals"

    def __init__(self, problem: Problem, scale: float = 0.25, p_structural: float = 0.15):
        self.problem = problem
        self.scale = scale
        self.p_structural = p_structural

    def initial_states(self, rng: random.Random) -> list[Any]:
        return list(self.problem.seed_programs())

    def neighbor(self, state: str, rng: random.Random) -> str:
        return mutate_program(state, rng, scale=self.scale, p_structural=self.p_structural)

    def to_program(self, state: str) -> str:
        return state


class SolutionSpaceMutator:
    name = "solution_space"

    def __init__(self, problem: Problem):
        if not isinstance(problem, SolutionSpace):
            raise TypeError(f"{type(problem).__name__} does not implement the SolutionSpace protocol")
        self.problem = problem

    def initial_states(self, rng: random.Random) -> list[Any]:
        return [self.problem.initial_solution(rng)]

    def neighbor(self, state: Any, rng: random.Random) -> Any:
        return self.problem.neighbor(state, rng)

    def to_program(self, state: Any) -> str:
        return self.problem.solution_to_program(state)


@dataclass
class AnnealingConfig:
    run_id: str
    seed: int = 0
    results_dir: str | None = None
    max_evals: int = 500
    max_proposals: int | None = None   # 默认 20 * max_evals
    t_start: float = 0.05              # 初温（与分数同量纲）
    t_end: float = 1e-4                # 末温；按“已用评估次数 / max_evals”几何插值
    checkpoint_every: int = 25         # 每多少次唯一评估写一次断点

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AnnealingConfig:
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


class AnnealingSearch:
    def __init__(self, problem: Problem, mutator: Mutator, config: AnnealingConfig):
        self.problem = problem
        self.mutator = mutator
        self.config = config
        self.run_dir = make_run_dir(config.run_id, config.results_dir)
        self.rng = random.Random(config.seed)
        self.eval_log = JsonlLog(self.run_dir / "evaluations.jsonl")
        self.evaluator = CachedEvaluator(problem, self.eval_log)
        self.current: Any = None
        self.current_score = -math.inf
        self.best: dict[str, Any] | None = None
        self.proposals = 0
        self.accepted = 0
        self.stop_reason: str | None = None
        self._resumed = False

    @classmethod
    def resume(cls, run_id: str, problem: Problem, mutator: Mutator, *, results_dir: str | None = None,
               max_evals: int | None = None) -> AnnealingSearch:
        import json

        run_dir = make_run_dir(run_id, results_dir, must_exist=True)
        state = json.loads((run_dir / "state.json").read_text())
        cfg = dict(state["config"])
        if max_evals is not None:
            cfg["max_evals"] = max_evals
        if results_dir is not None:
            cfg["results_dir"] = results_dir
        s = cls(problem, mutator, AnnealingConfig.from_dict(cfg))
        if state["problem"] != problem.fingerprint() or state["mutator"] != mutator.name:
            raise ValueError("checkpoint was produced by a different problem/mutator")
        s.rng.setstate((state["rng_state"][0], tuple(state["rng_state"][1]), state["rng_state"][2]))
        ev = state["evaluator"]
        s.evaluator = CachedEvaluator(problem, s.eval_log, ev["cache"], ev["n_evals"], ev["n_cache_hits"])
        s.eval_log.truncate(state["log_offset"])
        s.current, s.current_score = state["current"], state["current_score"]
        s.best, s.proposals, s.accepted = state["best"], state["proposals"], state["accepted"]
        s._resumed = True
        return s

    def _temperature(self) -> float:
        frac = min(1.0, self.evaluator.n_evals / max(1, self.config.max_evals))
        return self.config.t_start * (self.config.t_end / self.config.t_start) ** frac

    def _consider(self, state: Any, ctx: dict[str, Any]) -> None:
        src = self.mutator.to_program(state)
        h, res, hit, idx = self.evaluator.evaluate(src, {"origin": self.mutator.name, **ctx})
        if not res.valid:
            return
        if self.best is None or res.score > self.best["score"]:
            self.best = {"score": res.score, "hash": h, "src": src, "metrics": res.metrics, "eval_index": idx}
        if self.current is None or res.score >= self.current_score:
            accept = True
        else:
            T = self._temperature()
            accept = T > 0 and self.rng.random() < math.exp((res.score - self.current_score) / T)
        if accept:
            self.current, self.current_score = state, res.score
            self.accepted += 1

    def run(self) -> dict[str, Any]:
        cfg = self.config
        max_props = cfg.max_proposals if cfg.max_proposals is not None else 20 * cfg.max_evals
        if not self._resumed:
            if (self.run_dir / "state.json").exists():
                raise FileExistsError(f"{self.run_dir} already has a checkpoint; use AnnealingSearch.resume()")
            atomic_write_json(self.run_dir / "config.json", {
                "kind": "annealing", "config": cfg.to_dict(), "mutator": self.mutator.name,
                "problem": self.problem.fingerprint(), "created": time.strftime("%Y-%m-%dT%H:%M:%S")})
            for st in self.mutator.initial_states(self.rng):
                self._consider(st, {"init": True})
            if self.current is None:
                raise ValueError("no valid initial state for annealing")
            self._checkpoint()
        last_ckpt = self.evaluator.n_evals
        self.stop_reason = None
        while True:
            if self.evaluator.n_evals >= cfg.max_evals:
                self.stop_reason = "max_evals"
                break
            if self.proposals >= max_props:
                self.stop_reason = "max_proposals"
                break
            self.proposals += 1
            cand = self.mutator.neighbor(self.current, self.rng)
            self._consider(cand, {"proposal": self.proposals, "T": self._temperature()})
            if self.evaluator.n_evals - last_ckpt >= cfg.checkpoint_every:
                self._checkpoint()
                last_ckpt = self.evaluator.n_evals
        self._checkpoint()
        summary = {
            "kind": "annealing", "run_id": cfg.run_id, "mutator": self.mutator.name,
            "stop_reason": self.stop_reason, "best_score": None if self.best is None else self.best["score"],
            "best_hash": None if self.best is None else self.best["hash"],
            "best_metrics": None if self.best is None else self.best["metrics"],
            "n_evals": self.evaluator.n_evals, "n_cache_hits": self.evaluator.n_cache_hits,
            "proposals": self.proposals, "accepted": self.accepted,
        }
        atomic_write_json(self.run_dir / "summary.json", summary)
        if self.best is not None:
            (self.run_dir / "best_program.py").write_text(
                f"# score={self.best['score']!r} hash={self.best['hash']}\n{self.best['src']}\n")
        return summary

    def _checkpoint(self) -> None:
        version, internal, gauss = self.rng.getstate()
        atomic_write_json(self.run_dir / "state.json", {
            "config": self.config.to_dict(), "problem": self.problem.fingerprint(),
            "mutator": self.mutator.name, "rng_state": [version, list(internal), gauss],
            "evaluator": self.evaluator.state_dict(), "log_offset": self.eval_log.offset(),
            "current": self.current, "current_score": self.current_score, "best": self.best,
            "proposals": self.proposals, "accepted": self.accepted,
        })
