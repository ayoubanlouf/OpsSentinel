-- ==============================================================================
-- OpsSentinel Database Initialization Script
-- Configures pgvector extension, runbook embeddings table, and incident history
-- ==============================================================================

-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Runbooks Vector Store Table
CREATE TABLE IF NOT EXISTS runbooks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    chunk_index INT NOT NULL DEFAULT 0,
    embedding vector(768),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexing for fast cosine similarity vector search
CREATE INDEX IF NOT EXISTS runbooks_embedding_hnsw_idx 
ON runbooks USING hnsw (embedding vector_cosine_ops);

-- Standard B-tree indices for fast filtering
CREATE INDEX IF NOT EXISTS runbooks_filename_idx ON runbooks (filename);
CREATE INDEX IF NOT EXISTS runbooks_category_idx ON runbooks (category);
CREATE INDEX IF NOT EXISTS runbooks_created_at_idx ON runbooks (created_at DESC);

-- Incidents Audit Log Table
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'P2',
    query TEXT NOT NULL,
    status VARCHAR(64) NOT NULL DEFAULT 'TRIAGED',
    diagnostics JSONB DEFAULT '{}'::jsonb,
    matched_runbooks JSONB DEFAULT '[]'::jsonb,
    remediation_plan TEXT,
    n8n_dispatched BOOLEAN DEFAULT FALSE,
    dispatched_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS incidents_incident_id_idx ON incidents (incident_id);
CREATE INDEX IF NOT EXISTS incidents_status_idx ON incidents (status);
CREATE INDEX IF NOT EXISTS incidents_created_at_idx ON incidents (created_at DESC);

