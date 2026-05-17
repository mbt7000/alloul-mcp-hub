# Alloul MCP Hub — Architecture

**Version:** 1.0  
**Date:** 2026-05-17  
**Repository:** https://github.com/mbt7000/alloul-mcp-hub

---

## 1. Overview: The Hub-and-Spoke Model

Alloul Holdings is building two distinct AI-powered SaaS products: **ALLOUL&Q** (an AI workspace platform for Arabic and English teams) and **Handex** (an AI-powered handover and document intelligence platform for enterprises). Both products require identical foundational capabilities: identity and authentication, LLM routing, vector search, audit logging, billing, and analytics.

Rather than duplicate these capabilities in each product, the Alloul MCP Hub acts as the **AI Operating System** for the entire Holdings group. Every product calls the Hub via the Model Context Protocol (MCP) — a standardized JSON-RPC-over-HTTP protocol for tool invocation. The Hub handles all infrastructure concerns; products focus purely on user experience and domain logic.

This is a **hub-and-spoke** model where:

- The **Hub** (this repo) owns: identity, reasoning, knowledge, audit, analytics, billing, and domain extensions
- The **Spokes** (product apps) own: UX, routing, product-specific business logic
- All spoke-to-hub communication happens via MCP tool calls over authenticated HTTPS

The result is a single codebase that can serve multiple products, a single place to improve LLM routing for all products simultaneously, and a unified audit trail across the entire Holdings group.

---

## 2. The Four Layers

### Layer 1: Core Services (ports 8001–8005)

Core services provide infrastructure that any product can use. They have no product-specific logic.

| Server | Port | Responsibility |
|--------|------|----------------|
| alloul.identity | 8001 | JWT issuance, tenant resolution, permission checks |
| alloul.reasoning | 8002 | LLM routing, fallback chain, budget enforcement |
| alloul.knowledge | 8003 | Vector embeddings, RAG search, collection management |
| alloul.audit | 8004 | Immutable audit log writes and queries |
| alloul.analytics | 8005 | KPI computation, churn risk, expansion signals |

Core services are the most critical — they must be highly available. In production they run with at least 2 replicas each behind Caddy.

### Layer 2: Product Services (ports 8006–8007)

Product services contain logic that is shared between ALLOUL&Q and Handex but is product-facing rather than infrastructure.

| Server | Port | Responsibility |
|--------|------|----------------|
| product.workspace | 8006 | Teams, employees, roles, invitations, notifications, sessions |
| product.billing | 8007 | Subscriptions, invoices, usage metering, quota checks |

### Layer 3: Handex Extensions (ports 8008–8009)

These servers contain domain logic specific to the Handex product. They call Core and Product services internally but are not used by ALLOUL&Q.

| Server | Port | Responsibility |
|--------|------|----------------|
| handex.docintel | 8008 | Document extraction (PDF/DOCX/OCR), summarization, entity extraction, classification |
| handex.workflow | 8009 | State machine workflows, task management, SLA timers, escalation |

### Layer 4: Adapters (in shared/)

The shared library (`shared/`) provides Python modules used by all servers:

- `shared/db.py` — asyncpg connection pool management
- `shared/envelope.py` — ok/err response envelope standard
- `shared/errors.py` — typed error codes
- `shared/auth.py` — JWT validation helpers
- `shared/tenant.py` — tenant context extraction
- `shared/audit.py` — audit log write helper
- `shared/adapter.py` — base adapter class for LLM providers
- `shared/telemetry.py` — structlog + trace ID propagation

---

## 3. Database Schema Separation

All servers share a single PostgreSQL instance but use separate schemas for hard isolation:

### `alloul_core` Schema
Contains the foundational tables used by identity, reasoning, and audit:

- `tenants` — one row per tenant (org), tagged with `product` (alloulq/handex)
- `employees` — users within tenants, with roles and permissions
- `permissions` — role-to-permission mappings
- `audit_log` — append-only audit trail for all mutations
- `llm_calls` — every LLM API call logged with cost, latency, tokens
- `llm_budgets` — per-tenant monthly spending limits with alert thresholds

### `product` Schema
Contains billing and subscription data:

- `subscriptions` — active/cancelled plans per tenant per product
- `invoices` — billing invoices with Stripe integration fields
- `usage_counters` — metered usage aggregated by metric + period

### `handex` Schema
Contains Handex-specific domain tables:

- `documents` — uploaded files with extraction status and text content
- `workflow_definitions` — JSON state machine definitions per tenant
- `workflow_instances` — running workflow instances with current state
- `workflow_tasks` — individual tasks assigned to users within instances

