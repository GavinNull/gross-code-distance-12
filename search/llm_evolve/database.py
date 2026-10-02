"""程序数据库：岛模型 + 分数/多样性选择 + 规范化哈希。"""

from __future__ import annotations

import ast
import hashlib
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|\S")


def _strip_docstrings(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]


def normalize_source(src: str) -> str:
    """规范化源码：解析为 AST 再 unparse（去掉注释、空白差异、docstring）。

    语法错误的源码退化为“去掉行尾空白和空行”的文本。
    注意：不做 alpha 重命名，变量名不同的等价程序会被视为不同程序。
    """
    try:
        tree = ast.parse(src)
        _strip_docstrings(tree)
        return ast.unparse(tree)
    except (SyntaxError, ValueError, RecursionError):
        lines = [ln.rstrip() for ln in src.strip().splitlines()]
        return "\n".join(ln for ln in lines if ln)


def program_hash(src: str) -> str:
    return hashlib.sha256(normalize_source(src).encode()).hexdigest()[:20]


def token_set(src: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(normalize_source(src)))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


@dataclass
class Program:
    hash: str
    src: str
    score: float
    metrics: dict[str, Any] = field(default_factory=dict)
    diagnostics: str = ""
    island: int = 0
    eval_index: int = 0           # 第几次（唯一）评估产生
    parents: list[str] = field(default_factory=list)
    origin: str = "seed"          # seed / llm:<tier> / migrated

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Program:
        return cls(**d)


class ProgramDatabase:
    """多个岛独立进化；``reset_worst_islands`` 把最差的若干岛重置为最好岛的精英。

    父代选择：
      1. 岛内分数做 min-max 归一化 s∈[0,1]；
      2. 第一个父代按 softmax(s / T) 采样；
      3. 之后的父代按 softmax((s + λ·(1 - max_jaccard(已选))) / T) 采样（不放回），
         λ = diversity_weight，鼓励给 LLM 看“风格不同”的程序。
    岛满了淘汰分数最低者（同分淘汰更早的）。全局最优单独记录，永不丢失，因此
    best_score 随评估次数单调不降。
    """

    def __init__(self, num_islands: int = 4, island_capacity: int = 20,
                 temperature: float = 0.3, diversity_weight: float = 0.3):
        if num_islands < 1:
            raise ValueError("num_islands must be >= 1")
        self.num_islands = num_islands
        self.island_capacity = island_capacity
        self.temperature = temperature
        self.diversity_weight = diversity_weight
        self.islands: list[list[Program]] = [[] for _ in range(num_islands)]
        self.best: Program | None = None
        self.num_resets = 0
        self._tokens: dict[str, frozenset[str]] = {}

    # ---- 增删 ----
    def add(self, prog: Program, island: int) -> None:
        isl = self.islands[island]
        if any(p.hash == prog.hash for p in isl):
            return
        prog = Program.from_dict({**prog.to_dict(), "island": island})
        isl.append(prog)
        if len(isl) > self.island_capacity:
            # 淘汰分数最低者；同分淘汰更早的（eval_index 小）
            worst = min(range(len(isl)), key=lambda i: (isl[i].score, isl[i].eval_index))
            isl.pop(worst)
        if self.best is None or prog.score > self.best.score:
            self.best = prog

    def add_to_all(self, prog: Program) -> None:
        for i in range(self.num_islands):
            self.add(prog, i)

    # ---- 选择 ----
    def _toks(self, p: Program) -> frozenset[str]:
        t = self._tokens.get(p.hash)
        if t is None:
            t = self._tokens[p.hash] = token_set(p.src)
        return t

    def sample_parents(self, island: int, k: int, rng) -> list[Program]:
        pool = list(self.islands[island])
        if not pool:
            # 岛被清空的极端情况：退回全局最优
            return [self.best] if self.best is not None else []
        k = min(k, len(pool))
        scores = [p.score for p in pool]
        lo, hi = min(scores), max(scores)
        norm = [(s - lo) / (hi - lo) if hi > lo else 1.0 for s in scores]
        chosen: list[Program] = []
        remaining = list(range(len(pool)))
        T = max(self.temperature, 1e-6)
        while len(chosen) < k:
            logits = []
            for i in remaining:
                v = norm[i]
                if chosen and self.diversity_weight:
                    sim = max(jaccard(self._toks(pool[i]), self._toks(c)) for c in chosen)
                    v += self.diversity_weight * (1.0 - sim)
                logits.append(v / T)
            m = max(logits)
            weights = [math.exp(x - m) for x in logits]
            r = rng.random() * sum(weights)
            acc = 0.0
            pick = remaining[-1]
            for i, w in zip(remaining, weights):
                acc += w
                if r <= acc:
                    pick = i
                    break
            chosen.append(pool[pick])
            remaining.remove(pick)
        chosen.sort(key=lambda p: p.score)  # prompt 中按分数升序，最好的放最后
        return chosen

    # ---- 岛重置 ----
    def island_best(self, i: int) -> float:
        return max((p.score for p in self.islands[i]), default=-math.inf)

    def reset_worst_islands(self, num_reset: int, elites: int = 1) -> list[int]:
        """把最差的 num_reset 个岛清空，并放入最好岛的前 ``elites`` 名精英。返回被重置的岛编号。"""
        if self.num_islands < 2 or num_reset < 1:
            return []
        order = sorted(range(self.num_islands), key=lambda i: (self.island_best(i), -i))
        best_island = order[-1]
        donors = sorted(self.islands[best_island], key=lambda p: -p.score)[:max(1, elites)]
        reset = [i for i in order[:num_reset] if i != best_island]
        for i in reset:
            self.islands[i] = []
            for d in donors:
                self.add(Program.from_dict({**d.to_dict(), "origin": "migrated"}), i)
        self.num_resets += 1
        return reset

    # ---- 统计与序列化 ----
    def size(self) -> int:
        return sum(len(i) for i in self.islands)

    def summary(self) -> dict[str, Any]:
        return {
            "best_score": None if self.best is None else self.best.score,
            "best_hash": None if self.best is None else self.best.hash,
            "island_best": [None if not isl else max(p.score for p in isl) for isl in self.islands],
            "island_sizes": [len(isl) for isl in self.islands],
            "num_resets": self.num_resets,
        }

    def state_dict(self) -> dict[str, Any]:
        return {
            "num_islands": self.num_islands, "island_capacity": self.island_capacity,
            "temperature": self.temperature, "diversity_weight": self.diversity_weight,
            "islands": [[p.to_dict() for p in isl] for isl in self.islands],
            "best": None if self.best is None else self.best.to_dict(),
            "num_resets": self.num_resets,
        }

    @classmethod
    def from_state(cls, d: dict[str, Any]) -> ProgramDatabase:
        db = cls(d["num_islands"], d["island_capacity"], d["temperature"], d["diversity_weight"])
        db.islands = [[Program.from_dict(p) for p in isl] for isl in d["islands"]]
        db.best = None if d["best"] is None else Program.from_dict(d["best"])
        db.num_resets = d["num_resets"]
        return db
