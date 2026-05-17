import re
import time
import anthropic
from alloul_reasoning.providers.base import BaseProvider, LLMRequest, LLMResponse
from alloul_reasoning.settings import Settings

_KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9\-_]{10,}")


class ClaudeProvider(BaseProvider):
    name = "claude"

    def __init__(self, settings: Settings) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._settings = settings

    async def is_available(self) -> bool:
        return bool(self._settings.anthropic_api_key)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model_hint or self._settings.claude_model
        start = time.monotonic()
        kwargs: dict = {
            "model": model, "max_tokens": request.max_tokens,
            "temperature": request.temperature, "messages": request.messages,
        }
        if request.system:
            if len(request.system) > 4000:
                kwargs["system"] = [{"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}]
            else:
                kwargs["system"] = request.system
        if request.json_schema:
            kwargs["tools"] = [{"name": "structured_output", "description": "Return structured JSON", "input_schema": request.json_schema}]
            kwargs["tool_choice"] = {"type": "tool", "name": "structured_output"}
        resp = await self._client.messages.create(**kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)
        usage = resp.usage
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        s = self._settings
        cost = ((usage.input_tokens * s.claude_input_cost_per_mtok) // 1_000_000
                + (usage.output_tokens * s.claude_output_cost_per_mtok) // 1_000_000)
        if request.json_schema:
            block = next((b for b in resp.content if b.type == "tool_use"), None)
            text = str(block.input) if block else ""
        else:
            text = resp.content[0].text if resp.content else ""
        return LLMResponse(text=text, provider=self.name, model=model,
                           prompt_tokens=usage.input_tokens, completion_tokens=usage.output_tokens,
                           cached_tokens=cached, cost_usd_micros=cost, latency_ms=latency_ms)
