"""Data ingestion + normalisation (JSONL cases, CSV alerts/logs)."""
import csv
import datetime as dt
import json
from .topology import SERVICES

SEV = {"crit": "critical", "critical": "critical", "high": "critical", "error": "critical",
       "warn": "warning", "warning": "warning", "medium": "warning", "info": "info", "low": "info"}


class IngestionError(ValueError):
    pass


def norm_service(s):
    s = str(s).strip().lower().replace("_", "-").replace(" ", "-")
    if s not in SERVICES:
        raise IngestionError(f"unknown service '{s}'")
    return s


def norm_ts(ts):
    """Accept epoch seconds or ISO-8601; return epoch float."""
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError as e:
        raise IngestionError(f"bad timestamp {ts!r}") from e


def normalize_alert(a):
    for k in ("alert_id", "ts", "service", "error_type"):
        if k not in a or a[k] in (None, ""):
            raise IngestionError(f"alert missing field '{k}': {a}")
    out = dict(a)
    out["ts"] = norm_ts(a["ts"])
    out["service"] = norm_service(a["service"])
    out["severity"] = SEV.get(str(a.get("severity", "warning")).lower(), "warning")
    out["error_type"] = str(a["error_type"]).strip().lower()
    out["trace_id"] = a.get("trace_id") or None
    return out


def normalize_log(l):
    out = dict(l)
    out["ts"], out["service"] = norm_ts(l["ts"]), norm_service(l["service"])
    out["level"] = str(l.get("level", "INFO")).upper()
    return out


def load_alerts_csv(path):
    with open(path, newline="") as f:
        return [normalize_alert(r) for r in csv.DictReader(f)]


def load_logs_csv(path):
    with open(path, newline="") as f:
        return [normalize_log(r) for r in csv.DictReader(f)]


def normalize_case(case):
    """Return a copy with normalised alerts/logs (metrics are assumed numeric lists)."""
    c = dict(case)
    c["alerts"] = [normalize_alert(a) for a in case.get("alerts", [])]
    c["logs"] = [normalize_log(l) for l in case.get("logs", [])]
    return c


def iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()
