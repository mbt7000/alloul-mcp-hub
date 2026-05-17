# Alloul MCP Hub — Product Integration Guide

**Version:** 1.0  
**Audience:** Engineers building ALLOUL&Q or Handex product features  
**Date:** 2026-05-17

---

## 1. What Is the Hub?

The Alloul MCP Hub is a collection of 9 backend microservices that handle all infrastructure concerns for Alloul Holdings products. When building a feature in ALLOUL&Q or Handex, you do not call Anthropic, DeepSeek, Stripe, or PostgreSQL directly. Instead, you call the appropriate Hub server using the MCP tool-call protocol.

This guide explains:
- How to authenticate against the Hub
- Which servers your product can access
- How to make tool calls
- How to handle responses
- Code examples for common patterns

---

## 2. Prerequisites

Before making any Hub calls, your product backend needs:

1. A **tenant record** in the Hub (created during onboarding via `workspace_create_tenant`)
2. A **service account** with an API key (provided by the Hub admin)
3. The **Hub base URLs** for each server you need (from your `.env` file)
4. The **JWT secret** is NOT shared with products — products use API keys, never raw secrets

---

## 3. Authentication Flow

### 3.1 Obtaining a JWT (Human Users)

When an end-user logs into your product, your product backend must authenticate them against the Hub's identity server and obtain a JWT:

```python
import httpx

async def authenticate_user(email: str, password_hash: str, tenant_id: str) -> str:
    """Returns a JWT token for the authenticated user."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://identity.alloul.com/call-tool",
            headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
            json={
                "name": "identity_issue_token",
                "arguments": {
                    "tenant_id": tenant_id,
                    "subject": email,
                    "roles": ["member"],
                    "ttl_hours": 8,
                }
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return data["token"]
```

The returned token contains: `sub`, `tenant_id`, `product`, `roles`, `permissions`, `exp`, `jti`.

Store this token in your product's session store (Redis, cookies, etc.). Send it on every subsequent Hub call.

### 3.2 Service Tokens (Server-to-Server)

Your product backend needs a **service token** to make Hub calls on behalf of its own processes (not a specific user). Service tokens are issued by calling `identity_issue_service_token` with your API key:

```python
async def get_service_token(api_key: str, tenant_id: str) -> str:
    """Obtain a short-lived service token using your product's API key."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://identity.alloul.com/call-tool",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "name": "identity_issue_service_token",
                "arguments": {
                    "service_name": "alloulq-backend",
                    "tenant_id": tenant_id,
                    "permissions": ["llm:call", "knowledge:read", "knowledge:write"],
                    "ttl_minutes": 60,
                }
            }
        )
        resp.raise_for_status()
        return resp.json()["token"]
```

Cache service tokens until 5 minutes before expiry. Do not request a new token for every API call.

### 3.3 Refreshing Tokens

JWTs are not refreshed in the traditional sense. When a token is within 30 minutes of expiry, your product should request a new one using the same credentials. There is no refresh token endpoint — the Hub uses short-lived tokens by design.

---

## 4. Making a Tool Call

All Hub servers accept tool calls at `POST /call-tool` with this JSON body:

```json
{
  "name": "tool_name",
  "arguments": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

Required headers:
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
X-Product: alloulq    (or: handex)
X-Trace-ID: <uuid>   (optional but recommended for debugging)
```

### Python Example (Generic)

```python
import httpx
import uuid

async def hub_call(
    server_url: str,
    tool_name: str,
    arguments: dict,
    token: str,
    product: str = "alloulq",
) -> dict:
    """Make a Hub tool call and return the parsed response."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{server_url}/call-tool",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Product": product,
                "X-Trace-ID": str(uuid.uuid4()),
            },
            json={"name": tool_name, "arguments": arguments},
        )
        resp.raise_for_status()
        return resp.json()
```

### JavaScript/TypeScript Example

```typescript
async function hubCall(
  serverUrl: string,
  toolName: string,
  args: Record<string, unknown>,
  token: string,
): Promise<unknown> {
  const response = await fetch(`${serverUrl}/call-tool`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Product": "alloulq",
    },
    body: JSON.stringify({ name: toolName, arguments: args }),
  });
  if (!response.ok) {
    throw new Error(`Hub call failed: ${response.status}`);
  }
  return response.json();
}
```

---

## 5. Response Envelope

All Hub tools return a consistent envelope:

### Success Response
```json
{
  "ok": true,
  "data": {
    "field1": "value1",
    "field2": "value2"
  }
}
```

### Error Response
```json
{
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Document abc123 not found"
  }
}
```

Always check `response["ok"]` before accessing `response["data"]`. Never assume success.

```python
result = await hub_call(REASONING_URL, "reasoning_complete", {...}, token)
if not result["ok"]:
    error_code = result["error"]["code"]
    error_msg = result["error"]["message"]
    # Handle specific error codes
    if error_code == "BUDGET_EXCEEDED":
        raise BudgetExceededException(error_msg)
    raise HubException(error_code, error_msg)
data = result["data"]
```

