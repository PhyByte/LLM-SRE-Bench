# SRE / Observability Benchmark — Comparison

Generated: 2026-08-31 10:44:51 UTC  
Runs per test: 3 · Models: 23 · Test cases: 280

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set for this track are ranked. See also [Developer / Coding](comparison_table_developer.md).

| Rank | Model | Global Score | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|
| 1 | **qwen3-coder-30b** 🥇 | **90.3** | 90.3 | 15m 16s | $0.00 |
| 2 | **gemma-3-12B** 🥈 | **88.8** | 88.8 | 30m 29s | $0.00 |
| 3 | **gpt-4o** 🥉 | **88.3** | 88.3 | 30m 53s | $2.73 |
| 4 | **qwen3.8-27b** | **88.0** | 88.0 | 41m 46s | $0.00 |
| 5 | **qwen3-32b** | **84.0** | 84.0 | 66m 27s | $0.00 |
| 6 | **qwen3.6-27b** | **84.0** | 84.0 | 69m 53s | $0.00 |
| 7 | **opus-4.8** | **79.8** | 79.8 | 74m 7s | $11.07 |
| 8 | **haiku-4-5** | **78.8** | 78.8 | 50m 34s | $2.22 |
| 9 | **gpt-5.6-terra** | **78.3** | 78.3 | 69m 9s | $6.52 |
| 10 | **fable-5-low** | **78.0** | 78.0 | 29m 13s | $7.09 |
| 11 | **grok-4** | **75.5** | 75.5 | 106m 39s | $4.13 |
| 12 | **grok-4.5-low** | **72.4** | 72.4 | 115m 35s | $2.94 |
| 13 | **gpt-5.6-sol** | **72.0** | 72.0 | 107m 49s | $15.20 |
| 14 | **gpt-5.6-luna** | **71.5** | 71.5 | 105m 6s | $3.76 |
| 15 | **grok-4.6-low** | **68.9** | 68.9 | 126m 54s | $3.03 |
| 16 | **sonnet-5** | **68.6** | 68.6 | 111m 56s | $11.73 |
| 17 | **gemini-3.6-flash** | **64.1** | 64.1 | 190m 28s | $2.29 |
| 18 | **fable-5** | **61.4** | 61.4 | 48m 5s | $13.05 |
| 19 | **grok-4.5** | **50.9** | 50.9 | 263m 2s | $2.90 |
| 20 | **gemini-3.1-pro** | **49.7** | 49.7 | 75m 35s | $0.47 |
| 21 | **grok-4.6** | **46.8** | 46.8 | 631m 35s | $3.09 |
| 22 | **gemma-4-31b** | **39.9** | 39.9 | 458m 44s | $0.00 |
| 23 | **gemma-4-26B-a4b** | **35.6** | 35.6 | 234m 19s | $0.00 |

## What each column measures

Scores are 0–100, higher is better. **Duration** and **Cost** are lower-is-better.

- **Rank** — position among models that ran the full category set, best Global Score first (🥇🥈🥉 mark the top three). Partial or all-failed models are listed separately below and not ranked.
- **Model** — the model's name as configured in `models.json`.
- **Global Score** — the headline quality number: the weighted average of the category columns, using the weights shown in each header. Only categories the model actually ran count (weights renormalize), so a partial run still yields a 0–100 value — which is why partial runs aren't ranked against full ones.
- **Efficiency & Consistency** (5% of Global Score) — Derived from the runs above, not a dataset. 0.4 speed (vs a 20s budget) + 0.3 token thrift (vs 4000 tokens) + 0.3 run-to-run score stability.
- **Duration** — total model time to run this model's whole set: the sum of every call's measured latency across all cases and runs. It is *not* wall-clock — cached calls keep their originally measured latency, so it stays stable across re-runs.
- **Cost** — total USD to run this model's whole set at provider list price: Σ(input_tokens × input_price + output_tokens × output_price) ÷ 1,000,000. It counts every call (including cached ones) — it's the cost of *running the benchmark*, not your actual billed amount. Self-hosted/local models show `$0.00`; models with no price configured show `—`.
