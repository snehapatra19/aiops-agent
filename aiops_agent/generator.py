"""Labelled SYNTHETIC scenario generator (fixed seeds, reproducible).

Every record is synthetic. Ground truth (root cause, alert->incident membership,
permitted action, expected final status) is stored with each case.
"""
import hashlib
import json
import random
from .config import CFG
from .topology import (SERVICES, METRICS, PCT, BASE, LAT_SCALE, ALERT_RULES,
                       threshold, callers_of, adjacent)

T0 = 1_761_000_000.0
COMPOSITION = {  # 120 cases
    "normal": 20, "cpu_saturation": 14, "db_pool_exhaustion": 14, "memory_leak": 12,
    "dependency_failure": 14, "bad_deployment": 10, "ambiguous": 10,
    "missing_evidence": 8, "action_unavailable": 6, "failed_remediation": 8,
    "partial_recovery": 4}
CAUSES = ["cpu_saturation", "db_pool_exhaustion", "memory_leak",
          "dependency_failure", "bad_deployment"]
ACTION_FOR_CAUSE = {"cpu_saturation": "scale_out_replicas", "db_pool_exhaustion": "increase_db_pool_size",
                    "memory_leak": "restart_service", "dependency_failure": "restart_service",
                    "bad_deployment": "rollback_deployment"}


def _clip(metric, v):
    v = max(0.0, v)
    return min(v, 100.0) if metric in PCT else v


def _series(rng, svc, metric, n):
    mu, sd = BASE[metric]
    if metric == "latency_ms":
        s = LAT_SCALE.get(svc, 1.0)
        mu, sd = mu * s, sd * s
    return [_clip(metric, rng.gauss(mu, sd)) for _ in range(n)]


def _inject(series, metric, onset, delta, ramp):
    for i in range(onset, len(series)):
        frac = min(1.0, (i - onset + 1) / ramp)
        series[i] = _clip(metric, series[i] + delta * frac)


def _lat(svc, x):  # scale latency deltas to the service
    return x * LAT_SCALE.get(svc, 1.0)


def cause_spec(cause, rng, svc=None):
    """Return injections/logs/traces/action for one root cause."""
    if cause == "cpu_saturation":
        svc = svc or rng.choice(["payment-service", "order-service", "api-gateway", "auth-service"])
        inj = [(svc, "cpu", 55, 1), (svc, "latency_ms", 450, 1)]
        for up in callers_of(svc)[:1]:
            inj.append((up, "latency_ms", 300, 1))
        return dict(inj=inj, logs=[(svc, "WARN", "CPU throttling detected: cgroup nr_throttled increasing", 5),
                                   (svc, "WARN", "request queue length growing", 3)],
                    trace=("compute", svc, None), log_alerts=[], root_service=svc, target=svc, deploy=None)
    if cause == "db_pool_exhaustion":
        inj = [("db-primary", "pool_util", 55, 1), ("db-primary", "latency_ms", 90, 1),
               ("payment-service", "latency_ms", 500, 1), ("payment-service", "error_rate", 5.5, 1),
               ("api-gateway", "error_rate", 5.5, 1)]
        return dict(inj=inj, logs=[("payment-service", "ERROR", "Connection timeout: HikariPool-1 connection not available, pool exhausted", 6),
                                   ("db-primary", "ERROR", "FATAL: too many connections for role app", 4)],
                    trace=("db", "db-primary", None),
                    log_alerts=[("payment-service", "db_conn_timeout", "DB connection timeout burst")],
                    root_service="db-primary", target="db-primary", deploy=None)
    if cause == "memory_leak":
        svc = svc or rng.choice(["payment-service", "order-service", "auth-service", "api-gateway"])
        inj = [(svc, "mem", 48, 14), (svc, "latency_ms", 300, 14), (svc, "error_rate", 3, 14)]
        return dict(inj=inj, logs=[(svc, "WARN", "GC overhead limit approaching: heap 93% used", 5),
                                   (svc, "ERROR", "java.lang.OutOfMemoryError: Java heap space", 2)],
                    trace=("gc", svc, None), log_alerts=[], root_service=svc, target=svc, deploy=None)
    if cause == "dependency_failure":
        d = svc or rng.choice(["auth-service", "cache-redis"])
        callers = callers_of(d)
        inj = [(d, "error_rate", 60, 1)]
        for c in callers:
            inj += [(c, "error_rate", 9, 1), (c, "latency_ms", 400, 1)]
        if d == "cache-redis":
            inj.append((d, "latency_ms", 60, 1))
        inj.append(("api-gateway", "error_rate", 6, 1))
        logs = [(c, "ERROR", f"upstream connect error or disconnect: 503 from {d}", 5) for c in callers]
        logs += [(c, "WARN", f"circuit breaker open for {d}", 3) for c in callers]
        return dict(inj=inj, logs=logs, trace=("network", d, d),
                    log_alerts=[(c, "dependency_unavailable", f"{d} unreachable") for c in callers],
                    root_service=d, target=d, deploy=None)
    if cause == "bad_deployment":
        svc = svc or rng.choice(["payment-service", "order-service", "api-gateway", "auth-service"])
        inj = [(svc, "error_rate", 12, 1), (svc, "latency_ms", 250, 1)]
        ver = f"v{rng.randint(2, 4)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}"
        return dict(inj=inj, logs=[(svc, "ERROR", f"java.lang.NullPointerException at com.shop.{svc}.Handler.process", 6),
                                   (svc, "ERROR", f"ValidationError: schema mismatch in release {ver}", 3)],
                    trace=("compute", svc, svc), log_alerts=[], root_service=svc, target=svc,
                    deploy=(svc, ver))
    raise ValueError(cause)


