import json
import os
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
SYSTEM = (
    "You explain automated incident handling to an on-call engineer. Use only the facts in the JSON. "
    "Do not invent services, numbers or causes. If the facts show the agent was unsure or handed the incident to a human, "
    "say so plainly and say what a person should check first. Write 4 to 6 short sentences in plain English, without headings or bullet points."
)
_cache = {}


def env(name, default=None):
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == name:
                    return v.strip().strip('"').strip("'")
    return default


def status():
    return dict(configured=bool(env("GEMINI_API_KEY")), model=env("GEMINI_MODEL", "gemini-2.5-flash"))


def facts(rep):
    rc = rep.get("root_cause") or {}
    ver = rep.get("verification") or {}
    return dict(
        outcome=rep.get("final_status"),
        escalation_reason=rep.get("escalation_reason"),
        abnormal_metrics=[dict(service=s["service"], metric=s["metric"], peak_value=s["peak_value"], peak_z=s["peak_z"]) for s in rep.get("symptoms", [])[:5]],
        related_alerts=len(rep.get("correlated_alerts", [])),
        root_cause=dict(top=rc.get("top"), service=rc.get("root_service"), confidence=rc.get("confidence"), ranked=(rc.get("ranked") or [])[:3],
                        evidence=rc.get("evidence"), missing=rc.get("missing"), uncertain=rc.get("uncertain"), next_step=rc.get("next_step")),
        proposed_action=rep.get("action"),
        policy=rep.get("policy"),
        executed=bool(rep.get("execution")),
        verification=dict(overall=ver.get("overall"), series=[dict(service=x.get("service"), metric=x.get("metric"), state=x.get("state")) for x in ver.get("series", [])]) if ver else None,
    )


def plain(name):
    return str(name or "unknown").replace("_", " ")


def by_rules(rep):
    f = facts(rep)
    rc = f["root_cause"]
    sym = f["abnormal_metrics"]
    out = []
    if sym:
        out.append(f"{len(sym)} metrics stayed abnormal, starting with {plain(sym[0]['metric'])} on {sym[0]['service']}, and {f['related_alerts']} alerts were grouped into this incident.")
    out.append(f"The most likely cause is {plain(rc['top'])} at {rc['service']} with {round((rc['confidence'] or 0) * 100)}% confidence." + (" The agent marked this as uncertain." if rc["uncertain"] else ""))
    if rc["evidence"]:
        out.append("Evidence: " + "; ".join(e.split(": ", 1)[-1] for e in rc["evidence"][:3]) + ".")
    act = f["proposed_action"]
    if act:
        out.append(f"It proposed {plain(act['action'])} on {act['target']}" + (" but the policy requires a person to approve it." if (f["policy"] or {}).get("requires_approval") else "."))
    ver = f["verification"]
    if ver:
        out.append(f"After the fix the metrics were re-measured and the result was {plain(ver['overall'])}.")
    if f["outcome"] == "escalated":
        out.append(f"A human was paged because: {plain(f['escalation_reason'])}." + (f" Suggested next step: {rc['next_step']}" if rc["next_step"] else ""))
    return " ".join(out)


def ask(prompt):
    body = dict(systemInstruction=dict(parts=[dict(text=SYSTEM)]), contents=[dict(role="user", parts=[dict(text=prompt)])],
                generationConfig=dict(temperature=0.2, maxOutputTokens=700))
    req = urllib.request.Request(URL.format(model=status()["model"]), data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": env("GEMINI_API_KEY")}, method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode("utf-8"))
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts).strip()


def explain(rep, question=None):
    key = (rep.get("incident_id"), question or "")
    if key in _cache:
        return _cache[key]
    fallback = by_rules(rep)
    if not env("GEMINI_API_KEY"):
        return dict(text=fallback, source="rules", note="No Gemini key found, showing the built-in explanation.")
    prompt = "Facts about one incident (JSON):\n" + json.dumps(facts(rep), default=str)
    prompt += f"\n\nQuestion from the engineer: {question}\nAnswer only from the facts. If the facts do not say, answer that you do not know." if question else "\n\nExplain what happened and what the agent did."
    try:
        out = dict(text=ask(prompt), source="gemini", model=status()["model"])
        _cache[key] = out
        return out
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError) as e:
        return dict(text=fallback, source="rules", note=f"Gemini could not be reached ({type(e).__name__}), showing the built-in explanation.")