### Common Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| `UNAUTHORIZED` | Invalid or expired JWT | Re-authenticate |
| `FORBIDDEN` | Missing permission | Check tenant role |
| `NOT_FOUND` | Resource not found | Check IDs |
| `BUDGET_EXCEEDED` | Monthly LLM budget hit | Notify user |
| `ALREADY_SUBSCRIBED` | Duplicate subscription | Show current plan |
| `UNKNOWN_PLAN` | Invalid plan name | Check plans catalog |
| `INVALID_TRIGGER` | Bad workflow trigger | Check available triggers |
| `RATE_LIMITED` | Too many requests | Retry with backoff |

---

## 6. Server Access Matrix

Not all servers are available to all products. This matrix shows what each product can call:

| Server | ALLOUL&Q | Handex | Notes |
|--------|----------|--------|-------|
| alloul.identity | Yes | Yes | All products need identity |
| alloul.reasoning | Yes | Yes | Via service token |
| alloul.knowledge | Yes | Yes | Tenant-isolated collections |
| alloul.audit | Yes (write) | Yes (write) | Both can log events; query requires holdings:read |
| alloul.analytics | Read-only (own tenant) | Read-only (own tenant) | Holdings view requires special role |
| product.workspace | Yes | Yes | Shared team management |
| product.billing | Yes | Yes | Separate plan catalogs |
| handex.docintel | No | Yes | Handex-exclusive |
| handex.workflow | No | Yes | Handex-exclusive |

---

## 7. Common Integration Patterns

### 7.1 AI Question Answering (ALLOUL&Q)

```python
async def answer_question(
    tenant_id: str,
    user_id: str,
    question: str,
    token: str,
) -> str:
    # Step 1: Check budget
    budget_check = await hub_call(
        REASONING_URL,
        "reasoning_check_budget",
        {"tenant_id": tenant_id, "estimated_tokens": 2000},
        token,
    )
    if not budget_check["ok"] or not budget_check["data"]["allowed"]:
        raise BudgetExceededException("Monthly AI budget exceeded")

    # Step 2: Search knowledge base for context
    search_result = await hub_call(
        KNOWLEDGE_URL,
        "knowledge_search",
        {
            "tenant_id": tenant_id,
            "product": "alloulq",
            "query": question,
            "top_k": 5,
        },
        token,
    )
    context_chunks = search_result["data"]["results"] if search_result["ok"] else []
    context = "\n\n".join(c["text"] for c in context_chunks)

    # Step 3: Call reasoning
    messages = []
    if context:
        messages.append({"role": "system", "content": f"Use this context:\n{context}"})
    messages.append({"role": "user", "content": question})

    result = await hub_call(
        REASONING_URL,
        "reasoning_complete",
        {
            "messages": messages,
            "tenant_id": tenant_id,
            "caller_service": "alloulq-backend",
            "caller_tool": "answer_question",
        },
        token,
    )
    if not result["ok"]:
        raise HubException(result["error"]["code"], result["error"]["message"])
    return result["data"]["text"]
```

### 7.2 Document Processing (Handex)

```python
import base64

async def process_document(
    tenant_id: str,
    file_bytes: bytes,
    filename: str,
    token: str,
) -> dict:
    file_b64 = base64.b64encode(file_bytes).decode()

    # Step 1: Extract text
    extract = await hub_call(
        DOCINTEL_URL,
        "docintel_extract",
        {
            "tenant_id": tenant_id,
            "file_b64": file_b64,
            "filename": filename,
            "mime_type": "application/pdf",
            "use_ocr": True,
        },
        token,
        product="handex",
    )
    if not extract["ok"]:
        raise Exception(f"Extraction failed: {extract['error']['message']}")

    doc_id = extract["data"]["document_id"]

    # Step 2: Classify the document
    classify = await hub_call(
        DOCINTEL_URL,
        "docintel_classify",
        {"tenant_id": tenant_id, "document_id": doc_id},
        token,
        product="handex",
    )

    # Step 3: Ingest into knowledge base
    await hub_call(
        KNOWLEDGE_URL,
        "knowledge_ingest",
        {
            "tenant_id": tenant_id,
            "product": "handex",
            "collection_name": "documents",
            "text": extract["data"]["text_preview"],
            "metadata": {"document_id": doc_id, "filename": filename},
        },
        token,
        product="handex",
    )

    return {
        "document_id": doc_id,
        "classification": classify["data"].get("classification", {}),
    }
```

### 7.3 Subscription Management