### `knowledge` Schema
Contains vector search data:

- `collections` — named vector collections per tenant per product
- `chunks` — text chunks with pgvector HNSW embeddings (1024-dim)

This schema separation means a database error in `handex` cannot corrupt `alloul_core` data. It also allows per-schema access controls so product.billing cannot read handex.documents.

---

## 4. The Nine Servers in Detail

### alloul.identity (8001) — 8 tools

The identity server is the **trust anchor** for the entire Hub. Every JWT in the system was issued or validated by this server.

Key responsibilities:
- `identity_tenant_resolve` — maps an API key or subdomain to a tenant record
- `identity_issue_token` — issues a signed JWT for human users after authentication
- `identity_issue_service_token` — issues short-lived machine tokens for service-to-service calls
- `identity_verify_token` — validates a JWT and returns claims (used by every other server at gateway level)
- `identity_check_permission` — checks if a user/service has a specific permission
- `identity_revoke_token` — adds a token to the revocation list
- `identity_list_permissions` — lists all permissions for a role
- `identity_rotate_secret` — rotates the JWT signing secret (admin operation)

The JWT payload includes: `sub` (user ID), `tenant_id`, `product`, `roles`, `permissions[]`, `exp`, `iat`, `jti`.

### alloul.reasoning (8002) — 5 tools

The reasoning server is the **LLM router**. No product code should ever call an LLM API directly — all LLM calls go through this server, which handles provider selection, fallback, cost tracking, and budget enforcement.

Key responsibilities:
- `reasoning_complete` — text completion via provider cascade
- `reasoning_structured` — structured JSON output with schema validation
- `reasoning_embed` — text-to-vector embedding for RAG
- `reasoning_check_budget` — pre-flight budget check before expensive operations
- `reasoning_get_providers` — list available providers and their current status

### alloul.knowledge (8003) — 6 tools

The knowledge server provides **multilingual RAG** using pgvector with HNSW indexing. Embeddings use `intfloat/multilingual-e5-large` (1024-dimensional) computed locally on the VPS — no external embedding APIs.

Key capabilities:
- `knowledge_create_collection` — create a named vector collection for a tenant
- `knowledge_ingest` — chunk text and insert embeddings
- `knowledge_search` — semantic search with tenant isolation
- `knowledge_delete_collection` — remove a collection and all its chunks
- `knowledge_get_collection` — get collection metadata and chunk count
- `knowledge_list_collections` — list all collections for a tenant

### alloul.audit (8004) — 3 tools

The audit server provides an **immutable audit trail**. Every mutation in the system that matters (login, document upload, workflow state change, plan change, permission grant) is logged here.

- `audit_log` — write an audit event (append-only)
- `audit_query` — query audit log with filters (tenant, user, action, date range)
- `audit_export` — export audit log as CSV for compliance

### alloul.analytics (8005) — 6 tools

Analytics provides **business intelligence** without requiring a separate BI tool. Queries are cached in Redis (15-minute TTL) to avoid hammering Postgres.

- `analytics_kpis_holdings` — top-level Holdings view: tenants, LLM costs, subscriptions
- `analytics_kpis_product` — per-product breakdown
- `analytics_kpis_tenant` — per-tenant view with expansion signals
- `analytics_weekly_executive` — Markdown weekly report for executive team
- `analytics_churn_risk` — detects tenants with declining usage
- `analytics_expansion_signal` — detects tenants near plan limits (upsell candidates)

### product.workspace (8006) — 27 tools

The workspace server handles all multi-tenant SaaS operations: team management, employee lifecycle, role assignment, invitations, notifications, and session management. It is consumed by both ALLOUL&Q and Handex.

### product.billing (8007) — 11 tools

The billing server manages subscriptions and usage metering. It is Stripe-ready but can operate without Stripe for internal/manual billing.

Plans for ALLOUL&Q: Starter ($30/mo, 3 seats), Pro ($90/mo, 10 seats), Business ($210/mo, 30 seats), Enterprise (custom).
Plans for Handex: Enterprise only (custom pricing).

### handex.docintel (8008) — 6 tools

Document intelligence for the Handex product. Handles PDF and DOCX extraction using PyMuPDF, Arabic+English OCR via Tesseract, and AI-powered analysis via the reasoning server.

Key design: docintel never calls LLMs directly. It delegates all AI work to `alloul.reasoning` via HTTP, which means LLM costs flow through the budget system and get logged in `alloul_core.llm_calls`.

