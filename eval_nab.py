"""Detection experiment on a REAL public dataset: Numenta Anomaly Benchmark (NAB), AWS CloudWatch series.

Source: https://github.com/numenta/NAB  (data/realAWSCloudwatch/*.csv, labels/combined_windows.json)
Compares OUR detector idea (robust z-score, 6 sigma, 4 consecutive samples, same thresholds as config.py,
rolling baseline = previous 200 points) with a simple static-threshold baseline (mean + 3 std of the first 15%,
alarm on any single sample). Nothing is tuned on NAB. Detection only: NAB has no root-cause or remediation labels.

Run:  python eval_nab.py
"""
import csv
import datetime as dt
import json
import os
import statistics as st
import urllib.request

from aiops_agent.config import CFG
from aiops_agent.detection import baseline_stats

RAW = "https://raw.githubusercontent.com/numenta/NAB/master/"
CACHE = os.path.join("data", "nab")
WINDOW = 200


def fetch(path):
    dst = os.path.join(CACHE, path.replace("/", "__"))
    if not os.path.exists(dst):
        os.makedirs(CACHE, exist_ok=True)
        with urllib.request.urlopen(RAW + path, timeout=30) as r, open(dst, "wb") as f:
            f.write(r.read())
    return dst


def ts(s):
    return dt.datetime.fromisoformat(s.split(".")[0])


def load_series(name):
    with open(fetch("data/" + name)) as f:
        rows = list(csv.DictReader(f))
    return [ts(r["timestamp"]) for r in rows], [float(r["value"]) for r in rows]


def alarms_ours(vals, start):
    """Event alarms: robust z > z_thresh for `sustain` consecutive samples, rolling baseline."""
    out, run, active = [], 0, False
    for i in range(max(start, WINDOW), len(vals)):
        med, sig = baseline_stats(vals[i - WINDOW:i], n=WINDOW)
        if (vals[i] - med) / sig > CFG.z_thresh:
            run += 1
            if run >= CFG.sustain and not active:
                out.append(i); active = True
        else:
            run, active = 0, False
    return out


def alarms_static(vals, start):
    """Baseline: alarm on any single sample above mean + 3 std of the first 15% (one alarm per run)."""
    p = max(2, int(0.15 * len(vals)))
    thr = st.mean(vals[:p]) + 3 * st.pstdev(vals[:p])
    out, prev = [], False
    for i in range(start, len(vals)):
        above = vals[i] > thr
        if above and not prev:
            out.append(i)
        prev = above
    return out


def score(times, alarms, windows):
    idx = lambda t: next((i for i, x in enumerate(times) if x >= t), len(times))
    wins = [(idx(ts(a)), idx(ts(b))) for a, b in windows]
    hit, delays = 0, []
    for a, b in wins:
        inside = [i for i in alarms if a <= i <= b]
        if inside:
            hit += 1
            delays.append((times[inside[0]] - times[a]).total_seconds() / 60)
    tp_alarms = sum(any(a <= i <= b for a, b in wins) for i in alarms)
    return dict(windows=len(wins), windows_hit=hit, alarms=len(alarms), alarms_in_window=tp_alarms, delays=delays)


def main():
    labels = json.load(open(fetch("labels/combined_windows.json")))
    names = sorted(k for k in labels if k.startswith("realAWSCloudwatch/"))
    rows, tot = [], {"ours": dict(w=0, h=0, a=0, t=0, d=[]), "static": dict(w=0, h=0, a=0, t=0, d=[])}
    for n in names:
        times, vals = load_series(n)
        start = int(0.15 * len(vals))   # NAB convention: first 15% is a probationary period
        for m, fn in (("ours", alarms_ours), ("static", alarms_static)):
            s = score(times, fn(vals, start), labels[n])
            rows.append(dict(series=n.split("/")[1], method=m, points=len(vals), windows=s["windows"], windows_hit=s["windows_hit"],
                             alarms=s["alarms"], alarms_in_window=s["alarms_in_window"]))
            t = tot[m]; t["w"] += s["windows"]; t["h"] += s["windows_hit"]; t["a"] += s["alarms"]; t["t"] += s["alarms_in_window"]; t["d"] += s["delays"]
    os.makedirs("results", exist_ok=True)
    with open("results/nab_per_series.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    summ = {}
    print(f"NAB realAWSCloudwatch: {len(names)} series, {tot['ours']['w']} labelled anomaly windows\n")
    print(f"{'method':<8}{'window recall':>15}{'alarm precision':>17}{'F1':>8}{'alarms':>9}{'mean delay (min)':>19}")
    for m, t in tot.items():
        rec = t["h"] / t["w"] if t["w"] else 0
        pre = t["t"] / t["a"] if t["a"] else 0
        f1 = 2 * rec * pre / (rec + pre) if rec + pre else 0
        dly = st.mean(t["d"]) if t["d"] else None
        summ[m] = dict(windows=t["w"], windows_hit=t["h"], alarms=t["a"], alarms_in_window=t["t"], window_recall=round(rec, 3),
                       alarm_precision=round(pre, 3), f1=round(f1, 3), mean_delay_min=None if dly is None else round(dly, 1))
        print(f"{m:<8}{rec:>15.3f}{pre:>17.3f}{f1:>8.3f}{t['a']:>9}{(dly if dly is not None else float('nan')):>19.1f}")
    json.dump(dict(dataset="NAB realAWSCloudwatch", series=len(names), results=summ,
                   note="detection only; thresholds taken from config.py, not tuned on NAB"), open("results/nab_summary.json", "w"), indent=2)
    print("\nSaved results/nab_summary.json and results/nab_per_series.csv")


if __name__ == "__main__":
    main()