from __future__ import annotations
import re
import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")

def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    sentences = re.split(r'(?<=[.!?؟])\s+', text.strip())
    chunks: list[str] = []
    current: list[int] = []
    for sent in sentences:
        toks = _enc.encode(sent)
        if len(current) + len(toks) > chunk_size and current:
            chunks.append(_enc.decode(current))
            current = current[-overlap:] + list(toks)
        else:
            current.extend(toks)
    if current:
        chunks.append(_enc.decode(current))
    return [c for c in chunks if c.strip()]

def count_tokens(text: str) -> int:
    return len(_enc.encode(text))
