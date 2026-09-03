# Developer / Coding Benchmark — Comparison

Generated: 2026-09-03 22:57:45 UTC  
Runs per test: 3 · Models: 24 · Test cases: 280

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set for this track are ranked. See also [SRE / Observability](comparison_table.md).

| Rank | Model | Global Score | Code Generation (35%) | Code Efficiency (15%) | Bug Fixing (15%) | Refactoring (15%) | Code Review (15%) | Efficiency & Consistency (5%) | Duration | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **opus-4.8** 🥇 | **94.4** | 92.9 | 99.4 | 99.4 | 98.9 | 88.1 | 79.8 | 74m 7s | $11.07 |
| 2 | **fable-5.1** 🥈 | **92.5** | 95.2 | 88.4 | 98.1 | 98.6 | 88.6 | 63.4 | 164m 39s | $34.14 |
| 3 | **grok-4.5-low** 🥉 | **92.5** | 90.4 | 99.6 | 100.0 | 98.3 | 83.5 | 72.4 | 115m 35s | $2.94 |
| 4 | **grok-4.5** | **92.0** | 91.9 | 98.8 | 100.0 | 98.9 | 84.3 | 50.9 | 263m 2s | $2.90 |
| 5 | **grok-4.6-low** | **90.0** | 87.7 | 96.3 | 100.0 | 99.1 | 77.0 | 68.9 | 126m 54s | $3.03 |
| 6 | **qwen3.8-27b** | **89.9** | 89.9 | 83.9 | 96.5 | 98.7 | 80.9 | 88.0 | 41m 46s | $0.00 |
| 7 | **sonnet-5** | **88.7** | 80.0 | 94.1 | 100.0 | 99.0 | 88.3 | 68.6 | 111m 56s | $11.73 |
| 8 | **gpt-5.6-sol** | **88.3** | 81.6 | 97.5 | 97.7 | 98.3 | 80.6 | 72.0 | 107m 49s | $15.20 |
| 9 | **gpt-5.6-terra** | **87.2** | 82.1 | 91.4 | 98.3 | 96.5 | 77.7 | 78.3 | 69m 9s | $6.52 |
| 10 | **gpt-5.6-luna** | **86.2** | 76.2 | 97.1 | 97.7 | 96.6 | 81.4 | 71.5 | 105m 6s | $3.76 |
| 11 | **haiku-4-5** | **85.1** | 78.9 | 80.9 | 100.0 | 95.7 | 80.3 | 78.8 | 50m 34s | $2.22 |
| 12 | **gemma-4-26B-a4b** | **84.7** | 83.0 | 91.6 | 99.3 | 95.7 | 72.2 | 35.6 | 234m 19s | $0.00 |
| 13 | **grok-4.6** | **83.2** | 87.2 | 95.5 | 80.8 | 80.2 | 78.9 | 46.8 | 631m 35s | $3.09 |
| 14 | **gemma-4-31b** | **83.1** | 89.7 | 96.2 | 79.0 | 79.2 | 77.1 | 39.9 | 458m 44s | $0.00 |
| 15 | **gpt-4o** | **81.2** | 72.2 | 86.2 | 97.7 | 92.4 | 66.8 | 88.3 | 30m 53s | $2.73 |
| 16 | **grok-4** | **78.1** | 78.6 | 79.5 | 79.0 | 80.2 | 73.1 | 75.5 | 106m 39s | $4.13 |
| 17 | **gemini-3.6-flash** | **77.4** | 78.8 | 78.3 | 79.5 | 79.5 | 73.1 | 64.1 | 190m 28s | $2.29 |
| 18 | **qwen3-coder-30b** | **73.1** | 70.6 | 72.8 | 72.9 | 76.0 | 70.8 | 90.3 | 15m 16s | $0.00 |
| 19 | **qwen3.6-27b** | **72.6** | 67.0 | 64.4 | 79.0 | 79.2 | 76.9 | 84.0 | 69m 53s | $0.00 |
| 20 | **qwen3-32b** | **65.5** | 59.7 | 57.1 | 67.4 | 74.6 | 70.3 | 84.0 | 66m 27s | $0.00 |
| 21 | **fable-5.1-low** | **61.7** | 35.6 | 69.5 | 73.1 | 71.3 | 90.0 | 72.1 | 115m 51s | $23.85 |
| 22 | **gemma-3-12B** | **54.5** | 44.9 | 55.9 | 64.2 | 59.8 | 49.2 | 88.8 | 30m 29s | $0.00 |
| 23 | **fable-5-low** | **36.6** | 70.2 | 46.8 | 3.8 | 3.8 | 0.0 | 78.0 | 29m 13s | $7.09 |
| 24 | **fable-5** | **33.3** | 65.3 | 45.6 | 2.6 | 0.6 | 0.0 | 61.4 | 48m 5s | $13.05 |

## By language

The same runs as above, grouped by target language instead of by category. Every case exists in all four languages, so these columns are directly comparable — but they are a view, not extra weight in the Global Score.

| Model | Python | TypeScript | Go | Rust |
|---|---|---|---|---|
| opus-4.8 | 97.2 | 96.5 | 95.5 | 93.1 |
| fable-5.1 | 96.1 | 97.0 | 92.0 | 90.5 |
| grok-4.5-low | 96.6 | 96.3 | 91.2 | 92.2 |
| grok-4.5 | 97.2 | 96.9 | 92.0 | 92.1 |
| grok-4.6-low | 95.5 | 94.9 | 86.0 | 90.4 |
| qwen3.8-27b | 95.1 | 94.6 | 87.2 | 83.0 |
| sonnet-5 | 97.8 | 97.3 | 90.1 | 80.4 |
| gpt-5.6-sol | 96.4 | 95.3 | 83.6 | 86.4 |
| gpt-5.6-terra | 95.1 | 94.7 | 76.7 | 88.3 |
| gpt-5.6-luna | 96.3 | 95.0 | 76.1 | 87.9 |
| haiku-4-5 | 94.1 | 95.2 | 76.5 | 80.5 |
| gemma-4-26B-a4b | 91.8 | 92.2 | 85.1 | 83.0 |
| grok-4.6 | 95.9 | 63.5 | 87.7 | 91.7 |
| gemma-4-31b | 95.6 | 64.9 | 90.5 | 87.5 |
| gpt-4o | 91.3 | 93.8 | 60.1 | 83.9 |
| grok-4 | 95.2 | 37.9 | 90.8 | 88.6 |
| gemini-3.6-flash | 95.9 | 36.8 | 91.0 | 88.0 |
| qwen3-coder-30b | 94.9 | 36.5 | 82.5 | 76.0 |
| qwen3.6-27b | 94.1 | 36.9 | 78.3 | 82.2 |
| qwen3-32b | 88.4 | 33.7 | 74.3 | 65.0 |
| fable-5.1-low | 96.8 | 16.9 | 75.6 | 73.1 |
| gemma-3-12B | 80.9 | 31.5 | 53.7 | 50.3 |
| fable-5-low | 30.5 | 35.8 | 25.3 | 21.1 |
| fable-5 | 29.5 | 30.6 | 23.4 | 20.0 |

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
