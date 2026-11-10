"""Tests for OpsSentinel operational diagnostic tools and webhook dispatcher."""

import json
from unittest.mock import MagicMock, patch

from opssentinel.agent.tools import (
    dispatch_n8n_alert_tool,
    query_system_diagnostics_tool,
    search_runbooks_tool,
)


def test_query_system_diagnostics_all():
    """Verify diagnostic tool returns all subsystem metrics."""
    result_str = query_system_diagnostics_tool(service_name="all", check_type="all")
    data = json.loads(result_str)
    assert "metrics" in data
    assert "database" in data["metrics"]
    assert "memory" in data["metrics"]
    assert "gateway" in data["metrics"]
    assert "ssl" in data["metrics"]
    assert "health_status" in data


def test_query_system_diagnostics_database():
    """Verify database diagnostic checks."""
    result_str = query_system_diagnostics_tool(service_name="postgres", check_type="database")
    data = json.loads(result_str)
    assert "database" in data["metrics"]
    db_metrics = data["metrics"]["database"]
    assert "active_connections" in db_metrics
    assert "pool_saturation_pct" in db_metrics
    assert db_metrics["pool_saturation_pct"] > 0


def test_query_system_diagnostics_memory():
    """Verify memory diagnostic checks detect OOM anomalies."""
    result_str = query_system_diagnostics_tool(service_name="worker-pod", check_type="memory")
    data = json.loads(result_str)
    assert "memory" in data["metrics"]
    assert data["metrics"]["memory"]["last_exit_code"] == 137
    assert len(data["anomalies_detected"]) > 0


@patch("opssentinel.agent.tools.get_db_connection")
@patch("opssentinel.agent.tools.compute_embedding")
@patch("opssentinel.agent.tools.get_gemini_client")
def test_search_runbooks_tool_success(mock_client, mock_embed, mock_db):
    """Verify vector runbook search returns formatted results."""
    mock_embed.return_value = [0.1] * 768

    # Mock DB cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "title": "Database Connection Pool Exhaustion",
            "filename": "db_connection_pool_exhaustion.md",
            "category": "Database",
            "content": "Step 1: terminate idle connections...",
            "chunk_index": 0,
            "similarity": 0.895,
        }
    ]
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_db.return_value.__enter__.return_value = mock_conn

    res_str = search_runbooks_tool(query="Postgres pool exhausted")
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert data["matches_count"] == 1
    assert data["runbooks"][0]["title"] == "Database Connection Pool Exhaustion"
    assert data["runbooks"][0]["similarity_score"] == 0.895


@patch("opssentinel.agent.tools.httpx.Client.post")
@patch("opssentinel.agent.tools.record_incident_audit")
@patch("opssentinel.agent.tools.get_db_connection")
def test_dispatch_n8n_alert_tool(mock_db, mock_audit, mock_post):
    """Verify n8n alert dispatch and audit log persistence."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "received", "success": True}
    mock_post.return_value = mock_resp

    res_str = dispatch_n8n_alert_tool(
        title="Critical DB Pool Exhaustion",
        severity="P1",
        summary="Pool saturation at 98%",
        remediation_plan="Restart leaky pods and terminate idle sessions",
        incident_id="INC-TEST-001",
    )
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert data["incident_id"] == "INC-TEST-001"
    assert data["n8n_dispatched"] is True
