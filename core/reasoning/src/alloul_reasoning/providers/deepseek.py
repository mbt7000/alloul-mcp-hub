import time
import httpx
from alloul_reasoning.providers.base import BaseProvider, LLMRequest, LLMResponse
from alloul_reasoning.settings import Settings


class DeepSeekProvider(BaseProvider):
    name = "deepseek"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.deepseek_base_url,
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            timeout=60.0,
        )

    async def is_available(self) -> bool:
        return bool(self._settings.deepseek_api_key)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        messages = list(request.messages)
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages
        payload: dict = {"model": "deepseek-chat", "messages": messages,
                         "max_tokens": request.max_tokens, "temperature": request.temperature}
        if request.json_schema:
            payload["response_format"] = {"type": "json_object"}
        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        latency_ms = int((time.monotonic() - start) * 1000)
        usage = data.get("usage", {})
        p_tok = usage.get("prompt_tokens", 0)
        c_tok = usage.get("completion_tokens", 0)
        s = self._settings
        cost = ((p_tok * s.deepseek_input_cost_per_mtok) // 1_000_000
                + (c_tok * s.deepseek_output_cost_per_mtok) // 1_000_000)
        return LLMResponse(text=data["choices"][0]["message"]["content"], provider=self.name,
                           model="deepseek-chat", prompt_tokens=p_tok, completion_tokens=c_tok,
                           cached_tokens=0, cost_usd_micros=cost, latency_ms=latency_ms)
