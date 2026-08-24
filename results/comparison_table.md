# LLM Observability Benchmark — Comparison

Generated: 2026-08-24 20:13:56 UTC  
Runs per test: 3 · Models: 23 · Test cases: 82

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set are ranked.

| Rank | Model | Global Score | Log Parsing (15%) | Anomaly Detection (25%) | Pattern & Correlation (15%) | Metrics Time-Series (10%) | Root Cause & Summary (10%) | Multi-modal RCA (20%) | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **opus-4.8** 🥇 | **73.3** | 91.9 | 68.8 | 86.0 | 81.8 | 55.2 | 60.6 | 71.8 | 17m 38s | $4.24 |
| 2 | **grok-4.6-low** 🥈 | **72.6** | 91.3 | 64.3 | 83.3 | 77.6 | 54.6 | 68.8 | 66.8 | 32m 31s | $1.10 |
| 3 | **gpt-5.6-terra** 🥉 | **70.6** | 91.9 | 62.1 | 86.0 | 77.9 | 49.8 | 59.5 | 74.1 | 16m 5s | $2.08 |
| 4 | **grok-4.5-low** | **70.4** | 91.9 | 63.0 | 82.0 | 69.3 | 56.2 | 65.9 | 57.8 | 42m 18s | $1.24 |
| 5 | **grok-4.5** | **70.0** | 91.6 | 61.6 | 85.3 | 69.5 | 54.5 | 68.3 | 39.4 | 108m 25s | $1.26 |
| 6 | **grok-4.6** | **69.2** | 91.4 | 55.6 | 86.0 | 79.6 | 55.9 | 65.2 | 41.0 | 248m 2s | $1.15 |
| 7 | **sonnet-5** | **68.3** | 89.3 | 63.1 | 86.0 | 69.5 | 54.0 | 54.9 | 58.9 | 31m 19s | $4.07 |
| 8 | **grok-4** | **67.9** | 89.5 | 62.8 | 72.0 | 68.7 | 52.7 | 63.6 | 63.0 | 33m 10s | $1.74 |
| 9 | **gpt-5.6-sol** | **67.3** | 91.7 | 61.1 | 75.3 | 73.7 | 49.2 | 56.2 | 68.9 | 26m 46s | $4.46 |
| 10 | **gpt-5.6-luna** | **67.2** | 91.3 | 63.1 | 82.7 | 66.1 | 48.5 | 51.4 | 70.7 | 20m 9s | $1.09 |
| 11 | **qwen3.8-27b** | **66.9** | 88.0 | 69.3 | 79.3 | 59.3 | 49.9 | 60.1 | 30.3 | 91m 1s | $0.00 |
| 12 | **fable-5-low** | **66.6** | 91.0 | 67.4 | 61.3 | 71.5 | 41.4 | 61.4 | 66.1 | 24m 16s | $7.67 |
| 13 | **gemini-3.1-pro** | **66.4** | 90.7 | 64.0 | 71.3 | 69.3 | 46.8 | 59.8 | 50.1 | 68m 59s | $1.41 |
| 14 | **gemma-4-26B-a4b** | **66.2** | 88.7 | 70.9 | 73.3 | 58.1 | 45.3 | 60.4 | 34.9 | 65m 37s | $0.00 |
| 15 | **gemini-3.6-flash** | **66.0** | 89.7 | 64.8 | 72.0 | 71.6 | 51.3 | 54.5 | 48.2 | 67m 52s | $0.97 |
| 16 | **qwen3.6-27b** | **64.2** | 91.1 | 63.0 | 68.0 | 61.5 | 48.5 | 60.2 | 30.0 | 175m 1s | $0.00 |
| 17 | **fable-5** | **64.1** | 92.1 | 64.3 | 63.3 | 63.6 | 40.5 | 57.6 | 55.4 | 41m 9s | $10.38 |
| 18 | **gemma-4-31b** | **64.1** | 90.4 | 61.7 | 66.0 | 72.2 | 46.1 | 59.2 | 30.7 | 150m 3s | $0.00 |
| 19 | **haiku-4-5** | **63.8** | 91.6 | 52.7 | 79.3 | 53.9 | 49.5 | 54.2 | 76.5 | 10m 34s | $0.71 |
| 20 | **gpt-4o** | **61.0** | 90.6 | 62.4 | 61.3 | 42.5 | 39.1 | 53.0 | 77.3 | 15m 21s | $1.32 |
| 21 | **qwen3-coder-30b** | **55.8** | 87.9 | 60.9 | 67.3 | 22.5 | 44.4 | 33.3 | 77.8 | 7m 38s | $0.00 |
| 22 | **qwen3-32b** | **52.1** | 84.1 | 48.3 | 71.3 | 19.4 | 45.2 | 41.5 | 38.2 | 70m 36s | $0.00 |
| 23 | **gemma-3-12B** | **50.6** | 74.8 | 51.8 | 76.0 | 19.1 | 38.2 | 36.0 | 42.4 | 237m 39s | $0.00 |

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
- **Cost** — total USD to run this model's whole set at provider list price: Σ(input_tokens × input_price + output_tokens × output_price) ÷ 1,000,000. It counts every call (including cached ones) — it's the cost of *running the benchmark*, not your actual billed amount. Self-hosted/local models show `$0.00`; models with no price configured show `—`.
