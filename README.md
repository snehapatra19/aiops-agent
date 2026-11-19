# AI-Agent-Based Incident Detection, RCA and Self-Healing — simulation prototype

Project: *An AI-Agent-Based Autonomous Framework for Intelligent Incident Detection, Root Cause Analysis, and Self-Healing in Enterprise Systems.*

**Everything here runs on a labelled SYNTHETIC benchmark with SIMULATED remediation.** No production system is touched.

## Screenshots



### Incident Explanation and Report

![Incident explanation and report](docs/incident_explanation_and_report.png)



### Live Incident Dashboard

![Live incident dashboard](docs/live_incident_dashboard.png)



### External Dataset Evaluation

![External dataset evaluation](docs/external_dataset_evaluation.png)



### Detection Performance Comparison

![Detection performance comparison](docs/detection_performance_comparison.png)



### Real Dataset Comparison

![Real dataset comparison](docs/real_dataset_comparison.png)



### Real Data Lab

![Real data lab dashboard](docs/real_data_lab_dashboard.png)



### Live Machine Monitoring

![Live machine monitoring](docs/live_machine_monitoring.png)



### Agent Workflow

![Agent workflow dashboard](docs/agent_workflow_dashboard.png)

## Integration status (honest)

|Component|Status|
|-|-|
|Python pipeline (ingest, detect, correlate, RCA, plan, execute, verify, escalate, report)|Implemented, tested|
|LangGraph orchestration (`workflow.py`)|Implemented; falls back to an equivalent state machine if not installed. A test checks both give the same status|
|LLM API|Optional re-ranker in `llm.py`, schema-validated. **Not executed in any reported run** (no key used)|
|OpenTelemetry, Prometheus, Grafana, ELK, Docker/Kubernetes|**NOT integrated.** Data comes from synthetic JSONL/CSV with the same shape (alerts, logs, metrics, trace summaries). Future work|
|Web UI: FastAPI (`api.py`) + React/Tailwind/Framer Motion (`frontend/`)|Built (prebuilt in `frontend/dist`). API endpoints tested with curl; UI smoke-tested in jsdom (renders, no JS errors). |
|MHP-RCA (base paper)|**Not reproduced.** Baseline here is a simple rule baseline, not MHP-RCA|

## Setup (VS Code terminal, Python 3.10+)

```
python -m venv .venv
.venv\\Scripts\\activate          # Windows   (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python -m pytest -q             # 13 tests
python cli.py demo --scenario db_pool_exhaustion
python cli.py experiments       # regenerates EVERYTHING in results/
uvicorn api:app --port 8000     # then open http://127.0.0.1:8000  (web UI)
```

Scenarios for `--scenario`: normal, cpu_saturation, db_pool_exhaustion, memory_leak, dependency_failure, bad_deployment, ambiguous, missing_evidence, action_unavailable, failed_remediation, partial_recovery.



**Datasets**



`data/nab/` and the synthetic data are included in the repo. The large public datasets in `data/real/` are NOT included (GitHub size limit). Download them and place the zip files in `data/real/`:



\- KPI-Anomaly-Detection: https://github.com/NetManAIOps/KPI-Anomaly-Detection

\- OmniAnomaly: https://github.com/NetManAIOps/OmniAnomaly

\- SKAB: https://github.com/waico/SKAB

\- loghub: https://github.com/logpai/loghub



(Add the source of the remaining two zips, `archive__12_.zip` and `location_info_of_ssd_csv.zip`, here.)

## Regenerate all paper numbers

`python cli.py experiments` -> `results/`: scenario_summary.csv, incident_predictions.csv, alert_correlation_results.csv,
rca_evaluation.csv, remediation_results.csv, verification_results.csv, baseline_comparison.csv, aggregate_metrics.json,
repeated_runs.{csv,json}, confusion_*.png/json, comparison.png, ieee_tables.tex, reports/<case>.json, dataset_synthetic.jsonl.
Tables are produced by `aiops_agent/reporting.py` from the JSON files; nothing is typed by hand. Main run = seed 42 (120 cases); repeated runs = seeds 42-46.

## Method summary

* **Detection**: robust z-score (median/MAD of first 20 samples) > 6 for >= 4 consecutive samples + absolute floor. Symptoms only.
* **Correlation**: rules R1 same service, R2 adjacent in call graph + (shared trace | same type | propagation), within 120 s; union-find.
* **RCA**: weighted evidence features -> softmax *relative support* (not calibrated probability). Escalate if top < 0.60 or margin < 0.20 (thresholds fixed in `config.py` before experiments).
* **Safety**: allowlist + policy (target, params, sandbox only); no shell; `rollback_deployment` needs human approval; live mode raises `NotImplementedError`.
* **Verification**: median of last 5 post samples vs baseline/peak; resolved / unresolved / inconclusive. Execution OK != resolved.
* **Baseline**: see `baseline.py` docstring. Detection = any alert; group by service; first-alert-type -> cause; executes mapped action, claims success without verification.
* **Simulated time**: detection delay + configured action duration + verification window (seconds, simulated). Not comparable to real MTTR. Baseline TTR is over only the few cases where it truly fixed the incident, so it is not a like-for-like comparison.

## Limitations (use in the paper)

1. **Synthetic data, authored by us.** The generator and the RCA rules share the same domain assumptions (rule leakage); high scores show the pipeline works on this benchmark, not that it generalises to real systems.
2. Scenarios are independent draws of a fixed template set; seed std measures generator randomness only, not real-world uncertainty. No significance tests were run.
3. Several scenarios (failed remediation, partial recovery, bad deployment, ambiguous) are *designed* to expect escalation; the baseline lacks verification/gating by construction, so the gap in false-resolution and final-decision accuracy is partly a design property.
4. Remediation outcomes come from a simulator, not real systems. Policy safety test uses 13 hand-written proposals, not an adversarial LLM study.
5. Only 5 root-cause classes, one topology, single incident per case plus unrelated alerts.
6. Observability stack and live LLM are not integrated/evaluated. Human-in-the-loop is modelled as escalation only.
7. Time-to-resolution is simulated.

## Future work

Real telemetry via OpenTelemetry/Prometheus/ELK on a Docker/Kubernetes testbed (e.g. Sock-Shop with fault injection); reproduce MHP-RCA properly as a baseline; evaluate LLM-assisted RCA with schema validation; multi-incident cases; learned correlation; human feedback loop.

## Troubleshooting

* `ModuleNotFoundError: langgraph` -> `pip install langgraph` (otherwise the fallback state machine is used automatically).
* Plots missing -> `pip install matplotlib`.
* Run commands from the project root (where `cli.py` is).

## Web UI

```
python cli.py experiments          # once, so the Evaluation tab has data
uvicorn api:app --port 8000        # open http://127.0.0.1:8000
```

Node.js is needed to build the UI: `cd frontend \&\& npm install \&\& npm run build`. To edit the UI: `cd frontend \&\& npm install \&\& npm run dev` (run the API too; dev server on :5173 proxies /api). Rebuild with `npm run build`.
Tabs: **Live board** (inject a fault, watch telemetry stream, the agent's steps, the verdict stamp, a safety card, and a side-by-side with the rule-based baseline; autopilot cycles all scenarios for the expo) and **Scorecard** (agent vs baseline on the 120 synthetic cases, confusion matrix, seed variability).
The live feel: the agent pipeline really runs per click; telemetry is replayed from pre-generated synthetic data (1 sample = 15 simulated seconds). The 'baseline would have wrongly closed' counter compares the baseline's claim with the simulator's ground truth.

