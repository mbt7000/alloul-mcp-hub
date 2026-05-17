# Alloul MCP Hub — Tools Catalog

**Total Tools:** 79  
**Servers:** 9  
**Date:** 2026-05-17

All tools return the standard envelope: `{"ok": true, "data": {...}}` or `{"ok": false, "error": {"code": "...", "message": "..."}}`.

All tools require `Authorization: Bearer <jwt>` header. All data-accessing tools require a `tenant_id` parameter for isolation.

---

## Server 1: alloul.identity (port 8001) — 8 tools

### identity_tenant_resolve
Resolve a tenant from an API key or subdomain slug. Used during product initialization.

**Parameters:**
- `api_key` (str, optional) — product API key
- `subdomain` (str, optional) — tenant subdomain slug

**Example:**
```json
{"name": "identity_tenant_resolve", "arguments": {"api_key": "ak_live_xxx"}}
```
**Response:** `{"tenant_id": "uuid", "product": "alloulq", "plan": "pro", "status": "active"}`

---

### identity_issue_token
Issue a JWT for a human user. Call this after verifying credentials in your product.

**Parameters:**
- `tenant_id` (str, required) — UUID of the tenant
- `subject` (str, required) — user email or ID
- `roles` (list[str], required) — list of role names
- `ttl_hours` (int, default=8) — token lifetime

**Response:** `{"token": "eyJ...", "expires_at": "2026-05-17T20:00:00Z"}`

---

### identity_issue_service_token
Issue a short-lived service-to-service token.

**Parameters:**
- `service_name` (str, required) — name of the calling service
- `tenant_id` (str, required) — tenant context
- `permissions` (list[str], required) — permissions to grant
- `ttl_minutes` (int, default=60) — token lifetime

**Response:** `{"token": "eyJ...", "expires_at": "..."}`  
**Note:** Only callable by services with `admin:service_tokens` permission.

---

### identity_verify_token
Validate a JWT and return its claims. Used by gateway-level middleware.

**Parameters:**
- `token` (str, required) — JWT to validate

**Response:** `{"valid": true, "claims": {"sub": "...", "tenant_id": "...", "roles": [...], "permissions": [...]}}`  
**Error codes:** `TOKEN_EXPIRED`, `TOKEN_INVALID`, `TOKEN_REVOKED`

---

### identity_check_permission
Check if a subject has a specific permission within a tenant.

**Parameters:**
- `tenant_id` (str, required)
- `subject` (str, required) — user ID or service name
- `permission` (str, required) — e.g., `"knowledge:write"`, `"billing:manage"`

**Response:** `{"allowed": true, "reason": "role:admin"}`

---

### identity_revoke_token
Add a token to the revocation set. Invalidates immediately across all servers.

**Parameters:**
- `jti` (str, required) — JWT ID (from token claims)
- `reason` (str, optional) — reason for revocation

**Response:** `{"revoked": true}`

---

### identity_list_permissions
List all permissions granted to a role within a tenant.

**Parameters:**
- `tenant_id` (str, required)
- `role` (str, required) — role name

**Response:** `{"role": "admin", "permissions": ["knowledge:read", "knowledge:write", ...]}`

---

### identity_rotate_secret
Rotate the JWT signing secret. All existing tokens become invalid immediately.

**Parameters:**
- `tenant_id` (str, required)
- `confirm` (bool, required) — must be `true` to execute

**Response:** `{"rotated": true, "effective_at": "..."}`  
**Note:** Requires `admin:secret_rotation` permission. Use with extreme caution.

---

## Server 2: alloul.reasoning (port 8002) — 5 tools

### reasoning_complete
Generate a text completion using the LLM fallback chain (Claude → DeepSeek → Ollama).

**Parameters:**
- `messages` (list[dict], required) — OpenAI-format message array
- `tenant_id` (str, required) — for cost attribution and budget checks
- `caller_service` (str, required) — name of calling service (for audit)
- `caller_tool` (str, required) — name of calling tool (for audit)
- `max_tokens` (int, default=2048) — maximum response tokens
- `temperature` (float, default=0.7)
- `privacy` (str, optional) — set to `"high"` to route to Ollama only

**Response:** `{"text": "...", "provider": "claude", "model": "claude-3-5-sonnet", "tokens": {"prompt": 150, "completion": 200}, "cost_usd": 0.00035, "latency_ms": 823}`

---

### reasoning_structured
Generate a structured JSON response conforming to a JSON Schema.

