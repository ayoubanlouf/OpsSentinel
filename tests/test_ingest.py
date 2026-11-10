"""Tests for OpsSentinel runbook ingestion and semantic chunking."""


from opssentinel.ingestion.ingest import (
    chunk_text_semantically,
    compute_embedding,
    parse_runbook_metadata,
)

SAMPLE_RUNBOOK = """# Operational Runbook: Database Connection Pool Exhaustion

## Service Information
- **Service Name**: Core PostgreSQL Cluster
- **Severity**: P1 / High
- **Category**: Database & Data Infrastructure
- **Owning Team**: SRE & Database Infrastructure Team

---

## 1. Overview & Incident Description
Database connection pool exhaustion occurs when client services open more simultaneous connections to PostgreSQL.

---

## 2. Common Symptoms & Alert Triggers
- Prometheus Alert: PostgresqlConnectionPoolSaturation (> 90% connection usage).

---

## 3. Diagnostic Procedures
SELECT count(*), state FROM pg_stat_activity GROUP BY state;

---

## 4. Immediate Mitigation Steps
Step 1: Terminate Idle in Transaction Sessions.
Step 2: Restart leaky pods.
"""


def test_parse_runbook_metadata():
    """Verify metadata extraction from markdown runbook."""
    title, category, metadata = parse_runbook_metadata(SAMPLE_RUNBOOK, "db_connection_pool_exhaustion.md")
    assert title == "Operational Runbook: Database Connection Pool Exhaustion"
    assert category == "Database & Data Infrastructure"
    assert metadata["severity"] == "P1 / High"
    assert metadata["service"] == "Core PostgreSQL Cluster"
    assert metadata["filename"] == "db_connection_pool_exhaustion.md"


def test_chunk_text_semantically():
    """Verify semantic chunking splits at headers and preserves content."""
    chunks = chunk_text_semantically(SAMPLE_RUNBOOK, chunk_size=250, chunk_overlap=50)
    assert len(chunks) >= 3
    # First chunk should contain header or service info
    assert "Operational Runbook" in chunks[0] or "Service Information" in chunks[0]
    # Check that later chunks contain section topics
    full_text = " ".join(chunks)
    assert "Diagnostic Procedures" in full_text
    assert "Immediate Mitigation Steps" in full_text


def test_compute_embedding(mock_gemini_client):
    """Verify embedding computation via Gemini client."""
    embedding = compute_embedding(mock_gemini_client, "Sample text query", dimensions=768)
    assert isinstance(embedding, list)
    assert len(embedding) == 768
    mock_gemini_client.models.embed_content.assert_called_once()
