# Alloul MCP Hub

A Python monorepo of 9 MCP (Model Context Protocol) servers powering the Alloul platform — serving both **ALLOUL&Q** and **Handex** products with a shared infrastructure layer.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Caddy (TLS Reverse Proxy)                │
└──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┘
       │      │      │      │      │      │      │      │
   :8001  :8002  :8003  :8004  :8005  :8006  :8007  :8008  :8009
       │      │      │      │      │      │      │      │      │
  identity reasoning knowledge audit analytics workspace billing docintel workflow
       │      │      │      │      │      │      │      │      │
       └──────┴──────┴──────┴──────┴──────┴──────┘      └──────┘
                    core/  (shared infra)              handex/
                                │
                    ┌───────────┴───────────┐
                    │                       │
               PostgreSQL 16           Redis 7
              (pgvector ext.)         (cache/pub-sub)
                    │
               Ollama (local LLM)
```

## Servers

| Server | Package | Port | Domain | Description |
|--------|---------|------|--------|-------------|
| identity | `alloul-identity` | 8001 | identity.alloul.com | JWT auth, employees, permissions |
| reasoning | `alloul-reasoning` | 8002 | reasoning.alloul.com | LLM routing: Claude → DeepSeek → Ollama |
| knowledge | `alloul-knowledge` | 8003 | knowledge.alloul.com | Vector RAG with pgvector + E5-large |
| audit | `alloul-audit` | 8004 | audit.alloul.com | Immutable audit log, CSV/JSON export |
| analytics | `alloul-analytics` | 8005 | analytics.alloul.com | Usage metrics and dashboards |
| workspace | `alloul-workspace` | 8006 | workspace.alloul.com | CRM, tasks, meetings, handovers (27 tools) |
| billing | `alloul-billing` | 8007 | billing.alloul.com | Stripe subscriptions and invoices |
| docintel | `alloul-docintel` | 8008 | docintel.handex.alloul.com | Document intelligence for Handex |
| workflow | `alloul-workflow` | 8009 | workflow.handex.alloul.com | Handex workflow state machine |

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/mbt7000/alloul-mcp-hub
cd alloul-mcp-hub
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start infrastructure

```bash
docker compose up postgres redis ollama -d
```

### 3. Run migrations

```bash
for f in migrations/*.sql; do
  psql postgresql://alloul:localdev@localhost:5432/alloul_hub -f "$f"
done
```

### 4. Start all servers

```bash
docker compose up -d --build
```

### 5. Pull Ollama models (optional, for local LLM)

```bash
docker exec alloul-mcp-hub-ollama-1 ollama pull qwen2.5-coder:32b
docker exec alloul-mcp-hub-ollama-1 ollama pull llama3.3:70b
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Claude API key | Yes (for reasoning) |
| `DEEPSEEK_API_KEY` | DeepSeek API key | No (fallback) |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `JWT_SECRET_KEY` | Secret for JWT signing | Yes |
| `SUPABASE_URL` | Supabase project URL | Optional |
| `SUPABASE_ANON_KEY` | Supabase anon key | Optional |
| `ALLOULQ_BACKEND_URL` | ALLOUL&Q backend URL | For workspace |
| `HANDEX_BACKEND_URL` | Handex backend URL | For workspace |
| `STRIPE_SECRET_KEY` | Stripe secret key | For billing |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret | For billing |
| `OLLAMA_BASE_URL` | Ollama server URL | No (local LLM) |

## Development

Each server is an independent Python package with its own `pyproject.toml`.

```bash
# Install dev dependencies for a server
cd core/identity
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/

# Type check
uv run mypy src/
```

## Shared Library (`shared/`)

All servers import from the `shared/` module:

- `shared.db` — asyncpg connection pool
- `shared.auth` — JWT issue/verify helpers
- `shared.envelope` — `ok()` / `err()` response wrappers
- `shared.adapter` — `HTTPBackendAdapter` for calling product backends
- `shared.tenant` — `TenantContext` dataclass with permission checks
- `shared.audit_log` — direct audit log writer
- `shared.errors` — typed MCP error classes
- `shared.telemetry` — structlog configuration

## Tenant Isolation

Every tool that reads data takes `tenant_id` + `product` as required parameters. All SQL queries include `WHERE tenant_id=$1 AND product=$2`. Cross-tenant queries are architecturally impossible.

## LLM Routing (reasoning server)

```
privacy=high  →  Ollama only (never leaves server)
privacy=normal:
  budget >= 10%  →  Claude → DeepSeek → Ollama (fallback chain)
  budget < 10%   →  DeepSeek → Ollama
```

## CI/CD

GitHub Actions runs on every push:
- Matrix tests across all 9 servers
- ruff lint + mypy type check + pytest with 80% coverage requirement
- Deploy to VPS on merge to `main` via SSH + `docker compose up -d --build`
