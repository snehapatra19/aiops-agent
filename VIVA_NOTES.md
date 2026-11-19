# Viva preparation (defend the work honestly)
**One-liner**: an end-to-end, safety-gated incident workflow (detect -> correlate -> RCA -> plan -> simulated fix -> verify -> escalate -> report) evaluated against a rule baseline on a labelled synthetic benchmark.

**Likely questions**
1. *Why synthetic data?* No real operational data/infra available before deadline; labels needed for ground truth. We state the leakage risk openly.
2. *Why is RCA not 100%?* Ambiguous/missing-evidence/misleading-log cases; see confusion matrix. Uncertain ones are escalated, so selective accuracy (confident cases) is higher than overall top-1.
3. *What is "confidence"?* softmax of summed evidence scores: relative support among 5 candidates, not a probability.
4. *Why not mark success after action?* Execution OK != recovery; we compare post-action metrics to pre-incident baseline (ratio rule). Baseline's false-resolution rate shows why.
5. *Safety?* allowlist + policy + approval for high risk + simulation only; LLM (optional) can only choose from a fixed cause list.
6. *Is this an LLM agent?* The LangGraph graph is a stateful multi-step workflow with deterministic tools. The LLM is optional and untested here; do not claim an LLM-driven multi-agent system.
7. *vs MHP-RCA?* Not reproduced; it targets microservice RCA from alert/event time series (Hawkes/Granger/PageRank). Verify details from the paper before writing claims.
8. *Equations*: z = (x - median)/(1.4826*MAD); P = F1 = 2PR/(P+R); confidence_c = e^{s_c}/sum e^{s_k}; verification ratio = (post - base)/(peak - base).
