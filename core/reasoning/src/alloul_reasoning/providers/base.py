from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMRequest:
    messages: list[dict[str, Any]]
    system: str | None = None
    max_tokens: int = 2048
    temperature: float = 0.7
    model_hint: str | None = None
    json_schema: dict[str, Any] | None = None
    privacy: str = "normal"
    tenant_id: str | None = None
    caller_service: str = "unknown"
    caller_tool: str = "unknown"
    trace_id: str | None = None


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    cost_usd_micros: int
    latency_ms: int


class BaseProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def is_available(self) -> bool: ...
