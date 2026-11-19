"""Feedback on the agent's decisions. Stored in the same SQLite file as the incident history."""
import time

from fastapi import APIRouter, Body, HTTPException

from aiops_agent import store

router = APIRouter()


def _init():
    with store._LOCK, store._conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, case_id TEXT, status TEXT, rating TEXT, comment TEXT)""")


def _summary():
    _init()
    with store._LOCK, store._conn() as c:
        up = c.execute("SELECT COUNT(*) FROM feedback WHERE rating='up'").fetchone()[0]
        down = c.execute("SELECT COUNT(*) FROM feedback WHERE rating='down'").fetchone()[0]
    return dict(up=up, down=down, total=up + down)


@router.post("/api/feedback")
def add_feedback(item: dict = Body(...)):
    rating = item.get("rating")
    if rating not in ("up", "down"):
        raise HTTPException(422, "rating must be 'up' or 'down'")
    _init()
    with store._LOCK, store._conn() as c:
        c.execute("INSERT INTO feedback(ts, case_id, status, rating, comment) VALUES (?,?,?,?,?)",
                  (time.time(), str(item.get("case_id") or "")[:80], str(item.get("status") or "")[:30],
                   rating, str(item.get("comment") or "")[:500]))
    return _summary()


@router.get("/api/feedback")
def list_feedback(limit: int = 50):
    _init()
    with store._LOCK, store._conn() as c:
        rows = c.execute("SELECT id, ts, case_id, status, rating, comment FROM feedback ORDER BY id DESC LIMIT ?",
                         (limit,)).fetchall()
    return dict(summary=_summary(), items=[dict(r) for r in rows])