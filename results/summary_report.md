# LLM Observability Benchmark — Summary Report

Generated: 2026-08-12 19:58:18 UTC

## Overall Ranking

1. **claude-opus-4-8** — global score 82.2/100 (0/138 failed runs) — completed in 7m 9s
2. **grok-4.6-low** — global score 79.4/100 (0/46 failed runs) — completed in 5m 59s
3. **fable-5-low** — global score 78.7/100 (0/138 failed runs) — completed in 12m 29s
4. **grok-4.5-low** — global score 78.0/100 (0/46 failed runs) — completed in 7m 29s
5. **fable-5** — global score 77.8/100 (0/138 failed runs) — completed in 22m 15s
6. **sonnet-5** — global score 76.2/100 (3/138 failed runs) — completed in 10m 53s
7. **gpt-5.6-terra** — global score 76.2/100 (0/138 failed runs) — completed in 6m 41s
8. **grok-4.5** — global score 76.1/100 (0/138 failed runs) — completed in 33m 1s
9. **gpt-5.6-luna** — global score 75.6/100 (1/138 failed runs) — completed in 8m 29s
10. **grok-4.6** — global score 74.4/100 (1/138 failed runs) — completed in 90m 8s
11. **gpt-5.6-sol** — global score 73.5/100 (0/138 failed runs) — completed in 13m 31s
12. **grok-4** — global score 72.0/100 (0/138 failed runs) — completed in 24m 59s
13. **haiku-4-5** — global score 70.6/100 (0/138 failed runs) — completed in 4m 9s
14. **gemma-4-31b** — global score 68.5/100 (4/138 failed runs) — completed in 54m 39s
15. **gpt-4o** — global score 65.6/100 (0/138 failed runs) — completed in 3m 59s
16. **qwen3-32b** — global score 59.5/100 (6/138 failed runs) — completed in 34m 43s

## Category Leaders

- **Log Parsing**: grok-4.5-low with 92.4 (next: grok-4.5 at 92.2)
- **Anomaly Detection**: claude-opus-4-8 with 68.8 (next: fable-5-low at 67.4)
- **Pattern & Correlation**: grok-4.5-low with 92.0 (next: claude-opus-4-8 at 90.7)
- **Metrics Time-Series**: claude-opus-4-8 with 100.0 (next: grok-4.6-low at 100.0)
- **Root Cause & Summary**: fable-5-low with 62.3 (next: fable-5 at 60.3)
- **Efficiency & Consistency**: gpt-4o with 91.4 (next: haiku-4-5 at 87.8)

## Efficiency Details

- **claude-opus-4-8**: avg latency 3.11s, avg tokens/call 892, score stddev across runs 0.8 points, full set: 7m 9s
- **grok-4.6-low**: avg latency 7.81s, avg tokens/call 820, score stddev across runs 0.0 points, full set: 5m 59s
- **fable-5-low**: avg latency 5.43s, avg tokens/call 886, score stddev across runs 1.0 points, full set: 12m 29s
- **grok-4.5-low**: avg latency 9.78s, avg tokens/call 823, score stddev across runs 0.0 points, full set: 7m 29s
- **fable-5**: avg latency 9.68s, avg tokens/call 1047, score stddev across runs 1.1 points, full set: 22m 15s
- **sonnet-5**: avg latency 4.03s, avg tokens/call 1030, score stddev across runs 3.1 points, full set: 10m 53s
- **gpt-5.6-terra**: avg latency 2.91s, avg tokens/call 753, score stddev across runs 3.0 points, full set: 6m 41s
- **grok-4.5**: avg latency 14.36s, avg tokens/call 826, score stddev across runs 2.1 points, full set: 33m 1s
- **gpt-5.6-luna**: avg latency 3.46s, avg tokens/call 909, score stddev across runs 1.9 points, full set: 8m 29s
- **grok-4.6**: avg latency 39.47s, avg tokens/call 824, score stddev across runs 1.2 points, full set: 90m 8s
- **gpt-5.6-sol**: avg latency 5.88s, avg tokens/call 791, score stddev across runs 2.4 points, full set: 13m 31s
- **grok-4**: avg latency 10.86s, avg tokens/call 791, score stddev across runs 2.8 points, full set: 24m 59s
- **haiku-4-5**: avg latency 1.81s, avg tokens/call 725, score stddev across runs 2.6 points, full set: 4m 9s
- **gemma-4-31b**: avg latency 22.41s, avg tokens/call 2035, score stddev across runs 0.5 points, full set: 54m 39s
- **gpt-4o**: avg latency 1.74s, avg tokens/call 631, score stddev across runs 0.4 points, full set: 3m 59s
- **qwen3-32b**: avg latency 15.64s, avg tokens/call 1661, score stddev across runs 3.1 points, full set: 34m 43s

## Reliability

- qwen3-32b: 6 failed run(s) (API errors or invalid JSON output)
- gemma-4-31b: 4 failed run(s) (API errors or invalid JSON output)
- sonnet-5: 3 failed run(s) (API errors or invalid JSON output)
- gpt-5.6-luna: 1 failed run(s) (API errors or invalid JSON output)
- grok-4.6: 1 failed run(s) (API errors or invalid JSON output)

## Recommendations

- **claude-opus-4-8** is the strongest overall pick for log/metrics analysis workloads in this run (global score 82.2).
- For **log parsing** specifically, consider **grok-4.5-low** (92.4 vs 91.9).
- For **pattern & correlation** specifically, consider **grok-4.5-low** (92.0 vs 90.7).
- For **root cause & summary** specifically, consider **fable-5-low** (62.3 vs 57.8).
- For **efficiency & consistency** specifically, consider **gpt-4o** (91.4 vs 86.1).
