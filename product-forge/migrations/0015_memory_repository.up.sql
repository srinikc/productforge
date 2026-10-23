-- EDP-21 / BI-PF-1313: memory repository substrate (metadata + FTS + optional pgvector).
-- Additive by design: content/source/owner and embeddings are DATA; the down migration never drops them.
SET LOCAL lock_timeout = '5s';

ALTER TABLE memory ADD COLUMN IF NOT EXISTS content TEXT NOT NULL DEFAULT '';
ALTER TABLE memory ADD COLUMN IF NOT EXISTS source  TEXT NOT NULL DEFAULT '';
ALTER TABLE memory ADD COLUMN IF NOT EXISTS owner   TEXT NOT NULL DEFAULT '';

ALTER TABLE memory ADD COLUMN IF NOT EXISTS tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_memory_tsv ON memory USING GIN (tsv);
CREATE INDEX IF NOT EXISTS idx_memory_acl ON memory (tenant_id, project_id, kind, acl_scope);
CREATE INDEX IF NOT EXISTS idx_memory_source ON memory (tenant_id, source);
CREATE INDEX IF NOT EXISTS idx_memory_owner ON memory (tenant_id, owner);

-- Fail closed for NEW rows without blocking legacy data.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'memory_kind_valid') THEN
        ALTER TABLE memory ADD CONSTRAINT memory_kind_valid CHECK (
            kind IN ('raw_evidence','semantic','episodic','decision','procedural','failure','policy','working')) NOT VALID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'memory_acl_valid') THEN
        ALTER TABLE memory ADD CONSTRAINT memory_acl_valid CHECK (
            acl_scope IN ('', 'private', 'project', 'tenant', 'shared')) NOT VALID;
    END IF;
END $$;

-- Optional vector support: the extension may be unavailable on a stock PostgreSQL; the repository then
-- serves FTS-only (no migration failure, no schema divergence in the required columns).
DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS vector;
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        EXECUTE 'ALTER TABLE memory ADD COLUMN IF NOT EXISTS embedding vector(1536)';
        BEGIN
            EXECUTE 'CREATE INDEX IF NOT EXISTS idx_memory_embedding ON memory USING hnsw (embedding vector_cosine_ops)';
        EXCEPTION WHEN OTHERS THEN
            NULL;  -- index method/version unavailable: keep the column, search still works exactly
        END;
    END IF;
END $$;
