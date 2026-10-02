"""玩具问题：圆上点的 TSP（廉价、已知最优解）。

候选程序实现 ``solve(points) -> list[int]``，返回闭合回路的访问顺序。测试实例的点都在单位圆上
（候选程序不被告知），因此最优回路就是按极角排序，最优长度可精确计算。

score = mean_i(最优长度_i / 回路长度_i) ∈ (0, 1]，1.0 即最优。
种子程序按绕参考点 (cx, cy) 的极角排序，参考点在圆外 -> 次优；把参考点移进圆内即可达到最优，
因此数值变异（MockClient / 退火）也有路可走，LLM 则可以直接想到“绕质心排序”或 2-opt。
"""

from __future__ import annotations

import json
import math
import random
from typing import Any

from .problem import EvalResult, Problem
from .sandbox import run_in_sandbox

SEED_PROGRAM = '''\
import math


def solve(points):
    """Return a visiting order (a permutation of range(len(points))) for a closed tour."""
    cx, cy = 2.0, 1.5  # reference point for the angular sort
    return sorted(range(len(points)), key=lambda i: math.atan2(points[i][1] - cy, points[i][0] - cx))
'''

OPTIMAL_PROGRAM = '''\
import math


def solve(points):
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return sorted(range(len(points)), key=lambda i: math.atan2(points[i][1] - cy, points[i][0] - cx))
'''

NEAREST_NEIGHBOR_PROGRAM = '''\
def solve(points):
    n = len(points)
    left = set(range(1, n))
    tour = [0]
    while left:
        x, y = points[tour[-1]]
        j = min(left, key=lambda k: (points[k][0] - x) ** 2 + (points[k][1] - y) ** 2)
        tour.append(j)
        left.remove(j)
    return tour
'''

# 用于测试的“坏”程序
TIMEOUT_PROGRAM = "def solve(points):\n    while True:\n        pass\n"
RAISING_PROGRAM = "def solve(points):\n    raise ValueError('boom')\n"
BAD_OUTPUT_PROGRAM = "def solve(points):\n    return [0] * len(points)\n"


def tour_length(points: list[list[float]], order: list[int]) -> float:
    n = len(order)
    return sum(math.dist(points[order[i]], points[order[(i + 1) % n]]) for i in range(n))


def _segments_cross(p1, p2, p3, p4) -> bool:
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return (d1 * d2 < 0) and (d3 * d4 < 0)


def count_crossings(points, order) -> int:
    n = len(order)
    edges = [(points[order[i]], points[order[(i + 1) % n]]) for i in range(n)]
    c = 0
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _segments_cross(*edges[i], *edges[j]):
                c += 1
    return c


class CircleTSPProblem(Problem):
    name = "toy_circle_tsp"
    function_name = "solve"

    def __init__(self, sizes: tuple[int, ...] = (12, 20, 31), instance_seed: int = 0,
                 timeout_s: float = 5.0, mem_mb: int = 512):
        self.sizes = tuple(sizes)
        self.instance_seed = instance_seed
        self.timeout_s = timeout_s
        self.mem_mb = mem_mb
        rng = random.Random(instance_seed)
        self.instances: list[list[list[float]]] = []
        self.optimal: list[float] = []
        for n in self.sizes:
            angles = sorted(rng.uniform(0, 2 * math.pi) for _ in range(n))
            pts = [[round(math.cos(a), 9), round(math.sin(a), 9)] for a in angles]
            self.optimal.append(tour_length(pts, list(range(n))))
            perm = list(range(n))
            rng.shuffle(perm)
            self.instances.append([pts[i] for i in perm])  # 打乱顺序，隐藏最优解

    def fingerprint(self) -> dict[str, Any]:
        return {**super().fingerprint(), "sizes": list(self.sizes), "instance_seed": self.instance_seed}

    def description(self) -> str:
        return (
            "Write a Python function\n\n"
            "    def solve(points: list[list[float]]) -> list[int]\n\n"
            "that receives n 2-D points (each a [x, y] list, 10 <= n <= 50) and returns a visiting order "
            "for a CLOSED tour: a permutation of range(n). The score is the average over several test "
            "instances of (optimal tour length / your tour length), so 1.0 is optimal. "
            "Only the standard library (math, itertools, random, ...) and numpy may be used. "
            f"Each evaluation has a {self.timeout_s:.0f}s time limit for all instances together. "
            "The function must be deterministic."
        )

    def seed_programs(self) -> list[str]:
        return [SEED_PROGRAM]

    def evaluate(self, program_src: str) -> EvalResult:
        r = run_in_sandbox(program_src, self.function_name, [[pts] for pts in self.instances],
                           timeout_s=self.timeout_s, mem_mb=self.mem_mb)
        if not r.ok:
            return EvalResult.invalid(r.diagnostics(), error_type=r.error_type, elapsed=r.elapsed)
        ratios, lines = [], []
        for pts, opt, out in zip(self.instances, self.optimal, r.outputs or []):
            n = len(pts)
            try:
                order = [int(v) for v in out]
            except (TypeError, ValueError):
                return EvalResult.invalid(f"n={n}: output is not a list of ints: {str(out)[:200]}",
                                          error_type="BadOutput")
            if sorted(order) != list(range(n)):
                return EvalResult.invalid(
                    f"n={n}: output is not a permutation of range({n}) "
                    f"(len={len(order)}, distinct={len(set(order))})", error_type="BadOutput")
            length = tour_length(pts, order)
            ratio = opt / length
            ratios.append(ratio)
            lines.append(f"n={n}: tour length {length:.4f}, optimal/length={ratio:.4f}, "
                         f"self-crossing edge pairs={count_crossings(pts, order)}")
        score = sum(ratios) / len(ratios)
        return EvalResult(valid=True, score=score,
                          metrics={"ratios": ratios, "elapsed": round(r.elapsed, 4)},
                          diagnostics="\n".join(lines))

    def mock_presets(self) -> list[str]:
        """MockClient 的预设回复（只用于离线测试/演示；真实 LLM 不需要）。"""
        return [NEAREST_NEIGHBOR_PROGRAM, RAISING_PROGRAM, BAD_OUTPUT_PROGRAM, OPTIMAL_PROGRAM]

    # ---- SolutionSpace 协议（供经典退火基线直接在解空间上搜索）----
    def initial_solution(self, rng: random.Random) -> list[list[int]]:
        sol = []
        for n in self.sizes:
            p = list(range(n))
            rng.shuffle(p)
            sol.append(p)
        return sol

    def neighbor(self, solution: list[list[int]], rng: random.Random) -> list[list[int]]:
        """2-opt：随机选一个实例，反转一段。"""
        sol = [list(p) for p in solution]
        k = rng.randrange(len(sol))
        n = len(sol[k])
        i, j = sorted(rng.sample(range(n), 2))
        sol[k][i:j + 1] = reversed(sol[k][i:j + 1])
        return sol

    def solution_to_program(self, solution: list[list[int]]) -> str:
        table = {len(p): list(p) for p in solution}
        return f"TABLE = {json.dumps(table)}\n\n\ndef solve(points):\n    return TABLE[str(len(points))]\n"
