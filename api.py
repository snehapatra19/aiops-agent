"""FastAPI backend.  Run:  uvicorn api:app --port 8000   then open http://127.0.0.1:8000"""
import json
import os
from functools import lru_cache
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from aiops_agent.generator import generate_dataset
from aiops_agent.workflow import run_incident, HAVE_LANGGRAPH
from aiops_agent.baseline import run_baseline
from aiops_agent.evaluation import build_report
from aiops_agent.ingestion import normalize_case
from aiops_agent.correlation import correlate
from aiops_agent.topology import SERVICES, DEPENDS_ON
from aiops_agent import store
from aiops_agent.live import LiveMonitor
import real_lab
import gemini_explain

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "results")
DIST = os.path.join(ROOT, "frontend", "dist")

app = FastAPI(title="AIOps Agent (synthetic simulation)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


MONITOR = LiveMonitor()
store.init()


@lru_cache(maxsize=8)
def _cases(seed: int):
    return {c["case_id"]: c for c in generate_dataset(seed)}


@app.get("/api/health")
def health():
    return dict(ok=True, langgraph=HAVE_LANGGRAPH, synthetic=True, mode="simulate")


@app.get("/api/topology")
def topology():
    return dict(services=SERVICES, edges=[[a, b] for a, v in DEPENDS_ON.items() for b in v])


@app.get("/api/cases")
def cases(seed: int = 42):
    return [dict(case_id=c["case_id"], scenario=c["scenario_type"], is_incident=c["is_incident"],
                 n_alerts=len(c["alerts"])) for c in _cases(seed).values()]


@app.get("/api/run/{case_id}")
def run(case_id: str, seed: int = 42):
    c = _cases(seed).get(case_id)
    if not c:
        raise HTTPException(404, "unknown case")
    s = run_incident(c)
    rep = build_report(c, s)
    post = s.get("exec", {}).get("post_metrics", {})
    series = []
    for a in s["anomalies"][:8]:
        p = post.get(a.service, {}).get(a.metric)
        series.append(dict(service=a.service, metric=a.metric, onset=a.onset_idx,
                           pre=[round(x, 2) for x in c["metrics"][a.service][a.metric]],
                           post=[round(x, 2) for x in p] if p else None))
    groups = correlate(normalize_case(c)["alerts"])
    gidx = {aid: i for i, g in enumerate(groups) for aid in g}
    inc_ids = set(rep["correlated_alerts"])
    alerts = [dict(id=a["alert_id"], t=round(a["ts"] - c["t0"]), service=a["service"], type=a["error_type"],
                   severity=a["severity"], group=gidx.get(a["alert_id"]), in_incident=a["alert_id"] in inc_ids)
              for a in c["alerts"]]
    b = run_baseline(c)
    baseline = dict(status=b["status"], cause=b.get("cause"), action=b.get("proposal", {}).get("action"),
                    target=b.get("proposal", {}).get("target"),
                    actually_effective=bool(b.get("exec") and b["exec"]["post_mode"] == "fixed"))
    return dict(case_id=case_id, scenario=c["scenario_type"], synthetic=True, engine=s["engine"], report=rep, baseline=baseline,
                series=series, alerts=alerts, n_groups=len(groups), onset=c["onset_idx"],
                truth=dict(is_incident=c["is_incident"], root_cause=c["root_cause"], root_service=c["root_service"],
                           expected_final=c["expected_final"], permitted_action=c["permitted_action"]))


@app.post("/api/ingest/case")
def ingest_case(case: dict = Body(...)):
    """Ingest one operational case (alerts, logs, metrics, traces, events as JSON), run the full agent
    pipeline, store the incident in SQLite and return the report."""
    for k in ("case_id", "metrics", "alerts"):
        if k not in case:
            raise HTTPException(422, f"missing field '{k}'")
    case.setdefault("logs", []); case.setdefault("traces", []); case.setdefault("events", [])
    case.setdefault("onset_idx", 20); case.setdefault("step_s", 15); case.setdefault("t0", 0)
    case.setdefault("post", {"fixed": {}, "unfixed": {}, "partial": {}}); case.setdefault("post_mode", "unfixed")
    case.setdefault("permitted_action", "none"); case.setdefault("action_target", "none")
    s = run_incident(case)
    rep = build_report(case, s)
    store.save(rep, "ingest-api")
    return rep


@app.get("/api/incidents")
def incidents(limit: int = 50):
    return store.list_incidents(limit)


@app.get("/api/incidents/{iid}")
def incident(iid: str):
    r = store.get(iid)
    if not r:
        raise HTTPException(404, "unknown incident")
    return r


@app.get("/api/live/state")
def live_state():
    return MONITOR.snapshot()


@app.post("/api/live/start")
def live_start():
    MONITOR.start()
    return dict(ok=True)


@app.post("/api/live/stop")
def live_stop():
    MONITOR.stop()
    return dict(ok=True)


@app.get("/api/llm/status")
def llm_status():
    return gemini_explain.status()


@app.post("/api/explain")
def explain(body: dict = Body(...)):
    c = _cases(int(body.get("seed", 42))).get(body.get("case_id"))
    if not c:
        raise HTTPException(404, "unknown case")
    rep = build_report(c, run_incident(c))
    return gemini_explain.explain(rep, (body.get("question") or "").strip()[:300] or None)


@app.get("/api/real/catalog")
def real_catalog():
    return real_lab.catalog()


@app.get("/api/real/replay")
def real_replay(dataset: str, series: str, dim: int = -1, win: int = 0):
    try:
        return real_lab.replay(dataset, series, dim, win)
    except (FileNotFoundError, KeyError) as e:
        raise HTTPException(404, f"not found: {e}")


@app.get("/api/results")
def results():
    def load(n):
        p = os.path.join(RES, n)
        return json.load(open(p)) if os.path.exists(p) else None
    agg = load("aggregate_metrics.json")
    if not agg:
        raise HTTPException(404, "Run `python cli.py experiments` first")
    return dict(aggregate=agg, repeated=load("repeated_runs.json"),
                confusion=dict(proposed=load("confusion_proposed.json"), baseline=load("confusion_baseline.json")),
                real=dict(nab=load("nab_summary.json"), others=load("real_summary.json")),
                extra=load("extra_summary.json"))


if os.path.isdir(os.path.join(DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")


@app.get("/{path:path}")
def spa(path: str):
    idx = os.path.join(DIST, "index.html")
    if os.path.exists(idx):
        return FileResponse(idx)
    return JSONResponse(dict(message="Frontend not built. API docs at /docs"))