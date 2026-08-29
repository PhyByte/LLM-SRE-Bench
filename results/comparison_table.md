# SRE / Observability Benchmark — Comparison

Generated: 2026-08-26 21:30:28 UTC  
Runs per test: 3 · Models: 23 · Test cases: 80

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set for this track are ranked. See also [Developer / Coding](comparison_table_developer.md).

| Rank | Model | Global Score | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|
| 1 | **qwen3-coder-30b** 🥇 | **91.0** | 91.0 | 3m 31s | $0.00 |
| 2 | **qwen3.8-27b** 🥈 | **90.0** | 90.0 | 10m 6s | $0.00 |
| 3 | **gemma-3-12B** 🥉 | **89.6** | 89.6 | 8m 51s | $0.00 |
| 4 | **gpt-4o** | **88.4** | 88.4 | 12m 5s | $0.71 |
| 5 | **qwen3-32b** | **87.1** | 87.1 | 14m 40s | $0.00 |
| 6 | **qwen3.6-27b** | **86.7** | 86.7 | 16m 19s | $0.00 |
| 7 | **opus-4.8** | **81.4** | 81.4 | 21m 4s | $2.87 |
| 8 | **fable-5-low** | **80.6** | 80.6 | 10m 44s | $2.62 |
| 9 | **haiku-4-5** | **80.0** | 80.0 | 12m 58s | $0.64 |
| 10 | **gpt-5.6-terra** | **79.4** | 79.4 | 20m 5s | $1.61 |
| 11 | **grok-4.5-low** | **77.8** | 77.8 | 25m 53s | $0.78 |
| 12 | **grok-4** | **77.0** | 77.0 | 29m 38s | $1.05 |
| 13 | **gpt-5.6-luna** | **73.1** | 73.1 | 27m 57s | $1.02 |
| 14 | **grok-4.6-low** | **72.7** | 72.7 | 29m 32s | $0.81 |
| 15 | **sonnet-5** | **72.5** | 72.5 | 27m 19s | $2.79 |
| 16 | **gpt-5.6-sol** | **68.8** | 68.8 | 35m 37s | $4.20 |
| 17 | **gemini-3.6-flash** | **66.8** | 66.8 | 48m 28s | $0.61 |
| 18 | **fable-5** | **59.8** | 59.8 | 18m 3s | $5.08 |
| 19 | **grok-4.5** | **58.3** | 58.3 | 63m 55s | $0.76 |
| 20 | **gemini-3.1-pro** | **53.8** | 53.8 | 40m 49s | $0.27 |
| 21 | **gemma-4-26B-a4b** | **49.2** | 49.2 | 49m 48s | $0.00 |
| 22 | **grok-4.6** | **47.0** | 47.0 | 151m 25s | $0.83 |
| 23 | **gemma-4-31b** | **42.6** | 42.6 | 111m 0s | $0.00 |

## What each column measures

Scores are 0–100, higher is better. **Duration** and **Cost** are lower-is-better.

- **Rank** — position among models that ran the full category set, best Global Score first (🥇🥈🥉 mark the top three). Partial or all-failed models are listed separately below and not ranked.
- **Model** — the model's name as configured in `models.json`.
- **Global Score** — the headline quality number: the weighted average of the category columns, using the weights shown in each header. Only categories the model actually ran count (weights renormalize), so a partial run still yields a 0–100 value — which is why partial runs aren't ranked against full ones.
- **Efficiency & Consistency** (5% of Global Score) — Derived from the runs above, not a dataset. 0.4 speed (vs a 20s budget) + 0.3 token thrift (vs 4000 tokens) + 0.3 run-to-run score stability.
- **Duration** — total model time to run this model's whole set: the sum of every call's measured latency across all cases and runs. It is *not* wall-clock — cached calls keep their originally measured latency, so it stays stable across re-runs.
- **Cost** — total USD to run this model's whole set at provider list price: Σ(input_tokens × input_price + output_tokens × output_price) ÷ 1,000,000. It counts every call (including cached ones) — it's the cost of *running the benchmark*, not your actual billed amount. Self-hosted/local models show `$0.00`; models with no price configured show `—`.
