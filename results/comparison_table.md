# LLM Observability Benchmark — Comparison

Generated: 2026-08-16 22:59:45 UTC  
Runs per test: 3 · Models: 16 · Test cases: 64

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set are ranked.

| Rank | Model | Global Score | Log Parsing (15%) | Anomaly Detection (25%) | Pattern & Correlation (15%) | Metrics Time-Series (10%) | Root Cause & Summary (10%) | Multi-modal RCA (20%) | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **claude-opus-4-8** 🥇 | **77.7** | 91.9 | 68.8 | 90.7 | 100.0 | 57.8 | 68.1 | 74.5 | 11m 35s | $2.77 |
| 2 | **fable-5-low** 🥈 | **76.3** | 91.0 | 67.4 | 74.7 | 100.0 | 62.3 | 74.1 | 70.7 | 17m 34s | $5.37 |
| 3 | **grok-4.6-low** 🥉 | **75.2** | 91.4 | 64.1 | 88.0 | 100.0 | 53.9 | 70.3 | 55.6 | 11m 38s | $0.55 |
| 4 | **grok-4.5-low** | **72.6** | 92.4 | 61.5 | 92.0 | 90.0 | 54.8 | 64.0 | 45.8 | 18m 53s | $0.83 |
| 5 | **gpt-5.6-terra** | **72.4** | 91.9 | 62.1 | 82.7 | 86.3 | 54.2 | 63.9 | 76.6 | 9m 34s | $1.35 |
| 6 | **gpt-5.6-sol** | **71.5** | 91.7 | 61.1 | 74.7 | 83.3 | 54.3 | 69.6 | 72.1 | 17m 11s | $2.78 |
| 7 | **gpt-5.6-luna** | **71.4** | 91.3 | 63.1 | 85.3 | 79.6 | 51.9 | 60.8 | 76.5 | 11m 13s | $0.71 |
| 8 | **haiku-4-5** | **68.6** | 91.6 | 52.7 | 80.0 | 71.4 | 53.3 | 66.3 | 78.4 | 7m 8s | $0.48 |

**Incomplete coverage** (ran only some categories — not ranked, because a partial run's global score isn't comparable). Re-run the full suite for these:

- fable-5 — ran only: anomaly_detection, log_parsing, metrics_timeseries, pattern_correlation, root_cause
- sonnet-5 — ran only: anomaly_detection, log_parsing, metrics_timeseries, pattern_correlation, root_cause
- grok-4.5 — ran only: anomaly_detection, log_parsing, metrics_timeseries, pattern_correlation, root_cause
- grok-4.6 — ran only: anomaly_detection, log_parsing, metrics_timeseries, pattern_correlation, root_cause
- grok-4 — ran only: anomaly_detection, log_parsing, metrics_timeseries, pattern_correlation, root_cause
- gemma-4-31b — ran only: anomaly_detection, log_parsing, metrics_timeseries, pattern_correlation, root_cause
- gpt-4o — ran only: anomaly_detection, log_parsing, metrics_timeseries, pattern_correlation, root_cause
- qwen3-32b — ran only: anomaly_detection, log_parsing, metrics_timeseries, pattern_correlation, root_cause

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
