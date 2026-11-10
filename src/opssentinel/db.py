"""Database management, connection pooling, and pgvector operations for OpsSentinel."""

import json
import logging
from contextlib import contextmanager
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from opssentinel.config import settings

logger = logging.getLogger("opssentinel.db")

_pool: ConnectionPool | None = None


def get_db_pool() -> ConnectionPool:
    """Initialize or return the singleton database connection pool."""
    global _pool
    if _pool is None or _pool.closed:
        logger.info("Initializing PostgreSQL connection pool at %s", settings.database_url)
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=2,
            max_size=10,
            open=True,
            timeout=10.0,
            configure=register_vector,
        )
    return _pool


def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None and not _pool.closed:
        logger.info("Closing PostgreSQL connection pool")
        _pool.close()
        _pool = None


@contextmanager
def get_db_connection():
    """Context manager for acquiring a connection from the pool with pgvector registered."""
    pool = get_db_pool()
    with pool.connection() as conn:
        register_vector(conn)
        yield conn


def insert_runbook_chunk(
    conn: psycopg.Connection,
    title: str,
    filename: str,
    category: str,
    content: str,
    chunk_index: int,
    embedding: list[float],
    metadata: dict[str, Any] | None = None,
) -> int:
    """Insert a runbook chunk with vector embedding into PostgreSQL."""
    meta = json.dumps(metadata or {})
    query = """
        INSERT INTO runbooks (title, filename, category, content, chunk_index, embedding, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id;
    """
    with conn.cursor() as cur:
        cur.execute(
            query,
            (title, filename, category, content, chunk_index, embedding, meta),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else 0


def search_runbooks(
    conn: psycopg.Connection,
    query_embedding: list[float],
    limit: int = 3,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Perform cosine distance similarity search using pgvector."""
    base_query = """
        SELECT id, title, filename, category, content, chunk_index, metadata,
               1 - (embedding <=> %s::vector) AS similarity
        FROM runbooks
    """
    params: list[Any] = [query_embedding]
    if category:
        base_query += " WHERE category = %s"
        params.append(category)

    base_query += """
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s;
    """
    params.extend([query_embedding, limit])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(base_query, params)
        results = cur.fetchall()
        return [dict(r) for r in results]


def clear_runbooks(conn: psycopg.Connection) -> int:
    """Clear all ingested runbooks from the table."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE runbooks RESTART IDENTITY;")
        conn.commit()
    return 0


def record_incident_audit(
    conn: psycopg.Connection,
    incident_id: str,
    title: str,
    severity: str,
    query: str,
    status: str,
    diagnostics: dict[str, Any],
    matched_runbooks: list[dict[str, Any]],
    remediation_plan: str,
    n8n_dispatched: bool,
) -> int:
    """Record or update an incident in the audit log table."""
    stmt = """
        INSERT INTO incidents (
            incident_id, title, severity, query, status,
            diagnostics, matched_runbooks, remediation_plan, n8n_dispatched, dispatched_at
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s::jsonb, %s::jsonb, %s, %s,
            CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END
        )
        ON CONFLICT (incident_id) DO UPDATE SET
            status = EXCLUDED.status,
            remediation_plan = EXCLUDED.remediation_plan,
            n8n_dispatched = EXCLUDED.n8n_dispatched,
            dispatched_at = EXCLUDED.dispatched_at
        RETURNING id;
    """
    with conn.cursor() as cur:
        cur.execute(
            stmt,
            (
                incident_id,
                title,
                severity,
                query,
                status,
                json.dumps(diagnostics),
                json.dumps(matched_runbooks),
                remediation_plan,
                n8n_dispatched,
                n8n_dispatched,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else 0
