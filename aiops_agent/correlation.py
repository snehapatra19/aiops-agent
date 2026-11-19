"""Alert correlation: transparent rule-based linking + union-find.

Two alerts are linked when the time gap <= window AND one of:
  R1 same service
  R2 adjacent services (call-graph edge) AND (shared trace_id OR same error type OR
     propagation: resource alert on a callee + service-level alert on its caller OR
     service-level alert on callee + service-level alert on its caller)
Alerts that satisfy none stay in separate groups. Duplicates (R1, same type) merge.
"""
from .config import CFG
from .topology import RESOURCE_TYPES, SERVICE_TYPES, depends_on, adjacent


def _propagates(a, b):
    """a on callee, b on caller: does a plausibly cause b?"""
    if not depends_on(b["service"], a["service"]):
        return False
    return (a["error_type"] in RESOURCE_TYPES | SERVICE_TYPES) and b["error_type"] in SERVICE_TYPES


def linked(a, b, window=None):
    if abs(a["ts"] - b["ts"]) > (window or CFG.corr_window_s):
        return None
    if a["service"] == b["service"]:
        return "R1_same_service"
    if adjacent(a["service"], b["service"]):
        if a.get("trace_id") and a.get("trace_id") == b.get("trace_id"):
            return "R2_shared_trace"
        if a["error_type"] == b["error_type"]:
            return "R2_same_type"
        if _propagates(a, b) or _propagates(b, a):
            return "R2_propagation"
    return None


def correlate(alerts, window=None):
    parent = list(range(len(alerts)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(len(alerts)):
        for j in range(i + 1, len(alerts)):
            if linked(alerts[i], alerts[j], window):
                parent[find(i)] = find(j)
    groups = {}
    for i, a in enumerate(alerts):
        groups.setdefault(find(i), []).append(a["alert_id"])
    return sorted(groups.values(), key=lambda g: g[0])


def correlate_by_service(alerts, window=300):
    """BASELINE: group alerts by service within a 5-minute window (no topology)."""
    parent = list(range(len(alerts)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(len(alerts)):
        for j in range(i + 1, len(alerts)):
            if alerts[i]["service"] == alerts[j]["service"] and abs(alerts[i]["ts"] - alerts[j]["ts"]) <= window:
                parent[find(i)] = find(j)
    g = {}
    for i, a in enumerate(alerts):
        g.setdefault(find(i), []).append(a["alert_id"])
    return sorted(g.values(), key=lambda x: x[0])
