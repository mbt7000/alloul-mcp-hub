import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_privacy_high_goes_to_ollama() -> None:
    from alloul_reasoning.providers.base import LLMRequest, LLMResponse, BaseProvider
    from alloul_reasoning.router import select_chain

    class FP(BaseProvider):
        def __init__(self, n: str) -> None:
            self.name = n
        async def is_available(self) -> bool: return True
        async def complete(self, r: LLMRequest) -> LLMResponse:
            return LLMResponse("ok", self.name, "test", 0, 0, 0, 0, 0)

    providers = {"claude": FP("claude"), "deepseek": FP("deepseek"), "ollama": FP("ollama")}
    req = LLMRequest(messages=[], privacy="high")
    chain = await select_chain(req, providers)
    assert len(chain) == 1
    assert chain[0].name == "ollama"
