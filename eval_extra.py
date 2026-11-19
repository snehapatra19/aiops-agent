"""Extra real-data experiments, one per dataset role.

Copy these zips into data/real/ :  archive__13_.zip (NAB corpus), archive__12_.zip (UCI incident log),
loghub-master.zip, location_info_of_ssd_csv.zip.   Needs data/nab/labels__combined_windows.json (created by eval_nab.py).

  1. NAB corpus, 4 more real categories: same detector and thresholds as eval_real.py
  2. UCI incident log: triage model that flags tickets likely to be handed off or to breach SLA, trained on the past, tested on the future
  3. Loghub: log-evidence scorers, checked against the labelled BGL alert lines, plus a profile of all 16 systems
  4. Alibaba SSD location data: hardware topology context for alert grouping (no failure labels, so no accuracy score)

Run:  python eval_extra.py
"""
import bisect
import csv
import datetime as dt
import io
import json
import math
import os
import re
import statistics as st
import zipfile
from collections import Counter

import numpy as np

import eval_real as ER

DIR = os.path.join("data", "real")
LABELS = os.path.join("data", "nab", "labels__combined_windows.json")
CATS = ("realKnownCause", "realAdExchange", "realTraffic", "realTweets")


def zopen(name):
    p = os.path.join(DIR, name)
    if not os.path.exists(p):
        raise FileNotFoundError(f"Missing {p}. Copy the zip into {DIR}.")
    return zipfile.ZipFile(p)


def when(s):
    return dt.datetime.fromisoformat(s.split(".")[0])


def nab_more():
    if not os.path.exists(LABELS):
        raise FileNotFoundError(f"Missing {LABELS}. Run python eval_nab.py once so it downloads the label file.")
    labels = json.load(open(LABELS))
    zf = zopen("archive__13_.zip")
    tot = {m: dict(w=0, h=0, a=0, t=0) for m, _, _ in ER.METHODS}
    rows, points = [], 0
    for cat in CATS:
        for key in sorted(k for k in labels if k.startswith(cat + "/")):
            f, name = key.split("/")
            data = list(csv.DictReader(io.TextIOWrapper(zf.open(f"{cat}/{cat}/{name}"), "utf-8")))
            times = [when(r["timestamp"]) for r in data]
            x = np.array([[float(r["value"])] for r in data])
            wins = [(bisect.bisect_left(times, when(a)), bisect.bisect_right(times, when(b)) - 1) for a, b in labels[key]]
            start = max(int(0.15 * len(x)), ER.WINDOW)
            wins = [(a, b) for a, b in wins if b >= start]
            al = ER.alarms_for(x, start)
            points += len(x) - start
            for m, _, _ in ER.METHODS:
                s = ER.score(al[m], wins)
                t = tot[m]
                t["w"] += s["windows"]; t["h"] += s["windows_hit"]; t["a"] += s["alarms"]; t["t"] += s["alarms_in_window"]
                rows.append(dict(dataset="nab_more", series=key, method=m, points=len(x), windows=s["windows"], windows_hit=s["windows_hit"], alarms=s["alarms"]))
            print(f"  nab {key}: {len(wins)} windows, {len(x)} samples", flush=True)
    res = {}
    for m, t in tot.items():
        rec = t["h"] / t["w"] if t["w"] else 0
        pre = t["t"] / t["a"] if t["a"] else 0
        f1 = 2 * rec * pre / (rec + pre) if rec + pre else 0
        res[m] = dict(windows=t["w"], windows_hit=t["h"], alarms=t["a"], window_recall=round(rec, 3), alarm_precision=round(pre, 3),
                      f1=round(f1, 3), alarms_per_1000=round(1000 * t["a"] / max(points, 1), 2))
    return dict(name="NAB, four more real categories", series=len({r["series"] for r in rows}), results=res), rows


