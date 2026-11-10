# OpsSentinel: Phase 1 Setup & Checkpoint Guide 🛡️

Welcome to **OpsSentinel**! Phase 1 scaffolding, operational runbooks, database initialization schemas, Docker Compose orchestration, and the n8n automation workflow have been successfully created and tracked in local Git.

Before proceeding to **Phase 2 (Autonomous Implementation)**, please complete the verification steps below and provide your GitHub remote repository URL.

---

## 1. Configure Local Environment Variables

Create your local `.env` file by copying `.env.example`:

```bash
# In your WSL 2 terminal
cd /mnt/c/Users/Msi/Downloads/OpsSentinel
cp .env.example .env
```

Open `.env` and fill in the required parameters:

| Environment Variable | Description | Default / Example Value |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | **Required**: Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) | `AIzaSy...` |
| `GEMINI_MODEL` | SRE reasoning and tool-calling model | `gemini-3.8-flash` |
| `GEMINI_EMBEDDING_MODEL` | Vector embedding model for runbooks | `gemini-embedding-001` |
| `POSTGRES_USER` | PostgreSQL superuser username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL superuser password | `postgres` |
| `POSTGRES_DB` | OpsSentinel database name | `opssentinel` |
| `POSTGRES_PORT` | PostgreSQL host exposed port | `5432` |
| `DATABASE_URL` | SQLAlchemy / Psycopg connection string | `postgresql://postgres:postgres@localhost:5432/opssentinel` |
| `N8N_PORT` | n8n Web UI and webhook exposed port | `5678` |
| `N8N_WEBHOOK_URL` | Production webhook endpoint for incident alert dispatch | `http://localhost:5678/webhook/incident-alert` |
| `N8N_WEBHOOK_TEST_URL` | Test webhook endpoint for active editor sessions in n8n | `http://localhost:5678/webhook-test/incident-alert` |

---

## 2. Spin Up WSL 2 Containers & Verify Daemon Health

Since Docker is hosted within WSL 2, execute the following commands in your WSL terminal:

### 2.1 Launch Services
```bash
cd /mnt/c/Users/Msi/Downloads/OpsSentinel
docker compose up -d
```

### 2.2 Verify Container Health Status
Run the automated health check script or inspect Docker Compose:
```bash
./scripts/wait_for_services.sh
```
Or check container statuses directly:
```bash
docker compose ps
```
You should see both `opssentinel-postgres` and `opssentinel-n8n` in a `healthy` state.

### 2.3 Verify pgvector Extension & Tables
Confirm that PostgreSQL initialized with the `vector` extension and the runbook schema:
```bash
docker exec -it opssentinel-postgres psql -U postgres -d opssentinel -c "\dx"
docker exec -it opssentinel-postgres psql -U postgres -d opssentinel -c "\dt"
```
Output must show `vector` in the extension list and the `runbooks` and `incidents` tables.

---

## 3. Configure the n8n Automation Engine & Workflow

1. **Access the n8n UI**:
   Open [http://localhost:5678](http://localhost:5678) in your web browser.
2. **Initial Admin Setup**:
   Create the primary owner account (name, email, password) if prompted.
3. **Import Workflow**:
   - In the left sidebar, click **Workflows** -> **Add Workflow** (or the **+** button).
   - In the top-right menu (three dots `⋮`), click **Import from File**.
   - Select the file located at: `n8n/workflows/incident_alert.json`.
4. **Activate the Workflow**:
   - Verify the three nodes:
     1. `Incident Webhook Ingest` (Path: `incident-alert`, POST)
     2. `Format Incident Notification` (JavaScript alert formatter with Slack/Discord blocks)
     3. `Respond to Caller` (JSON response)
   - Toggle the workflow switch in the top-right corner from **Inactive** to **Active**.
   - Click **Save**.

---

## 4. GitHub Repository & Secrets Configuration

### 4.1 Create Empty GitHub Repository
1. Log into your GitHub account and create a new repository (e.g. `OpsSentinel`).
2. **Important**: Do not initialize with a README, .gitignore, or license (the local repo already contains them).
3. Copy the Git URL (HTTPS or SSH), for example:
   - `https://github.com/<your-username>/OpsSentinel.git`
   - or `git@github.com:<your-username>/OpsSentinel.git`

### 4.2 Set GitHub Actions Secrets
In your new GitHub repository:
1. Navigate to **Settings** > **Secrets and variables** > **Actions**.
2. Click **New repository secret**.
3. Add:
   - **Name**: `GEMINI_API_KEY`
   - **Value**: Your Google Gemini API Key.

---

## 5. Checkpoint Confirmation to Proceed

To trigger **PHASE 2: Autonomous Implementation**, please reply with:

```text
proceed <YOUR_GITHUB_REPO_URL>
```

*(Example: `proceed https://github.com/myusername/OpsSentinel.git`)*

Once received, OpsSentinel will autonomously:
- Bind git remote origin and push branch `main`.
- Ingest operational runbooks (`/docs`) into PostgreSQL with Gemini embeddings.
- Implement the agentic incident response loop with FastAPI and Gemini tool-calling (Vector search, System Diagnostics, n8n Webhook Dispatch).
- Execute comprehensive Pytest suites directly in WSL.
- Configure GitHub Actions CI and finalize production documentation.
