# Developer / Coding Benchmark — Comparison

Generated: 2026-08-26 21:30:28 UTC  
Runs per test: 3 · Models: 23 · Test cases: 80

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set for this track are ranked. See also [SRE / Observability](comparison_table.md).

| Rank | Model | Global Score | Code Generation (35%) | Code Efficiency (15%) | Bug Fixing (15%) | Refactoring (15%) | Code Review (15%) | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **grok-4.5-low** 🥇 | **93.0** | 86.5 | 100.0 | 100.0 | 98.6 | 93.7 | 77.8 | 25m 53s | $0.78 |
| 2 | **opus-4.8** 🥈 | **92.9** | 86.2 | 100.0 | 100.0 | 100.0 | 91.3 | 81.4 | 21m 4s | $2.87 |
| 3 | **grok-4.5** 🥉 | **92.8** | 88.2 | 100.0 | 100.0 | 99.5 | 93.6 | 58.3 | 63m 55s | $0.76 |
| 4 | **grok-4** | **92.6** | 88.8 | 100.0 | 100.0 | 100.0 | 84.3 | 77.0 | 29m 38s | $1.05 |
| 5 | **grok-4.6-low** | **91.7** | 84.1 | 100.0 | 100.0 | 99.5 | 91.5 | 72.7 | 29m 32s | $0.81 |
| 6 | **qwen3.8-27b** | **91.3** | 89.7 | 87.5 | 100.0 | 100.0 | 81.6 | 90.0 | 10m 6s | $0.00 |
| 7 | **gemma-4-31b** | **90.7** | 86.8 | 100.0 | 100.0 | 100.0 | 88.0 | 42.6 | 111m 0s | $0.00 |
| 8 | **gemini-3.6-flash** | **89.6** | 87.3 | 92.1 | 97.5 | 99.1 | 82.7 | 66.8 | 48m 28s | $0.61 |
| 9 | **sonnet-5** | **89.1** | 79.8 | 89.4 | 100.0 | 99.5 | 94.8 | 72.5 | 27m 19s | $2.79 |
| 10 | **grok-4.6** | **89.1** | 82.2 | 100.0 | 100.0 | 99.1 | 87.5 | 47.0 | 151m 25s | $0.83 |
| 11 | **gemma-4-26B-a4b** | **88.8** | 85.7 | 89.4 | 100.0 | 100.0 | 86.4 | 49.2 | 49m 48s | $0.00 |
| 12 | **gpt-5.6-sol** | **87.6** | 77.0 | 100.0 | 97.5 | 99.5 | 84.4 | 68.8 | 35m 37s | $4.20 |
| 13 | **qwen3.6-27b** | **87.4** | 77.6 | 87.6 | 100.0 | 99.0 | 86.1 | 86.7 | 16m 19s | $0.00 |
| 14 | **gpt-5.6-luna** | **86.7** | 74.9 | 97.4 | 100.0 | 96.1 | 85.3 | 73.1 | 27m 57s | $1.02 |
| 15 | **qwen3-coder-30b** | **86.3** | 79.5 | 99.5 | 98.8 | 86.9 | 74.3 | 91.0 | 3m 31s | $0.00 |
| 16 | **gpt-5.6-terra** | **85.9** | 79.0 | 89.4 | 95.0 | 93.1 | 84.3 | 79.4 | 20m 5s | $1.61 |
| 17 | **haiku-4-5** | **84.6** | 72.3 | 79.4 | 100.0 | 98.5 | 91.0 | 80.0 | 12m 58s | $0.64 |
| 18 | **qwen3-32b** | **82.7** | 80.3 | 71.0 | 92.5 | 91.7 | 79.8 | 87.1 | 14m 40s | $0.00 |
| 19 | **gpt-4o** | **81.3** | 70.7 | 89.1 | 100.0 | 85.3 | 73.4 | 88.4 | 12m 5s | $0.71 |
| 20 | **gemma-3-12B** | **70.4** | 63.4 | 81.2 | 83.2 | 72.5 | 54.8 | 89.6 | 8m 51s | $0.00 |
| 21 | **fable-5-low** | **37.4** | 69.3 | 44.4 | 0.0 | 16.7 | 0.0 | 80.6 | 10m 44s | $2.62 |
| 22 | **fable-5** | **31.4** | 59.7 | 47.2 | 0.0 | 2.8 | 0.0 | 59.8 | 18m 3s | $5.08 |
| 23 | **gemini-3.1-pro** | **23.3** | 58.8 | 0.0 | 0.0 | 0.0 | 0.0 | 53.8 | 40m 49s | $0.27 |

## By language

The same runs as above, grouped by target language instead of by category. Every case exists in all four languages, so these columns are directly comparable — but they are a view, not extra weight in the Global Score.

