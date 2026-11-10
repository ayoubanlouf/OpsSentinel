#!/usr/bin/env python3
"""Interactive CLI demo for OpsSentinel.
Runs live triage simulations across the 4 major incident categories.
"""

import sys
import time
from opssentinel.agent.agent import IncidentAgent

SCENARIOS = [
    {
        "name": "Database Connection Pool Exhaustion (P1)",
        "query": "Production Incident: Database connection pool exhaustion. Application APIs throwing 500 errors and psycopg FATAL: remaining connection slots are reserved.",
    },
    {
        "name": "Compute OOM Pod Crash (P1)",
        "query": "Worker deployment api-gateway pods crashing repeatedly in production. Pod exit code 137 OOMKilled detected. Node memory pressure alarm triggered.",
    },
    {
        "name": "SSL/TLS Certificate Expiration (P1)",
        "query": "Urgent Alert: Public HTTPS endpoint api.opssentinel.io failing with SSL: CERTIFICATE_VERIFY_FAILED. Cert-manager ACME challenge solver timed out.",
    },
    {
        "name": "API Gateway 504 Gateway Timeout (P2)",
        "query": "Ingress reverse proxy returning HTTP 504 Gateway Time-out on POST /api/v1/transactions. Upstream response time p99 is over 45 seconds.",
    },
]


def run_demo():
    print("=" * 70)
    print(" 🛡️  OpsSentinel Live Autonomous Incident Response Demonstrator")
    print("=" * 70)
    print(f"Loaded {len(SCENARIOS)} operational incident scenarios.\n")

    agent = IncidentAgent()

    for i, sc in enumerate(SCENARIOS, 1):
        print(f"\n[{i}/{len(SCENARIOS)}] SCENARIO: {sc['name']}")
        print(f"Alert Query: {sc['query']}")
        print("-" * 70)
        
        start = time.time()
        result = agent.analyze_incident(query=sc["query"])
        elapsed = round(time.time() - start, 2)
        
        print(f"Status:         {result.status}")
        print(f"Severity:       {result.severity}")
        print(f"Steps Taken:    {len(result.steps)}")
        print(f"n8n Dispatched: {result.n8n_dispatched}")
        print(f"Elapsed:        {elapsed}s")
        print(f"\n--- Remediation Plan ---")
        print(result.remediation_plan[:350] + "...")
        print("=" * 70)


if __name__ == "__main__":
    run_demo()
