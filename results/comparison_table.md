# SRE / Observability Benchmark — Comparison

Generated: 2026-08-25 16:42:01 UTC  
Runs per test: 3 · Models: 22 · Test cases: 24

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set for this track are ranked. See also [Developer / Code Generation](comparison_table_developer.md).

| Rank | Model | Global Score | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|
| 1 | **qwen3-coder-30b** 🥇 | **92.0** | 92.0 | 1m 10s | $0.00 |
| 2 | **gpt-4o** 🥈 | **89.6** | 89.6 | 3m 38s | $0.23 |
| 3 | **gemma-3-12B** 🥉 | **88.0** | 88.0 | 3m 10s | $0.00 |
| 4 | **fable-5-low** | **81.4** | 81.4 | 6m 48s | $1.69 |
| 5 | **opus-4.8** | **80.6** | 80.6 | 6m 22s | $1.00 |
| 6 | **gpt-5.6-terra** | **79.0** | 79.0 | 5m 56s | $0.54 |
| 7 | **grok-4.5-low** | **76.5** | 76.5 | 7m 54s | $0.25 |
| 8 | **grok-4** | **72.4** | 72.4 | 11m 20s | $0.33 |
| 9 | **sonnet-5** | **71.1** | 71.1 | 9m 11s | $1.06 |
| 10 | **gemini-3.6-flash** | **68.5** | 68.5 | 14m 51s | $0.22 |
| 11 | **grok-4.6-low** | **67.6** | 67.6 | 10m 3s | $0.26 |
| 12 | **gpt-5.6-luna** | **66.2** | 66.2 | 10m 21s | $0.39 |
| 13 | **haiku-4-5** | **65.2** | 65.2 | 5m 22s | $0.24 |
| 14 | **fable-5** | **62.0** | 62.0 | 13m 21s | $3.86 |
| 15 | **gpt-5.6-sol** | **60.4** | 60.4 | 13m 51s | $1.60 |
| 16 | **grok-4.5** | **53.8** | 53.8 | 22m 52s | $0.24 |
| 17 | **grok-4.6** | **48.9** | 48.9 | 46m 56s | $0.26 |
| 18 | **gemma-4-31b** | **41.7** | 41.7 | 41m 4s | $0.00 |
| 19 | **gemma-4-26B-a4b** | **30.2** | 30.2 | 20m 46s | $0.00 |
| 20 | **qwen3.6-27b** | **30.0** | 30.0 | 94m 51s | $0.00 |
| 21 | **qwen3.8-27b** | **25.0** | 25.0 | 104m 0s | $0.00 |
| 22 | **qwen3-32b** | **21.6** | 21.6 | 96m 22s | $0.00 |

## What each column measures

Scores are 0–100, higher is better. **Duration** and **Cost** are lower-is-better.

- **Rank** — position among models that ran the full category set, best Global Score first (🥇🥈🥉 mark the top three). Partial or all-failed models are listed separately below and not ranked.
- **Model** — the model's name as configured in `models.json`.
- **Global Score** — the headline quality number: the weighted average of the category columns, using the weights shown in each header. Only categories the model actually ran count (weights renormalize), so a partial run still yields a 0–100 value — which is why partial runs aren't ranked against full ones.
- **Efficiency & Consistency** (5% of Global Score) — Derived from the runs above, not a dataset. 0.4 speed (vs a 20s budget) + 0.3 token thrift (vs 4000 tokens) + 0.3 run-to-run score stability.
- **Duration** — total model time to run this model's whole set: the sum of every call's measured latency across all cases and runs. It is *not* wall-clock — cached calls keep their originally measured latency, so it stays stable across re-runs.
- **Cost** — total USD to run this model's whole set at provider list price: Σ(input_tokens × input_price + output_tokens × output_price) ÷ 1,000,000. It counts every call (including cached ones) — it's the cost of *running the benchmark*, not your actual billed amount. Self-hosted/local models show `$0.00`; models with no price configured show `—`.
