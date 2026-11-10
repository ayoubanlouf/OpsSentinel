"""FastAPI application for OpsSentinel: Enterprise Agentic Incident Response Platform.
Exposes REST and streaming endpoints for incident analysis, health monitoring, and runbook retrieval.
"""

import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from opssentinel.agent.agent import IncidentAgent, IncidentAnalysisResult
from opssentinel.config import settings
from opssentinel.db import close_db_pool, get_db_connection, get_db_pool
from opssentinel.ingestion.ingest import ingest_all_runbooks

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("opssentinel.api")

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager: initializes database pool on startup and cleans up on shutdown."""
    logger.info("Starting OpsSentinel API server on %s:%d", settings.app_host, settings.app_port)
    # Warm up database pool
    try:
        get_db_pool()
        logger.info("Database connection pool initialized successfully.")
    except Exception as e:
        logger.warning("Could not initialize database pool on startup: %s", e)
    yield
    logger.info("Shutting down OpsSentinel API server...")
    close_db_pool()


app = FastAPI(
    title="OpsSentinel Incident Response Platform",
    description="Enterprise Agentic Incident Response & Runbook RAG Platform powered by Google Gemini and n8n",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"], include_in_schema=False)
@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard() -> HTMLResponse:
    """Serve the interactive OpsSentinel SRE Incident Response Dashboard."""
    template_path = os.path.join(TEMPLATE_DIR, "dashboard.html")
    if os.path.exists(template_path):
        with open(template_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>OpsSentinel Dashboard</h1><p><a href='/docs'>API Documentation</a></p>")


class IncidentAnalyzeRequest(BaseModel):
    """Request payload for analyzing an infrastructure incident."""
    query: str = Field(..., description="Description of the incident, alert, or error symptoms", min_length=5)
    incident_id: str | None = Field(default=None, description="Optional custom incident tracking ID")
    stream: bool = Field(default=False, description="Whether to stream the agent thought process and tool invocations via SSE")


class IngestionRequest(BaseModel):
    """Request payload for triggering runbook ingestion."""
    docs_dir: str = Field(default="docs", description="Directory path containing runbooks")
    reset: bool = Field(default=True, description="Whether to clear existing runbooks before indexing")


@app.get("/health", tags=["System"])
@app.get("/api/v1/health", tags=["System"])
def health_check() -> dict[str, Any]:
    """Health check endpoint verifying API service, PostgreSQL, and pgvector extension."""
    db_healthy = False
    pgvector_installed = False

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                db_healthy = bool(cur.fetchone())
                cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
                pgvector_installed = bool(cur.fetchone())
    except Exception as e:
        logger.error("Database health check error: %s", e)

    overall_status = "healthy" if (db_healthy and pgvector_installed) else "degraded"

    return {
        "status": overall_status,
        "service": "OpsSentinel Incident Response API",
        "version": "0.1.0",
        "database": {
            "connected": db_healthy,
            "pgvector_enabled": pgvector_installed,
        },
        "gemini_model": settings.gemini_model,
        "n8n_webhook": settings.n8n_webhook_url,
    }


@app.post(
    "/api/v1/incident/analyze",
    response_model=IncidentAnalysisResult,
    tags=["Incidents"],
    summary="Analyze incident via Gemini tool-calling agent",
)
def analyze_incident(request: IncidentAnalyzeRequest):
    """Analyze an incoming infrastructure incident.
    The Gemini agent inspects system diagnostics, searches vector runbooks,
    formulates a remediation plan, and dispatches an alert to n8n.
    """
    if request.stream:
        return StreamingResponse(
            _stream_incident_analysis(request.query, request.incident_id),
            media_type="text/event-stream",
        )

    try:
        agent = IncidentAgent()
        result = agent.analyze_incident(query=request.query, incident_id=request.incident_id)
        return result
    except Exception as e:
        logger.error("Incident analysis failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Incident triage failed: {str(e)}",
        )


async def _stream_incident_analysis(
    query: str,
    incident_id: str | None,
) -> AsyncGenerator[str, None]:
    """Stream incident analysis steps as Server-Sent Events (SSE)."""
    yield f"event: start\ndata: {json.dumps({'message': 'Starting OpsSentinel incident analysis', 'query': query})}\n\n"
    try:
        agent = IncidentAgent()
        result = agent.analyze_incident(query=query, incident_id=incident_id)
        for step in result.steps:
            yield f"event: step\ndata: {step.model_dump_json()}\n\n"
        yield f"event: complete\ndata: {result.model_dump_json()}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@app.get("/api/v1/incidents", tags=["Incidents"], summary="List historical incident audit logs")
def list_incidents(limit: int = 20) -> list[dict[str, Any]]:
    """Retrieve historical triaged incidents from the PostgreSQL audit log."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT incident_id, title, severity, query, status,
                           diagnostics, matched_runbooks, remediation_plan,
                           n8n_dispatched, dispatched_at, created_at
                    FROM incidents
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        logger.error("Failed to fetch historical incidents: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ingest", tags=["Runbooks"], summary="Trigger vector ingestion of runbooks")
def trigger_ingest(request: IngestionRequest = IngestionRequest()) -> dict[str, Any]:
    """Ingest markdown runbooks from docs directory into PostgreSQL pgvector."""
    try:
        count = ingest_all_runbooks(docs_dir=request.docs_dir, reset=request.reset)
        return {
            "status": "success",
            "message": f"Successfully ingested {count} runbook chunks into pgvector.",
            "chunks_count": count,
        }
    except Exception as e:
        logger.error("Ingestion failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