def auc(score, y):
    s, y = np.asarray(score, float), np.asarray(y)
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return None
    u, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    rank = (np.cumsum(cnt) - (cnt - 1) / 2)[inv]
    return round(float((rank[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)), 3)


def top_precision(score, y, frac):
    s, y = np.asarray(score, float), np.asarray(y)
    k = max(1, int(frac * len(s)))
    return round(float(y[np.argsort(-s, kind="stable")[:k]].mean()), 3)


def metrics(score, y, frac):
    return dict(auc=auc(score, y), precision_at_top=top_precision(score, y, frac), base_rate=round(float(np.mean(y)), 3))


class NB:
    def __init__(self, X, y, nf):
        self.n = Counter(y)
        self.c = [[Counter() for _ in range(nf)] for _ in (0, 1)]
        self.v = [set() for _ in range(nf)]
        for x, t in zip(X, y):
            for j, v in enumerate(x):
                self.c[t][j][v] += 1
                self.v[j].add(v)

    def score(self, x):
        s = math.log((self.n[1] + 1) / (self.n[0] + 1))
        for j, v in enumerate(x):
            V = len(self.v[j]) + 1
            s += math.log((self.c[1][j][v] + 1) / (self.n[1] + V)) - math.log((self.c[0][j][v] + 1) / (self.n[0] + V))
        return s


FEATS = ["category", "subcategory", "u_symptom", "impact", "urgency", "priority", "contact_type", "location", "assignment_group"]


def triage():
    zf = zopen("archive__12_.zip")
    rows = list(csv.DictReader(io.TextIOWrapper(zf.open("incident_event_log.csv"), "latin-1")))
    first, last = {}, {}
    for r in rows:
        first.setdefault(r["number"], r)
        last[r["number"]] = r
    stamp = lambda s: dt.datetime.strptime(s, "%d/%m/%Y %H:%M")
    ids = sorted(first, key=lambda k: stamp(first[k]["opened_at"]))
    cut = int(0.7 * len(ids))
    X = [[first[k][f] for f in FEATS] for k in ids]
    targets = dict(
        handoff=[int(int(last[k]["reassignment_count"]) >= 2) for k in ids],
        sla_breach=[int(last[k]["made_sla"] == "false") for k in ids],
    )
    out = {}
    pr = FEATS.index("priority")
    for name, y in targets.items():
        nb = NB(X[:cut], y[:cut], len(FEATS))
        sc = [nb.score(x) for x in X[cut:]]
        rate = {}
        for x, t in zip(X[:cut], y[:cut]):
            rate.setdefault(x[pr], []).append(t)
        base = [st.mean(rate.get(x[pr], [0.0])) for x in X[cut:]]
        out[name] = dict(model=metrics(sc, y[cut:], 0.2), priority_only=metrics(base, y[cut:], 0.2))
    hours = {}
    for k in ids:
        r = last[k]
        try:
            h = (stamp(r["resolved_at"]) - stamp(first[k]["opened_at"])).total_seconds() / 3600
        except ValueError:
            continue
        if h >= 0:
            hours.setdefault(first[k]["priority"], []).append(h)
    med = {p: dict(incidents=len(v), median_hours=round(st.median(v), 1)) for p, v in sorted(hours.items())}
    return dict(name="UCI incident event log", events=len(rows), incidents=len(ids), train=cut, test=len(ids) - cut, results=out, resolution=med)


KW = re.compile(r"error|fail|fatal|exception|denied|refused|timeout|timed out|panic|abort|kill|unable|critical|severe|corrupt", re.I)


def loghub():
    zf = zopen("loghub-master.zip")
    names = sorted(n for n in zf.namelist() if n.endswith("_2k.log_structured.csv"))
    systems = []
    bgl = None
    for n in names:
        rows = list(csv.DictReader(io.TextIOWrapper(zf.open(n), "utf-8", errors="replace")))
        sysname = n.split("/")[1]
        hit = sum(bool(KW.search(r["Content"])) for r in rows)
        systems.append(dict(system=sysname, lines=len(rows), templates=len({r["EventId"] for r in rows}), error_like_pct=round(100 * hit / len(rows), 1)))
        if sysname == "BGL":
            bgl = rows
    res = None
    if bgl:
        y = [int(r["Label"] != "-") for r in bgl]
        cut = len(bgl) // 2
        freq = Counter(r["EventId"] for r in bgl[:cut])
        total = sum(freq.values())
        rare = lambda r: -math.log((freq[r["EventId"]] + 0.5) / (total + 0.5 * (len(freq) + 1)))
        sev = {"FATAL": 3, "SEVERE": 3, "FAILURE": 3, "ERROR": 2, "WARNING": 1}
        test, yt = bgl[cut:], y[cut:]
        score = lambda v: dict(auc=auc(v, yt))
        res = dict(lines_tested=len(test), alert_lines=int(sum(yt)), results={
            "rare_template": score([rare(r) for r in test]),
            "error_keywords": score([int(bool(KW.search(r["Content"]))) for r in test]),
            "severity_level": score([sev.get(r["Level"], 0) for r in test]),
            "keywords_plus_rare": score([int(bool(KW.search(r["Content"]))) + 0.01 * rare(r) for r in test])})
    return dict(name="Loghub, 16 systems", systems=systems, bgl=res)


def ssd():
    zf = zopen("location_info_of_ssd_csv.zip")
    apps, models, nodes, racks, n = Counter(), Counter(), Counter(), set(), 0
    with zf.open("location_info_of_ssd.csv") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, "utf-8")):
            n += 1
            apps[r["app"]] += 1
            models[r["model"]] += 1
            nodes[(r["rack_id"], r["node_id"])] += 1
            racks.add(r["rack_id"])
    per = list(nodes.values())
    return dict(name="Alibaba SSD location data", disks=n, racks=len(racks), nodes=len(nodes), apps=dict(apps.most_common(6)),
                models=dict(models.most_common(6)), mean_disks_per_node=round(st.mean(per), 1), max_disks_per_node=max(per))


def main():
    out, rows = {}, []
    print("NAB corpus")
    out["nab_more"], r = nab_more()
    rows += r
    print("UCI incident log", flush=True)
    t = triage()
    print("Loghub", flush=True)
    lg = loghub()
    print("SSD location data", flush=True)
    hw = ssd()
    os.makedirs("results", exist_ok=True)
    with open("results/extra_per_series.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    json.dump(dict(datasets=out, triage=t, logs=lg, hardware=hw), open("results/extra_summary.json", "w"), indent=2)
    print(json.dumps(out["nab_more"]["results"], indent=1))
    print(json.dumps(t["results"], indent=1))
    print(json.dumps(lg["bgl"], indent=1))
    print("Saved results/extra_summary.json")


if __name__ == "__main__":
    main()