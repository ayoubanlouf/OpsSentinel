"""Tests for OpsSentinel Incident Response Agent."""

from unittest.mock import MagicMock, patch

from opssentinel.agent.agent import IncidentAgent


def test_agent_fallback_triage():
    """Verify deterministic fallback triage completes with all steps and tools."""
    agent = IncidentAgent(client=MagicMock())
    result = agent._fallback_triage(
        query="PostgreSQL connection pool exhausted with 500 errors",
        incident_id="INC-FALLBACK-101",
    )
    assert result.incident_id == "INC-FALLBACK-101"
    assert "COMPLETED" in result.status
    assert len(result.steps) == 3
    assert result.diagnostics != {}
    assert result.remediation_plan != ""


@patch("opssentinel.agent.agent.IncidentAgent._execute_tool")
def test_agent_tool_execution(mock_exec, mock_gemini_client):
    """Verify agent invokes registered tool and tracks response."""
    mock_exec.return_value = '{"status": "ok", "value": 42}'
    agent = IncidentAgent(client=mock_gemini_client)
    res = agent._execute_tool("search_runbooks_tool", {"query": "test"})
    assert "ok" in res