### handex.workflow (8009) — 7 tools

A flexible state machine engine for enterprise workflows. Tenants can define any workflow they need — approval chains, document reviews, employee onboarding — by providing a JSON state machine definition. The engine handles state transitions, SLA timers, task assignment, and escalation rules.

---

## 5. LLM Fallback Chain

The reasoning server implements a cascading fallback strategy:

```
Primary: Anthropic Claude (claude-3-5-sonnet)
     |
     v (on rate limit or error)
Fallback 1: DeepSeek API (deepseek-chat)
     |
     v (on rate limit or error, or privacy=high)
Fallback 2: Ollama (local VPS, llama3.1 / qwen2.5)
```

**Privacy routing:** If a caller passes `privacy="high"`, the reasoning server skips external providers entirely and routes directly to Ollama. This is used for documents containing personally identifiable information (PII) or confidential enterprise data.

**Cost tracking:** Every call to any provider is logged to `alloul_core.llm_calls` with: provider, model, prompt_tokens, completion_tokens, cached_tokens, cost_usd_micros, latency_ms, tenant_id, caller_service, caller_tool.

**Budget enforcement:** Before routing an LLM call, the reasoning server checks `alloul_core.llm_budgets` for the tenant's current month. If `current_usd_micros >= limit_usd_micros`, the call is rejected with `BUDGET_EXCEEDED`. At 80% of limit, an alert is written to the audit log.

---

## 6. Tenant Isolation Model

Tenant isolation is enforced at **three levels**:

### Level 1: JWT Claims
Every request must carry a JWT with `tenant_id` in the claims. The gateway (Caddy or the MCP server itself) validates the JWT and rejects requests with missing or invalid tokens.

### Level 2: SQL-Level Isolation
Every SQL query that accesses tenant data includes a `WHERE tenant_id=$N` clause. There are no queries that return cross-tenant data except in the analytics server (which requires `holdings:read` permission — a special Holdings-level role).

### Level 3: Schema Separation
The `handex` schema is only accessible to servers running as the `handex_service` DB role. The `alloulq` product cannot accidentally access Handex documents even if a query bug omits `tenant_id`.

---

## 7. Unified JWT Authentication

A single JWT token is valid across all 9 MCP servers. This is achieved by having all servers share the same JWT signing secret (from environment variable `JWT_SECRET`), and all servers validate tokens using the same logic from `shared/auth.py`.

**Token lifecycle:**
1. Product app authenticates user (email/password or SSO)
2. Product app calls `identity_issue_token` with user credentials
3. Hub returns a signed JWT (default 8-hour TTL)
4. Product app stores JWT in session; sends it as `Authorization: Bearer <token>` on every MCP call
5. Any Hub server validates the JWT locally (no round-trip to identity server for each call)
6. Token revocation: compromised tokens are added to a Redis-backed revocation set; all servers check this set

---

## 8. Service-to-Service Calls

When `handex.docintel` needs to call `alloul.reasoning` to summarize a document, it cannot use a user JWT (those are personal tokens). Instead it uses the service token pattern:

```python
# docintel calls reasoning internally:
async with httpx.AsyncClient() as client:
    resp = await client.post(
        f"{settings.reasoning_mcp_url}/call-tool",
        json={
            "name": "reasoning_complete",
            "arguments": {
                "messages": [...],
                "tenant_id": tenant_id,
                "caller_service": "handex.docintel",
                "caller_tool": "docintel.summarize",
            }
        }
    )
```

Service tokens are short-lived (1-hour TTL), have a fixed set of permissions scoped to what the service needs, and include `caller_service` in their claims for audit attribution.

The reasoning server does not validate that `caller_service` matches the token subject — that would create circular dependencies. Instead, the `caller_service` field is used only for cost attribution in `llm_calls`.

---

## 9. Audit Everything

The audit server implements an append-only log for compliance and security. The rule is: **every mutation that affects money, access, or data must be logged**.

Events that are always logged:
- User login / logout
- JWT issuance and revocation
- Tenant creation, plan changes, subscription cancellation
- Employee invitation, role changes, deactivation
- Document upload and classification
- Workflow state transitions
- Permission grants and revocations
- Budget threshold alerts

The audit log is written by the `shared/audit.py` helper, which is called explicitly in each server's mutation tools. The log includes: `tenant_id`, `actor_id`, `actor_type` (human/service), `action`, `resource_type`, `resource_id`, `before_state`, `after_state`, `ip_address`, `trace_id`, `created_at`.

