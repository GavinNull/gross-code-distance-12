"""LLM 客户端抽象：``AnthropicClient``（真实 API）与 ``MockClient``（离线测试）。

引擎只依赖 ``LLMClient.complete(LLMRequest) -> LLMResponse``。快/强模型的分配比例由
引擎决定（``EvolutionConfig.strong_fraction``），客户端只负责把 tier 映射到具体模型。
"""

from __future__ import annotations

import os
import random
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from .mutation import mutate_program
from .prompt import SYSTEM_PROMPT

DEFAULT_FAST_MODEL = "claude-sonnet-5-5"
DEFAULT_STRONG_MODEL = "claude-opus-5-5"

# 美元 / 百万 token（输入, 输出），仅用于日志里的费用估算；预算按 token 执行。
DEFAULT_PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}


class LLMConfigError(RuntimeError):
    pass


@dataclass
class LLMRequest:
    prompt: str
    tier: str              # "fast" | "strong"
    max_tokens: int
    seed: int              # 由引擎的 RNG 生成；真实 API 无法使用（无采样种子），MockClient 用它保证确定性
    system: str = SYSTEM_PROMPT


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = None
    latency_s: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...

    def describe(self) -> dict[str, Any]: ...


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int,
                      prices: dict[str, tuple[float, float]] | None = None) -> float | None:
    p = (prices or DEFAULT_PRICES).get(model)
    if p is None:
        return None
    return (input_tokens * p[0] + output_tokens * p[1]) / 1e6


# --------------------------------------------------------------------------- Anthropic
class AnthropicClient:
    """用 ``anthropic`` SDK 调用 Messages API。

    * API key 只从环境变量 ``ANTHROPIC_API_KEY`` 读取（不读 .env 文件）；
    * 模型名从 ``LLM_MODEL_FAST`` / ``LLM_MODEL_STRONG`` 读取，默认 claude-sonnet-5-5 / claude-opus-5-5；
    * 这两个模型不接受 temperature 等采样参数，也不支持关闭 thinking；思考深度用 ``effort`` 控制；
    * 默认启用服务端 refusal fallback（``fallbacks="default"``），被拒答时由 API 自动换模型重试；
    * token 用量：input = input_tokens + cache 读写 tokens；output_tokens 已包含 thinking。
    """

    def __init__(self, *, fast_model: str | None = None, strong_model: str | None = None,
                 effort: dict[str, str] | None = None, use_fallbacks: bool = True,
                 timeout_s: float = 600.0, max_retries: int = 2, sdk_client: Any = None):
        self.models = {
            "fast": fast_model or os.environ.get("LLM_MODEL_FAST") or DEFAULT_FAST_MODEL,
            "strong": strong_model or os.environ.get("LLM_MODEL_STRONG") or DEFAULT_STRONG_MODEL,
        }
        self.effort = effort or {"fast": "medium", "strong": "high"}
        self.use_fallbacks = use_fallbacks
        if sdk_client is not None:  # 测试注入
            self._client = sdk_client
            return
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMConfigError("ANTHROPIC_API_KEY is not set in the environment")
        import anthropic

        self._client = anthropic.Anthropic(api_key=key, timeout=timeout_s, max_retries=max_retries)

    def describe(self) -> dict[str, Any]:
        return {"type": "anthropic", "models": self.models, "effort": self.effort,
                "use_fallbacks": self.use_fallbacks}

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = self.models[request.tier]
        kwargs: dict[str, Any] = dict(
            model=model,
            max_tokens=request.max_tokens,
            system=request.system,
            messages=[{"role": "user", "content": request.prompt}],
            output_config={"effort": self.effort.get(request.tier, "medium")},
        )
        t0 = time.perf_counter()
        if self.use_fallbacks:
            resp = self._client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        else:
            resp = self._client.messages.create(**kwargs)
        latency = time.perf_counter() - t0
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
        u = resp.usage
        input_tokens = (getattr(u, "input_tokens", 0) or 0) \
            + (getattr(u, "cache_creation_input_tokens", 0) or 0) \
            + (getattr(u, "cache_read_input_tokens", 0) or 0)
        extra: dict[str, Any] = {"request_id": getattr(resp, "_request_id", None)}
        if resp.stop_reason == "refusal":
            sd = getattr(resp, "stop_details", None)
            extra["refusal_category"] = getattr(sd, "category", None) if sd else None
        return LLMResponse(text=text, model=getattr(resp, "model", model), input_tokens=input_tokens,
                           output_tokens=getattr(u, "output_tokens", 0) or 0,
                           stop_reason=resp.stop_reason, latency_s=latency, extra=extra)


# --------------------------------------------------------------------------- Mock
_PROMPT_BLOCK_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)


class MockClient:
    """离线假 LLM：从 prompt 里解析父代程序，做随机小改动，或以一定概率返回预设程序。

    行为完全由 ``request.seed`` 决定（确定性，可复现、可续跑）。token 用量按 4 字符/token 估算。
    """

    def __init__(self, presets: list[str] | None = None, p_preset: float = 0.2,
                 p_garbage: float = 0.0, chars_per_token: int = 4):
        self.presets = list(presets or [])
        self.p_preset = p_preset
        self.p_garbage = p_garbage
        self.chars_per_token = chars_per_token
        self.calls = 0

    def describe(self) -> dict[str, Any]:
        return {"type": "mock", "num_presets": len(self.presets), "p_preset": self.p_preset,
                "p_garbage": self.p_garbage}

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        rng = random.Random(request.seed)
        parents = [b.strip() for b in _PROMPT_BLOCK_RE.findall(request.prompt)]
        u = rng.random()
        if u < self.p_garbage:
            text = "I am not sure how to improve this."  # 无代码块 -> 提取失败
        elif self.presets and (u < self.p_garbage + self.p_preset or not parents):
            text = f"Here is a new approach:\n```python\n{rng.choice(self.presets).strip()}\n```\n"
        else:
            base = parents[-1] if rng.random() < 0.7 or len(parents) == 1 else rng.choice(parents)
            text = f"Improved version:\n```python\n{mutate_program(base, rng)}\n```\n"
        model = "mock-strong" if request.tier == "strong" else "mock-fast"
        return LLMResponse(
            text=text, model=model,
            input_tokens=max(1, (len(request.system) + len(request.prompt)) // self.chars_per_token),
            output_tokens=max(1, len(text) // self.chars_per_token),
            stop_reason="end_turn",
        )