def _merge(a, b):
    return dict(inj=a["inj"] + b["inj"], logs=a["logs"] + b["logs"], trace=None,
                log_alerts=a["log_alerts"] + b["log_alerts"], root_service=a["root_service"],
                target=a["target"], deploy=None)


def make_case(seed, idx, scenario):
    rng = random.Random(f"{seed}-{idx}-{scenario}")
    cid = f"S{seed}-{idx:03d}"
    N, onset = CFG.n_pre, rng.randint(20, 24)
    metrics = {s: {m: _series(rng, s, m, N) for m in METRICS} for s in SERVICES}
    case = dict(case_id=cid, seed=seed, synthetic=True, scenario_type=scenario, onset_idx=onset,
                step_s=CFG.step_s, t0=T0, is_incident=scenario != "normal", root_cause="none",
                root_service="none", permitted_action="none", action_target="none",
                action_available=True, remediation_effective=True, post_mode="fixed",
                expected_final="no_incident", evidence_dropout=False, has_distractor=False)
    spec, drop_evidence = None, False

    if scenario == "normal":
        pass
    elif scenario in CAUSES:
        cause = scenario
        spec = cause_spec(cause, rng)
    elif scenario == "ambiguous":
        cause = rng.choice(["cpu_saturation", "db_pool_exhaustion"])
        a = cause_spec("cpu_saturation", rng, "payment-service")
        b = cause_spec("db_pool_exhaustion", rng)
        spec = _merge(a, b)
        truth = a if cause == "cpu_saturation" else b
        spec.update(root_service=truth["root_service"], target=truth["target"])
        spec["trace"] = None if rng.random() < 0.75 else (a["trace"] if rng.random() < .5 else b["trace"])
    elif scenario == "missing_evidence":
        cause = rng.choice(["cpu_saturation", "db_pool_exhaustion", "memory_leak", "dependency_failure"])
        full = cause_spec(cause, rng, "payment-service" if cause != "dependency_failure" else None)
        lat = [x for x in full["inj"] if x[1] == "latency_ms"][:1] or [("payment-service", "latency_ms", 450, 1)]
        spec = dict(full, inj=lat, logs=[], trace=None, log_alerts=[])
        drop_evidence = True
    elif scenario in ("action_unavailable", "failed_remediation", "partial_recovery"):
        pool = {"action_unavailable": CAUSES[:3], "failed_remediation": CAUSES[:4],
                "partial_recovery": CAUSES[:3]}[scenario]
        cause = rng.choice(pool)
        spec = cause_spec(cause, rng)
    else:
        raise ValueError(scenario)

    inc_keys, logs, traces, events, log_alerts = set(), [], [], [], []
    if spec:
        for svc, m, delta, ramp in spec["inj"]:
            _inject(metrics[svc][m], m, onset, delta, ramp)
            inc_keys.add((svc, m))
        case.update(root_cause=cause, root_service=spec["root_service"],
                    permitted_action=ACTION_FOR_CAUSE[cause], action_target=spec["target"])
        if scenario == "action_unavailable":
            case["action_available"] = False
        if scenario == "failed_remediation":
            case["remediation_effective"], case["post_mode"] = False, "unfixed"
        if scenario == "partial_recovery":
            case["post_mode"] = "partial"
        case["expected_final"] = ("resolved" if scenario in ("cpu_saturation", "db_pool_exhaustion",
                                  "memory_leak", "dependency_failure") else "escalated")
        # logs
        for svc, lvl, msg, cnt in spec["logs"]:
            for k in range(cnt):
                logs.append(dict(ts=T0 + (onset + 1 + k) * CFG.step_s + rng.uniform(0, 10),
                                 service=svc, level=lvl, message=msg))
        if spec["logs"] and rng.random() < 0.2:   # misleading line from a different cause
            other = cause_spec(rng.choice([c for c in CAUSES if c != cause]), rng)
            s2, l2, m2, _ = other["logs"][0]
            logs.append(dict(ts=T0 + (onset + 3) * CFG.step_s, service=s2, level=l2, message=m2))
        if spec["logs"] and rng.random() < 0.06 and scenario in CAUSES:
            logs, case["evidence_dropout"] = [], True
        # traces
        if spec["trace"] and not (rng.random() < 0.12 and scenario in CAUSES):
            kind, dom, err = spec["trace"]
            if rng.random() < 0.10:
                kind = rng.choice(["compute", "db", "gc", "network"])
            for k in range(rng.randint(3, 6)):
                traces.append(dict(trace_id=f"tr-{cid}-{k}", ts=T0 + (onset + 2 + k) * CFG.step_s,
                                   dominant_span_service=dom, dominant_kind=kind,
                                   error_span_service=err, duration_ms=round(rng.uniform(800, 3000), 1)))
        elif spec["trace"]:
            case["evidence_dropout"] = True
        if spec["deploy"]:
            events.append(dict(ts=T0 + (onset - 2) * CFG.step_s, type="deployment",
                               service=spec["deploy"][0], version=spec["deploy"][1]))
        log_alerts = spec["log_alerts"]

    # background log noise
    for k in range(rng.randint(3, 6)):
        logs.append(dict(ts=T0 + rng.uniform(0, N * CFG.step_s), service=rng.choice(SERVICES),
                         level="INFO", message=rng.choice(["health check ok", "cache refreshed", "request completed"])))

    # transient spikes: flapping (normal) or distractor (incident cases)
    n_spikes = 0
    if scenario == "normal":
        n_spikes = rng.choice([0, 0, 1, 1, 2])
    elif rng.random() < 0.5:
        n_spikes, case["has_distractor"] = 1, True
    inc_svcs = {s for s, _ in inc_keys}
    for _ in range(n_spikes):
        if inc_svcs:
            hard = rng.random() < 0.5
            pool = [s for s in SERVICES if s not in inc_svcs and (any(adjacent(s, i) for i in inc_svcs) == hard)] \
                or [s for s in SERVICES if s not in inc_svcs]
        else:
            pool = SERVICES
        svc = rng.choice(pool)
        m = rng.choice(["cpu", "mem", "latency_ms", "error_rate"])
        i0 = rng.randint(onset - 3, onset + 3) if inc_svcs else rng.randint(5, N - 5)
        for j in range(i0, i0 + rng.choice([1, 1, 2])):
            metrics[svc][m][j] = threshold(svc, m) * rng.uniform(1.05, 1.4)
            if m in PCT:
                metrics[svc][m][j] = min(metrics[svc][m][j], 100.0)

    # alerts from metrics (single-sample threshold rules => noisy, like real alert rules)
    alerts, n = [], 0
    for svc in SERVICES:
        for m in METRICS:
            atype, _ = ALERT_RULES[m]
            thr, ser = threshold(svc, m), metrics[svc][m]
            i = 0
            while i < N:
                if ser[i] > thr:
                    j = i
                    while j + 1 < N and ser[j + 1] > thr:
                        j += 1
                    is_inc = (svc, m) in inc_keys and j >= onset
                    grp = "INC" if is_inc else f"NOISE-{svc}-{m}-{i}"
                    picks = [i] + ([i + 1] if i + 1 <= j and rng.random() < 0.5 else []) \
                            + ([i + 4] if i + 4 <= j and rng.random() < 0.3 else [])
                    for p in picks:
                        n += 1
                        tr = None
                        if is_inc and atype in ("latency_high", "error_rate_high") and rng.random() < 0.6:
                            tr = f"tr-{cid}-inc"
                        alerts.append(dict(alert_id=f"{cid}-A{n:02d}", ts=T0 + p * CFG.step_s, service=svc,
                                           error_type=atype, severity="critical" if ser[p] > 1.15 * thr else "warning",
                                           value=round(ser[p], 2), message=f"{atype} on {svc}",
                                           trace_id=tr, true_group=grp))
                    i = j + 1
                else:
                    i += 1
    for svc, atype, msg in log_alerts:
        n += 1
        alerts.append(dict(alert_id=f"{cid}-A{n:02d}", ts=T0 + (onset + 1) * CFG.step_s, service=svc,
                           error_type=atype, severity="critical", value=1.0, message=msg,
                           trace_id=f"tr-{cid}-inc" if rng.random() < 0.6 else None, true_group="INC"))
    alerts.sort(key=lambda a: a["ts"])

    # post-action measurements for the injected series (simulation ground truth)
    post = {"fixed": {}, "unfixed": {}, "partial": {}}
    for svc, m, delta, _ in (spec["inj"] if spec else []):
        for mode, f in (("fixed", 0.0), ("unfixed", 1.0), ("partial", 0.5)):
            s = [_clip(m, v + delta * f) for v in _series(rng, svc, m, CFG.n_post)]
            post[mode].setdefault(svc, {})[m] = s
    case.update(metrics=metrics, post=post, alerts=alerts, logs=sorted(logs, key=lambda x: x["ts"]),
                traces=traces, events=events)
    return case


def generate_dataset(seed=42, composition=None):
    comp = composition or COMPOSITION
    cases, idx = [], 0
    for scen, k in comp.items():
        for _ in range(k):
            cases.append(make_case(seed, idx, scen))
            idx += 1
    random.Random(seed).shuffle(cases)
    return cases


def save_jsonl(cases, path):
    with open(path, "w") as f:
        for c in cases:
            f.write(json.dumps(c, sort_keys=True) + "\n")


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def dataset_hash(cases):
    return hashlib.sha256("\n".join(json.dumps(c, sort_keys=True) for c in cases).encode()).hexdigest()[:16]
