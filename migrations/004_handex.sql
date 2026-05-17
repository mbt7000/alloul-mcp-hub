CREATE TABLE IF NOT EXISTS handex.documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    name text NOT NULL,
    mime_type text NOT NULL,
    size_bytes bigint,
    storage_path text NOT NULL,
    doc_type text,
    language text,
    extracted_text text,
    metadata jsonb DEFAULT '{}',
    status text NOT NULL DEFAULT 'pending',
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS docs_tenant ON handex.documents(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS handex.workflow_definitions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    name text NOT NULL,
    definition jsonb NOT NULL,
    version int NOT NULL DEFAULT 1,
    created_at timestamptz DEFAULT now(),
    UNIQUE(tenant_id, name)
);

CREATE TABLE IF NOT EXISTS handex.workflow_instances (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    definition_id uuid REFERENCES handex.workflow_definitions(id),
    current_state text NOT NULL,
    context jsonb DEFAULT '{}',
    started_by uuid,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS handex.workflow_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id uuid NOT NULL REFERENCES handex.workflow_instances(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL,
    assignee_id uuid,
    title text NOT NULL,
    description text,
    due_at timestamptz,
    completed_at timestamptz,
    status text NOT NULL DEFAULT 'pending',
    created_at timestamptz DEFAULT now()
);
