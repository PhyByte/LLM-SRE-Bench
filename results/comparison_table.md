# LLM Observability Benchmark — Comparison

Generated: 2026-07-27 13:51:42 UTC  
Runs per test: 3 · Models: 12 · Test cases: 46

All scores are 0-100. The global score is the weighted average of the category scores. Only models that ran the full category set are ranked.

| Rank | Model | Global Score | Log Parsing (20%) | Anomaly Detection (30%) | Pattern & Correlation (20%) | Metrics Time-Series (15%) | Root Cause & Summary (10%) | Efficiency & Consistency (5%) | Duration |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **claude-opus-4-8** 🥇 | **82.2** | 91.9 | 68.8 | 90.7 | 100.0 | 57.8 | 86.1 | 7m 9s |
| 2 | **grok-4.5-low** 🥈 | **78.0** | 92.4 | 61.5 | 92.0 | 90.0 | 54.8 | 74.3 | 7m 29s |
| 3 | **gpt-5.6-terra** 🥉 | **76.2** | 91.9 | 62.1 | 82.7 | 86.3 | 54.2 | 84.9 | 6m 41s |
| 4 | **grok-4.5** | **76.1** | 92.2 | 62.3 | 81.3 | 93.3 | 55.5 | 62.5 | 33m 1s |
| 5 | **gpt-5.6-luna** | **75.6** | 91.3 | 63.1 | 85.3 | 79.6 | 51.9 | 83.9 | 8m 29s |
| 6 | **gpt-5.6-sol** | **73.5** | 91.7 | 61.1 | 74.7 | 83.3 | 54.3 | 79.4 | 13m 31s |
| 7 | **grok-4** | **72.0** | 89.5 | 62.8 | 73.3 | 80.0 | 51.8 | 69.0 | 24m 59s |
| 8 | **gemma-4-31b** | **68.5** | 90.3 | 61.4 | 58.7 | 86.7 | 50.8 | 44.1 | 54m 39s |
| 9 | **gpt-4o** | **65.6** | 90.6 | 62.4 | 60.0 | 53.3 | 42.3 | 91.4 | 3m 59s |
| 10 | **gemma** | **58.5** | 74.8 | 51.8 | 81.3 | 24.3 | 40.5 | 80.1 | 14m 13s |

**Incomplete coverage** (ran only some categories — not ranked, because a partial run's global score isn't comparable). Re-run the full suite for these:

- gemma-3-12b — ran only: log_parsing

**Did not complete** (every call failed — bad key, no model access, or unreachable endpoint):

- llama-3.3-70b (138 calls failed)
