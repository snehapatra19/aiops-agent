"""Live machine monitor: REAL telemetry (psutil) -> detect -> evidence -> RCA -> policy -> REAL sandbox action
-> verify from REAL measurements -> escalate or close -> save to SQLite.

Scope (be honest in the viva): it monitors this machine's CPU, the only action is `throttle_workload`
on our own local stress-app (127.0.0.1), nothing else is ever touched.
"""
import json
import math
import threading
import time
import urllib.request
from collections import deque
from statistics import median

import psutil

from . import actions, store
from .config import CFG
from .detection import baseline_stats, detect_series

STATUS_URL = actions.CONTROL_URL + "/status"
CAUSES = ["workload_overload", "unattributed_cpu_load"]


def _top_procs(n=3):
    procs = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)
            procs.append(p)
        except Exception:
            pass
    time.sleep(0.5)
    out = []
    for p in procs:
        try:
            if p.info["name"] in ("System Idle Process", "Idle"):
                continue
            out.append(dict(pid=p.info["pid"], name=p.info["name"], cpu=p.cpu_percent(None)))
        except Exception:
            pass
    return sorted(out, key=lambda x: -x["cpu"])[:n]


def _control_status():
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=1) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _softmax(scores):
    z = sum(math.exp(v) for v in scores.values())
    return {k: math.exp(v) / z for k, v in scores.items()}


