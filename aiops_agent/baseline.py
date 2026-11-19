"""Transparent rule-based BASELINE (defined before looking at results).

 detection : any alert with severity >= warning => incident
 correlation: group alerts by service within 5 min
 RCA        : earliest alert's type -> fixed cause (latency_high->cpu_saturation, cpu_high->cpu_saturation,
              memory_high->memory_leak, pool_exhausted/db_conn_timeout->db_pool_exhaustion,
              error_rate_high->bad_deployment, dependency_unavailable->dependency_failure); top-1 only
 action     : fixed cause->action on the alerting service (same allowlist/executor), NO confidence
              gating, NO risk gating, NO verification: success is declared if the command returned ok.
"""
from . import ingestion, correlation, actions
from .generator import ACTION_FOR_CAUSE
from .config import CFG

RULE = {"cpu_high": "cpu_saturation", "latency_high": "cpu_saturation", "memory_high": "memory_leak",
        "pool_exhausted": "db_pool_exhaustion", "db_conn_timeout": "db_pool_exhaustion",
        "error_rate_high": "bad_deployment", "dependency_unavailable": "dependency_failure"}


def run_baseline(case):
    c = ingestion.normalize_case(case)
    alerts = [a for a in c["alerts"] if a["severity"] in ("warning", "critical")]
    s = dict(case=c, trace=[], groups=correlation.correlate_by_service(c["alerts"]))
    if not alerts:
        s["status"] = "no_incident"
        return s
    first = min(alerts, key=lambda a: a["ts"])
    cause = RULE[first["error_type"]]
    act = ACTION_FOR_CAUSE[cause]
    prop = dict(action=act, target=first["service"], params=actions.DEFAULT_PARAMS.get(act, {}), environment="sandbox")
    s.update(cause=cause, proposal=prop, first_alert_ts=first["ts"])
    try:
        s["exec"] = actions.execute(prop, c, approved=True)   # baseline has no approval gate
        s["status"] = "resolved"                               # claimed, never verified
    except Exception as e:
        s["status"], s["escalation_reason"] = "escalated", type(e).__name__
    return s
