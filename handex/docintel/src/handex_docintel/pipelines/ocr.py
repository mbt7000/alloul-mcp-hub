from __future__ import annotations
import asyncio


async def ocr_image(image_bytes: bytes, lang: str = "eng+ara") -> str:
    def _run() -> str:
        import pytesseract
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img, lang=lang)
    return await asyncio.get_event_loop().run_in_executor(None, _run)