**Parameters:**
- `messages` (list[dict], required)
- `json_schema` (dict, required) — JSON Schema for the expected output
- `tenant_id` (str, required)
- `caller_service` (str, required)
- `caller_tool` (str, required)

**Response:** `{"parsed": {...}, "raw": "...", "provider": "claude", "valid": true}`

---

### reasoning_embed
Generate a vector embedding for text. Used by knowledge server internally.

**Parameters:**
- `text` (str, required) — text to embed (max 2048 tokens)
- `tenant_id` (str, required)

**Response:** `{"embedding": [0.023, -0.145, ...], "dimensions": 1024, "model": "multilingual-e5-large"}`

---

### reasoning_check_budget
Pre-flight budget check before an expensive LLM operation.

**Parameters:**
- `tenant_id` (str, required)
- `estimated_tokens` (int, required) — expected total token usage

**Response:** `{"allowed": true, "remaining_usd": 4.23, "period": "2026-05"}`  
**Error codes:** `BUDGET_EXCEEDED`

---

### reasoning_get_providers
List available LLM providers and their current health status.

**Parameters:** none (no tenant required)

**Response:** `{"providers": [{"name": "claude", "status": "healthy", "latency_p50_ms": 450}, ...]}`

---

## Server 3: alloul.knowledge (port 8003) — 6 tools

### knowledge_create_collection
Create a named vector collection for a tenant.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required) — `"alloulq"` or `"handex"`
- `name` (str, required) — collection name
- `description` (str, optional)

**Response:** `{"collection_id": "uuid", "name": "...", "product": "...", "created_at": "..."}`

---

### knowledge_ingest
Chunk text and insert embeddings into a collection.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `collection_name` (str, required)
- `text` (str, required) — text to chunk and embed
- `metadata` (dict, optional) — arbitrary metadata stored with each chunk
- `chunk_size` (int, default=512) — characters per chunk
- `chunk_overlap` (int, default=50)

**Response:** `{"chunks_created": 5, "collection_id": "uuid"}`

---

### knowledge_search
Semantic search across a collection. Returns top-K most relevant chunks.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `query` (str, required)
- `collection_name` (str, optional) — if omitted, searches all tenant collections
- `top_k` (int, default=5)
- `min_score` (float, default=0.7)

**Response:** `{"results": [{"text": "...", "score": 0.91, "metadata": {...}}, ...]}`  
**Note:** Results are strictly isolated to the requesting tenant.

---

### knowledge_delete_collection
Delete a collection and all its chunks. Irreversible.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `collection_name` (str, required)
- `confirm` (bool, required) — must be `true`

**Response:** `{"deleted": true, "chunks_removed": 143}`

---

### knowledge_get_collection
Get collection metadata and statistics.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `collection_name` (str, required)

**Response:** `{"id": "uuid", "name": "...", "chunk_count": 143, "created_at": "...", "description": "..."}`

---

### knowledge_list_collections
List all collections for a tenant and product.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)

**Response:** `{"collections": [{"name": "...", "chunk_count": 5, "created_at": "..."}]}`

---

## Server 4: alloul.audit (port 8004) — 3 tools

### audit_log
Write an audit event. Append-only — events cannot be modified or deleted.

**Parameters:**
- `tenant_id` (str, required)
- `actor_id` (str, required) — user or service ID
- `actor_type` (str, required) — `"human"` or `"service"`
- `action` (str, required) — e.g., `"document.uploaded"`, `"subscription.changed"`
- `resource_type` (str, required) — e.g., `"document"`, `"subscription"`
- `resource_id` (str, optional) — ID of the affected resource
- `before_state` (dict, optional) — state before the action
- `after_state` (dict, optional) — state after the action
- `metadata` (dict, optional) — additional context

**Response:** `{"logged": true, "event_id": "uuid"}`

---

### audit_query
Query the audit log with filters.

**Parameters:**
- `tenant_id` (str, required) — required unless caller has `holdings:read`
- `actor_id` (str, optional) — filter by actor
- `action` (str, optional) — filter by action name
- `resource_type` (str, optional)
- `from_date` (str, optional) — ISO 8601
- `to_date` (str, optional) — ISO 8601
- `limit` (int, default=100)

**Response:** `{"events": [{...}], "total": 47}`

---

### audit_export
Export audit log as CSV for compliance reporting.

