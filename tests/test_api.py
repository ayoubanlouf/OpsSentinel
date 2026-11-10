"""Tests for OpsSentinel FastAPI REST and streaming endpoints."""

from unittest.mock import patch


def test_health_check(test_client):
    """Verify health check endpoint returns 200 with service details."""
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert "database" in data


def test_dashboard_endpoint(test_client):
    """Verify dashboard endpoint serves interactive web console."""
    response = test_client.get("/dashboard")
    assert response.status_code == 200
    assert "OpsSentinel" in response.text
    assert "Incident Triage Console" in response.text


@patch("opssentinel.api.main.IncidentAgent.analyze_incident")
def test_analyze_incident_endpoint(mock_analyze, test_client):
    """Verify /api/v1/incident/analyze executes agent and returns structured result."""
    from opssentinel.agent.agent import IncidentAnalysisResult

    mock_analyze.return_value = IncidentAnalysisResult(
        incident_id="INC-API-001",
        query="High memory usage on worker pods with OOMKilled",
        status="COMPLETED",
        severity="P1",
        title="High Memory OOM Crash",
        remediation_plan="Scale worker replicas and patch memory limit",
        n8n_dispatched=True,
        final_analysis="Analysis complete: memory leak in caching layer.",
    )

    payload = {
        "query": "High memory usage on worker pods with OOMKilled",
        "incident_id": "INC-API-001",
        "stream": False,
    }
    response = test_client.post("/api/v1/incident/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == "INC-API-001"
    assert data["severity"] == "P1"
    assert data["n8n_dispatched"] is True
    assert "remediation_plan" in data


@patch("opssentinel.api.main.IncidentAgent.analyze_incident")
def test_analyze_incident_streaming_endpoint(mock_analyze, test_client):
    """Verify /api/v1/incident/analyze supports SSE streaming response."""
    from opssentinel.agent.agent import AgentStep, IncidentAnalysisResult

    mock_analyze.return_value = IncidentAnalysisResult(
        incident_id="INC-STREAM-001",
        query="SSL cert expired on public gateway",
        status="COMPLETED",
        steps=[
            AgentStep(step_number=1, tool_name="query_system_diagnostics_tool", tool_args={"service_name": "ssl"}),
            AgentStep(step_number=2, tool_name="search_runbooks_tool", tool_args={"query": "ssl expiration"}),
        ],
        remediation_plan="Renew cert-manager order and patch ingress secret",
    )

    payload = {
        "query": "SSL cert expired on public gateway",
        "incident_id": "INC-STREAM-001",
        "stream": True,
    }
    response = test_client.post("/api/v1/incident/analyze", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    text = response.text
    assert "event: start" in text
    assert "event: step" in text
    assert "event: complete" in text
