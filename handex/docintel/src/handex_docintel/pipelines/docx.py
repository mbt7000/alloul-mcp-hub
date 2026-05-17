from __future__ import annotations
import asyncio


async def extract_docx(file_bytes: bytes) -> str:
    def _extract() -> str:
        import io
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return await asyncio.get_event_loop().run_in_executor(None, _extract)
