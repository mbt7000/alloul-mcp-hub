# Alloul MCP Hub — COMPLETE

**Repository:** https://github.com/mbt7000/alloul-mcp-hub  
**Build Date:** 2026-05-17  
**Total Servers:** 9  
**Total Tools:** 79

## Servers

| Server | Port | Tools | Layer |
|--------|------|-------|-------|
| alloul.identity | 8001 | 8 | Core |
| alloul.reasoning | 8002 | 5 | Core |
| alloul.knowledge | 8003 | 6 | Core |
| alloul.audit | 8004 | 3 | Core |
| alloul.analytics | 8005 | 6 | Core |
| product.workspace | 8006 | 27 | Product |
| product.billing | 8007 | 11 | Product |
| handex.docintel | 8008 | 6 | Handex |
| handex.workflow | 8009 | 7 | Handex |

## Database Schemas
- `alloul_core` — tenants, employees, permissions, audit_log, llm_calls, llm_budgets
- `product` — subscriptions, invoices, usage_counters
- `handex` — documents, workflow_definitions, workflow_instances, workflow_tasks
- `knowledge` — collections, chunks (pgvector HNSW)

## Staging Subdomains
| Subdomain | Server |
|-----------|--------|
| identity.alloul.com | alloul.identity:8001 |
| reasoning.alloul.com | alloul.reasoning:8002 |
| knowledge.alloul.com | alloul.knowledge:8003 |
| audit.alloul.com | alloul.audit:8004 |
| analytics.alloul.com | alloul.analytics:8005 |
| workspace.alloul.com | product.workspace:8006 |
| billing.alloul.com | product.billing:8007 |
| docintel.handex.alloul.com | handex.docintel:8008 |
| workflow.handex.alloul.com | handex.workflow:8009 |

## Architecture Highlights
- **Hub-and-Spoke**: 9 MCP servers as AI OS for Alloul Holdings
- **Unified JWT**: one token resolves identity across all servers
- **LLM Fallback**: Claude -> DeepSeek -> Ollama (privacy=high -> Ollama only)
- **Multilingual RAG**: intfloat/multilingual-e5-large (Arabic + English)
- **Audit Everything**: every mutation auto-logged to alloul_core.audit_log
- **Tenant Isolation**: every query enforces tenant_id + product at SQL level
- **Zero External Embeddings**: all embeddings computed locally on VPS

## Quality
- 79 tools implemented (no stubs)
- Shared library: db, envelope, errors, auth, tenant, audit, adapter, telemetry
- 6 migrations covering 4 schemas
- All servers have tests + Dockerfiles
- CI matrix tests all 9 servers
- mypy strict compatible
- ruff clean

## Deploy Command
```bash
docker compose up -d --build
```
