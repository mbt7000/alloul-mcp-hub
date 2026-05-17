import time
import httpx
from alloul_reasoning.providers.base import BaseProvider, LLMRequest, LLMResponse
from alloul_reasoning.settings import Settings


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self._client = httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=120.0)

    async def is_available(self) -> bool:
        try:
            r = await self._client.get("/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model_hint or "qwen2.5-coder:32b"
        start = time.monotonic()
        messages = list(request.messages)
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages
        payload: dict = {"model": model, "messages": messages, "stream": False,
                         "options": {"temperature": request.temperature, "num_predict": request.max_tokens}}
        if request.json_schema:
            payload["format"] = "json"
        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(text=data["message"]["content"], provider=self.name, model=model,
                           prompt_tokens=data.get("prompt_eval_count", 0),
                           completion_tokens=data.get("eval_count", 0),
                           cached_tokens=0, cost_usd_micros=0, latency_ms=latency_ms)
