import pytest
from aiops_agent.generator import generate_dataset, dataset_hash, make_case
from aiops_agent.detection import detect
from aiops_agent.correlation import correlate, linked
from aiops_agent.actions import validate, execute, ActionUnavailable
from aiops_agent.verification import verify
from aiops_agent.workflow import run_incident
from aiops_agent.evaluation import prf, safety_eval, pair_counts, run_experiment
from aiops_agent.ingestion import normalize_alert, IngestionError


def test_reproducible():
    assert dataset_hash(generate_dataset(7)) == dataset_hash(generate_dataset(7))
    assert dataset_hash(generate_dataset(7)) != dataset_hash(generate_dataset(8))


def test_normal_has_no_detection():
    for i in range(10):
        assert detect(make_case(1, i, "normal")["metrics"]) == []


def test_cpu_detected():
    c = make_case(1, 0, "cpu_saturation")
    assert any(a.metric == "cpu" for a in detect(c["metrics"]))


def test_policy_blocks_commands():
    for a in ["rm -rf /", "restart_service; ls", "format_disk"]:
        assert not validate(dict(action=a, target="payment-service")).allowed
    assert not validate(dict(action="restart_service", target="db-primary")).allowed
    assert not validate(dict(action="restart_service", target="payment-service", environment="production")).allowed
    assert validate(dict(action="rollback_deployment", target="payment-service")).requires_approval


def test_rollback_needs_approval_to_execute():
    c = make_case(1, 0, "bad_deployment")
    with pytest.raises(PermissionError):
        execute(dict(action="rollback_deployment", target=c["action_target"]), c)


def test_unavailable_action():
    c = make_case(1, 0, "action_unavailable")
    with pytest.raises(ActionUnavailable):
        execute(dict(action=c["permitted_action"], target=c["action_target"]), c)


def test_correlation_separates_unrelated():
    a = dict(alert_id="1", ts=0, service="payment-service", error_type="latency_high", trace_id=None)
    b = dict(alert_id="2", ts=10, service="auth-service", error_type="cpu_high", trace_id=None)
    assert linked(a, b) is None
    assert correlate([a, b]) == [["1"], ["2"]]
    c = dict(alert_id="3", ts=20, service="payment-service", error_type="cpu_high", trace_id=None)
    assert len(correlate([a, b, c])) == 2


def test_verification_states():
    c = make_case(2, 0, "cpu_saturation")
    an = detect(c["metrics"])
    assert verify(c, an, c["post"]["fixed"])["overall"] == "resolved"
    assert verify(c, an, c["post"]["unfixed"])["overall"] == "unresolved"
    assert verify(c, an, c["post"]["partial"])["overall"] == "inconclusive"
    assert verify(c, an, {})["overall"] == "inconclusive"


def test_workflow_paths():
    assert run_incident(make_case(3, 0, "db_pool_exhaustion"))["status"] == "resolved"
    assert run_incident(make_case(3, 0, "normal"))["status"] == "no_incident"
    s = run_incident(make_case(3, 0, "failed_remediation"))
    assert s["status"] == "escalated" and s["escalation_reason"] == "verification_failed"
    assert run_incident(make_case(3, 1, "bad_deployment"))["escalation_reason"] == "high_risk_requires_approval"


def test_engines_agree():
    c = make_case(4, 0, "memory_leak")
    assert run_incident(c, True)["status"] == run_incident(c, False)["status"]


def test_metrics_math():
    assert prf(8, 2, 2) == (0.8, 0.8, 0.8)
    cases = [dict(case_id="x", alerts=[dict(alert_id="a", true_group="G"), dict(alert_id="b", true_group="G"),
                                       dict(alert_id="c", true_group="H")])]
    tp, fp, fn, ex = pair_counts(cases, {"x": {"a": 0, "b": 0, "c": 0}})
    assert (tp, fp, fn, ex) == (1, 2, 0, 0)


def test_safety_and_ingestion():
    s = safety_eval()
    assert s["prevented_or_escalated"] == s["unsafe_proposals"]
    with pytest.raises(IngestionError):
        normalize_alert(dict(alert_id="1", ts="bad", service="payment-service", error_type="x"))
    assert normalize_alert(dict(alert_id="1", ts=1, service="Payment_Service", error_type="X", severity="CRIT"))["severity"] == "critical"


def test_end_to_end_no_false_verified_resolution(tmp_path):
    res, cases, P, B = run_experiment(11, str(tmp_path))
    assert res["proposed"]["remediation"]["false_resolution_claims"] == 0
    assert (tmp_path / "incident_predictions.csv").exists() and (tmp_path / "aggregate_metrics.json").exists()


def test_live_policy_and_store(tmp_path, monkeypatch):
    from aiops_agent import store
    assert validate(dict(action="throttle_workload", target="stress-app")).allowed
    assert not validate(dict(action="throttle_workload", target="db-primary")).allowed
    assert not validate(dict(action="throttle_workload", target="stress-app", environment="production")).allowed
    monkeypatch.setenv("AIOPS_DB", str(tmp_path / "t.db"))
    iid = store.save(dict(incident_id="X1", final_status="resolved", root_cause=dict(top="cpu_saturation")), "test")
    assert iid == "X1" and store.get("X1")["final_status"] == "resolved" and store.list_incidents()[0]["id"] == "X1"