"""Enterprise Agentic Incident Response Agent powered by Google Gemini.
Coordinates tool calling across pgvector runbook retrieval, system diagnostics, and n8n webhook alert dispatching.
"""

import json
import logging
import time
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from opssentinel.agent.tools import (
    dispatch_n8n_alert_tool,
    query_system_diagnostics_tool,
    search_runbooks_tool,
)
from opssentinel.config import settings
from opssentinel.ingestion.ingest import get_gemini_client

logger = logging.getLogger("opssentinel.agent")

SYSTEM_INSTRUCTION = """You are OpsSentinel, an expert Enterprise Autonomous SRE and Incident Response Agent.
Your responsibility is to analyze infrastructure incident queries, triage operational failures, determine root causes, and execute rapid remediation.

You have access to three specialized operational tools:
1. `query_system_diagnostics_tool(service_name, check_type)`: Queries live diagnostic telemetry, error rates, CPU/memory pressure, active connections, and latency anomalies.
2. `search_runbooks_tool(query, category, limit)`: Performs semantic vector search in PostgreSQL pgvector against technical runbooks and standard operating procedures (SOPs).
3. `dispatch_n8n_alert_tool(title, severity, summary, remediation_plan, incident_id, diagnostics, matched_runbooks)`: Dispatches structured, actionable incident alerts to the on-call team via self-hosted n8n workflows and records the incident in PostgreSQL audit logs.

Execution Protocol:
1. Always start by inspecting real-time telemetry using `query_system_diagnostics_tool` to identify anomaly indicators.
2. Search relevant runbooks using `search_runbooks_tool` to obtain proven operational remediation steps and escalation paths.
3. Formulate an actionable incident summary, identify root cause, and formulate clear step-by-step remediation procedures.
4. Dispatch the alert to on-call teams via `dispatch_n8n_alert_tool`.
5. Present a clear, executive-grade final analysis detailing:
   - Incident Severity & Impact
   - Root Cause Analysis
   - Real-time Diagnostic Telemetry findings
   - Matched Runbook references
   - Step-by-step Remediation Actions (Immediate mitigation & Long-term prevention)
"""


class AgentStep(BaseModel):
    """Represents a single step/turn in the agent's reasoning loop."""
    step_number: int
    thought: str = ""
    tool_name: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    tool_result: Any | None = None
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


class IncidentAnalysisResult(BaseModel):
    """Comprehensive incident triage and remediation report."""
    incident_id: str
    query: str
    status: str
    severity: str = "P2"
    title: str = "Infrastructure Incident Triage"
    steps: list[AgentStep] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    matched_runbooks: list[dict[str, Any]] = Field(default_factory=list)
    remediation_plan: str = ""
    n8n_dispatched: bool = False
    final_analysis: str = ""
    execution_time_seconds: float = 0.0


