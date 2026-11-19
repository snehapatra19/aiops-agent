import csv
import io
import os
import zipfile
from functools import lru_cache

import numpy as np

import eval_real as ER
from aiops_agent.config import CFG

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "real")
ZIPS = dict(smd="OmniAnomaly-master.zip", kpi="KPI-Anomaly-Detection-master.zip", skab="SKAB-master.zip")
SMD = "OmniAnomaly-master/ServerMachineDataset/"
SKAB = "SKAB-master/data/"


def zf(key):
    return ER.open_zip(DIR, ZIPS[key])


@lru_cache(maxsize=1)
def kpi_all():
    return {name: (x, y) for name, x, y in ER.load_kpi(DIR, 10 ** 6)}


def catalog():
    out = {}
    for key, fn in ZIPS.items():
        if not os.path.exists(os.path.join(DIR, fn)):
            continue
        if key == "smd":
            names = sorted(n[len(SMD + "test/"):-4] for n in zf(key).namelist() if n.startswith(SMD + "test/") and n.endswith(".txt"))
        elif key == "skab":
            names = sorted(n.split("data/")[1][:-4] for n in zf(key).namelist() if n.startswith(SKAB) and n.endswith(".csv") and "anomaly-free" not in n)
        else:
            names = sorted(kpi_all())
        out[key] = dict(name=ER.NAMES[key], series=names)
    return out


@lru_cache(maxsize=6)
def load(key, name):
    if key == "kpi":
        return kpi_all()[name]
    z = zf(key)
    if key == "smd":
        x = np.loadtxt(io.TextIOWrapper(z.open(f"{SMD}test/{name}.txt"), "utf-8"), delimiter=",", ndmin=2)
        y = np.loadtxt(io.TextIOWrapper(z.open(f"{SMD}test_label/{name}.txt"), "utf-8"), delimiter=",")
        return x, y
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(f"{SKAB}{name}.csv"), "utf-8"), delimiter=";"))
    cols = [c for c in rows[0] if c not in ("datetime", "anomaly", "changepoint")]
    return np.array([[float(r[c]) for c in cols] for r in rows]), np.array([float(r["anomaly"]) for r in rows])


def dim_alarms(v):
    start = max(int(0.15 * len(v)), ER.WINDOW)
    f1 = ER.rolling_z(v) > CFG.z_thresh
    f1[:start] = False
    p = max(2, int(0.15 * len(v)))
    f2 = (v - np.mean(v[:p])) / (np.std(v[:p]) + 1e-12) > 3
    f2[:start] = False
    return ER.event_alarms(f1, CFG.sustain), ER.event_alarms(f2, 1)


@lru_cache(maxsize=16)
def best_dim(key, name):
    x, y = load(key, name)
    wins = [(a, b) for a, b in ER.runs(y) if b > ER.WINDOW]
    best, top = 0, (-1, -1.0)
    for j in range(x.shape[1]):
        v = x[:, j]
        ours, _ = dim_alarms(v)
        hits = sum(any(a <= i <= b + ER.SLACK for a, b in wins) for i in ours.tolist())
        z = ER.rolling_z(v)
        peaks = [np.nanmax(z[max(a, ER.WINDOW):b + 1]) for a, b in wins if np.isfinite(z[max(a, ER.WINDOW):b + 1]).any()]
        score = (hits, float(max(peaks)) if peaks else 0.0)
        if score > top:
            best, top = j, score
    return best


def stat(alarms, wins):
    s = ER.score(alarms, wins)
    return dict(windows=s["windows"], hit=s["windows_hit"], alarms=s["alarms"])


def replay(key, name, dim, win):
    if key not in ZIPS:
        raise FileNotFoundError("unknown dataset")
    x, y = load(key, name)
    wins = ER.runs(y)
    if dim < 0 or dim >= x.shape[1]:
        dim = best_dim(key, name)
    v = x[:, dim]
    ours, static = dim_alarms(v)
    win = min(max(win, 0), max(len(wins) - 1, 0))
    a, b = wins[win] if wins else (len(v) // 2, len(v) // 2 + 50)
    s = max(a - 300, ER.WINDOW)
    e = min(len(v), max(b + 250, s + 600))
    e = min(e, s + 1500)
    idx = np.arange(s, e)
    w = np.stack([v[i - ER.WINDOW:i] for i in idx])
    med = np.median(w, axis=1)
    mad = np.median(np.abs(w - med[:, None]), axis=1)
    sig = np.maximum(np.maximum(1.4826 * mad, 0.05 * np.abs(med)), 0.1)
    upper = med + CFG.z_thresh * sig
    return dict(dataset=key, series=name, n=int(len(v)), dims=int(x.shape[1]), dim=int(dim), win=int(win), n_windows=len(wins),
                start=int(s), window=[int(a), int(b)],
                values=[round(float(t), 4) for t in v[s:e]], upper=[round(float(t), 4) for t in upper],
                labels=[int(t) for t in (y[s:e] > 0)],
                ours=[int(i) for i in ours if s <= i < e], static=[int(i) for i in static if s <= i < e],
                stats=dict(ours=stat(ours, wins), static=stat(static, wins)))