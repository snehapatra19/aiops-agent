"""SQLite incident store (incident history). Default file: results/incidents.db"""
import json
import os
import sqlite3
import threading
import time

_LOCK = threading.Lock()


def _path():
    return os.getenv("AIOPS_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "incidents.db"))


def _conn():
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    c = sqlite3.connect(_path(), timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _LOCK, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS incidents(
            id TEXT PRIMARY KEY, ts REAL, source TEXT, status TEXT, root_cause TEXT,
            action TEXT, verification TEXT, escalation_reason TEXT, report TEXT)""")


def save(rep, source):
    """rep: incident report dict. Returns incident id."""
    init()
    rc = rep.get("root_cause") or {}
    iid = rep.get("incident_id") or f"INC-{int(time.time() * 1000)}"
    row = (iid, time.time(), source, rep.get("final_status"), rc.get("top"),
           (rep.get("action") or {}).get("action"), (rep.get("verification") or {}).get("overall"),
           rep.get("escalation_reason"), json.dumps(rep, default=str))
    with _LOCK, _conn() as c:
        c.execute("INSERT OR REPLACE INTO incidents VALUES (?,?,?,?,?,?,?,?,?)", row)
    return iid


def list_incidents(limit=50):
    init()
    with _LOCK, _conn() as c:
        rows = c.execute("SELECT id, ts, source, status, root_cause, action, verification, escalation_reason "
                         "FROM incidents ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get(iid):
    init()
    with _LOCK, _conn() as c:
        r = c.execute("SELECT report FROM incidents WHERE id=?", (iid,)).fetchone()
    return json.loads(r["report"]) if r else None