```python
async def start_trial(tenant_id: str, token: str) -> dict:
    result = await hub_call(
        BILLING_URL,
        "billing_start_subscription",
        {
            "tenant_id": tenant_id,
            "product": "alloulq",
            "plan": "starter",
        },
        token,
    )
    if not result["ok"]:
        code = result["error"]["code"]
        if code == "ALREADY_SUBSCRIBED":
            # Get current status instead
            return await hub_call(
                BILLING_URL,
                "billing_get_status",
                {"tenant_id": tenant_id, "product": "alloulq"},
                token,
            )
        raise HubException(code, result["error"]["message"])
    return result["data"]
```

### 7.4 Workflow Integration (Handex)

```python
async def create_approval_workflow(tenant_id: str, token: str) -> str:
    """Define and start a document approval workflow."""
    # Define the workflow (once per tenant)
    await hub_call(
        WORKFLOW_URL,
        "workflow_define",
        {
            "tenant_id": tenant_id,
            "name": "document_approval",
            "definition": {
                "states": ["draft", "submitted", "reviewing", "approved", "rejected"],
                "initial": "draft",
                "transitions": [
                    {"from": "draft", "to": "submitted", "trigger": "submit", "requires_role": "employee"},
                    {"from": "submitted", "to": "reviewing", "trigger": "start_review", "requires_role": "reviewer"},
                    {"from": "reviewing", "to": "approved", "trigger": "approve", "requires_role": "reviewer"},
                    {"from": "reviewing", "to": "rejected", "trigger": "reject", "requires_role": "reviewer"},
                ],
                "terminal_states": ["approved", "rejected"],
                "sla_hours": {"submitted": 48, "reviewing": 24},
            },
        },
        token,
        product="handex",
    )

    # Start an instance
    start = await hub_call(
        WORKFLOW_URL,
        "workflow_start",
        {
            "tenant_id": tenant_id,
            "workflow_name": "document_approval",
            "started_by": "user_123",
            "context": {"document_id": "doc_abc", "requester": "Ahmed"},
        },
        token,
        product="handex",
    )
    return start["data"]["instance_id"]
```

---

## 8. Tenant Isolation Guarantees

Every Hub tool that accesses data requires a `tenant_id` parameter. The Hub guarantees:

1. A tenant can only read/write its own data — SQL queries always include `WHERE tenant_id=$N`
2. A valid JWT is required — unauthenticated calls return HTTP 401
3. The JWT's `tenant_id` claim is checked against the `tenant_id` in the request arguments — mismatches are rejected
4. Schema-level separation prevents accidental cross-product data access

You do not need to implement any additional isolation in your product code. Trust the Hub's tenant isolation.

---

## 9. Logging and Tracing

Pass a `X-Trace-ID` header with a UUID on every Hub call. The Hub will:
- Include this trace ID in all structured log lines for that request
- Propagate the trace ID when the server makes internal calls (e.g., docintel calling reasoning)
- Include the trace ID in audit log entries

This allows you to trace a single user action across multiple Hub servers using your log aggregation tool (Loki, Datadog, etc.).

```python
import uuid

trace_id = str(uuid.uuid4())
# Pass trace_id as X-Trace-ID header on all Hub calls for this user request
```

---

## 10. Environment Variables

Your product backend needs these environment variables to talk to the Hub:

```bash
# Hub Server URLs
HUB_IDENTITY_URL=https://identity.alloul.com
HUB_REASONING_URL=https://reasoning.alloul.com
HUB_KNOWLEDGE_URL=https://knowledge.alloul.com
HUB_AUDIT_URL=https://audit.alloul.com
HUB_ANALYTICS_URL=https://analytics.alloul.com
HUB_WORKSPACE_URL=https://workspace.alloul.com
HUB_BILLING_URL=https://billing.alloul.com

# Handex only:
HUB_DOCINTEL_URL=https://docintel.handex.alloul.com
HUB_WORKFLOW_URL=https://workflow.handex.alloul.com

# Authentication
HUB_SERVICE_API_KEY=<your-product-api-key>
HUB_PRODUCT=alloulq  # or: handex
```

Never hardcode URLs or API keys. Always use environment variables.

---

## 11. Rate Limits and Backoff

The Hub applies rate limits per tenant per server. Default limits:

- Identity: 100 requests/minute
- Reasoning: 60 requests/minute (LLM calls are expensive)
- Knowledge: 200 requests/minute
- Billing: 30 requests/minute
- Workspace: 300 requests/minute

When rate-limited, the Hub returns HTTP 429 with `error.code = "RATE_LIMITED"`. Implement exponential backoff:

```python
import asyncio
import random

async def hub_call_with_retry(
    server_url: str, tool_name: str, arguments: dict, token: str, max_retries: int = 3
) -> dict:
    for attempt in range(max_retries):
        result = await hub_call(server_url, tool_name, arguments, token)
        if result.get("ok"):
            return result
        if result.get("error", {}).get("code") == "RATE_LIMITED":
            wait = (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(wait)
            continue
        return result  # Non-retriable error
    raise HubException("RATE_LIMITED", "Max retries exceeded")
```
