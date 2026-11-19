"""Detection experiment on REAL public datasets: SMD (server machines), KPI (AIOps 2018 web KPIs), SKAB (industrial sensors).

Put these three zip files in data/real/ :  OmniAnomaly-master.zip, KPI-Anomaly-Detection-master.zip, SKAB-master.zip
Same detector idea and same thresholds as config.py (robust z-score, 6 sigma, 4 consecutive samples, rolling baseline of the
previous 200 points) against a static-threshold baseline (mean + 3 std of the first 15%, alarm on any single sample).
Multi-metric data: the machine raises an alarm if any metric does. Nothing is tuned. Detection only.

Run:  python eval_real.py            (all three, a few minutes)
      python eval_real.py --only skab,kpi
      python eval_real.py --smd-machines 6
"""
import argparse
import csv
import io
import json
import os
import statistics as st
import time
import zipfile
from array import array

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from aiops_agent.config import CFG

WINDOW = 200
CHUNK = 20000
SLACK = 2 * CFG.sustain
METHODS = (("ours", "z", False), ("ours_2sided", "z", True), ("static", "s", False), ("static_2sided", "s", True))
NAMES = {
    "smd": "SMD, server machines (OmniAnomaly)",
    "kpi": "KPI, web service KPIs (AIOps 2018)",
    "skab": "SKAB, industrial sensor testbed",
}


def open_zip(folder, name):
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}. Copy the zip into {folder}.")
    return zipfile.ZipFile(path)


def runs(labels):
    f = np.concatenate(([0], (np.asarray(labels) > 0).astype(np.int8), [0]))
    d = np.diff(f)
    return list(zip(np.flatnonzero(d == 1).tolist(), (np.flatnonzero(d == -1) - 1).tolist()))


def load_smd(folder, limit):
    zf = open_zip(folder, "OmniAnomaly-master.zip")
    base = "OmniAnomaly-master/ServerMachineDataset/"
    names = sorted(n[len(base + "test/"):-4] for n in zf.namelist() if n.startswith(base + "test/") and n.endswith(".txt"))
    for m in names[:limit]:
        x = np.loadtxt(io.TextIOWrapper(zf.open(f"{base}test/{m}.txt"), "utf-8"), delimiter=",", ndmin=2)
        y = np.loadtxt(io.TextIOWrapper(zf.open(f"{base}test_label/{m}.txt"), "utf-8"), delimiter=",")
        yield m, x, y


def load_kpi(folder, limit):
    zf = open_zip(folder, "KPI-Anomaly-Detection-master.zip")
    data = {}
    with zf.open("KPI-Anomaly-Detection-master/Preliminary_dataset/train.csv") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, "utf-8")):
            t, v, y = data.setdefault(r["KPI ID"], (array("q"), array("d"), array("b")))
            t.append(int(r["timestamp"])); v.append(float(r["value"])); y.append(int(r["label"]))
    for k in sorted(data)[:limit]:
        t, v, y = (np.frombuffer(a, dtype=d) for a, d in zip(data[k], ("q", "d", "b")))
        o = np.argsort(t, kind="stable")
        yield k, v[o].reshape(-1, 1), y[o]


def load_skab(folder, limit):
    zf = open_zip(folder, "SKAB-master.zip")
    names = sorted(n for n in zf.namelist() if n.startswith("SKAB-master/data/") and n.endswith(".csv") and "anomaly-free" not in n)
    for n in names[:limit]:
        rows = list(csv.DictReader(io.TextIOWrapper(zf.open(n), "utf-8"), delimiter=";"))
        cols = [c for c in rows[0] if c not in ("datetime", "anomaly", "changepoint")]
        x = np.array([[float(r[c]) for c in cols] for r in rows])
        y = np.array([float(r["anomaly"]) for r in rows])
        yield n.split("data/")[1][:-4], x, y


def rolling_z(x):
    n = len(x)
    z = np.full(n, np.nan)
    for s in range(0, n - WINDOW, CHUNK):
        e = min(s + CHUNK, n - WINDOW)
        w = sliding_window_view(x[s:e + WINDOW - 1], WINDOW)
        med = np.median(w, axis=1)
        mad = np.median(np.abs(w - med[:, None]), axis=1)
        sig = np.maximum(np.maximum(1.4826 * mad, 0.05 * np.abs(med)), 0.1)
        z[s + WINDOW:e + WINDOW] = (x[s + WINDOW:e + WINDOW] - med) / sig
    return z


def event_alarms(flag, sustain):
    d = np.diff(np.concatenate(([0], flag.astype(np.int8), [0])))
    s, e = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return s[(e - s) >= sustain] + sustain - 1


