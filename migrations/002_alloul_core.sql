CREATE TABLE IF NOT EXISTS alloul_core.tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    product text NOT NULL CHECK (product IN ('alloulq','handex')),
    plan text NOT NULL DEFAULT 'starter',
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alloul_core.employees (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES alloul_core.tenants(id) ON DELETE CASCADE,
    product text NOT NULL,
    employee_code text UNIQUE NOT NULL,
    name text NOT NULL,
    email text NOT NULL,
    role text NOT NULL DEFAULT 'member',
    status text NOT NULL DEFAULT 'active',
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS emp_tenant_email ON alloul_core.employees(tenant_id, email);

CREATE TABLE IF NOT EXISTS alloul_core.permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    employee_id uuid NOT NULL REFERENCES alloul_core.employees(id) ON DELETE CASCADE,
    permission text NOT NULL,
    granted_by uuid,
    created_at timestamptz DEFAULT now(),
    UNIQUE(employee_id, permission)
);

CREATE TABLE IF NOT EXISTS alloul_core.api_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    product text NOT NULL,
    name text NOT NULL,
    token_hash text NOT NULL UNIQUE,
    expires_at timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alloul_core.audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid,
    product text,
    user_id uuid,
    service text NOT NULL,
    tool text NOT NULL,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text,
    payload jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_tenant_time ON alloul_core.audit_log(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_resource ON alloul_core.audit_log(resource_type, resource_id);
