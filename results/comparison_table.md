# LLM Observability Benchmark — Comparison

Generated: 2026-08-17 22:54:23 UTC  
Runs per test: 3 · Models: 14 · Test cases: 64

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set are ranked.

| Rank | Model | Global Score | Log Parsing (15%) | Anomaly Detection (25%) | Pattern & Correlation (15%) | Metrics Time-Series (10%) | Root Cause & Summary (10%) | Multi-modal RCA (20%) | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **grok-4.6-low** 🥇 | **74.7** | 91.4 | 64.1 | 88.0 | 100.0 | 53.9 | 68.8 | 51.5 | 13m 56s | $0.79 |
| 2 | **grok-4.5-low** 🥈 | **72.9** | 92.4 | 61.5 | 92.0 | 90.0 | 54.8 | 65.9 | 45.0 | 18m 53s | $0.83 |
| 3 | **opus-4.8** 🥉 | **72.0** | 91.9 | 68.8 | 90.7 | 100.0 | 57.8 | 38.6 | 77.5 | 10m 47s | $2.29 |
| 4 | **fable-5** | **71.7** | 92.1 | 64.3 | 77.3 | 100.0 | 60.3 | 57.6 | 53.1 | 36m 32s | $9.49 |
| 5 | **gpt-5.6-terra** | **71.3** | 91.9 | 62.1 | 82.7 | 86.3 | 54.2 | 59.5 | 71.9 | 11m 27s | $1.72 |
| 6 | **grok-4.6** | **70.4** | 91.4 | 55.6 | 84.0 | 96.7 | 55.0 | 65.2 | 38.6 | 173m 42s | $1.00 |
| 7 | **gpt-5.6-luna** | **69.3** | 91.3 | 63.1 | 85.3 | 79.6 | 51.9 | 51.4 | 72.7 | 12m 59s | $0.85 |
| 8 | **grok-4** | **69.0** | 89.5 | 62.8 | 73.3 | 80.0 | 51.8 | 63.6 | 59.3 | 30m 55s | $1.52 |
| 9 | **sonnet-5** | **69.0** | 89.3 | 63.1 | 84.0 | 86.9 | 55.3 | 52.1 | 51.1 | 36m 29s | $3.47 |
| 10 | **gpt-5.6-sol** | **68.6** | 91.7 | 61.1 | 74.7 | 83.3 | 54.3 | 56.2 | 67.3 | 21m 21s | $3.65 |
| 11 | **fable-5-low** | **68.3** | 91.0 | 67.4 | 74.7 | 100.0 | 62.3 | 32.8 | 76.0 | 15m 45s | $3.58 |
| 12 | **gpt-4o** | **62.1** | 90.6 | 62.4 | 60.0 | 53.3 | 42.3 | 53.0 | 76.1 | 13m 11s | $1.17 |
| 13 | **haiku-4-5** | **61.5** | 91.6 | 52.7 | 80.0 | 71.4 | 53.3 | 30.0 | 83.2 | 5m 57s | $0.32 |
| 14 | **gemma-3-12B** | **52.1** | 74.8 | 51.8 | 81.3 | 24.3 | 40.5 | 36.0 | 40.2 | 232m 23s | $0.00 |

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
