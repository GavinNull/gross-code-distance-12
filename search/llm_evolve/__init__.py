"""LLM 进化搜索框架（FunSearch / AlphaEvolve 风格内循环），与具体问题解耦。

问题通过 ``Problem`` 接口接入；见 README.md。
"""

from .baseline import (
    AnnealingConfig,
    AnnealingSearch,
    ProgramMutator,
    SolutionSpaceMutator,
)
from .database import Program, ProgramDatabase, normalize_source, program_hash
from .engine import EvolutionConfig, EvolutionEngine
from .llm import (
    AnthropicClient,
    LLMClient,
    LLMConfigError,
    LLMRequest,
    LLMResponse,
    MockClient,
)
from .problem import EvalResult, Problem, SolutionSpace
from .prompt import build_prompt, extract_program
from .runlog import best_at, best_so_far_curve
from .sandbox import SandboxResult, run_in_sandbox

__all__ = [
    "AnnealingConfig", "AnnealingSearch", "AnthropicClient", "EvalResult", "EvolutionConfig",
    "EvolutionEngine", "LLMClient", "LLMConfigError", "LLMRequest", "LLMResponse", "MockClient",
    "Problem", "Program", "ProgramDatabase", "ProgramMutator", "SandboxResult", "SolutionSpace",
    "SolutionSpaceMutator", "best_at", "best_so_far_curve", "build_prompt", "extract_program",
    "normalize_source", "program_hash", "run_in_sandbox",
]
