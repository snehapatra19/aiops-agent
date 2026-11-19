"""Evidence-driven RCA: weighted evidence scoring + softmax relative support.

confidence(c) = exp(score_c) / sum_k exp(score_k)  -> "relative support among the five
candidate causes". It is NOT a calibrated probability. Escalate if top confidence <
CFG.conf_min or (top - second) < CFG.margin_min.
"""
import math
import re
from dataclasses import dataclass, field
from .config import CFG
from .topology import DEPENDS_ON

CAUSES = ["cpu_saturation", "db_pool_exhaustion", "memory_leak", "dependency_failure", "bad_deployment"]
NEXT_STEP = {
    "cpu_saturation": "Inspect per-pod CPU and recent traffic; confirm autoscaling headroom.",
    "db_pool_exhaustion": "Check active DB connections and pool settings on db-primary.",
    "memory_leak": "Capture heap profile and check memory growth trend over the last hours.",
    "dependency_failure": "Check health/readiness of the suspected downstream service.",
    "bad_deployment": "Compare error rate before/after the latest deployment; review release diff."}
RESOURCE = {"cpu", "mem", "pool_util"}


@dataclass
class RCAResult:
    ranked: list                 # [(cause, confidence)]
    top_cause: str
    confidence: float
    margin: float
    root_service: str
    evidence: dict               # cause -> [feature strings]
    missing: list
    next_step: str
    uncertain: bool
    method: str = "deterministic"


def _count(logs, pattern):
    rx = re.compile(pattern, re.I)
    return sum(1 for l in logs if rx.search(l["message"]))


def collect_evidence(case, anomalies, group_alerts):
    """Evidence collection tool: gathers logs/traces/events relevant to the incident."""
    logs = case.get("logs", [])
    traces = case.get("traces", [])
    events = case.get("events", [])
    return dict(logs=[l for l in logs if l["level"] != "INFO"], traces=traces, events=events,
                alert_types=sorted({a["error_type"] for a in group_alerts}))


def score_causes(anomalies, ev, step_s=CFG.step_s):
    A = {(a.service, a.metric): a for a in anomalies}
    by_metric = lambda m: [a for a in anomalies if a.metric == m]
    resource_anoms = [a for a in anomalies if a.metric in RESOURCE]
    err_svcs = {a.service for a in by_metric("error_rate")}
    lat = by_metric("latency_ms")
    logs, traces = ev["logs"], ev["traces"]
    kinds = [t["dominant_kind"] for t in traces]
    top_kind = max(set(kinds), key=kinds.count) if kinds else None
    S = {c: 0.0 for c in CAUSES}
    E = {c: [] for c in CAUSES}

    def add(c, w, why):
        S[c] += w
        E[c].append(f"+{w}: {why}")

    if by_metric("cpu"): add("cpu_saturation", 2.0, "CPU anomaly on " + by_metric("cpu")[0].service)
    if _count(logs, r"cpu throttl"): add("cpu_saturation", 1.5, "log: CPU throttling")
    if top_kind == "compute": add("cpu_saturation", 1.0, "trace: dominant span is compute")
    if lat: add("cpu_saturation", 0.5, "latency symptom present")

    if by_metric("pool_util"): add("db_pool_exhaustion", 2.0, "DB pool utilisation anomaly")
    if _count(logs, r"pool exhausted|too many connections|connection timeout"):
        add("db_pool_exhaustion", 1.5, "log: DB connection timeout/pool exhausted")
    if top_kind == "db": add("db_pool_exhaustion", 1.0, "trace: dominant span is DB")
    if any(a.service in ("payment-service", "order-service") for a in lat):
        add("db_pool_exhaustion", 0.5, "latency on a DB-dependent service")

    if by_metric("mem"): add("memory_leak", 2.0, "memory anomaly on " + by_metric("mem")[0].service)
    if _count(logs, r"GC overhead|OutOfMemory"): add("memory_leak", 1.5, "log: GC/OOM")
    if top_kind == "gc": add("memory_leak", 1.0, "trace: dominant span is GC")
    if lat: add("memory_leak", 0.5, "latency symptom present")

    if _count(logs, r"503 from|upstream connect error|circuit breaker"):
        add("dependency_failure", 1.5, "log: upstream 503 / circuit breaker")
    if "dependency_unavailable" in ev["alert_types"]:
        add("dependency_failure", 1.0, "alert: dependency_unavailable")
    if len(err_svcs) >= 2 and not resource_anoms:
        add("dependency_failure", 1.0, "errors on >=2 services, no resource anomaly")
    if lat: add("dependency_failure", 0.5, "latency symptom present")

    onset = min((a.onset_idx for a in anomalies), default=None)
    dep = [e for e in ev["events"] if e["type"] == "deployment"]
    if dep and onset is not None and any(0 <= (onset * step_s + 1_761_000_000.0) - e["ts"] <= 600 for e in dep):
        add("bad_deployment", 2.0, f"deployment on {dep[-1]['service']} {dep[-1]['version']} shortly before onset")
    if _count(logs, r"NullPointer|ValidationError|schema mismatch"):
        add("bad_deployment", 1.5, "log: new exception types")
    if err_svcs and not resource_anoms:
        add("bad_deployment", 1.0, "error-rate anomaly without resource anomaly")
    return S, E


def root_service_for(cause, anomalies, ev):
    pick = lambda m: max((a for a in anomalies if a.metric == m), key=lambda a: a.peak_z, default=None)
    if cause == "cpu_saturation":
        a = pick("cpu"); return a.service if a else (pick("latency_ms").service if pick("latency_ms") else "unknown")
    if cause == "db_pool_exhaustion":
        return "db-primary"
    if cause == "memory_leak":
        a = pick("mem"); return a.service if a else (pick("latency_ms").service if pick("latency_ms") else "unknown")
    if cause == "dependency_failure":
        for l in ev["logs"]:
            m = re.search(r"503 from (\S+)", l["message"])
            if m: return m.group(1)
        errs = [t["error_span_service"] for t in ev["traces"] if t.get("error_span_service")]
        return errs[0] if errs else "unknown"
    if cause == "bad_deployment":
        dep = [e for e in ev["events"] if e["type"] == "deployment"]
        if dep: return dep[-1]["service"]
        a = pick("error_rate"); return a.service if a else "unknown"
    return "unknown"


def run_rca(anomalies, ev):
    S, E = score_causes(anomalies, ev)
    z = sum(math.exp(v) for v in S.values())
    conf = {c: math.exp(S[c]) / z for c in CAUSES}
    ranked = sorted(conf.items(), key=lambda kv: (-kv[1], kv[0]))
    (c1, p1), (_, p2) = ranked[0], ranked[1]
    missing = []
    if not ev["logs"]: missing.append("no error/warn logs retrieved")
    if not ev["traces"]: missing.append("no trace summaries retrieved")
    if not any(a.metric in RESOURCE for a in anomalies): missing.append("no resource-metric anomaly (cpu/mem/pool)")
    uncertain = p1 < CFG.conf_min or (p1 - p2) < CFG.margin_min
    return RCAResult(ranked=[(c, round(p, 4)) for c, p in ranked], top_cause=c1, confidence=round(p1, 4),
                     margin=round(p1 - p2, 4), root_service=root_service_for(c1, anomalies, ev),
                     evidence=E, missing=missing, next_step=NEXT_STEP[c1], uncertain=uncertain)
