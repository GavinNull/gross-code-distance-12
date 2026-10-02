"""问题接口：框架与具体问题之间唯一的契约。

框架只通过 ``Problem`` 的三个入口和问题交互：

* ``description()``    —— 给 LLM 看的任务说明（含函数签名、约束、可用库）；
* ``seed_programs()``  —— 初始种子程序（完整 Python 源码字符串）；
* ``evaluate(src)``    —— 打分，返回 ``EvalResult``。分数**越大越好**。

框架绝不 import 评估器内部函数；``evaluate`` 是唯一的打分入口。
问题自己负责在 ``evaluate`` 里调用 ``sandbox.run_in_sandbox`` 执行候选程序
（候选程序的输出由父进程里的问题代码校验/打分，候选程序拿不到打分逻辑）。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class EvalResult:
    """一次评估的结果。

    valid:       候选程序是否合法（能运行、输出满足约束）。invalid 的程序不进数据库。
    score:       越大越好；仅当 valid=True 时有意义，必须是有限浮点数。
    metrics:     任意可 JSON 序列化的附加指标（会写进日志）。
    diagnostics: 给 LLM 看的诊断文本（例如“第 3 层 hook error 导致距离降为 10”或截断后的 traceback）。
    """

    valid: bool
    score: float
    metrics: dict[str, Any] = field(default_factory=dict)
    diagnostics: str = ""

    def __post_init__(self) -> None:
        self.score = float(self.score)
        if self.valid and not math.isfinite(self.score):
            # 合法程序必须有有限分数，否则排序/退火都会出错
            self.valid = False
            self.diagnostics = f"non-finite score {self.score!r}; " + self.diagnostics
        if not math.isfinite(self.score):
            self.score = -1e300

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EvalResult:
        return cls(valid=d["valid"], score=d["score"], metrics=d.get("metrics", {}),
                   diagnostics=d.get("diagnostics", ""))

    @classmethod
    def invalid(cls, diagnostics: str, **metrics: Any) -> EvalResult:
        return cls(valid=False, score=-1e300, metrics=dict(metrics), diagnostics=diagnostics)


class Problem(ABC):
    """所有可搜索问题的基类。

    子类必须设置 ``name`` 和 ``function_name``（候选程序里必须定义的入口函数名），
    并实现三个抽象方法。``evaluate`` 必须是确定性的（同一源码同一分数），
    否则缓存和断点续跑的语义会被破坏；如需随机性，由问题自己固定种子。
    """

    name: str = "problem"
    function_name: str = "solve"

    @abstractmethod
    def description(self) -> str:
        """任务说明 + 函数签名 + 约束。会原样放进 prompt。"""

    @abstractmethod
    def seed_programs(self) -> list[str]:
        """至少一个合法的种子程序源码。"""

    @abstractmethod
    def evaluate(self, program_src: str) -> EvalResult:
        """给候选程序打分。不得抛异常（框架兜底，但会记为 evaluator_error）。"""

    def fingerprint(self) -> dict[str, Any]:
        """用于记录到运行配置、续跑时校验“是不是同一个问题”。子类可扩展。"""
        return {"name": self.name, "function_name": self.function_name, "class": type(self).__qualname__}


@runtime_checkable
class SolutionSpace(Protocol):
    """可选协议：问题若能提供一个“直接解空间”，经典基线可以在其上做模拟退火。

    解对象必须可 JSON 序列化（用于断点续跑）。``solution_to_program`` 把一个解
    包装成合法的候选程序源码，这样基线和 LLM 搜索走**同一个** ``evaluate`` 入口、
    计同样的评估次数。
    """

    def initial_solution(self, rng: Any) -> Any: ...

    def neighbor(self, solution: Any, rng: Any) -> Any: ...

    def solution_to_program(self, solution: Any) -> str: ...