def alarms_for(x, start):
    out = {m: [] for m, _, _ in METHODS}
    p = max(2, int(0.15 * len(x)))
    for j in range(x.shape[1]):
        v = x[:, j]
        z = rolling_z(v)
        dev = (v - np.mean(v[:p])) / (np.std(v[:p]) + 1e-12)
        for name, kind, two in METHODS:
            if kind == "z":
                a = np.abs(z) if two else z
                flag = a > CFG.z_thresh
                sustain = CFG.sustain
            else:
                flag = (np.abs(dev) if two else dev) > 3
                sustain = 1
            flag = flag.copy()
            flag[:start] = False
            out[name].append(event_alarms(flag, sustain))
    return {k: np.unique(np.concatenate(v)) if v else np.array([], dtype=int) for k, v in out.items()}


def score(alarms, wins):
    hit, delays = 0, []
    for a, b in wins:
        inside = alarms[(alarms >= a) & (alarms <= b + SLACK)]
        if len(inside):
            hit += 1
            delays.append(int(inside[0] - a))
    tp = sum(any(a <= i <= b + SLACK for a, b in wins) for i in alarms.tolist())
    return dict(windows=len(wins), windows_hit=hit, alarms=len(alarms), alarms_in_window=tp, delays=delays)


def run_dataset(key, loader, folder, limit):
    tot = {m: dict(w=0, h=0, a=0, t=0, d=[]) for m, _, _ in METHODS}
    rows, points, t0 = [], 0, time.time()
    for name, x, y in loader(folder, limit):
        start = max(int(0.15 * len(x)), WINDOW)
        wins = [(a, b) for a, b in runs(y) if b >= start]
        al = alarms_for(x, start)
        points += len(x) - start
        for m, _, _ in METHODS:
            s = score(al[m], wins)
            rows.append(dict(dataset=key, series=name, method=m, points=len(x), windows=s["windows"], windows_hit=s["windows_hit"],
                             alarms=s["alarms"], alarms_in_window=s["alarms_in_window"]))
            t = tot[m]
            t["w"] += s["windows"]; t["h"] += s["windows_hit"]; t["a"] += s["alarms"]; t["t"] += s["alarms_in_window"]; t["d"] += s["delays"]
        print(f"  {key} {name}: {len(wins)} windows, {len(x)} samples ({time.time() - t0:.0f}s)", flush=True)
    summ = {}
    for m, t in tot.items():
        rec = t["h"] / t["w"] if t["w"] else 0
        pre = t["t"] / t["a"] if t["a"] else 0
        f1 = 2 * rec * pre / (rec + pre) if rec + pre else 0
        summ[m] = dict(windows=t["w"], windows_hit=t["h"], alarms=t["a"], alarms_in_window=t["t"], window_recall=round(rec, 3),
                       alarm_precision=round(pre, 3), f1=round(f1, 3), alarms_per_1000=round(1000 * t["a"] / max(points, 1), 2),
                       mean_delay_samples=round(st.mean(t["d"]), 1) if t["d"] else None)
    return dict(name=NAMES[key], series=len({r["series"] for r in rows}), samples_scored=points, results=summ), rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.path.join("data", "real"))
    ap.add_argument("--only", default="smd,kpi,skab")
    ap.add_argument("--smd-machines", type=int, default=28)
    ap.add_argument("--kpi-series", type=int, default=26)
    a = ap.parse_args()
    plan = dict(smd=(load_smd, a.smd_machines), kpi=(load_kpi, a.kpi_series), skab=(load_skab, 10 ** 6))
    out, all_rows = {}, []
    for key in [k.strip() for k in a.only.split(",") if k.strip() in plan]:
        print(f"{NAMES[key]}", flush=True)
        loader, limit = plan[key]
        out[key], rows = run_dataset(key, loader, a.data_dir, limit)
        all_rows += rows
        print(f"\n{'method':<15}{'window recall':>15}{'alarm precision':>17}{'F1':>8}{'alarms':>9}{'per 1000':>10}")
        for m, r in out[key]["results"].items():
            print(f"{m:<15}{r['window_recall']:>15.3f}{r['alarm_precision']:>17.3f}{r['f1']:>8.3f}{r['alarms']:>9}{r['alarms_per_1000']:>10.2f}")
        print()
    os.makedirs("results", exist_ok=True)
    with open("results/real_per_series.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0])); w.writeheader(); w.writerows(all_rows)
    json.dump(dict(datasets=out, window=WINDOW, z_thresh=CFG.z_thresh, sustain=CFG.sustain, alarm_tolerance_samples=SLACK,
                   note="detection only; thresholds from config.py, nothing tuned; multi-metric series alarm if any metric alarms"),
              open("results/real_summary.json", "w"), indent=2)
    print("Saved results/real_summary.json and results/real_per_series.csv")


if __name__ == "__main__":
    main()