**Parameters:**
- `tenant_id` (str, required)
- `from_date` (str, required) — ISO 8601
- `to_date` (str, required) — ISO 8601

**Response:** `{"csv": "event_id,tenant_id,actor_id,...\n...", "row_count": 1203}`

---

## Server 5: alloul.analytics (port 8005) — 6 tools

### analytics_kpis_holdings
Top-level Holdings KPIs. Requires `holdings:read` permission.

**Parameters:**
- `period_days` (int, default=30) — lookback period

**Response:** `{"period_days": 30, "tenants": [...], "active_subscriptions": [...], "llm_costs": [...]}`  
**Note:** Cached in Redis for 15 minutes.

---

### analytics_kpis_product
KPIs for a specific product.

**Parameters:**
- `product` (str, required) — `"alloulq"` or `"handex"`
- `period_days` (int, default=30)

**Response:** `{"product": "alloulq", "tenants": {...}, "subscriptions": [...], "llm": {...}, "rag": {...}}`

---

### analytics_kpis_tenant
Per-tenant KPIs including expansion signals and churn indicators.

**Parameters:**
- `tenant_id` (str, required)
- `period_days` (int, default=30)

**Response:** `{"tenant_id": "...", "total_llm_cost_usd": 12.45, "expansion_signal": true, "llm_breakdown": [...]}`

---

### analytics_weekly_executive
Generate weekly executive report as Markdown.

**Parameters:** none

**Response:** `{"markdown": "# Alloul Holdings — Weekly Executive Report\n...", "generated_at": "..."}`

---

### analytics_churn_risk
Detect tenants with declining usage — potential churn signals.

**Parameters:**
- `threshold_days_inactive` (int, default=14) — inactivity window

**Response:** `{"at_risk": [{"tenant_id": "...", "recent": 5, "historical": 42, "risk_level": "high"}], "threshold_days": 14}`

---

### analytics_expansion_signal
Detect tenants near plan limits — upsell opportunities.

**Parameters:** none

**Response:** `{"expansion_candidates": [{"tenant_id": "...", "pct_used": 85.2, "plan": "pro"}], "period": "2026-05"}`

---

## Server 6: product.workspace (port 8006) — 27 tools

*(Grouped by domain)*

**Team Management:** `workspace_create_tenant`, `workspace_get_tenant`, `workspace_update_tenant`, `workspace_list_tenants`

**Employee Lifecycle:** `workspace_invite_employee`, `workspace_accept_invite`, `workspace_deactivate_employee`, `workspace_list_employees`, `workspace_get_employee`

**Roles:** `workspace_assign_role`, `workspace_revoke_role`, `workspace_list_roles`

**Departments:** `workspace_create_department`, `workspace_list_departments`, `workspace_move_employee`

**Notifications:** `workspace_send_notification`, `workspace_list_notifications`, `workspace_mark_read`

**Sessions:** `workspace_create_session`, `workspace_end_session`, `workspace_list_sessions`

**Settings:** `workspace_get_settings`, `workspace_update_settings`

All workspace tools require `tenant_id` and return tenant-isolated data.

---

## Server 7: product.billing (port 8007) — 11 tools

### billing_list_plans
List available subscription plans for a product.

**Parameters:**
- `product` (str, required) — `"alloulq"` or `"handex"`

**Response:** `{"product": "alloulq", "plans": [{"name": "starter", "price_usd": 30, "seats": 3, "storage_gb": 5}, ...]}`

---

### billing_start_subscription
Start a new subscription for a tenant.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `plan` (str, required) — `"starter"`, `"pro"`, `"business"`, or `"enterprise"`
- `stripe_payment_method_id` (str, optional)

**Response:** `{"id": "uuid", "tenant_id": "...", "product": "alloulq", "plan": "starter", "status": "active"}`  
**Error codes:** `ALREADY_SUBSCRIBED`, `UNKNOWN_PLAN`

---

### billing_change_plan
Upgrade or downgrade subscription plan.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `new_plan` (str, required)

**Response:** `{"id": "uuid", "plan": "pro", "status": "active"}`

---

### billing_cancel_subscription
Cancel an active subscription.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `reason` (str, optional)

**Response:** `{"cancelled": true, "id": "uuid", "plan": "pro", "status": "cancelled"}`

---

### billing_get_status
Get current subscription status.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)

**Response:** `{"id": "uuid", "plan": "pro", "status": "active", "current_period_end": "2026-06-17"}`  
**Note:** Returns `{"status": "no_subscription"}` if no subscription exists.

