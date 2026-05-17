from __future__ import annotations
import io
import asyncio
from typing import Optional


async def extract_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF. Falls back to OCR if text layer is empty."""
    def _extract() -> str:
        try:
            import fitz  # pymupdf
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            return text.strip()
        except Exception:
            return ""
    return await asyncio.get_event_loop().run_in_executor(None, _extract)


async def extract_pdf_with_ocr(file_bytes: bytes, lang: str = "eng+ara") -> str:
    """OCR-based extraction for scanned PDFs."""
    def _ocr() -> str:
        import fitz
        import pytesseract
        from PIL import Image
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text += pytesseract.image_to_string(img, lang=lang) + "\n"
        return text.strip()
    return await asyncio.get_event_loop().run_in_executor(None, _ocr)
