"""Stateful incident workflow. Uses LangGraph StateGraph when installed, otherwise an
equivalent explicit state machine (same nodes, same routing) is used.

detect -> correlate -> evidence -> rca -> plan -> execute -> verify -> report
                 (escalate branch from detect-less, plan, execute, verify)
"""
import time
from .config import CFG
from . import ingestion, detection, correlation, rca as rca_mod, actions, verification

try:
    from langgraph.graph import StateGraph, END
    HAVE_LANGGRAPH = True
except Exception:  # pragma: no cover
    HAVE_LANGGRAPH = False


def _log(s, node, msg):
    s["trace"].append(dict(node=node, msg=msg))


def n_detect(s):
    s["anomalies"] = detection.detect(s["case"]["metrics"])
    _log(s, "detect", f"{len(s['anomalies'])} sustained anomalies")
    return s


def n_correlate(s):
    alerts = s["case"]["alerts"]
    s["groups"] = correlation.correlate(alerts)
    svcs = {a.service for a in s["anomalies"]}
    amap = {a["alert_id"]: a for a in alerts}
    best, bs = [], -1
    for g in s["groups"]:
        sc = sum(1 for i in g if amap[i]["service"] in svcs)
        if sc > bs or (sc == bs and len(g) > len(best)):
            best, bs = g, sc
    s["incident_alerts"] = [amap[i] for i in best] if bs > 0 else []
    s["incident_id"] = f"INC-{s['case']['case_id']}"
    _log(s, "correlate", f"{len(alerts)} alerts -> {len(s['groups'])} groups; incident has {len(s['incident_alerts'])} alerts")
    return s


def n_evidence(s):
    s["evidence"] = rca_mod.collect_evidence(s["case"], s["anomalies"], s["incident_alerts"])
    _log(s, "evidence", f"{len(s['evidence']['logs'])} logs, {len(s['evidence']['traces'])} traces")
    return s


def n_rca(s):
    s["rca"] = rca_mod.run_rca(s["anomalies"], s["evidence"])
    r = s["rca"]
    _log(s, "rca", f"top={r.top_cause} conf={r.confidence} margin={r.margin} uncertain={r.uncertain}")
    return s


def n_plan(s):
    r = s["rca"]
    if r.uncertain:
        s["escalation_reason"] = "uncertain_rca"
        return s
    act = {"cpu_saturation": "scale_out_replicas", "db_pool_exhaustion": "increase_db_pool_size",
           "memory_leak": "restart_service", "dependency_failure": "restart_service",
           "bad_deployment": "rollback_deployment"}[r.top_cause]
    prop = dict(action=act, target=r.root_service, params=actions.DEFAULT_PARAMS.get(act, {}), environment="sandbox")
    d = actions.validate(prop)
    s["proposal"], s["policy"] = prop, d
    _log(s, "plan", f"{act} on {r.root_service}: {d.reason} (risk={d.risk})")
    if not d.allowed:
        s["escalation_reason"] = "policy_blocked"
    elif d.requires_approval:
        s["escalation_reason"] = "high_risk_requires_approval"
    return s


def n_execute(s):
    try:
        s["exec"] = actions.execute(s["proposal"], s["case"])
        _log(s, "execute", s["exec"]["detail"])
    except actions.ActionUnavailable as e:
        s["escalation_reason"] = "action_unavailable"; _log(s, "execute", str(e))
    except Exception as e:
        s["escalation_reason"] = "execution_error"; _log(s, "execute", repr(e))
    return s


def n_verify(s):
    s["verification"] = verification.verify(s["case"], s["anomalies"], s["exec"]["post_metrics"])
    o = s["verification"]["overall"]
    _log(s, "verify", o)
    if o == "unresolved":
        s["escalation_reason"] = "verification_failed"
    elif o == "inconclusive":
        s["escalation_reason"] = "verification_inconclusive"
    return s


def n_escalate(s):
    s["status"] = "escalated"
    _log(s, "escalate", s.get("escalation_reason", "unknown"))
    return s


def n_report(s):
    if "status" not in s:
        s["status"] = "no_incident" if not s["anomalies"] else "resolved"
    _log(s, "report", s["status"])
    return s


def r_detect(s): return "report" if not s["anomalies"] else "correlate"
def r_plan(s): return "escalate" if s.get("escalation_reason") else "execute"
def r_exec(s): return "escalate" if s.get("escalation_reason") else "verify"
def r_verify(s): return "escalate" if s.get("escalation_reason") else "report"


NODES = dict(detect=n_detect, correlate=n_correlate, evidence=n_evidence, rca=n_rca, plan=n_plan,
             execute=n_execute, verify=n_verify, escalate=n_escalate, report=n_report)
LINEAR = {"correlate": "evidence", "evidence": "rca", "rca": "plan", "escalate": "report"}
ROUTERS = {"detect": r_detect, "plan": r_plan, "execute": r_exec, "verify": r_verify}


def _build_langgraph():
    g = StateGraph(dict)
    for k, f in NODES.items():
        g.add_node(k, f)
    g.set_entry_point("detect")
    for a, b in LINEAR.items():
        g.add_edge(a, b)
    for a, fn in ROUTERS.items():
        g.add_conditional_edges(a, fn)
    g.add_edge("report", END)
    return g.compile()


_GRAPH = _build_langgraph() if HAVE_LANGGRAPH else None


def run_incident(case, use_langgraph=True):
    t0 = time.perf_counter()
    s = dict(case=ingestion.normalize_case(case), trace=[])
    if HAVE_LANGGRAPH and use_langgraph:
        s = _GRAPH.invoke(s)
        engine = "langgraph"
    else:
        node, engine = "detect", "state_machine"
        while True:
            s = NODES[node](s)
            if node == "report":
                break
            node = ROUTERS[node](s) if node in ROUTERS else LINEAR[node]
    s["engine"], s["wall_ms"] = engine, round((time.perf_counter() - t0) * 1000, 2)
    return s
