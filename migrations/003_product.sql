CREATE TABLE IF NOT EXISTS product.usage_counters (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    product text NOT NULL,
    metric text NOT NULL,
    period text NOT NULL,
    value bigint DEFAULT 0,
    updated_at timestamptz DEFAULT now(),
    UNIQUE(tenant_id, product, metric, period)
);

CREATE TABLE IF NOT EXISTS product.subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    product text NOT NULL,
    plan text NOT NULL,
    stripe_subscription_id text UNIQUE,
    stripe_customer_id text,
    status text NOT NULL DEFAULT 'active',
    current_period_start timestamptz,
    current_period_end timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS product.invoices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    product text NOT NULL,
    stripe_invoice_id text UNIQUE,
    amount_cents int NOT NULL,
    currency text NOT NULL DEFAULT 'usd',
    status text NOT NULL,
    due_date timestamptz,
    paid_at timestamptz,
    created_at timestamptz DEFAULT now()
);