The `audit_log` tool in `alloul.audit` is also callable by products to log product-specific events (e.g., "user viewed document X", "AI summary was generated for handover Y").

---

## 10. Deployment Topology

### VPS Layout
The entire Hub runs on a single DigitalOcean or Hetzner VPS (8 vCPU, 16GB RAM recommended). Each MCP server runs as a Docker container. Caddy acts as the TLS-terminating reverse proxy.

### Docker Compose
All 9 servers plus PostgreSQL, Redis, Ollama, and Caddy are defined in `docker-compose.yml`. Services communicate over the `hub_net` Docker network.

### Subdomains
Each server gets its own subdomain:

| Subdomain | Container | Port |
|-----------|-----------|------|
| identity.alloul.com | alloul-identity | 8001 |
| reasoning.alloul.com | alloul-reasoning | 8002 |
| knowledge.alloul.com | alloul-knowledge | 8003 |
| audit.alloul.com | alloul-audit | 8004 |
| analytics.alloul.com | alloul-analytics | 8005 |
| workspace.alloul.com | product-workspace | 8006 |
| billing.alloul.com | product-billing | 8007 |
| docintel.handex.alloul.com | handex-docintel | 8008 |
| workflow.handex.alloul.com | handex-workflow | 8009 |

### Caddy Configuration
Caddy handles automatic TLS certificates (Let's Encrypt), HTTPS-to-HTTP proxying to containers, and rate limiting. The `Caddyfile` in the repo root defines all 9 reverse proxy entries.

### Ollama (Local LLM)
Ollama runs on the VPS CPU/GPU and serves as the final fallback in the LLM chain and as the exclusive provider for `privacy=high` requests. Models preloaded: `llama3.1:8b`, `qwen2.5:7b` (for Arabic). The `multilingual-e5-large` model is served separately for embeddings.

---

## 11. How ALLOUL&Q Consumes the Hub

ALLOUL&Q is a Next.js / React Native application. Its backend (a Node.js or Python API server) communicates with the Hub using MCP tool calls over HTTPS.

Typical request flow for an ALLOUL&Q user action:

1. User submits a question in the AI workspace
2. ALLOUL&Q backend validates the user's session JWT
3. Backend calls `reasoning_check_budget` — confirms the tenant has budget
4. Backend calls `knowledge_search` — retrieves relevant context from the team's knowledge base
5. Backend calls `reasoning_complete` — sends context + question to the LLM
6. LLM response returned to user
7. Hub automatically logs the LLM call cost to `llm_calls` and updates `llm_budgets`
8. Hub automatically writes an audit event for the AI interaction

ALLOUL&Q never talks directly to Anthropic, DeepSeek, or Ollama APIs. All AI costs flow through the Hub's budget system.

---

## 12. How Handex Consumes the Hub

Handex is an enterprise web application for employee handovers and document management. It uses more Hub servers than ALLOUL&Q because it has domain-specific needs.

Typical request flow for a Handex document upload:

1. Handex user uploads a PDF contract
2. Handex backend calls `docintel_extract` — PDF text is extracted and stored
3. Handex backend calls `docintel_classify` — document type identified (contract)
4. Handex backend calls `knowledge_ingest` — document chunked and embedded into tenant's knowledge collection
5. User requests a summary
6. Handex backend calls `docintel_summarize` — which internally calls `reasoning_complete` via service-to-service HTTP
7. All costs attributed to the tenant via `caller_service: handex.docintel`

Typical flow for a workflow:

1. HR admin calls `workflow_define` to create an "employee_onboarding" state machine
2. New employee triggers `workflow_start` — creates an active instance in `draft` state
3. HR system calls `workflow_complete_task` with trigger `submit` — advances to `submitted`
4. Manager receives task notification; calls `workflow_complete_task` with `approve`
5. Workflow reaches terminal state `approved` and is marked complete

---

## 13. Quality Standards

- **79 tools total** across 9 servers — no stubs, all tools have working implementations
- **Shared library** in `shared/` — db, envelope, errors, auth, tenant, audit, adapter, telemetry
- **6 migrations** covering 4 schemas — idempotent, run in order
- **All servers have tests** — at minimum server creation test + domain logic tests
- **All servers have Dockerfiles** — python:3.11-slim base with uv for dependency management
- **mypy strict compatible** — type annotations throughout
- **ruff clean** — no linting errors
- **structlog** — structured JSON logging with trace_id propagation across service calls
