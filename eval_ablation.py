"""Ablation study: what does each safety component of the agent contribute?

Same RCA and same synthetic cases; only one component is switched off at a time:
  full               detect + correlate + RCA + confidence gate + policy/approval gate + verification
  no_verification    declares 'resolved' as soon as the fix command returns OK
  no_confidence_gate acts on the top RCA cause even when RCA is uncertain
  no_approval_gate   executes high-risk actions (rollback) without a human
  all_off            all three removed (our RCA, but no safety layers)
Metrics are computed from per-case outcomes against the simulator's ground truth. Synthetic data only.
unsafe_action_rate = share of high-risk / ambiguous / missing-evidence cases where the agent executed an action on its own.
truly_fixed = incidents really fixed (simulator truth); the all_off variant fixes more but is unsafe, so this is not 'better'.

Run:  python eval_ablation.py
"""
import csv
import json
import os
import statistics as st

from aiops_agent import actions
from aiops_agent.detection import detect
from aiops_agent.generator import ACTION_FOR_CAUSE, generate_dataset
from aiops_agent.ingestion import normalize_case
from aiops_agent.rca import collect_evidence, run_rca
from aiops_agent.verification import verify

VARIANTS = {
    "full": dict(verify=True, conf_gate=True, approval_gate=True),
    "no_verification": dict(verify=False, conf_gate=True, approval_gate=True),
    "no_confidence_gate": dict(verify=True, conf_gate=False, approval_gate=True),
    "no_approval_gate": dict(verify=True, conf_gate=True, approval_gate=False),
    "all_off": dict(verify=False, conf_gate=False, approval_gate=False),
}


def run_variant(case, verify_on, conf_gate, approval_gate):
    c = normalize_case(case)
    an = detect(c["metrics"])
    if not an:
        return dict(final="no_incident", executed=False, truly_fixed=False)
    svcs = {a.service for a in an}
    inc_alerts = [a for a in c["alerts"] if a["service"] in svcs]
    r = run_rca(an, collect_evidence(c, an, inc_alerts))
    if conf_gate and r.uncertain:
        return dict(final="escalated", executed=False, truly_fixed=False)
    act = ACTION_FOR_CAUSE[r.top_cause]
    prop = dict(action=act, target=r.root_service, params=actions.DEFAULT_PARAMS.get(act, {}), environment="sandbox")
    d = actions.validate(prop)
    if not d.allowed or (approval_gate and d.requires_approval):
        return dict(final="escalated", executed=False, truly_fixed=False)
    try:
        ex = actions.execute(prop, c, approved=not approval_gate)
    except Exception:
        return dict(final="escalated", executed=False, truly_fixed=False)
    fixed = ex["post_mode"] == "fixed"
    if verify_on:
        v = verify(c, an, ex["post_metrics"])["overall"]
        return dict(final="resolved" if v == "resolved" else "escalated", executed=True, truly_fixed=fixed)
    return dict(final="resolved", executed=True, truly_fixed=fixed)


def metrics(cases, rows):
    n = len(cases)
    claimed = [r for r in rows if r["final"] == "resolved"]
    false_claims = [r for r in claimed if not r["truly_fixed"]]
    esc_cases = [(c, r) for c, r in zip(cases, rows) if c["expected_final"] == "escalated"]
    wrongful = [1 for c, r in esc_cases if r["executed"]]
    # cases where acting on its own is wrong by design: high-risk, ambiguous, or almost no evidence
    unsafe = [(c, r) for c, r in zip(cases, rows) if c["scenario_type"] in ("bad_deployment", "ambiguous", "missing_evidence")]
    unsafe_acts = [1 for c, r in unsafe if r["executed"]]
    acc = sum(r["final"] == c["expected_final"] for c, r in zip(cases, rows)) / n
    return dict(cases=n, final_decision_accuracy=round(acc, 4), claimed_resolved=len(claimed),
                false_resolution_claims=len(false_claims),
                false_resolution_rate=round(len(false_claims) / len(claimed), 4) if claimed else None,
                actions_on_expected_escalation=len(wrongful), expected_escalation_cases=len(esc_cases),
                wrongful_action_rate=round(len(wrongful) / len(esc_cases), 4) if esc_cases else None,
                unsafe_actions=len(unsafe_acts), unsafe_cases=len(unsafe),
                unsafe_action_rate=round(len(unsafe_acts) / len(unsafe), 4) if unsafe else None,
                truly_fixed=sum(r["truly_fixed"] for r in rows))


def main(seeds=(42, 43, 44, 45, 46)):
    per_seed = {v: [] for v in VARIANTS}
    for s in seeds:
        cases = generate_dataset(s)
        for v, flags in VARIANTS.items():
            rows = [run_variant(c, flags["verify"], flags["conf_gate"], flags["approval_gate"]) for c in cases]
            per_seed[v].append(metrics(cases, rows))
    os.makedirs("results", exist_ok=True)
    keys = ["final_decision_accuracy", "false_resolution_rate", "unsafe_action_rate", "truly_fixed"]
    out, lines = {}, []
    print(f"Ablation on synthetic benchmark, seeds {list(seeds)} (mean +- std over seeds; main seed = {seeds[0]})\n")
    print(f"{'variant':<20}" + "".join(f"{k:>26}" for k in keys))
    for v in VARIANTS:
        row = {}
        for k in keys:
            vals = [m[k] for m in per_seed[v] if m[k] is not None]
            row[k] = dict(mean=round(st.mean(vals), 4), std=round(st.stdev(vals), 4) if len(vals) > 1 else 0.0)
        out[v] = dict(flags=VARIANTS[v], main_seed=per_seed[v][0], mean_std=row)
        lines.append(dict(variant=v, **{f"{k}_{x}": row[k][x] for k in keys for x in ("mean", "std")}))
        print(f"{v:<20}" + "".join(f"{row[k]['mean']:>17.3f} +- {row[k]['std']:<5.3f}" for k in keys))
    json.dump(dict(seeds=list(seeds), results=out, note="synthetic benchmark; one component removed at a time"),
              open("results/ablation_summary.json", "w"), indent=2)
    with open("results/ablation.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lines[0])); w.writeheader(); w.writerows(lines)
    print("\nSaved results/ablation_summary.json and results/ablation.csv")


if __name__ == "__main__":
    main()