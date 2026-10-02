"""提示构造与回复中程序的提取。"""

from __future__ import annotations

import ast
import re

from .database import Program
from .sandbox import truncate_middle

SYSTEM_PROMPT = (
    "You are an expert algorithm designer taking part in an evolutionary program search. "
    "You improve Python functions so that an automatic evaluator gives them a higher score. "
    "Reply with exactly one complete Python code block."
)

_CODE_BLOCK_RE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)


def build_prompt(problem_description: str, function_name: str, parents: list[Program],
                 *, max_diag_chars: int = 800, extra_instructions: str = "") -> str:
    """父代按分数升序排列（最好的在最后），每个附分数和评估器诊断。"""
    parts = [
        "# Task\n",
        problem_description.strip(),
        "\n\n# Previous versions (sorted from worst to best; higher score is better)\n",
    ]
    for i, p in enumerate(parents):
        diag = truncate_middle(p.diagnostics.strip(), max_diag_chars) if p.diagnostics else "(none)"
        parts.append(
            f"\n## Version {i} — score {p.score:.6g}\n"
            f"Evaluator diagnostics:\n{diag}\n\n```python\n{p.src.strip()}\n```\n"
        )
    parts.append(
        "\n# Your job\n"
        f"Write an improved version of `{function_name}` that should score higher than all versions above. "
        "You may combine ideas from several versions or try a substantially different approach. "
        "Output the COMPLETE program (all imports and helper functions it needs, and the function "
        f"`{function_name}` with the same signature) in a single ```python code block. "
        "Do not read or write files, use the network, or spawn processes; such programs are rejected."
    )
    if extra_instructions:
        parts.append("\n" + extra_instructions.strip())
    return "".join(parts)


def extract_program(text: str, function_name: str) -> str | None:
    """从 LLM 回复中提取程序：优先选“定义了目标函数且能解析”的最后一个代码块。"""
    blocks = [b.strip() for b in _CODE_BLOCK_RE.findall(text)]
    if not blocks:
        stripped = text.strip()
        if re.search(rf"^\s*def\s+{re.escape(function_name)}\s*\(", stripped, re.MULTILINE):
            blocks = [stripped]
    defining = [b for b in blocks if re.search(rf"\bdef\s+{re.escape(function_name)}\s*\(", b)]
    for b in reversed(defining):
        try:
            ast.parse(b)
            return b
        except SyntaxError:
            continue
    # 有定义但都有语法错误：仍返回最后一个，让评估器给出 SyntaxError 诊断
    return defining[-1] if defining else None