---

### billing_list_invoices
List invoices for a tenant.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `limit` (int, default=20)

**Response:** `{"invoices": [{"id": "uuid", "amount_cents": 9000, "currency": "usd", "status": "paid"}]}`

---

### billing_get_invoice
Get details of a specific invoice.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `invoice_id` (str, required)

**Response:** Full invoice record including line items and Stripe references.

---

### billing_retry_payment
Retry a failed invoice payment via Stripe.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `invoice_id` (str, required)

**Response:** `{"invoice_id": "...", "retry_initiated": true}`  
**Error codes:** `ALREADY_PAID`, `NOT_FOUND`

---

### billing_report_usage
Report usage for metered billing (AI calls, storage bytes, etc).

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `metric` (str, required) — e.g., `"ai_calls"`, `"storage_bytes"`
- `value` (int, required) — amount to add to current period counter
- `period` (str, optional) — `"YYYY-MM"` format, defaults to current month

**Response:** `{"reported": true, "metric": "ai_calls", "added": 1, "period": "2026-05"}`

---

### billing_get_usage
Get current usage metrics for a tenant in a period.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `period` (str, optional) — defaults to current month

**Response:** `{"tenant_id": "...", "period": "2026-05", "usage": [{"metric": "ai_calls", "value": 847}]}`

---

### billing_check_quota
Check if a tenant has quota remaining before performing an action.

**Parameters:**
- `tenant_id` (str, required)
- `product` (str, required)
- `metric` (str, required)
- `requested` (int, default=1)

**Response:** `{"allowed": true, "plan": "pro", "current_usage": 847, "requested": 1}`  
**Note:** Enterprise plans always return `allowed: true`.

---

## Server 8: handex.docintel (port 8008) — 6 tools

### docintel_extract
Extract text from a PDF or DOCX file. Optionally uses OCR for scanned documents.

**Parameters:**
- `tenant_id` (str, required)
- `file_b64` (str, required) — base64-encoded file content
- `filename` (str, required) — original filename with extension
- `mime_type` (str, required) — MIME type of the file
- `use_ocr` (bool, default=false) — enable OCR fallback for scanned PDFs
- `ocr_lang` (str, default="eng+ara") — Tesseract language string

**Response:** `{"document_id": "uuid", "filename": "contract.pdf", "extracted_chars": 12450, "text_preview": "...", "status": "extracted"}`

---

### docintel_summarize
Summarize a document using alloul.reasoning. Supports Arabic and English output.

**Parameters:**
- `tenant_id` (str, required)
- `document_id` (str, required) — ID from docintel_extract
- `language` (str, default="auto") — `"ar"`, `"en"`, or `"auto"`

**Response:** `{"document_id": "...", "summary": "This contract establishes...", "doc_name": "contract.pdf"}`  
**Note:** Calls reasoning server internally; cost is attributed to the tenant.

---

### docintel_entities
Extract named entities from a document: persons, organizations, dates, IDs, and money amounts.

**Parameters:**
- `tenant_id` (str, required)
- `document_id` (str, required)

**Response:**
```json
{
  "document_id": "uuid",
  "entities": {
    "persons": ["Ahmed Al-Rashidi", "Sarah Johnson"],
    "organizations": ["Alloul Holdings", "Ministry of Finance"],
    "dates": ["2026-01-15", "2026-12-31"],
    "ids": ["CR-2024-98765"],
    "money": ["SAR 450,000", "$12,500"]
  }
}
```

---

### docintel_classify
Classify document type using AI.

**Parameters:**
- `tenant_id` (str, required)
- `document_id` (str, required)

**Response:** `{"document_id": "...", "classification": {"doc_type": "contract", "confidence": 0.94, "reasoning": "Contains signature blocks..."}}`  
**Note:** Updates the document record's `doc_type` field automatically.

---

### docintel_compare
Semantically compare two documents — identify differences and similarities.

**Parameters:**
- `tenant_id` (str, required)
- `document_id_a` (str, required)
- `document_id_b` (str, required)

**Response:** `{"document_a": "v1_contract.pdf", "document_b": "v2_contract.pdf", "comparison": "Key differences:\n1. Payment terms changed from NET30 to NET15..."}`

---

### docintel_get_document
Get document metadata and processing status.

**Parameters:**
- `tenant_id` (str, required)
- `document_id` (str, required)

