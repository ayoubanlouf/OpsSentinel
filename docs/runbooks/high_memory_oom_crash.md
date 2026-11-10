# Operational Runbook: High Memory & OOM (Out-of-Memory) Crashes

## Service Information
- **Service Name**: Production API & Worker Workloads
- **Severity**: P1 / P2
- **Category**: Compute Infrastructure & Node Health
- **Owning Team**: Core Platform Engineering & SRE

---

## 1. Overview & Incident Description
An Out-Of-Memory (OOM) incident occurs when a container or process exceeds its allocated cgroup memory limit (`resources.limits.memory`) or when the host kernel encounters severe memory pressure and invokes the Linux OOM Killer. The kernel terminates the highest `oom_score` process, leading to container exit code 137 (`SIGKILL`), abrupt service disruption, dropped in-flight requests, and restart loops (CrashLoopBackOff).

---

## 2. Common Symptoms & Alert Triggers
- **Prometheus Alert**: `ContainerOOMKilled` or `KubePodMemoryUsageExceeded` (> 95% allocated limit).
- **Kubernetes Events**:
  - `Last State: Terminated with exit code 137, Reason: OOMKilled`
  - `Warning Evicted Node has insufficient memory available`
- **Application Logs**:
  - `java.lang.OutOfMemoryError: Java heap space` (JVM workloads)
  - `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory` (Node.js)
  - Process killed silently without traceback in Python/Go processes.

---

## 3. Diagnostic Procedures

### 3.1 Verify Container Exit Codes and Termination Reason
Run via `kubectl` to inspect the failing pod:
```bash
kubectl get pods -n production -l app=api-gateway -o wide
kubectl describe pod <pod-name> -n production | grep -E "(OOMKilled|Exit Code|Limits|Requests)"
```

### 3.2 Inspect Real-Time Memory Consumption
Check live resource utilization across pods and nodes:
```bash
# Check pod memory
kubectl top pod -n production --sort-by=memory

# Check node memory pressure
kubectl top nodes
```

### 3.3 Inspect Kernel Logs for OOM Killer Invocations
If running directly on VMs or bare-metal:
```bash
dmesg -T | grep -i -E "(oom|out of memory|killed process)"
```

### 3.4 Analyze Recent Traffic Spikes or Large Ingestion Payloads
Inspect ingress request sizes or queue backlogs:
```bash
# Check message queue depth
rabbitmqctl list_queues name messages_ready consumers
```

---

## 4. Immediate Mitigation Steps

### Step 1: Scale Pod Replicas to Distribute Load
Distributing traffic across more pods reduces individual pod working memory:
```bash
kubectl scale deployment/api-gateway -n production --replicas=8
```

### Step 2: Emergency Hot-Patch of Pod Memory Limits
If the workload legitimately requires more working memory under current load:
```bash
kubectl patch deployment api-gateway -n production -p '
{
  "spec": {
    "template": {
      "spec": {
        "containers": [
          {
            "name": "api-gateway",
            "resources": {
              "limits": {"memory": "4Gi"},
              "requests": {"memory": "2Gi"}
            }
          }
        ]
      }
    }
  }
}'
```

### Step 3: Roll Back Suspect Deployments
If memory growth began immediately following a recent release:
```bash
kubectl rollout undo deployment/api-gateway -n production
```

### Step 4: Clear or Isolate High-Volume Processing Queues
Temporarily throttle incoming worker queue consumption or drain poison-pill messages into a dead-letter queue (DLQ).

---

## 5. Long-Term Remediation
1. **Profiling & Heap Dumps**:
   - Collect memory profile (`py-spy`, `pprof`, or JVM heap dump) to locate memory leaks, circular object references, or unclosed buffer streams.
2. **Streaming and Pagination**:
   - Enforce pagination on all database queries and streaming parsing on file upload endpoints (`python-multipart` chunking).
3. **Autoscaling Configuration**:
   - Configure Kubernetes Horizontal Pod Autoscaler (HPA) targeting average memory utilization at 70%.

---

## 6. Escalation Matrix
- **L1 / On-Call SRE**: Triage within 5 minutes. Execute scaling and memory limit bump.
- **L2 / Application Owner**: Escalate if memory leak persists across rolled back deployments.
- **Incident Commander**: Declare incident if restart loops cause service unavailability.

