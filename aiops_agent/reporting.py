"""Builds LaTeX tables + plots strictly from results/*.json (no hand-typed numbers)."""
import json
import os


def _f(v, d=3):
    return "n/a" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))


def _tab(caption, label, header, rows, note):
    out = ["\\begin{table}[t]", "\\centering", f"\\caption{{{caption}}}", f"\\label{{{label}}}",
           "\\begin{tabular}{" + "l" + "r" * (len(header) - 1) + "}", "\\toprule", " & ".join(header) + " \\\\", "\\midrule"]
    out += [" & ".join(r).replace("_", "\\_") + " \\\\" for r in rows]
    out += ["\\bottomrule", "\\end{tabular}", f"\\par\\footnotesize {note}", "\\end{table}", ""]
    return "\n".join(out)


def make_latex(outdir):
    A = json.load(open(os.path.join(outdir, "aggregate_metrics.json")))
    R = json.load(open(os.path.join(outdir, "repeated_runs.json")))
    P, B, n = A["proposed"], A["baseline"], A["n_cases"]
    cond = (f"Synthetic benchmark, seed {A['seed']}, {n} cases (dataset hash {A['dataset_hash']}); "
            "simulated remediation; all values computed from saved per-case outputs.")
    t = []
    rows = [[m, _f(P["detection"][k]), _f(B["detection"][k])] for m, k in
            [("Precision", "precision"), ("Recall", "recall"), ("F1", "f1"), ("False-positive rate", "fpr")]]
    rows += [["TP/FP/TN/FN", "/".join(str(P["detection"][k]) for k in ("TP", "FP", "TN", "FN")),
              "/".join(str(B["detection"][k]) for k in ("TP", "FP", "TN", "FN"))]]
    t.append(_tab("Case-level incident detection (incident vs. normal).", "tab:detection",
                  ["Metric", "Proposed", "Baseline"], rows, cond))
    rows = [[m, _f(P["correlation"][k]), _f(B["correlation"][k])] for m, k in
            [("Pairwise precision", "pair_precision"), ("Pairwise recall", "pair_recall"), ("Pairwise F1", "pair_f1"),
             ("Exact-partition rate", "exact_partition_rate")]]
    rows += [["Alerts $\\to$ groups", f"{P['correlation']['alerts']}$\\to${P['correlation']['groups_out']}",
              f"{B['correlation']['alerts']}$\\to${B['correlation']['groups_out']}"],
             ["True groups", str(P["correlation"]["true_groups"]), str(B["correlation"]["true_groups"])]]
    t.append(_tab("Alert correlation. Pairwise metrics over alert pairs within each case; fewer groups alone is not better.",
                  "tab:corr", ["Metric", "Proposed", "Baseline"], rows, cond))
    rows = [["Top-1 accuracy", _f(P["rca"]["top1_acc"]), _f(B["rca"]["top1_acc"])],
            ["Top-3 accuracy", _f(P["rca"]["top3_acc"]), "n/a"],
            ["Root-service accuracy", _f(P["rca"]["root_service_acc"]), _f(B["rca"]["root_service_acc"])],
            ["Uncertain (escalated) cases", str(P["rca"]["uncertain_cases"]), "0"],
            ["Selective top-1 (confident only)", _f(P["rca"]["selective_top1_acc"]), _f(B["rca"]["selective_top1_acc"])]]
    t.append(_tab(f"Root-cause analysis on the {P['rca']['n_incident_cases']} incident cases (undetected counts as wrong).",
                  "tab:rca", ["Metric", "Proposed", "Baseline"], rows, cond))
    pr, br = P["remediation"], B["remediation"]
    rows = [["Actions executed", str(pr["attempts"]), str(br["attempts"])],
            ["Actually effective (simulator truth)", str(pr["actually_effective"]), str(br["actually_effective"])],
            ["Claimed resolved", str(pr["claimed_resolved"]), str(br["claimed_resolved"])],
            ["False-resolution claims / claimed", f"{pr['false_resolution_claims']}/{pr['claimed_resolved']}",
             f"{br['false_resolution_claims']}/{br['claimed_resolved']}"],
            ["Escalation rate (of all cases)", _f(pr["escalation_rate"]), _f(br["escalation_rate"])],
            ["Executed on expected-escalation cases", f"{pr['actions_executed_on_expected_escalation']}/{pr['expected_escalation_cases']}",
             f"{br['actions_executed_on_expected_escalation']}/{br['expected_escalation_cases']}"],
            ["Final-decision accuracy", _f(pr["final_decision_accuracy"]), _f(br["final_decision_accuracy"])]]
    t.append(_tab("Remediation, verification and escalation. Baseline never verifies, so it 'claims' success when the command returns OK.",
                  "tab:remed", ["Metric", "Proposed", "Baseline"], rows, cond))
    rows = []
    for k, v in R["repeated"].items():
        if k.startswith("proposed") or k.startswith("baseline"):
            rows.append([k.replace(".", ": ", 1).replace(".", " "), _f(v["mean"]), _f(v["std"])])
    t.append(_tab("Variability across five generator seeds (mean, std) on synthetic data; not a real-world confidence interval.",
                  "tab:seeds", ["Method: metric", "Mean", "Std"], rows, f"Seeds {R['seeds']}."))
    S = A["safety"]
    t.append(_tab("Policy safety test.", "tab:safety", ["Test set", "Result"],
                  [["Unsafe/high-risk proposals blocked or escalated", f"{S['prevented_or_escalated']}/{S['unsafe_proposals']}"],
                   ["Valid proposals allowed", f"{S['valid_allowed']}/{S['valid_proposals']}"]], S["note"]))
    open(os.path.join(outdir, "ieee_tables.tex"), "w").write("\n".join(t))


def make_plots(outdir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False
    for m in ("proposed", "baseline"):
        d = json.load(open(os.path.join(outdir, f"confusion_{m}.json")))
        L, M = d["labels"], d["matrix"]
        rows = list(M.keys())
        data = [[M[r][c] for c in L] for r in rows]
        fig, ax = plt.subplots(figsize=(6.2, 4.2))
        ax.imshow(data, cmap="Blues")
        ax.set_xticks(range(len(L))); ax.set_xticklabels(L, rotation=40, ha="right", fontsize=7)
        ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows, fontsize=7)
        for i, r in enumerate(data):
            for j, v in enumerate(r):
                ax.text(j, i, v, ha="center", va="center", fontsize=8)
        ax.set_xlabel("predicted"); ax.set_ylabel("true"); ax.set_title(f"RCA confusion ({m}, synthetic)")
        fig.tight_layout(); fig.savefig(os.path.join(outdir, f"confusion_{m}.png"), dpi=150); plt.close(fig)
    A = json.load(open(os.path.join(outdir, "aggregate_metrics.json")))
    keys = [("detection", "f1"), ("correlation", "pair_f1"), ("rca", "top1_acc"), ("remediation", "final_decision_accuracy")]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    w = 0.38
    for i, m in enumerate(("proposed", "baseline")):
        ax.bar([x + i * w for x in range(len(keys))], [A[m][g][k] for g, k in keys], w, label=m)
    ax.set_xticks([x + w / 2 for x in range(len(keys))]); ax.set_xticklabels([f"{g}\n{k}" for g, k in keys], fontsize=7)
    ax.set_ylim(0, 1.05); ax.legend(); ax.set_title("Proposed vs baseline (synthetic, seed %d)" % A["seed"])
    fig.tight_layout(); fig.savefig(os.path.join(outdir, "comparison.png"), dpi=150); plt.close(fig)
    return True