class LiveMonitor:
    def __init__(self, interval=1.0):
        self.interval = interval
        self.samples = deque(maxlen=400)
        self.base = []
        self.state = "stopped"
        self.running = False
        self.incident = None
        self.last_incident = None
        self._since_refresh = 0
        self.count = 0
        self._lock = threading.RLock()
        self._thread = None

    # ---------- control ----------
    def start(self):
        with self._lock:
            if self.running:
                return
            self.running, self.state, self.base, self.incident = True, "warming_up", [], None
            self.samples.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self.state = "stopped"

    def snapshot(self):
        with self._lock:
            s = list(self.samples)[-150:]
            b = None
            if len(self.base) >= CFG.baseline_points:
                med, sig = baseline_stats(self.base)
                b = dict(median=round(med, 1), sigma=round(sig, 2))
            return dict(running=self.running, state=self.state, samples=s, baseline=b,
                        incident=self.incident, last_incident=self.last_incident, interval=self.interval)

    # ---------- loop ----------
    def _loop(self):
        psutil.cpu_percent(None)
        while self.running:
            cpu, mem = psutil.cpu_percent(None), psutil.virtual_memory().percent
            try:
                with self._lock:
                    self._tick(cpu, mem)
            except Exception as e:  # never kill the monitor thread
                with self._lock:
                    self.state = f"error: {type(e).__name__}"
            time.sleep(self.interval)

    def _ev(self, node, msg):
        self.incident["timeline"].append(dict(t=time.time(), node=node, msg=msg))

    def _tick(self, cpu, mem):
        self.count += 1
        self.samples.append(dict(t=time.time(), cpu=round(cpu, 1), mem=round(mem, 1)))
        cpus = [x["cpu"] for x in self.samples]
        if self.state == "warming_up":
            if len(cpus) >= CFG.baseline_points:
                self.base = cpus[-CFG.baseline_points:]
                self.state = "monitoring"
        elif self.state == "monitoring":
            series = self.base[:CFG.baseline_points] + cpus[-15:]
            r = detect_series(series, "cpu")
            if r:
                self._open_incident(r)
            else:
                self._since_refresh += 1
                if self._since_refresh > 60 and max(cpus[-20:]) < 60:   # refresh baseline while calm
                    self.base, self._since_refresh = cpus[-CFG.baseline_points:], 0
        elif self.state == "acting_done":
            self._verify_step(cpus)
        elif self.state == "cooldown":
            if len(cpus) >= 12 and max(cpus[-12:]) < 60:
                self.base, self.state, self._since_refresh = cpus[-CFG.baseline_points:], "monitoring", 0

    # ---------- incident ----------
    def _open_incident(self, det):
        start, _, pz, peak = det
        self.incident = dict(incident_id=f"INC-LIVE-{int(time.time())}", source="live-sandbox", timeline=[],
                             symptoms=[dict(service="this-machine", metric="cpu", peak_z=round(pz, 1), peak_value=peak)])
        self.state = "investigating"
        self._ev("detect", f"CPU stayed abnormally high (peak {peak:.0f}%, z={pz:.1f})")
        # evidence (real): top processes + control-app status
        top = _top_procs()
        ctl = _control_status()
        pids = set(ctl["pids"]) if ctl else set()
        attributed = bool(pids) and sum(1 for p in top if p["pid"] in pids) >= 1
        self._ev("evidence", "top CPU processes: " + ", ".join(f"{p['name']}({p['pid']}) {p['cpu']:.0f}%" for p in top)
                 + ("; stress-app reachable" if ctl else "; stress-app NOT reachable"))
        # RCA (rule-based, same softmax idea as the main RCA)
        sc = {"workload_overload": 2.0 + (2.5 if attributed else 0.0),
              "unattributed_cpu_load": 2.0 + (0.0 if attributed else 1.5)}
        conf = _softmax(sc)
        ranked = sorted(conf.items(), key=lambda kv: -kv[1])
        top_c, p1 = ranked[0]
        margin = p1 - ranked[1][1]
        uncertain = p1 < CFG.conf_min or margin < CFG.margin_min
        self.incident["root_cause"] = dict(top=top_c, confidence=round(p1, 4), margin=round(margin, 4), uncertain=uncertain,
                                           ranked=[(c, round(p, 4)) for c, p in ranked], root_service="stress-app" if attributed else "unknown",
                                           evidence=[f"top processes: {[p['name'] for p in top]}", f"attributed to stress-app: {attributed}"],
                                           missing=[] if ctl else ["stress-app control API not reachable"],
                                           next_step="Inspect the top CPU process and decide whether to stop or limit it.")
        self._ev("rca", f"{top_c} (confidence {p1:.2f}, margin {margin:.2f})")
        if uncertain or top_c != "workload_overload":
            return self._finish("escalated", "uncertain_rca" if uncertain else "no_allowed_action_for_unattributed_load")
        prop = dict(action="throttle_workload", target="stress-app", params={}, environment="sandbox")
        d = actions.validate(prop)
        self.incident.update(action=prop, policy=vars(d))
        self._ev("plan", f"throttle_workload on stress-app: {d.reason} (risk={d.risk})")
        if not d.allowed or d.requires_approval:
            return self._finish("escalated", "policy_blocked" if not d.allowed else "high_risk_requires_approval")
        try:
            ex = actions.live_execute(prop)
        except Exception as e:
            self._ev("execute", f"failed: {type(e).__name__}: {e}")
            return self._finish("escalated", "execution_error")
        self.incident["execution"] = ex
        self._ev("execute", ex["detail"])
        self._act_idx = self.count
        self._pre_peak = median([x["cpu"] for x in list(self.samples)[-6:-1]] or [peak])
        self.state = "acting_done"

    def _verify_step(self, cpus):
        n = self.count - self._act_idx
        if n < 8:
            return
        med, _ = baseline_stats(self.base)
        cur = median(cpus[-CFG.verify_points:])
        ratio = (cur - med) / max(self._pre_peak - med, 1e-6)
        state = "resolved" if ratio <= CFG.resolved_ratio else "unresolved" if ratio >= CFG.unresolved_ratio else "inconclusive"
        if state == "resolved" or n >= 30:
            self.incident["verification"] = dict(overall=state, verify_window_s=n * self.interval,
                                                 series=[dict(service="this-machine", metric="cpu", state=state, ratio=round(ratio, 3),
                                                              baseline=round(med, 1), peak=round(self._pre_peak, 1), post=round(cur, 1))])
            self._ev("verify", f"re-measured real CPU: {state} ({cur:.0f}% vs baseline {med:.0f}%)")
            if state == "resolved":
                self._finish("resolved", None)
            else:
                self._finish("escalated", "verification_failed" if state == "unresolved" else "verification_inconclusive")

    def _finish(self, status, reason):
        if reason:
            self._ev("escalate", reason)
        self._ev("report", status)
        rep = dict(self.incident, final_status=status, escalation_reason=reason)
        store.save(rep, "live-sandbox")
        self.last_incident, self.incident = rep, None
        self.state = "cooldown"