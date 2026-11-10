# OpsSentinel 🛡️
> Enterprise Agentic Incident Response & Runbook RAG Platform

OpsSentinel is an intelligent operations platform designed for SRE and DevOps teams. It ingests technical runbooks and documentation into PostgreSQL with pgvector, analyzes incoming infrastructure incident queries via a tool-calling AI agent powered by Google Gemini, inspects system diagnostic states, and dispatches actionable alerts through a self-hosted n8n automation workflow.

---

## Architecture Overview

```
+-------------------------------------------------------------------------+
|                              OpsSentinel                                |
|                                                                         |
|  +-----------------------+              +----------------------------+  |
|  |   Ingestion Engine    |              |     FastAPI Agent Svc      |  |
|  |  (Gemini Embeddings)  |              |    (/api/v1/incident)      |  |
|  +-----------+-----------+              +-------------+--------------+  |
|              |                                        |                 |
|              v                                        v                 |
|  +-----------------------+              +----------------------------+  |
|  | PostgreSQL + pgvector | <----------- | Gemini Tool-Calling Agent  |  |
|  |   (Runbook Store)     |              | (RAG, Diagnostics, Alerts) |  |
|  +-----------------------+              +-------------+--------------+  |
|                                                       |                 |
|                                                       v                 |
|                                         +----------------------------+  |
|                                         |     n8n Automation Engine  |  |
|                                         |  (Webhook & Notifications) |  |
|                                         +----------------------------+  |
+-------------------------------------------------------------------------+
```

---

## Quick Start (Phase 1 Setup Checkpoint)

Please refer to [`SETUP_CHECKPOINT.md`](file:///c:/Users/Msi/Downloads/OpsSentinel/SETUP_CHECKPOINT.md) for detailed instructions on configuring `.env`, launching the Docker containers in WSL 2, importing the n8n incident dispatch workflow, and linking your remote GitHub repository.
