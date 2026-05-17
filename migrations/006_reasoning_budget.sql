CREATE TABLE IF NOT EXISTS alloul_core.llm_calls (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid,
    caller_service text,
    caller_tool text,
    provider text NOT NULL,
    model text NOT NULL,
    prompt_tokens int,
    completion_tokens int,
    cached_tokens int DEFAULT 0,
    cost_usd_micros bigint,
    latency_ms int,
    status text NOT NULL DEFAULT 'success',
    fallback_from text,
    error_code text,
    request_hash text,
    trace_id text,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS llm_calls_tenant_time ON alloul_core.llm_calls(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS llm_calls_service ON alloul_core.llm_calls(caller_service, created_at DESC);

CREATE TABLE IF NOT EXISTS alloul_core.llm_budgets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    period text NOT NULL,
    limit_usd_micros bigint NOT NULL,
    current_usd_micros bigint DEFAULT 0,
    alert_threshold_pct smallint DEFAULT 80,
    UNIQUE(tenant_id, period)
);
