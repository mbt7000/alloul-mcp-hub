from __future__ import annotations
import asyncio
from functools import lru_cache
from sentence_transformers import SentenceTransformer
import numpy as np

@lru_cache(maxsize=1)
def _model(name: str) -> SentenceTransformer:
    return SentenceTransformer(name)

async def embed_texts(texts: list[str], model_name: str) -> list[list[float]]:
    def _run() -> np.ndarray:
        m = _model(model_name)
        return m.encode([f"passage: {t}" for t in texts], normalize_embeddings=True)
    vecs = await asyncio.get_event_loop().run_in_executor(None, _run)
    return vecs.tolist()

async def embed_query(query: str, model_name: str) -> list[float]:
    def _run() -> np.ndarray:
        m = _model(model_name)
        return m.encode([f"query: {query}"], normalize_embeddings=True)
    vecs = await asyncio.get_event_loop().run_in_executor(None, _run)
    return vecs[0].tolist()
