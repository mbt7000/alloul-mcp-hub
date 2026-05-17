from __future__ import annotations
import hashlib, json
from typing import Any
import structlog
from fastmcp import FastMCP
from alloul_knowledge.settings import Settings
from alloul_knowledge.embeddings import embed_texts, embed_query
from alloul_knowledge.chunking import chunk_text, count_tokens
from shared.db import init_pool, get_pool
from shared.envelope import ok, err

log = structlog.get_logger()


def _src_hash(collection_id: str, source_ref: dict) -> str:
    return hashlib.sha256(f"{collection_id}:{json.dumps(source_ref, sort_keys=True)}".encode()).hexdigest()


def create_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("alloul.knowledge", version="0.1.0")

    @mcp.on_startup
    async def startup() -> None:
        await init_pool(settings.database_url)
        log.info("alloul.knowledge started")

    @mcp.tool()
    async def knowledge_collections_ensure(
        tenant_id: str,
        product: str,
        name: str,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        """Create or retrieve a knowledge collection."""
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO knowledge.collections (tenant_id, product, name, source_type, embedding_model, dim)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (tenant_id, product, name) DO UPDATE SET source_type=EXCLUDED.source_type
            RETURNING id, tenant_id, product, name, source_type, embedding_model, dim, created_at
            """,
            tenant_id, product, name, source_type, settings.embedding_model, settings.embedding_dim,
        )
        return ok(dict(row))

    @mcp.tool()
    async def knowledge_ingest(
        tenant_id: str,
        product: str,
        collection: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Ingest documents. Idempotent via source_hash. Tenant+product isolated."""
        pool = await get_pool()
        coll = await pool.fetchrow(
            "SELECT id FROM knowledge.collections WHERE tenant_id=$1 AND product=$2 AND name=$3",
            tenant_id, product, collection,
        )
        if not coll:
            coll = await pool.fetchrow(
                """INSERT INTO knowledge.collections (tenant_id, product, name, embedding_model, dim)
                   VALUES ($1,$2,$3,$4,$5) ON CONFLICT (tenant_id,product,name) DO UPDATE SET name=EXCLUDED.name
                   RETURNING id""",
                tenant_id, product, collection, settings.embedding_model, settings.embedding_dim,
            )
        cid = str(coll["id"])
        total, replaced = 0, 0
        for item in items:
            sh = _src_hash(cid, item["source_ref"])
            deleted = await pool.execute(
                "DELETE FROM knowledge.chunks WHERE collection_id=$1 AND source_hash=$2", cid, sh,
            )
            if deleted != "DELETE 0":
                replaced += 1
            chunks = chunk_text(item["text"], settings.chunk_size, settings.chunk_overlap)
            if not chunks:
                continue
            vecs = await embed_texts(chunks, settings.embedding_model)
            await pool.executemany(
                """INSERT INTO knowledge.chunks (collection_id, tenant_id, product, source_ref, text, embedding, metadata, token_count, source_hash)
                   VALUES ($1,$2,$3,$4,$5,$6::vector,$7,$8,$9)""",
                [(cid, tenant_id, product, json.dumps(item["source_ref"]), chunk,
                  f"[{','.join(str(v) for v in vec)}]",
                  json.dumps(item.get("metadata", {})), count_tokens(chunk), sh)
                 for chunk, vec in zip(chunks, vecs)],
            )
            total += len(chunks)
        return ok({"collection_id": cid, "items": len(items), "chunks": total, "replaced": replaced})

    @mcp.tool()
    async def knowledge_search(
        tenant_id: str,
        product: str,
        query: str,
        collection: str | None = None,
        k: int = 10,
    ) -> dict[str, Any]:
        """Semantic search. Always scoped to tenant+product — no cross-tenant leakage."""
        pool = await get_pool()
        qvec = await embed_query(query, settings.embedding_model)
        vs = f"[{','.join(str(v) for v in qvec)}]"
        if collection:
            coll = await pool.fetchrow(
                "SELECT id FROM knowledge.collections WHERE tenant_id=$1 AND product=$2 AND name=$3",
                tenant_id, product, collection,
            )
            if not coll:
                return ok({"results": [], "query": query})
            rows = await pool.fetch(
                """SELECT kc.text, kc.source_ref, kc.metadata, 1-(kc.embedding<=>$1::vector) AS score
                   FROM knowledge.chunks kc
                   WHERE kc.tenant_id=$2 AND kc.product=$3 AND kc.collection_id=$4
                   ORDER BY kc.embedding<=>$1::vector LIMIT $5""",
                vs, tenant_id, product, str(coll["id"]), k,
            )
        else:
            rows = await pool.fetch(
                """SELECT kc.text, kc.source_ref, kc.metadata, 1-(kc.embedding<=>$1::vector) AS score
                   FROM knowledge.chunks kc
                   WHERE kc.tenant_id=$2 AND kc.product=$3
                   ORDER BY kc.embedding<=>$1::vector LIMIT $4""",
                vs, tenant_id, product, k,
            )
        results = [{"text": r["text"], "score": float(r["score"]),
                    "source_ref": json.loads(r["source_ref"]),
                    "metadata": json.loads(r["metadata"])} for r in rows]
        return ok({"results": results, "query": query, "k": k})

    @mcp.tool()
    async def knowledge_search_multi_collection(
        tenant_id: str,
        product: str,
        query: str,
        collections: list[str],
        k: int = 10,
    ) -> dict[str, Any]:
        """Search across multiple collections for the same tenant+product."""
        all_results: list[dict] = []
        for coll in collections:
            r = await knowledge_search(tenant_id=tenant_id, product=product, query=query, collection=coll, k=k)
            for item in r.get("data", {}).get("results", []):
                item["from_collection"] = coll
                all_results.append(item)
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return ok({"results": all_results[:k]})

    @mcp.tool()
    async def knowledge_delete_source(
        tenant_id: str,
        product: str,
        collection: str,
        source_ref: dict[str, Any],
    ) -> dict[str, Any]:
        """Delete all chunks for a source. Tenant-isolated."""
        pool = await get_pool()
        coll = await pool.fetchrow(
            "SELECT id FROM knowledge.collections WHERE tenant_id=$1 AND product=$2 AND name=$3",
            tenant_id, product, collection,
        )
        if not coll:
            return err("NOT_FOUND", "Collection not found")
        sh = _src_hash(str(coll["id"]), source_ref)
        result = await pool.execute(
            "DELETE FROM knowledge.chunks WHERE collection_id=$1 AND source_hash=$2 AND tenant_id=$3",
            str(coll["id"]), sh, tenant_id,
        )
        count = int(result.split()[-1]) if result else 0
        return ok({"deleted_chunks": count})

    @mcp.tool()
    async def knowledge_reindex(
        tenant_id: str,
        product: str,
        collection: str,
    ) -> dict[str, Any]:
        """Recompute embeddings after model upgrade. Tenant-isolated."""
        pool = await get_pool()
        coll = await pool.fetchrow(
            "SELECT id FROM knowledge.collections WHERE tenant_id=$1 AND product=$2 AND name=$3",
            tenant_id, product, collection,
        )
        if not coll:
            return err("NOT_FOUND", "Collection not found")
        rows = await pool.fetch(
            "SELECT id, text FROM knowledge.chunks WHERE collection_id=$1 AND tenant_id=$2",
            str(coll["id"]), tenant_id,
        )
        if not rows:
            return ok({"reindexed": 0})
        vecs = await embed_texts([r["text"] for r in rows], settings.embedding_model)
        for row, vec in zip(rows, vecs):
            await pool.execute(
                "UPDATE knowledge.chunks SET embedding=$1::vector WHERE id=$2 AND tenant_id=$3",
                f"[{','.join(str(v) for v in vec)}]", row["id"], tenant_id,
            )
        return ok({"reindexed": len(rows)})

    return mcp
