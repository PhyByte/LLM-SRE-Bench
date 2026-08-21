# LLM Observability Benchmark — Comparison

Generated: 2026-08-21 23:21:07 UTC  
Runs per test: 3 · Models: 21 · Test cases: 82

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set are ranked.

| Rank | Model | Global Score | Log Parsing (15%) | Anomaly Detection (25%) | Pattern & Correlation (15%) | Metrics Time-Series (10%) | Root Cause & Summary (10%) | Multi-modal RCA (20%) | Efficiency & Consistency (5%) | Duration |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **opus-4.8** 🥇 | **76.0** | 91.9 | 68.8 | 90.7 | 100.0 | 57.8 | 60.6 | 69.5 | 14m 4s |
| 2 | **grok-4.6-low** 🥈 | **72.6** | 91.3 | 64.3 | 83.3 | 77.6 | 54.6 | 68.8 | 66.8 | 32m 31s |
| 3 | **fable-5** 🥉 | **71.7** | 92.1 | 64.3 | 77.3 | 100.0 | 60.3 | 57.6 | 53.1 | 36m 32s |
| 4 | **grok-4.6** | **70.7** | 91.4 | 55.6 | 84.0 | 100.0 | 55.0 | 65.2 | 38.7 | 176m 3s |
| 5 | **gpt-5.6-terra** | **70.6** | 91.9 | 62.1 | 86.0 | 77.9 | 49.8 | 59.5 | 74.1 | 16m 5s |
| 6 | **grok-4.5-low** | **70.4** | 91.9 | 63.0 | 82.0 | 69.3 | 56.2 | 65.9 | 57.8 | 42m 18s |
| 7 | **grok-4** | **67.9** | 89.5 | 62.8 | 72.0 | 68.7 | 52.7 | 63.6 | 63.0 | 33m 10s |
| 8 | **sonnet-5** | **67.8** | 89.3 | 63.1 | 86.0 | 69.5 | 48.7 | 54.9 | 58.7 | 31m 20s |
| 9 | **gpt-5.6-sol** | **67.3** | 91.7 | 61.1 | 75.3 | 73.7 | 49.2 | 56.2 | 68.9 | 26m 46s |
| 10 | **gpt-5.6-luna** | **67.2** | 91.3 | 63.1 | 82.7 | 66.1 | 48.5 | 51.4 | 70.7 | 20m 9s |
| 11 | **gemma-4-31b** | **64.1** | 90.4 | 61.7 | 66.0 | 72.2 | 46.1 | 59.2 | 30.7 | 150m 3s |
| 12 | **haiku-4-5** | **63.8** | 91.6 | 52.7 | 79.3 | 53.9 | 49.5 | 54.2 | 76.5 | 10m 34s |
| 13 | **gpt-4o** | **61.0** | 90.6 | 62.4 | 61.3 | 42.5 | 39.1 | 53.0 | 77.3 | 15m 21s |
| 14 | **fable-5-low** | **60.3** | 91.0 | 67.4 | 47.3 | 71.5 | 0.0 | 61.4 | 65.0 | 21m 8s |
| 15 | **qwen3-coder-30b** | **56.9** | 87.9 | 60.9 | 68.0 | 27.5 | 49.4 | 33.3 | 78.6 | 4m 50s |
| 16 | **gemma-3-12B** | **50.6** | 74.8 | 51.8 | 76.0 | 19.1 | 38.2 | 36.0 | 42.4 | 237m 39s |
| 17 | **qwen3.8-27b** | **45.1** | 88.0 | 69.3 | 0.0 | 37.2 | 0.0 | 33.1 | 85.5 | 3m 46s |

**Incomplete coverage** (ran only some categories — not ranked, because a partial run's global score isn't comparable). Re-run the full suite for these:

- grok-4.5 — ran only: metrics_timeseries, pattern_correlation, root_cause
- gemma-4-26B-a4b — ran only: metrics_timeseries, pattern_correlation, root_cause

**Did not complete** (every call failed — bad key, no model access, or unreachable endpoint):

- mock-heuristic (26 calls failed)
- mock-naive (26 calls failed)

## What each column measures

Scores are 0–100, higher is better. **Duration** and **Cost** are lower-is-better.

- **Rank** — position among models that ran the full category set, best Global Score first (🥇🥈🥉 mark the top three). Partial or all-failed models are listed separately below and not ranked.
- **Model** — the model's name as configured in `models.json`.
- **Global Score** — the headline quality number: the weighted average of the category columns, using the weights shown in each header. Only categories the model actually ran count (weights renormalize), so a partial run still yields a 0–100 value — which is why partial runs aren't ranked against full ones.
- **Log Parsing** (15% of Global Score) — Turning raw log lines into templates (variables masked). Score = 0.5 exact-template accuracy + 0.5 token-level F1 vs ground-truth templates.
- **Anomaly Detection** (25% of Global Score) — Flagging which log lines are anomalous. Precision/recall/F1 over per-line labels vs the ground truth.
- **Pattern & Correlation** (15% of Global Score) — Identifying recurring event patterns and cause→effect links between them.
- **Metrics Time-Series** (10% of Global Score) — Spotting anomalies in a numeric metric series. Point-wise precision/recall/F1 with a ±1-index tolerance.
- **Root Cause & Summary** (10% of Global Score) — Explaining the incident. 0.4 ROUGE-L on the summary + 0.3 ROUGE-1 on the root cause + 0.3 keyword recall of the key entities.
- **Multi-modal RCA** (20% of Global Score) — Localizing the culprit service across metrics, logs and traces on real microservice incidents. 0.4 culprit + 0.25 fault type + 0.25 modality grounding (citing the modalities that actually carry signal) + 0.1 evidence recall.
- **Efficiency & Consistency** (5% of Global Score) — Derived from the runs above, not a dataset. 0.4 speed (vs a 20s budget) + 0.3 token thrift (vs 4000 tokens) + 0.3 run-to-run score stability.
- **Duration** — total model time to run this model's whole set: the sum of every call's measured latency across all cases and runs. It is *not* wall-clock — cached calls keep their originally measured latency, so it stays stable across re-runs.
