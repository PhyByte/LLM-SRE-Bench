# LLM Observability Benchmark — Comparison

Generated: 2026-07-27 21:52:57 UTC  
Runs per test: 3 · Models: 12 · Test cases: 46

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set are ranked.

| Rank | Model | Global Score | Log Parsing (20%) | Anomaly Detection (30%) | Pattern & Correlation (20%) | Metrics Time-Series (15%) | Root Cause & Summary (10%) | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **claude-opus-4-8** 🥇 | **82.2** | 91.9 | 68.8 | 90.7 | 100.0 | 57.8 | 86.1 | 7m 9s | $1.10 |
| 2 | **fable-5-low** 🥈 | **78.7** | 91.0 | 67.4 | 74.7 | 100.0 | 62.3 | 81.3 | 12m 29s | $2.15 |
| 3 | **grok-4.5-low** 🥉 | **78.0** | 92.4 | 61.5 | 92.0 | 90.0 | 54.8 | 74.3 | 7m 29s | $0.09 |
| 4 | **fable-5** | **77.8** | 92.1 | 64.3 | 77.3 | 100.0 | 60.3 | 71.4 | 22m 15s | $3.26 |
| 5 | **gpt-5.6-terra** | **76.2** | 91.9 | 62.1 | 82.7 | 86.3 | 54.2 | 84.9 | 6m 41s | $0.65 |
| 6 | **grok-4.5** | **76.1** | 92.2 | 62.3 | 81.3 | 93.3 | 55.5 | 62.5 | 33m 1s | $0.28 |
| 7 | **gpt-5.6-luna** | **75.6** | 91.3 | 63.1 | 85.3 | 79.6 | 51.9 | 83.9 | 8m 29s | $0.41 |
| 8 | **gpt-5.6-sol** | **73.5** | 91.7 | 61.1 | 74.7 | 83.3 | 54.3 | 79.4 | 13m 31s | $1.46 |
| 9 | **grok-4** | **72.0** | 89.5 | 62.8 | 73.3 | 80.0 | 51.8 | 69.0 | 24m 59s | $0.47 |
| 10 | **gemma-4-31b** | **68.5** | 90.3 | 61.4 | 58.7 | 86.7 | 50.8 | 44.1 | 54m 39s | $0.00 |
| 11 | **gpt-4o** | **65.6** | 90.6 | 62.4 | 60.0 | 53.3 | 42.3 | 91.4 | 3m 59s | $0.00 |
| 12 | **qwen3-32b** | **59.5** | 80.3 | 48.3 | 85.3 | 29.7 | 47.5 | 52.6 | 34m 43s | $0.00 |

## What each column measures

Scores are 0–100, higher is better. **Duration** and **Cost** are lower-is-better.

- **Rank** — position among models that ran the full category set, best Global Score first (🥇🥈🥉 mark the top three). Partial or all-failed models are listed separately below and not ranked.
- **Model** — the model's name as configured in `models.json`.
- **Global Score** — the headline quality number: the weighted average of the category columns, using the weights shown in each header. Only categories the model actually ran count (weights renormalize), so a partial run still yields a 0–100 value — which is why partial runs aren't ranked against full ones.
- **Log Parsing** (20% of Global Score) — Turning raw log lines into templates (variables masked). Score = 0.5 exact-template accuracy + 0.5 token-level F1 vs ground-truth templates.
- **Anomaly Detection** (30% of Global Score) — Flagging which log lines are anomalous. Precision/recall/F1 over per-line labels vs the ground truth.
- **Pattern & Correlation** (20% of Global Score) — Identifying recurring event patterns and cause→effect links between them.
- **Metrics Time-Series** (15% of Global Score) — Spotting anomalies in a numeric metric series. Point-wise precision/recall/F1 with a ±1-index tolerance.
- **Root Cause & Summary** (10% of Global Score) — Explaining the incident. 0.4 ROUGE-L on the summary + 0.3 ROUGE-1 on the root cause + 0.3 keyword recall of the key entities.
- **Efficiency & Consistency** (5% of Global Score) — Derived from the runs above, not a dataset. 0.4 speed (vs a 20s budget) + 0.3 token thrift (vs 4000 tokens) + 0.3 run-to-run score stability.
- **Duration** — total model time to run this model's whole set: the sum of every call's measured latency across all cases and runs. It is *not* wall-clock — cached calls keep their originally measured latency, so it stays stable across re-runs.
- **Cost** — total USD to run this model's whole set at provider list price: Σ(input_tokens × input_price + output_tokens × output_price) ÷ 1,000,000. It counts every call (including cached ones) — it's the cost of *running the benchmark*, not your actual billed amount. Self-hosted/local models show `$0.00`; models with no price configured show `—`.