**Response:** `{"id": "uuid", "name": "contract.pdf", "mime_type": "application/pdf", "size_bytes": 245120, "doc_type": "contract", "status": "extracted", "created_at": "..."}`

---

## Server 9: handex.workflow (port 8009) — 7 tools

### workflow_define
Define a workflow state machine for a tenant.

**Parameters:**
- `tenant_id` (str, required)
- `name` (str, required) — unique workflow name within tenant
- `definition` (dict, required) — state machine definition:
  - `states` (list[str]) — all possible states
  - `initial` (str) — starting state
  - `transitions` (list[dict]) — `{from, to, trigger, requires_role}`
  - `terminal_states` (list[str]) — states where workflow ends
  - `sla_hours` (dict, optional) — `{state_name: hours}` for SLA timers

**Response:** `{"id": "uuid", "name": "document_approval", "version": 1, "created_at": "..."}`  
**Note:** Calling again with the same name increments version and updates definition.

---

### workflow_start
Start a new workflow instance.

**Parameters:**
- `tenant_id` (str, required)
- `workflow_name` (str, required)
- `started_by` (str, required) — user ID
- `context` (dict, optional) — arbitrary context data stored with instance

**Response:** `{"instance_id": "uuid", "workflow": "document_approval", "current_state": "draft", "available_triggers": ["submit"]}`

---

### workflow_list_tasks_for_user
List workflow tasks assigned to a specific user.

**Parameters:**
- `tenant_id` (str, required)
- `user_id` (str, required)
- `status` (str, default="pending") — `"pending"`, `"completed"`, or `"cancelled"`

**Response:** `{"tasks": [{"id": "uuid", "title": "Complete: reviewing", "due_at": "...", "instance_id": "..."}], "count": 3}`

---

### workflow_complete_task
Advance a workflow instance by firing a trigger.

**Parameters:**
- `tenant_id` (str, required)
- `instance_id` (str, required)
- `trigger` (str, required) — trigger name (must be valid for current state)
- `completed_by` (str, required) — user ID
- `comment` (str, optional) — optional comment

**Response:** `{"instance_id": "...", "previous_state": "draft", "current_state": "submitted", "is_complete": false, "available_triggers": ["start_review"]}`  
**Error codes:** `INVALID_TRIGGER`, `NOT_FOUND`

---

### workflow_cancel
Cancel an active workflow instance.

**Parameters:**
- `tenant_id` (str, required)
- `instance_id` (str, required)
- `cancelled_by` (str, required)
- `reason` (str, optional)

**Response:** `{"cancelled": true, "instance_id": "..."}`

---

### workflow_get_instance
Get full workflow instance state including task history.

**Parameters:**
- `tenant_id` (str, required)
- `instance_id` (str, required)

**Response:**
```json
{
  "id": "uuid",
  "workflow_name": "document_approval",
  "current_state": "reviewing",
  "status": "active",
  "started_by": "user_123",
  "context": {"document_id": "doc_abc"},
  "tasks": [
    {"title": "Complete: draft", "status": "completed", "completed_at": "..."},
    {"title": "Complete: reviewing", "status": "pending", "due_at": "..."}
  ]
}
```

---

### workflow_set_escalation_rule
Configure automatic escalation if a workflow stays in a state too long.

**Parameters:**
- `tenant_id` (str, required)
- `workflow_name` (str, required)
- `state` (str, required) — state to watch
- `escalate_after_hours` (int, required)
- `escalate_to_user_id` (str, required) — user to notify
- `notification_message` (str, optional)

**Response:** `{"workflow": "document_approval", "state": "reviewing", "escalate_after_hours": 24, "escalate_to": "manager_456"}`

---

## Permission Reference

| Permission | Servers | Description |
|------------|---------|-------------|
| `llm:call` | reasoning | Make LLM API calls |
| `knowledge:read` | knowledge | Search vector collections |
| `knowledge:write` | knowledge | Ingest documents |
| `audit:write` | audit | Write audit events |
| `audit:read` | audit | Query audit log (own tenant) |
| `billing:read` | billing | View subscription and invoices |
| `billing:manage` | billing | Change plans, retry payments |
| `workspace:read` | workspace | View team and employee data |
| `workspace:manage` | workspace | Invite, deactivate, assign roles |
| `holdings:read` | analytics, audit | Cross-tenant Holdings-level access |
| `admin:service_tokens` | identity | Issue service tokens |
| `admin:secret_rotation` | identity | Rotate JWT secret |
