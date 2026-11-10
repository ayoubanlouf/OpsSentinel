# Operational Runbook: API 504 Gateway Timeout

## Service Information
- **Service Name**: Ingress Gateway & Edge Reverse Proxy
- **Severity**: P1 / High
- **Category**: Networking, Gateway Routing & Upstream Latency
- **Owning Team**: Core Platform & Backend SRE

---

## 1. Overview & Incident Description
An HTTP 504 Gateway Timeout error occurs when an edge proxy or API gateway (such as NGINX Ingress, Envoy, or AWS ALB) sends a request to an upstream backend service, but does not receive a response within the configured proxy timeout window (typically 30s or 60s). This indicates that the downstream backend application is hanging, stalled by deadlocks, overwhelmed with processing, or stalled waiting on third-party dependencies.

---

## 2. Common Symptoms & Alert Triggers
- **Prometheus Alert**: `High5xxErrorRate` (> 2% total traffic) or `IngressUpstreamResponseTimeHigh` (p99 > 15s).
- **Client Status Codes**: `HTTP/1.1 504 Gateway Time-out` returned to web and mobile clients.
- **Ingress Controller Logs**:
  - `[error] 142#142: *894101 upstream timed out (110: Connection timed out) while reading response header from upstream, client: 198.51.100.24, server: api.opssentinel.io, request: "POST /v1/transactions HTTP/2.0", upstream: "http://10.244.2.15:8000"`

---

## 3. Diagnostic Procedures

### 3.1 Trace Latencies in Ingress Logs
Extract the slowest upstream endpoints and IP addresses:
```bash
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=500 | \
  grep " 504 " | \
  awk '{print $7, $9, $11}' | sort | uniq -c | sort -nr
```

### 3.2 Check Upstream Service Health & Resource Contention
Check if upstream backend pods are CPU throttled or experiencing high garbage collection pause times:
```bash
# Check CPU throttling on upstream pods
kubectl top pod -n production -l app=backend-api

# Check backend application logs for deadlock or timeouts
kubectl logs -n production -l app=backend-api --tail=200 --prefix | grep -i -E "(timeout|deadlock|slow query|blocked)"
```

### 3.3 Verify Database and External Dependency Latency
Check if the bottleneck is in PostgreSQL queries or third-party external webhooks:
```sql
SELECT query, calls, total_exec_time, mean_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 5;
```

---

## 4. Immediate Mitigation Steps

### Step 1: Temporarily Increase Ingress Proxy Timeout (Hot-Patch)
If the upstream process is legitimately executing long queries that can be tolerated temporarily:
```bash
kubectl annotate ingress opssentinel-api -n production --overwrite \
  nginx.ingress.kubernetes.io/proxy-connect-timeout="120" \
  nginx.ingress.kubernetes.io/proxy-read-timeout="120" \
  nginx.ingress.kubernetes.io/proxy-send-timeout="120"
```

### Step 2: Enable Circuit Breakers / Degraded Fallbacks
If a specific third-party integration is hanging upstream requests:
- Toggle feature flag `DISABLE_EXTERNAL_ENRICHMENT=true` in backend config.
- Force immediate return of cached or degraded responses.

### Step 3: Drain & Restart Stalled Backend Pods
If threads or event loops are permanently blocked:
```bash
kubectl rollout restart deployment/backend-api -n production
```

### Step 4: Scale Out Backend Pod Replicas
If the timeout is caused by request queuing due to worker pool saturation:
```bash
kubectl scale deployment/backend-api -n production --replicas=12
```

---

## 5. Long-Term Remediation
1. **Asynchronous Processing**: Offload any processing taking > 2 seconds to background worker queues (Celery, ARQ, or Kafka) and return HTTP 202 Accepted.
2. **Strict Client Timeouts**: Ensure all outgoing HTTP client requests from backend services configure explicit socket timeouts (`timeout=5.0s`).
3. **Distributed Tracing**: Implement OpenTelemetry tracing to track downstream dependency latency breakdowns.

---

## 6. Escalation Matrix
- **L1 / On-Call SRE**: Acknowledge alert within 3 minutes; identify offending route and restart degraded pods.
- **L2 / Backend Team Lead**: Escalate within 15 minutes if timeouts stem from database deadlocks or logic regressions.
- **Incident Commander**: Escalate to Sev-1 if > 10% of revenue-critical endpoints return 504.

