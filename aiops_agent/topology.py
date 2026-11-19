"""Synthetic enterprise topology + metric/alert conventions."""
SERVICES = ["frontend", "api-gateway", "payment-service", "order-service",
            "auth-service", "cache-redis", "db-primary"]
DEPENDS_ON = {  # caller -> callees
    "frontend": ["api-gateway"],
    "api-gateway": ["payment-service", "order-service", "auth-service"],
    "payment-service": ["db-primary"],
    "order-service": ["db-primary", "cache-redis"],
    "auth-service": ["cache-redis"],
    "cache-redis": [], "db-primary": [],
}
METRICS = ["cpu", "mem", "latency_ms", "error_rate", "pool_util"]
PCT = {"cpu", "mem", "error_rate", "pool_util"}
BASE = {"cpu": (35.0, 4.0), "mem": (50.0, 3.0), "latency_ms": (120.0, 10.0),
        "error_rate": (0.5, 0.15), "pool_util": (40.0, 5.0)}
LAT_SCALE = {"db-primary": 0.2, "cache-redis": 0.05}

# metric -> (alert type, threshold) ; latency threshold scaled per service
ALERT_RULES = {"cpu": ("cpu_high", 85.0), "mem": ("memory_high", 85.0),
               "latency_ms": ("latency_high", 400.0), "error_rate": ("error_rate_high", 5.0),
               "pool_util": ("pool_exhausted", 90.0)}
RESOURCE_TYPES = {"cpu_high", "memory_high", "pool_exhausted", "db_conn_timeout"}
SERVICE_TYPES = {"latency_high", "error_rate_high", "dependency_unavailable"}


def threshold(service: str, metric: str) -> float:
    t = ALERT_RULES[metric][1]
    return t * LAT_SCALE.get(service, 1.0) if metric == "latency_ms" else t


def depends_on(caller: str, callee: str) -> bool:
    return callee in DEPENDS_ON.get(caller, [])


def adjacent(a: str, b: str) -> bool:
    return depends_on(a, b) or depends_on(b, a)


def callers_of(svc: str):
    return [k for k, v in DEPENDS_ON.items() if svc in v]
