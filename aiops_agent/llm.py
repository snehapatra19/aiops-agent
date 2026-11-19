"""OPTIONAL live-LLM RCA re-ranker (hybrid mode). NOT used in reported experiments.

The LLM may only re-rank causes from the fixed candidate list; output is JSON-schema
validated and any invalid output is discarded (deterministic ranking is kept).
It never produces commands. Needs `pip install anthropic` and ANTHROPIC_API_KEY.
This path has NOT been executed in this project's test runs (no API key used).
"""
import json
import os
from .rca import CAUSES


def validate_llm_output(obj):
    if not isinstance(obj, dict) or obj.get("top_cause") not in CAUSES:
        raise ValueError("invalid top_cause")
    c = obj.get("confidence")
    if not isinstance(c, (int, float)) or not 0 <= c <= 1:
        raise ValueError("invalid confidence")
    if not isinstance(obj.get("reasoning", ""), str):
        raise ValueError("invalid reasoning")
    return obj


def llm_rerank(rca, evidence_summary, model=None):
    if not os.getenv("ANTHROPIC_API_KEY"):
        return rca, "llm_skipped_no_key"
    try:
        import anthropic
        client = anthropic.Anthropic()
        prompt = ("You are an SRE assistant. Choose the most likely root cause ONLY from "
                  f"{CAUSES}. Evidence:\n{json.dumps(evidence_summary)[:4000]}\n"
                  'Reply with JSON only: {"top_cause":..., "confidence":0-1, "reasoning":"..."}')
        msg = client.messages.create(model=model or os.getenv("AIOPS_LLM_MODEL", "claude-sonnet-4-6"),
                                     max_tokens=300, messages=[{"role": "user", "content": prompt}])
        out = validate_llm_output(json.loads(msg.content[0].text))
        rca.method = "hybrid_llm"
        rca.evidence["llm"] = [out["reasoning"]]
        if out["top_cause"] != rca.top_cause:   # disagreement => be conservative
            rca.uncertain = True
        return rca, "llm_ok"
    except Exception as e:  # any failure -> keep deterministic result
        return rca, f"llm_error:{type(e).__name__}"
