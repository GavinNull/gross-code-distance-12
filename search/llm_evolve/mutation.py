"""不依赖 LLM 的程序变异算子（MockClient 和经典基线共用）。"""

from __future__ import annotations

import ast
import random

_BINOP_SWAPS = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
_CMP_SWAPS = {ast.Lt: ast.Gt, ast.Gt: ast.Lt, ast.LtE: ast.GtE, ast.GtE: ast.LtE}


def _numeric_constants(tree: ast.AST) -> list[ast.Constant]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            out.append(node)
    return out


def _mutate_number(v: float, rng: random.Random, scale: float) -> int | float:
    if isinstance(v, int):
        step = max(1, int(abs(v) * scale))
        delta = rng.randint(1, step) * rng.choice((-1, 1))
        return v + delta
    sigma = scale * (abs(v) + 0.1)
    return round(v + rng.gauss(0.0, sigma), 6)


def mutate_program(src: str, rng: random.Random, *, scale: float = 0.25,
                   p_structural: float = 0.15, max_literals: int = 2) -> str:
    """随机修改 1..max_literals 个数值字面量；以 p_structural 概率交换一个算术/比较运算符。

    返回新源码（可能与原程序等价，调用方通过哈希去重）。无法解析时原样返回。
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    consts = _numeric_constants(tree)
    structural = [n for n in ast.walk(tree)
                  if (isinstance(n, ast.BinOp) and type(n.op) in _BINOP_SWAPS)
                  or (isinstance(n, ast.Compare) and any(type(o) in _CMP_SWAPS for o in n.ops))]
    did = False
    if structural and (not consts or rng.random() < p_structural):
        node = rng.choice(structural)
        if isinstance(node, ast.BinOp):
            node.op = _BINOP_SWAPS[type(node.op)]()
        else:
            idx = [i for i, o in enumerate(node.ops) if type(o) in _CMP_SWAPS]
            j = rng.choice(idx)
            node.ops[j] = _CMP_SWAPS[type(node.ops[j])]()
        did = True
    if consts and (not did or rng.random() < 0.5):
        for node in rng.sample(consts, k=min(len(consts), rng.randint(1, max_literals))):
            node.value = _mutate_number(node.value, rng, scale)
    return ast.unparse(tree)
