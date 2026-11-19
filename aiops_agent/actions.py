"""Allowlisted remediation actions, policy validation and SIMULATED execution.

SAFETY: no shell is ever invoked. An action is a name from ACTIONS plus a target and
numeric params. Anything else (including LLM-written commands) is rejected by policy.
Only mode='simulate' is implemented; live execution deliberately raises.
"""
import re
from dataclasses import dataclass
from .config import CFG

APP = {"api-gateway", "payment-service", "order-service", "auth-service"}
ACTIONS = {
    "scale_out_replicas": dict(risk="low", approval=False, targets=APP, params={"replicas": (1, 5)}),
    "restart_service": dict(risk="medium", approval=False, targets=APP | {"cache-redis"}, params={}),
    "increase_db_pool_size": dict(risk="low", approval=False, targets={"db-primary"}, params={"pool_size": (10, 200)}),
    "clear_cache": dict(risk="low", approval=False, targets={"cache-redis"}, params={}),
    "rollback_deployment": dict(risk="high", approval=True, targets=APP, params={}),
    # live sandbox action: pauses the CPU workers of our own stress-app (127.0.0.1 only)
    "throttle_workload": dict(risk="low", approval=False, targets={"stress-app"}, params={}),
}
CONTROL_URL = "http://127.0.0.1:9100"
DEFAULT_PARAMS = {"scale_out_replicas": {"replicas": 2}, "increase_db_pool_size": {"pool_size": 100}}


class ActionUnavailable(RuntimeError):
    pass


@dataclass
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    risk: str
    reason: str


def validate(proposal):
    """proposal: dict(action, target, params, environment). Returns PolicyDecision."""
    act, tgt = proposal.get("action"), proposal.get("target")
    params, env = proposal.get("params") or {}, proposal.get("environment", "sandbox")
    if not isinstance(act, str) or not re.fullmatch(r"[a-z_]+", act):
        return PolicyDecision(False, False, "blocked", "action is not a plain identifier (possible command)")
    if act not in ACTIONS:
        return PolicyDecision(False, False, "blocked", f"action '{act}' not in allowlist")
    spec = ACTIONS[act]
    if env != "sandbox":
        return PolicyDecision(False, False, "blocked", f"environment '{env}' not permitted")
    if tgt not in spec["targets"]:
        return PolicyDecision(False, False, "blocked", f"target '{tgt}' not allowed for {act}")
    for k, v in params.items():
        if k not in spec["params"]:
            return PolicyDecision(False, False, "blocked", f"unknown parameter '{k}'")
        lo, hi = spec["params"][k]
        if not isinstance(v, (int, float)) or not lo <= v <= hi:
            return PolicyDecision(False, False, "blocked", f"parameter {k}={v} outside [{lo},{hi}]")
    return PolicyDecision(True, spec["approval"], spec["risk"],
                          "approval required" if spec["approval"] else "allowed")


def simulated_post_mode(case, action, target):
    """Which post-action measurement series the simulated environment returns."""
    if action == case["permitted_action"] and target == case["action_target"]:
        return case["post_mode"]
    return "unfixed"


def execute(proposal, case, approved=False):
    """Simulated execution. Returns dict(exec_ok, detail, duration_s, post_metrics, post_mode).
    exec_ok only means 'the simulated command returned success' -- NOT that the incident is fixed."""
    if CFG.mode != "simulate":
        raise NotImplementedError("Only simulate mode is implemented (no production changes).")
    d = validate(proposal)
    if not d.allowed:
        raise PermissionError(d.reason)
    if d.requires_approval and not approved:
        raise PermissionError("human approval required")
    if not case.get("action_available", True):
        raise ActionUnavailable(f"{proposal['action']} unavailable (e.g. capacity/quota limit)")
    mode = simulated_post_mode(case, proposal["action"], proposal["target"])
    return dict(exec_ok=True, detail=f"[SIMULATED] {proposal['action']} on {proposal['target']}",
                duration_s=CFG.action_duration_s[proposal["action"]], post_mode=mode,
                post_metrics=case["post"][mode])


def live_execute(proposal, approved=False):
    """REAL execution, but only for the allowlisted `throttle_workload` on our own local stress-app.
    Same policy check as the simulator; no shell, no other target, localhost only."""
    import urllib.request
    d = validate(proposal)
    if not d.allowed:
        raise PermissionError(d.reason)
    if d.requires_approval and not approved:
        raise PermissionError("human approval required")
    if proposal["action"] != "throttle_workload":
        raise NotImplementedError("only throttle_workload has a live implementation")
    req = urllib.request.Request(CONTROL_URL + "/mitigate", data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=2) as r:
        body = r.read().decode()
    return dict(exec_ok=True, detail=f"[LIVE sandbox] throttle_workload on stress-app -> {body}", duration_s=0)