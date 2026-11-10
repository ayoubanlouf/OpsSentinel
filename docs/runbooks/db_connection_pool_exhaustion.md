# Operational Runbook: Database Connection Pool Exhaustion

## Service Information
- **Service Name**: Core PostgreSQL Cluster / Primary Connection Pooler
- **Severity**: P1 / High
- **Category**: Database & Data Infrastructure
- **Owning Team**: SRE & Database Infrastructure Team

---

## 1. Overview & Incident Description
Database connection pool exhaustion occurs when client services open more simultaneous connections to PostgreSQL or PgBouncer than the configured pool limits allow (`max_connections` or PgBouncer `max_client_conn`). New incoming requests fail to acquire a connection slot, causing widespread HTTP 500 errors across downstream APIs, transaction queue pileups, and cascading latency spikes.

---

## 2. Common Symptoms & Alert Triggers
- **Prometheus Alert**: `PostgresqlConnectionPoolSaturation` (> 90% connection usage).
- **Application Error Logs**:
  - `FATAL: remaining connection slots are reserved for non-replication superuser connections`
  - `psycopg.OperationalError: server closed the connection unexpectedly`
  - `timeout: pool exhausted, unable to checkout connection within 5000ms`
- **User Impact**: Ingestion APIs timing out, user logins failing with 500/503 status codes.

---

## 3. Diagnostic Procedures

### 3.1 Check Active Connection Counts by State
Connect to the database using the superuser pool or direct admin port:
```sql
SELECT state, count(*) 
FROM pg_stat_activity 
WHERE datname = 'opssentinel'
GROUP BY state 
ORDER BY count(*) DESC;
```

### 3.2 Identify Long-Running or Stuck Queries
Locate queries executing longer than 30 seconds:
```sql
SELECT pid, usename, client_addr, state, now() - query_start AS duration, query 
FROM pg_stat_activity 
WHERE state != 'idle' 
  AND (now() - query_start) > interval '30 seconds'
ORDER BY duration DESC;
```

### 3.3 Check PgBouncer Pool Status (if enabled)
Execute in the PgBouncer admin console (`psql -p 6432 -U pgbouncer pgbouncer`):
```sql
SHOW POOLS;
SHOW CLIENTS;
SHOW SERVERS;
```

---

## 4. Immediate Mitigation Steps

### Step 1: Terminate Idle in Transaction Sessions
Sessions left in `idle in transaction` often hold lock resources and leak connections:
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND (now() - state_change) > interval '5 minutes';
```

### Step 2: Cancel Runaway Queries
Terminate individual blocking queries that are saturating CPU/IO:
```sql
SELECT pg_cancel_backend(pid)
FROM pg_stat_activity
WHERE (now() - query_start) > interval '2 minutes'
  AND pid != pg_backend_pid();
```

### Step 3: Rolling Restart of Leaking Client Pods
If a specific microservice is identified as having a connection leak (e.g. `order-service` holding hundreds of connections):
```bash
kubectl rollout restart deployment/order-service -n production
```

### Step 4: Increase PgBouncer Client Limits (Emergency Hot-Patch)
If traffic volume is legitimate, edit `pgbouncer.ini`:
```ini
max_client_conn = 2000
default_pool_size = 50
reserve_pool_size = 10
```
Reload PgBouncer without dropping active sessions:
```bash
kill -HUP $(pgrep pgbouncer)
```

---

## 5. Long-Term Remediation
1. **Application Connection Management**: Configure strict client-side connection pooling using connection checkout timeouts (`pool_timeout=5s`) and maximum connection lifespans (`pool_recycle=1800s`).
2. **PostgreSQL Configuration**:
   - Set `idle_in_transaction_session_timeout = '60000ms'` in `postgresql.conf`.
   - Set `statement_timeout = '30000ms'` to prevent runaway queries from hanging indefinitely.
3. **Observability**: Add Prometheus alert rules for connection pool saturation at 75% (warning) and 90% (critical).

---

## 6. Escalation Matrix
- **L1 / On-Call SRE**: Execute steps 3.1 through 4.2 within 5 minutes of page.
- **L2 / Database Admin (DBA)**: Escalate if terminating idle sessions does not clear slot saturation within 10 minutes.
- **Incident Commander**: Declare major incident if user-facing API failure rate exceeds 5% for > 5 minutes.
