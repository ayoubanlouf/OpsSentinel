"""Live end-to-end integration test of OpsSentinel Agent."""

import json
from opssentinel.agent.agent import IncidentAgent

def main():
    agent = IncidentAgent()
    query = (
        "Production Incident: Database connection pool exhaustion. "
        "Application APIs throwing 500 errors and psycopg FATAL: remaining connection slots are reserved."
    )
    print("Executing agent analysis with Google Gemini...")
    result = agent.analyze_incident(query=query)
    
    print("\n================= AGENT TRIAGE SUMMARY =================")
    print(f"Incident ID:    {result.incident_id}")
    print(f"Status:         {result.status}")
    print(f"Severity:       {result.severity}")
    print(f"Title:          {result.title}")
    print(f"n8n Dispatched: {result.n8n_dispatched}")
    print(f"Execution Time: {result.execution_time_seconds}s")
    print(f"Total Steps:    {len(result.steps)}")
    
    for step in result.steps:
        print(f"\n--- Step {step.step_number}: Tool '{step.tool_name}' ---")
        print(f"Args: {json.dumps(step.tool_args, indent=2)}")
        print(f"Result Preview: {str(step.tool_result)[:180]}...")
        
    print("\n================= FINAL REMEDIATION PLAN =================")
    print(result.remediation_plan or result.final_analysis)

if __name__ == "__main__":
    main()

