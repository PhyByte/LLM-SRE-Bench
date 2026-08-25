# Developer / Code Generation Benchmark — Comparison

Generated: 2026-08-25 16:42:01 UTC  
Runs per test: 3 · Models: 22 · Test cases: 24

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set for this track are ranked. See also [SRE / Observability](comparison_table.md).

| Rank | Model | Global Score | Python (24%) | TypeScript (24%) | Go (24%) | Rust (24%) | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **grok-4** 🥇 | **85.4** | 94.2 | 96.7 | 92.2 | 61.2 | 72.4 | 11m 20s | $0.33 |
| 2 | **grok-4.5-low** 🥈 | **85.1** | 94.6 | 95.8 | 91.4 | 60.4 | 76.5 | 7m 54s | $0.25 |
| 3 | **grok-4.5** 🥉 | **85.0** | 94.6 | 95.8 | 95.8 | 60.1 | 53.8 | 22m 52s | $0.24 |
| 4 | **gemini-3.6-flash** | **83.8** | 94.6 | 95.8 | 95.8 | 52.2 | 68.5 | 14m 51s | $0.22 |
| 5 | **gemma-4-31b** | **83.5** | 94.6 | 95.6 | 95.8 | 56.8 | 41.7 | 41m 4s | $0.00 |
| 6 | **sonnet-5** | **82.9** | 94.6 | 95.8 | 87.8 | 55.9 | 71.1 | 9m 11s | $1.06 |
| 7 | **grok-4.6-low** | **81.5** | 94.6 | 95.8 | 79.4 | 58.9 | 67.6 | 10m 3s | $0.26 |
| 8 | **opus-4.8** | **81.5** | 94.6 | 95.8 | 85.0 | 50.5 | 80.6 | 6m 22s | $1.00 |
| 9 | **grok-4.6** | **81.1** | 94.6 | 95.8 | 80.3 | 60.3 | 48.9 | 46m 56s | $0.26 |
| 10 | **qwen3.6-27b** | **80.6** | 94.6 | 95.8 | 82.5 | 60.1 | 30.0 | 94m 51s | $0.00 |
| 11 | **fable-5-low** | **78.9** | 94.6 | 95.8 | 80.8 | 43.8 | 81.4 | 6m 48s | $1.69 |
| 12 | **gemma-4-26B-a4b** | **78.6** | 85.7 | 95.5 | 87.7 | 55.8 | 30.2 | 20m 46s | $0.00 |
| 13 | **qwen3-coder-30b** | **76.5** | 94.6 | 97.5 | 63.3 | 47.2 | 92.0 | 1m 10s | $0.00 |
| 14 | **qwen3-32b** | **76.3** | 90.3 | 86.9 | 86.1 | 53.2 | 21.6 | 96m 22s | $0.00 |
| 15 | **qwen3.8-27b** | **76.2** | 95.5 | 93.3 | 67.6 | 59.1 | 25.0 | 104m 0s | $0.00 |
| 16 | **gpt-5.6-terra** | **75.7** | 94.6 | 95.8 | 53.3 | 58.5 | 79.0 | 5m 56s | $0.54 |
| 17 | **gpt-5.6-sol** | **74.4** | 94.6 | 95.8 | 50.6 | 59.6 | 60.4 | 13m 51s | $1.60 |
| 18 | **gpt-5.6-luna** | **72.1** | 94.6 | 92.5 | 45.6 | 56.8 | 66.2 | 10m 21s | $0.39 |
| 19 | **fable-5** | **71.5** | 94.6 | 95.8 | 79.9 | 17.7 | 62.0 | 13m 21s | $3.86 |
| 20 | **gpt-4o** | **69.6** | 96.5 | 97.5 | 20.0 | 60.0 | 89.6 | 3m 38s | $0.23 |
| 21 | **gemma-3-12B** | **65.8** | 88.4 | 96.1 | 40.9 | 33.3 | 88.0 | 3m 10s | $0.00 |
| 22 | **haiku-4-5** | **62.1** | 94.6 | 70.8 | 49.4 | 32.8 | 65.2 | 5m 22s | $0.24 |

## What each column measures

Scores are 0–100, higher is better. **Duration** and **Cost** are lower-is-better.

- **Rank** — position among models that ran the full category set, best Global Score first (🥇🥈🥉 mark the top three). Partial or all-failed models are listed separately below and not ranked.
- **Model** — the model's name as configured in `models.json`.
- **Global Score** — the headline quality number: the weighted average of the category columns, using the weights shown in each header. Only categories the model actually ran count (weights renormalize), so a partial run still yields a 0–100 value — which is why partial runs aren't ranked against full ones.
- **Python** (24% of Global Score) — Code-generation cases targeting Python. Mean of the six Python task families (slugify, interval merge, rate limiter, config overlay, LRU cache, log parser).
- **TypeScript** (24% of Global Score) — Code-generation cases targeting TypeScript. Mean of the six TypeScript task families.
- **Go** (24% of Global Score) — Code-generation cases targeting Go. Mean of the six Go task families. Scores 0 when the Go toolchain is unavailable.
- **Rust** (24% of Global Score) — Code-generation cases targeting Rust. Mean of the six Rust task families.
- **Efficiency & Consistency** (5% of Global Score) — Derived from the runs above, not a dataset. 0.4 speed (vs a 20s budget) + 0.3 token thrift (vs 4000 tokens) + 0.3 run-to-run score stability.
- **Duration** — total model time to run this model's whole set: the sum of every call's measured latency across all cases and runs. It is *not* wall-clock — cached calls keep their originally measured latency, so it stays stable across re-runs.
- **Cost** — total USD to run this model's whole set at provider list price: Σ(input_tokens × input_price + output_tokens × output_price) ÷ 1,000,000. It counts every call (including cached ones) — it's the cost of *running the benchmark*, not your actual billed amount. Self-hosted/local models show `$0.00`; models with no price configured show `—`.
