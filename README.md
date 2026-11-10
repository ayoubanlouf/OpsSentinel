# OpsSentinel 🛡️
> **Enterprise Agentic Incident Response & Runbook RAG Platform**

[![CI/CD Pipeline](https://github.com/ayoubanlouf/OpsSentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/ayoubanlouf/OpsSentinel/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-3.8%20Flash-4285F4.svg)](https://aistudio.google.com/)
[![n8n](https://img.shields.io/badge/n8n-Automation%20Engine-EA4B71.svg)](https://n8n.io/)

OpsSentinel is an enterprise-grade autonomous incident response platform designed for SRE and DevOps engineering teams. It continuously ingests technical runbooks and standard operating procedures (SOPs) into PostgreSQL with vector embeddings, analyzes incoming infrastructure incident queries via an autonomous tool-calling AI agent powered by the **Google Gemini API**, inspects real-time diagnostic telemetry, and dispatches actionable alerts through a self-hosted **n8n automation workflow**.

---

## 🏛️ System Architecture

```text
                                  +-----------------------------------------------+
                                  |            SRE / Monitoring Alerts            |
                                  |     (Datadog, Prometheus, PagerDuty, Slack)   |
                                  +-----------------------+-----------------------+
                                                          |
                                                          | HTTP POST (JSON / SSE)
                                                          v
+---------------------------------------------------------------------------------------------------------+
|                                        OpsSentinel Platform Core                                        |
|                                                                                                         |
|  +--------------------------+                                 +--------------------------------------+  |
|  |     Runbook Ingestion    |                                 |          FastAPI Agent Service       |  |
|  |          Engine          |                                 |       (/api/v1/incident/analyze)     |  |
|  +------------+-------------+                                 +------------------+-------------------+  |
|               |                                                                  |                      |
|               | Text Chunks                                                      | User Query           |
|               v                                                                  v                      |
|  +--------------------------+         Embedding Vector        +--------------------------------------+  |
|  |    Gemini Embeddings     | ------------------------------> |      Autonomous Gemini AI Agent      |  |
|  |  (gemini-embedding-001)  |                                 |    (Reasoning & Tool Selection)      |  |
|  +------------+-------------+                                 +------------------+-------------------+  |
|               |                                                                  |                      |
|               | 768-dim Vectors                                                  | Function Calls       |
|               v                                                                  v                      |
|  +--------------------------+    Semantic Cosine Similarity   +--------------------------------------+  |
|  |  PostgreSQL 16 + pgvector| <============================== | Tool 1: search_runbooks_tool         |  |
|  |    (HNSW Vector Index)   |                                 +--------------------------------------+  |
|  +--------------------------+                                 | Tool 2: query_system_diagnostics_tool|  |
|               ^                                               +--------------------------------------+  |
|               | Audit Logging                                 | Tool 3: dispatch_n8n_alert_tool      |  |
|               +-----------------------------------------------+------------------+-------------------+  |
|                                                                                  |                      |
+----------------------------------------------------------------------------------|----------------------+
                                                                                   | Webhook Dispatch
                                                                                   v
                                                                +--------------------------------------+
                                                                |         n8n Automation Engine        |
                                                                |       (Incident Alert Workflow)      |
                                                                +------------------+-------------------+
                                                                                   |
                                                                                   | Notifications
                                                                                   v
                                                                +--------------------------------------+
                                                                |   Slack / Discord / PagerDuty Teams  |
                                                                +--------------------------------------+
```

---

## 🚀 Key Features

- **Semantic Runbook RAG Engine**: Markdown runbooks in `docs/runbooks/` are parsed, chunked with semantic boundary overlap, vectorized using `gemini-embedding-001`, and indexed in PostgreSQL using HNSW cosine distance indexing (`vector_cosine_ops`).
- **Autonomous Tool-Calling SRE Agent**: Multi-turn agent loop with Google Gemini equipped with three enterprise operational tools:
  - `search_runbooks_tool`: Retrieves verified SOPs and mitigation steps from pgvector.
  - `query_system_diagnostics_tool`: Inspects live infrastructure telemetry, pool saturation, memory pressure, cgroup exit codes, and latency metrics.
  - `dispatch_n8n_alert_tool`: Dispatches formatted alerts to self-hosted n8n workflows and records triages in PostgreSQL audit logs.
- **Resilient Model Failover**: Automatic fallback handling ensuring high availability even during upstream API demand spikes.
- **REST & SSE Streaming API**: Fast REST endpoint returning structured JSON reports, with Server-Sent Events (`stream=true`) streaming intermediate agent thoughts, tool invocations, and live results.
- **Self-Hosted n8n Automation**: Packaged with a production-ready, pre-configured n8n workflow supporting color-coded Slack and Discord embeds.
- **Tested & CI/CD Validated**: Comprehensive Pytest test suite with 100% pass rate and GitHub Actions CI workflow running automated linting, schema provisioning, and test execution.

---

## 📋 Technology Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Language & Runtime** | Python 3.10+ | Core language with asyncio support |
| **Web Framework** | FastAPI & Uvicorn | High-performance asynchronous REST & SSE API |
| **Vector Database** | PostgreSQL 16 + pgvector | Persistent relational storage & high-speed vector retrieval |
| **LLM & Embeddings** | Google Gemini API (`google-genai`) | `gemini-3.8-flash` / `gemini-3.5-flash-lite` reasoning & `gemini-embedding-001` embeddings |
| **Automation Engine** | Self-hosted n8n | Visual workflow automation for incident notifications |
| **Containerization** | Docker & Docker Compose | Production-ready multi-container orchestration in WSL 2 |
| **Testing & Quality** | Pytest, Pytest-Asyncio, Ruff | Unit/integration testing and strict linting |
| **CI/CD Pipeline** | GitHub Actions | Automated lint, schema validation, and test runs on push |

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` in the project root:

```bash
cp .env.example .env
```

| Variable | Description | Default / Example Value |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | **Required**: API key from [Google AI Studio](https://aistudio.google.com/apikey) | `AIzaSy...` |
| `GEMINI_MODEL` | Primary Gemini model for agentic triage | `gemini-3.8-flash` |
| `GEMINI_EMBEDDING_MODEL` | Embedding model for runbook vectors | `gemini-embedding-001` |
| `POSTGRES_USER` | PostgreSQL superuser username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL superuser password | `postgres` |
| `POSTGRES_DB` | Database name | `opssentinel` |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |
| `DATABASE_URL` | SQLAlchemy / Psycopg connection URI | `postgresql://postgres:postgres@localhost:5432/opssentinel` |
| `N8N_PORT` | n8n Web UI and webhook exposed port | `5678` |
| `N8N_WEBHOOK_URL` | Webhook URL for incident dispatch | `http://localhost:5678/webhook/incident-alert` |
| `APP_HOST` | FastAPI host bind address | `0.0.0.0` |
| `APP_PORT` | FastAPI listening port | `8000` |
| `ENVIRONMENT` | Deployment environment | `development` |
| `LOG_LEVEL` | Application logging verbosity | `INFO` |

---

## 🛠️ Quick Start Guide

### 1. Prerequisites
- Docker & Docker Compose running inside WSL 2 (Ubuntu environment)
- Python 3.10+
- Google Gemini API Key

### 2. Launch Backing Services (WSL 2)
```bash
# Navigate to the repository in WSL 2
cd /mnt/c/Users/Msi/Downloads/OpsSentinel

# Spin up PostgreSQL (pgvector) and n8n
docker compose up -d

# Verify container health
./scripts/wait_for_services.sh
```

### 3. Ingest Runbooks into Vector Store
Vectorize the markdown operational runbooks into PostgreSQL:
```bash
# Run the ingestion engine
python -m opssentinel.ingestion.ingest
```
Output:
```text
[INFO] Resetting existing runbooks table...
[INFO] Ingesting 'Operational Runbook: Database Connection Pool Exhaustion' (9 chunks)
[INFO] Ingesting 'Operational Runbook: High Memory & OOM Crashes' (9 chunks)
[INFO] Ingesting 'Operational Runbook: SSL/TLS Certificate Renewal' (9 chunks)
[INFO] Ingesting 'Operational Runbook: API 504 Gateway Timeout' (10 chunks)
[INFO] Successfully ingested 37 total chunks from 4 files.
```

### 4. Start the OpsSentinel API Server
```bash
uvicorn opssentinel.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API documentation will be available at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📡 API Reference & Usage Examples

### 1. Health Check
```bash
curl -s http://localhost:8000/api/v1/health | jq
```
```json
{
  "status": "healthy",
  "service": "OpsSentinel Incident Response API",
  "version": "0.1.0",
  "database": {
    "connected": true,
    "pgvector_enabled": true
  },
  "gemini_model": "gemini-3.8-flash",
  "n8n_webhook": "http://localhost:5678/webhook/incident-alert"
}
```

### 2. Analyze Incident (Standard JSON Response)
```bash
curl -X POST http://localhost:8000/api/v1/incident/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Production database connection pool exhaustion. Application APIs throwing 500 errors and psycopg FATAL: remaining connection slots are reserved."
  }' | jq
```

### 3. Analyze Incident (Live SSE Streaming)
```bash
curl -N -X POST http://localhost:8000/api/v1/incident/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Ingress returning 504 Gateway Timeouts on POST /api/v1/transactions",
    "stream": true
  }'
```

### 4. View Historical Incident Audit Logs
```bash
curl -s http://localhost:8000/api/v1/incidents | jq
```

---

## 🧪 Testing & Verification

Run the comprehensive Pytest suite directly in WSL:
```bash
pytest -v
```
Run Ruff linting and formatting verification:
```bash
ruff check src tests
```

---

## 📂 Project Structure

```text
OpsSentinel/
├── .env.example                     # Environment template
├── .gitignore                       # Git exclusion rules
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions CI workflow
├── Dockerfile                       # Multi-stage production container image
├── docker-compose.yml               # PostgreSQL (pgvector) & n8n orchestration
├── pyproject.toml                   # Project metadata and dependencies
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development and testing dependencies
├── README.md                        # Enterprise platform documentation
├── docs/
│   ├── ARCHITECTURE.md              # In-depth architectural & operational guide
│   └── runbooks/                    # Operational SRE runbooks
│       ├── api_504_gateway_timeout.md
│       ├── db_connection_pool_exhaustion.md
│       ├── high_memory_oom_crash.md
│       └── ssl_certificate_renewal.md
├── n8n/
│   └── workflows/
│       └── incident_alert.json      # n8n webhook alert workflow
├── scripts/
│   ├── init-db.sql                  # PostgreSQL & pgvector schema init
│   ├── wait_for_services.sh         # Container healthcheck utility
│   └── run_incident_demo.py         # Multi-scenario CLI demonstration runner
├── src/
│   └── opssentinel/
│       ├── __init__.py
│       ├── config.py                # Pydantic environment configuration
│       ├── db.py                    # Connection pool & pgvector queries
│       ├── metrics.py               # Prometheus metrics collection and exposition format
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── agent.py             # Autonomous Gemini agentic loop
│       │   └── tools.py             # Operational diagnostic tools & webhook dispatcher
│       ├── ingestion/
│       │   ├── __init__.py
│       │   └── ingest.py            # Runbook parsing, semantic chunking & vector indexing
│       └── api/
│           ├── __init__.py
│           ├── main.py              # FastAPI service & streaming endpoints
│           └── templates/
│               └── dashboard.html   # Glassmorphic SRE web dashboard
└── tests/
    ├── __init__.py
    ├── conftest.py                  # Pytest fixtures and mocks
    ├── test_agent.py                # Agent loop and fallback tests
    ├── test_api.py                  # FastAPI REST and SSE tests
    ├── test_ingest.py               # Ingestion and chunking tests
    └── test_tools.py                # Diagnostic tools & webhook tests
```

---

## 📄 License
This project is licensed under the MIT License.
