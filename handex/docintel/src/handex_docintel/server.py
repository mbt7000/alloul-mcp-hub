from __future__ import annotations
import base64
import json
from typing import Any
import structlog
from fastmcp import FastMCP
import httpx

from handex_docintel.settings import Settings
from handex_docintel.pipelines.pdf import extract_pdf, extract_pdf_with_ocr
from handex_docintel.pipelines.docx import extract_docx
from shared.db import init_pool, get_pool
from shared.envelope import ok, err

log = structlog.get_logger()

DOC_TYPES = {"contract", "invoice", "policy", "report", "memo", "handover", "other"}


def create_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("handex.docintel", version="0.1.0")

    @mcp.on_startup
    async def startup() -> None:
        await init_pool(settings.database_url)
        log.info("handex.docintel started")

    @mcp.tool()
    async def docintel_extract(
        tenant_id: str,
        file_b64: str,
        filename: str,
        mime_type: str,
        use_ocr: bool = False,
        ocr_lang: str = "eng+ara",
    ) -> dict[str, Any]:
        """
        Extract text from PDF, DOCX, or image file.
        file_b64: base64-encoded file content.
        Returns extracted text + metadata.
        """
        try:
            file_bytes = base64.b64decode(file_b64)
        except Exception:
            return err("INVALID_B64", "Could not decode base64 file content")

        text = ""
        if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
            text = await extract_pdf(file_bytes)
            if not text and use_ocr:
                text = await extract_pdf_with_ocr(file_bytes, ocr_lang)
        elif mime_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",) or filename.lower().endswith(".docx"):
            text = await extract_docx(file_bytes)
        else:
            return err("UNSUPPORTED_FORMAT", f"Unsupported mime type: {mime_type}")

        pool = await get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO handex.documents (tenant_id, name, mime_type, size_bytes, storage_path, extracted_text, status)
            VALUES ($1,$2,$3,$4,$5,$6,'extracted')
            RETURNING id, name, status, created_at
            """,
            tenant_id, filename, mime_type, len(file_bytes),
            f"/handex/{tenant_id}/{filename}", text,
        )

        return ok({
            "document_id": str(row["id"]),
            "filename": filename,
            "extracted_chars": len(text),
            "text_preview": text[:500],
            "status": "extracted",
        })

    @mcp.tool()
    async def docintel_summarize(
        tenant_id: str,
        document_id: str,
        language: str = "auto",
    ) -> dict[str, Any]:
        """
        Summarize a document using alloul.reasoning.
        Calls reasoning-mcp internally — NOT a direct LLM call.
        """
        pool = await get_pool()
        doc = await pool.fetchrow(
            "SELECT extracted_text, name FROM handex.documents WHERE id=$1 AND tenant_id=$2",
            document_id, tenant_id,
        )
        if not doc:
            return err("NOT_FOUND", f"Document {document_id} not found")
        if not doc["extracted_text"]:
            return err("NO_TEXT", "Document has no extracted text. Run docintel.extract first.")

        text = doc["extracted_text"][:8000]
        lang_hint = "Respond in Arabic." if language == "ar" else "Respond in English." if language == "en" else ""

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.reasoning_mcp_url}/call-tool",
                json={
                    "name": "reasoning_complete",
                    "arguments": {
                        "messages": [{"role": "user", "content": f"Summarize this document concisely. {lang_hint}\n\n{text}"}],
                        "tenant_id": tenant_id,
                        "caller_service": "handex.docintel",
                        "caller_tool": "docintel.summarize",
                        "max_tokens": 1024,
                    },
                },
            )
            resp.raise_for_status()
            result = resp.json()

        summary = result.get("text", "")
        return ok({"document_id": document_id, "summary": summary, "doc_name": doc["name"]})

    @mcp.tool()
    async def docintel_entities(
        tenant_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        """
        Extract named entities (PERSON, ORG, DATE, ID, MONEY) from a document
        via alloul.reasoning structured output.
        """
        pool = await get_pool()
        doc = await pool.fetchrow(
            "SELECT extracted_text FROM handex.documents WHERE id=$1 AND tenant_id=$2",
            document_id, tenant_id,
        )
        if not doc:
            return err("NOT_FOUND", f"Document {document_id} not found")

        text = doc["extracted_text"][:6000]
        schema = {
            "type": "object",
            "properties": {
                "persons": {"type": "array", "items": {"type": "string"}},
                "organizations": {"type": "array", "items": {"type": "string"}},
                "dates": {"type": "array", "items": {"type": "string"}},
                "ids": {"type": "array", "items": {"type": "string"}},
                "money": {"type": "array", "items": {"type": "string"}},
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.reasoning_mcp_url}/call-tool",
                json={
                    "name": "reasoning_structured",
                    "arguments": {
                        "messages": [{"role": "user", "content": f"Extract all named entities from this text:\n\n{text}"}],
                        "json_schema": schema,
                        "tenant_id": tenant_id,
                        "caller_service": "handex.docintel",
                        "caller_tool": "docintel.entities",
                    },
                },
            )
            resp.raise_for_status()
            result = resp.json()

        return ok({"document_id": document_id, "entities": result.get("parsed", {})})

    @mcp.tool()
    async def docintel_classify(
        tenant_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        """Classify document type: contract, invoice, policy, report, memo, handover, other."""
        pool = await get_pool()
        doc = await pool.fetchrow(
            "SELECT extracted_text, name FROM handex.documents WHERE id=$1 AND tenant_id=$2",
            document_id, tenant_id,
        )
        if not doc:
            return err("NOT_FOUND", f"Document {document_id} not found")

        text = doc["extracted_text"][:3000]
        schema = {
            "type": "object",
            "properties": {
                "doc_type": {"type": "string", "enum": list(DOC_TYPES)},
                "confidence": {"type": "number"},
                "reasoning": {"type": "string"},
            },
            "required": ["doc_type", "confidence"],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.reasoning_mcp_url}/call-tool",
                json={
                    "name": "reasoning_structured",
                    "arguments": {
                        "messages": [{"role": "user", "content": f"Classify the type of this document. Text:\n\n{text}"}],
                        "json_schema": schema,
                        "tenant_id": tenant_id,
                        "caller_service": "handex.docintel",
                        "caller_tool": "docintel.classify",
                    },
                },
            )
            resp.raise_for_status()
            result = resp.json()

        classification = result.get("parsed") or {}
        if classification.get("doc_type"):
            await pool.execute(
                "UPDATE handex.documents SET doc_type=$1 WHERE id=$2 AND tenant_id=$3",
                classification["doc_type"], document_id, tenant_id,
            )

        return ok({"document_id": document_id, "classification": classification})

    @mcp.tool()
    async def docintel_compare(
        tenant_id: str,
        document_id_a: str,
        document_id_b: str,
    ) -> dict[str, Any]:
        """Semantic comparison of two documents. Returns differences and similarities."""
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT id, name, extracted_text FROM handex.documents WHERE id=ANY($1) AND tenant_id=$2",
            [document_id_a, document_id_b], tenant_id,
        )
        if len(rows) < 2:
            return err("NOT_FOUND", "One or both documents not found for this tenant")

        doc_a = next(r for r in rows if str(r["id"]) == document_id_a)
        doc_b = next(r for r in rows if str(r["id"]) == document_id_b)

        prompt = f"""Compare these two documents and identify:
1. Key differences
2. Common elements
3. Overall similarity assessment

Document A ({doc_a['name']}):
{doc_a['extracted_text'][:3000]}

Document B ({doc_b['name']}):
{doc_b['extracted_text'][:3000]}"""

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.reasoning_mcp_url}/call-tool",
                json={
                    "name": "reasoning_complete",
                    "arguments": {
                        "messages": [{"role": "user", "content": prompt}],
                        "tenant_id": tenant_id,
                        "caller_service": "handex.docintel",
                        "caller_tool": "docintel.compare",
                        "max_tokens": 2048,
                    },
                },
            )
            resp.raise_for_status()
            result = resp.json()

        return ok({
            "document_a": doc_a["name"],
            "document_b": doc_b["name"],
            "comparison": result.get("text", ""),
        })

    @mcp.tool()
    async def docintel_get_document(
        tenant_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        """Get document metadata and status. Tenant-isolated."""
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT id, name, mime_type, size_bytes, doc_type, language, status, metadata, created_at FROM handex.documents WHERE id=$1 AND tenant_id=$2",
            document_id, tenant_id,
        )
        if not row:
            return err("NOT_FOUND", f"Document {document_id} not found")
        return ok(dict(row))

    return mcp
