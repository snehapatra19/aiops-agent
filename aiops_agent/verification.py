"""Post-remediation verification from measurements (never from 'action ran').

For each anomalous series: ratio = (post_median - baseline_median) / (peak_median - baseline_median)
 peak_median = median of last 5 pre-action samples; post_median = median of last 5 post samples.
 ratio <= resolved_ratio -> resolved ; >= unresolved_ratio -> unresolved ; else inconclusive.
"""
from statistics import median
from .config import CFG
from .detection import baseline_stats


def verify(case, anomalies, post_metrics):
    details, states = [], []
    for a in anomalies:
        pre = case["metrics"][a.service][a.metric]
        post = post_metrics.get(a.service, {}).get(a.metric)
        if not post or len(post) < CFG.verify_points:
            details.append(dict(service=a.service, metric=a.metric, state="inconclusive", ratio=None,
                                note="no/insufficient post-action data"))
            states.append("inconclusive")
            continue
        med, _ = baseline_stats(pre)
        peak = median(pre[-CFG.verify_points:])
        cur = median(post[-CFG.verify_points:])
        ratio = (cur - med) / max(peak - med, 1e-6)
        st = "resolved" if ratio <= CFG.resolved_ratio else "unresolved" if ratio >= CFG.unresolved_ratio else "inconclusive"
        details.append(dict(service=a.service, metric=a.metric, state=st, ratio=round(ratio, 3),
                            baseline=round(med, 2), peak=round(peak, 2), post=round(cur, 2)))
        states.append(st)
    if not states:
        overall = "inconclusive"
    elif "unresolved" in states:
        overall = "unresolved"
    elif "inconclusive" in states:
        overall = "inconclusive"
    else:
        overall = "resolved"
    return dict(overall=overall, series=details, verify_window_s=CFG.verify_points * CFG.step_s)
