"""Prometheus-compatible operational metrics collector for OpsSentinel."""

import threading
import time
from collections import Counter

_lock = threading.Lock()

# Metric store
_tool_invocations: Counter[str] = Counter()
_incident_triaged: Counter[tuple[str, str]] = Counter()  # (severity, status)
_n8n_dispatches: Counter[str] = Counter()  # status
_incident_durations: list[float] = []
_start_time = time.time()


def record_tool_metric(tool_name: str) -> None:
    """Increment invocation count for an agentic tool."""
    with _lock:
        _tool_invocations[tool_name] += 1


def record_dispatch_metric(status: str) -> None:
    """Record n8n alert dispatch status (e.g., success, failure)."""
    with _lock:
        _n8n_dispatches[status] += 1


def record_incident_metric(severity: str, status: str, duration: float) -> None:
    """Record triaged incident metrics including severity, status, and latency."""
    with _lock:
        _incident_triaged[(severity.upper(), status.upper())] += 1
        _incident_durations.append(duration)
        if len(_incident_durations) > 1000:
            _incident_durations.pop(0)


def format_prometheus_metrics() -> str:
    """Format stored metrics into standard Prometheus exposition format."""
    lines: list[str] = []

    # Uptime
    uptime = time.time() - _start_time
    lines.append("# HELP opssentinel_uptime_seconds Process uptime in seconds")
    lines.append("# TYPE opssentinel_uptime_seconds gauge")
    lines.append(f"opssentinel_uptime_seconds {uptime:.2f}")

    # Tool invocations
    lines.append("# HELP opssentinel_tool_invocations_total Total agent tool calls")
    lines.append("# TYPE opssentinel_tool_invocations_total counter")
    with _lock:
        for tool, count in _tool_invocations.items():
            lines.append(f'opssentinel_tool_invocations_total{{tool="{tool}"}} {count}')

        # Incidents
        lines.append("# HELP opssentinel_incidents_total Total incidents triaged")
        lines.append("# TYPE opssentinel_incidents_total counter")
        for (sev, stat), count in _incident_triaged.items():
            lines.append(f'opssentinel_incidents_total{{severity="{sev}",status="{stat}"}} {count}')

        # Dispatches
        lines.append("# HELP opssentinel_n8n_dispatches_total Total n8n alerts dispatched")
        lines.append("# TYPE opssentinel_n8n_dispatches_total counter")
        for stat, count in _n8n_dispatches.items():
            lines.append(f'opssentinel_n8n_dispatches_total{{status="{stat}"}} {count}')

        # Latency
        lines.append("# HELP opssentinel_incident_duration_seconds_avg Average incident triage duration")
        lines.append("# TYPE opssentinel_incident_duration_seconds_avg gauge")
        avg_duration = sum(_incident_durations) / len(_incident_durations) if _incident_durations else 0.0
        lines.append(f"opssentinel_incident_duration_seconds_avg {avg_duration:.3f}")

    return "\n".join(lines) + "\n"