class IncidentAgent:
    """Agentic Incident Responder orchestrating Gemini model and operational tools."""

    def __init__(self, client: genai.Client | None = None):
        self.client = client or get_gemini_client()
        self.tool_map = {
            "search_runbooks_tool": search_runbooks_tool,
            "query_system_diagnostics_tool": query_system_diagnostics_tool,
            "dispatch_n8n_alert_tool": dispatch_n8n_alert_tool,
        }

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """Safely invoke a tool function by name."""
        tool_fn = self.tool_map.get(name)
        if not tool_fn:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            return tool_fn(**args)
        except Exception as e:
            logger.error("Error executing tool %s: %s", name, e, exc_info=True)
            return json.dumps({"error": f"Tool execution failed: {str(e)}"})

    def analyze_incident(
        self,
        query: str,
        incident_id: str | None = None,
        max_turns: int = 6,
    ) -> IncidentAnalysisResult:
        """Run the full agentic loop on an incident query."""
        start_time = time.time()
        inc_id = incident_id or f"INC-{int(time.time()):X}"
        logger.info("Starting incident analysis for [%s]: '%s'", inc_id, query)

        result = IncidentAnalysisResult(
            incident_id=inc_id,
            query=query,
            status="IN_PROGRESS",
        )

        tools = [search_runbooks_tool, query_system_diagnostics_tool, dispatch_n8n_alert_tool]

        # Initialize conversation contents with user incident report
        contents: list[Any] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"Incident ID: {inc_id}\nIncident Report: {query}")],
            )
        ]

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tools,
            temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        active_model = settings.gemini_model
        fallback_models = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

        for turn in range(1, max_turns + 1):
            logger.info("Agent turn %d for incident %s using model %s", turn, inc_id, active_model)
            response = None
            models_to_attempt = [active_model] + [m for m in fallback_models if m != active_model]

            for candidate_model in models_to_attempt:
                try:
                    response = self.client.models.generate_content(
                        model=candidate_model,
                        contents=contents,
                        config=config,
                    )
                    active_model = candidate_model
                    break
                except Exception as e:
                    if "503" in str(e) or "UNAVAILABLE" in str(e):
                        logger.warning("Model %s unavailable (503), attempting fallback model...", candidate_model)
                        continue
                    else:
                        logger.error("Gemini API call failed during turn %d on %s: %s", turn, candidate_model, e)
                        break

            if response is None:
                logger.warning("All Gemini model attempts exhausted on turn %d. Engaging fallback triage.", turn)
                return self._fallback_triage(query, inc_id, error="Model generation unavailable")

            # Inspect candidate parts
            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content or not candidate.content.parts:
                logger.warning("Empty candidate response in turn %d", turn)
                break

            # Add model response to history
            contents.append(candidate.content)

            # Check for function calls
            function_calls = [
                part.function_call for part in candidate.content.parts if part.function_call
            ]
            thought_text = " ".join(
                [part.text for part in candidate.content.parts if part.text]
            ).strip()

            if not function_calls:
                # Model produced final text analysis
                result.final_analysis = thought_text
                result.status = "COMPLETED"
                break

            # Execute tool calls and prepare function response parts
            response_parts: list[types.Part] = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                logger.info("Agent executing tool: %s with args %s", tool_name, tool_args)
                tool_output_str = self._execute_tool(tool_name, tool_args)

                # Parse tool output to collect telemetry into result
                try:
                    parsed_output = json.loads(tool_output_str)
                except Exception:
                    parsed_output = {"raw": tool_output_str}

                if tool_name == "query_system_diagnostics_tool":
                    result.diagnostics = parsed_output
                elif tool_name == "search_runbooks_tool":
                    result.matched_runbooks = parsed_output.get("runbooks", [])
                elif tool_name == "dispatch_n8n_alert_tool":
                    result.n8n_dispatched = parsed_output.get("n8n_dispatched", False)
                    result.remediation_plan = tool_args.get("remediation_plan", "")
                    result.severity = tool_args.get("severity", "P2")
                    result.title = tool_args.get("title", result.title)

                step = AgentStep(
                    step_number=turn,
                    thought=thought_text,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=parsed_output,
                )
                result.steps.append(step)

                # Append function response part
                response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": tool_output_str},
                    )
                )

            # Feed function responses back into conversation history
            contents.append(types.Content(role="user", parts=response_parts))

        result.execution_time_seconds = round(time.time() - start_time, 2)
        if not result.final_analysis and result.remediation_plan:
            result.final_analysis = result.remediation_plan
            result.status = "COMPLETED"

        return result

    def _fallback_triage(
        self,
        query: str,
        incident_id: str,
        error: str | None = None,
    ) -> IncidentAnalysisResult:
        """Deterministic fallback triage when Gemini API is offline or mocked."""
        logger.warning("Executing deterministic fallback triage for %s (reason: %s)", incident_id, error)
        start_time = time.time()

        # Step 1: Query diagnostics
        diag_str = query_system_diagnostics_tool(service_name=query)
        diag = json.loads(diag_str)

        # Step 2: Search runbooks
        rb_str = search_runbooks_tool(query=query)
        rb_data = json.loads(rb_str)
        runbooks = rb_data.get("runbooks", [])

        # Step 3: Formulate remediation
        title = f"Alert: {query[:50]}"
        severity = "P1" if any(k in query.lower() for k in ["fatal", "crash", "oom", "down", "outage"]) else "P2"
        remediation_lines = [
            f"1. Verified live diagnostics: {diag.get('health_status', 'UNKNOWN')}.",
            "2. Identified relevant operational runbook procedures.",
            "3. Execute immediate mitigation from matched runbooks.",
            "4. Monitor error rates and connection metrics.",
        ]
        remediation = "\n".join(remediation_lines)

        # Step 4: Dispatch alert
        dispatch_str = dispatch_n8n_alert_tool(
            title=title,
            severity=severity,
            summary=query,
            remediation_plan=remediation,
            incident_id=incident_id,
            diagnostics=diag,
            matched_runbooks=runbooks,
        )
        dispatch_data = json.loads(dispatch_str)

        return IncidentAnalysisResult(
            incident_id=incident_id,
            query=query,
            status="COMPLETED_FALLBACK",
            severity=severity,
            title=title,
            steps=[
                AgentStep(step_number=1, tool_name="query_system_diagnostics_tool", tool_args={"service_name": query}, tool_result=diag),
                AgentStep(step_number=2, tool_name="search_runbooks_tool", tool_args={"query": query}, tool_result=rb_data),
                AgentStep(step_number=3, tool_name="dispatch_n8n_alert_tool", tool_args={"title": title, "severity": severity}, tool_result=dispatch_data),
            ],
            diagnostics=diag,
            matched_runbooks=runbooks,
            remediation_plan=remediation,
            n8n_dispatched=dispatch_data.get("n8n_dispatched", False),
            final_analysis=f"Triage completed for incident {incident_id}. Diagnostics evaluated, {len(runbooks)} runbooks matched, and alert dispatched to n8n.",
            execution_time_seconds=round(time.time() - start_time, 2),
        )
