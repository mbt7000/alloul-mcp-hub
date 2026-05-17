CREATE TABLE IF NOT EXISTS knowledge.collections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    product text NOT NULL,
    name text NOT NULL,
    source_type text,
    embedding_model text NOT NULL DEFAULT 'intfloat/multilingual-e5-large',
    dim int NOT NULL DEFAULT 1024,
    created_at timestamptz DEFAULT now(),
    UNIQUE(tenant_id, product, name)
);

CREATE TABLE IF NOT EXISTS knowledge.chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id uuid REFERENCES knowledge.collections(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL,
    product text NOT NULL,
    source_ref jsonb NOT NULL,
    text text NOT NULL,
    embedding vector(1024),
    metadata jsonb DEFAULT '{}',
    token_count int,
    source_hash text,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chunks_hnsw ON knowledge.chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX IF NOT EXISTS chunks_collection ON knowledge.chunks(collection_id);
CREATE UNIQUE INDEX IF NOT EXISTS chunks_dedup ON knowledge.chunks(collection_id, source_hash)
    WHERE source_hash IS NOT NULL;
