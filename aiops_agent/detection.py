"""Incident detection: sustained robust-z anomalies on metric series.

Observed SYMPTOMS (anomalies) are reported here; root causes are inferred later by RCA.
"""
from dataclasses import dataclass, asdict
from statistics import median
from .config import CFG


@dataclass
class Anomaly:
    service: str
    metric: str
    onset_idx: int
    detect_idx: int
    peak_z: float
    peak_value: float

    def dict(self):
        return asdict(self)


def baseline_stats(series, n=None):
    ref = series[: (n or CFG.baseline_points)]
    med = median(ref)
    mad = median(abs(x - med) for x in ref)
    sigma = max(1.4826 * mad, 0.05 * abs(med), 0.1)
    return med, sigma


def _floor_ok(metric, x, med):
    return {"cpu": x > 60, "mem": x > 70, "latency_ms": x > 1.8 * med,
            "error_rate": x > 2.0, "pool_util": x > 75}[metric]


def detect_series(series, metric):
    med, sigma = baseline_stats(series)
    run = 0
    for i in range(CFG.baseline_points, len(series)):
        z = (series[i] - med) / sigma
        if z > CFG.z_thresh and _floor_ok(metric, series[i], med):
            run += 1
            if run >= CFG.sustain:
                start = i - run + 1
                seg = series[start:]
                pz = (max(seg) - med) / sigma
                return start, i, pz, max(seg)
        else:
            run = 0
    return None


def detect(metrics):
    """metrics: {service: {metric: [values]}} -> list[Anomaly] sorted by onset."""
    out = []
    for svc, ms in metrics.items():
        for m, ser in ms.items():
            r = detect_series(ser, m)
            if r:
                out.append(Anomaly(svc, m, r[0], r[1], round(r[2], 2), round(r[3], 2)))
    return sorted(out, key=lambda a: (a.onset_idx, -a.peak_z))