| Model | Python | TypeScript | Go | Rust |
|---|---|---|---|---|
| grok-4.5-low | 98.1 | 97.5 | 91.4 | 86.8 |
| opus-4.8 | 97.4 | 97.1 | 93.4 | 84.8 |
| grok-4.5 | 97.6 | 97.6 | 94.4 | 87.4 |
| grok-4 | 96.7 | 97.7 | 93.1 | 85.3 |
| grok-4.6-low | 97.5 | 97.1 | 88.4 | 86.2 |
| qwen3.8-27b | 96.5 | 98.9 | 91.5 | 78.2 |
| gemma-4-31b | 95.8 | 95.7 | 97.2 | 83.0 |
| gemini-3.6-flash | 96.8 | 93.2 | 91.6 | 80.9 |
| sonnet-5 | 98.0 | 98.1 | 89.0 | 72.8 |
| grok-4.6 | 96.6 | 96.6 | 85.2 | 85.1 |
| gemma-4-26B-a4b | 93.4 | 97.5 | 89.2 | 82.6 |
| gpt-5.6-sol | 96.1 | 96.1 | 77.3 | 82.5 |
| qwen3.6-27b | 95.9 | 94.0 | 75.4 | 82.4 |
| gpt-5.6-luna | 95.6 | 94.8 | 72.9 | 83.8 |
| qwen3-coder-30b | 95.8 | 94.2 | 80.3 | 72.7 |
| gpt-5.6-terra | 95.4 | 97.1 | 68.9 | 82.1 |
| haiku-4-5 | 96.8 | 96.9 | 70.3 | 73.1 |
| qwen3-32b | 95.1 | 86.8 | 86.5 | 61.2 |
| gpt-4o | 92.7 | 93.8 | 51.5 | 83.7 |
| gemma-3-12B | 85.5 | 87.4 | 51.8 | 51.9 |
| fable-5-low | 38.4 | 53.7 | 34.6 | 20.8 |
| fable-5 | 38.4 | 35.6 | 33.8 | 17.8 |
| gemini-3.1-pro | 28.4 | 27.3 | 22.9 | 15.5 |

## What each column measures

Scores are 0–100, higher is better. **Duration** and **Cost** are lower-is-better.

- **Rank** — position among models that ran the full category set, best Global Score first (🥇🥈🥉 mark the top three). Partial or all-failed models are listed separately below and not ranked.
- **Model** — the model's name as configured in `models.json`.
- **Global Score** — the headline quality number: the weighted average of the category columns, using the weights shown in each header. Only categories the model actually ran count (weights renormalize), so a partial run still yields a 0–100 value — which is why partial runs aren't ranked against full ones.
- **Code Generation** (35% of Global Score) — Writing a utility from a spec and a signature, with the tests hidden. 0.6 tests passed + 0.2 compiles + 0.1 runtime + 0.1 code size.
- **Code Efficiency** (15% of Global Score) — Writing code that is fast enough, not just correct: each case is timed on a 200k-element input against a per-language budget. 0.45 correctness + 0.15 compiles + 0.35 within-budget speed (scaled by correctness, so a fast wrong answer earns nothing) + 0.05 code size.
- **Bug Fixing** (15% of Global Score) — Fixing a defect from the code plus the symptom a colleague reported. 0.7 correctness + 0.2 compiles + 0.1 code size, where correctness is half the whole test set and half the tests the shipped buggy version fails — so returning the code unchanged cannot collect most of the weight.
- **Refactoring** (15% of Global Score) — Restructuring working code without changing what it does. 0.4 tests still pass + 0.1 compiles + 0.5 structural rules scaled by correctness (the branch chain is gone, the table or loop is there, it got shorter). Handing the code back unchanged keeps the behavior half and forfeits most of the structure half; a stub that satisfies the rules without working earns neither.
- **Code Review** (15% of Global Score) — Finding the seeded defects in a snippet — injection, races, unbounded growth, leaked secrets, missing timeouts. 0.65 defect recall + 0.2 precision (speculative findings cost) + 0.15 line localization.
- **Efficiency & Consistency** (5% of Global Score) — Derived from the runs above, not a dataset. 0.4 speed (vs a 20s budget) + 0.3 token thrift (vs 4000 tokens) + 0.3 run-to-run score stability.
- **Duration** — total model time to run this model's whole set: the sum of every call's measured latency across all cases and runs. It is *not* wall-clock — cached calls keep their originally measured latency, so it stays stable across re-runs.
- **Cost** — total USD to run this model's whole set at provider list price: Σ(input_tokens × input_price + output_tokens × output_price) ÷ 1,000,000. It counts every call (including cached ones) — it's the cost of *running the benchmark*, not your actual billed amount. Self-hosted/local models show `$0.00`; models with no price configured show `—`.
