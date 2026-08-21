# LLM Observability Benchmark — Summary Report

Generated: 2026-08-21 23:21:07 UTC

## Overall Ranking

1. **opus-4.8** — global score 76.0/100 (0/192 failed runs) — completed in 14m 4s
2. **grok-4.6-low** — global score 72.6/100 (0/246 failed runs) — completed in 32m 31s
3. **fable-5** — global score 71.7/100 (0/192 failed runs) — completed in 36m 32s
4. **grok-4.6** — global score 70.7/100 (0/192 failed runs) — completed in 176m 3s
5. **gpt-5.6-terra** — global score 70.6/100 (0/246 failed runs) — completed in 16m 5s
6. **grok-4.5-low** — global score 70.4/100 (0/246 failed runs) — completed in 42m 18s
7. **grok-4.5** — global score 68.7/100 (0/114 failed runs) — completed in 62m 44s
8. **grok-4** — global score 67.9/100 (0/246 failed runs) — completed in 33m 10s
9. **sonnet-5** — global score 67.8/100 (3/246 failed runs) — completed in 31m 20s
10. **gpt-5.6-sol** — global score 67.3/100 (0/246 failed runs) — completed in 26m 46s
11. **gpt-5.6-luna** — global score 67.2/100 (0/246 failed runs) — completed in 20m 9s
12. **gemma-4-31b** — global score 64.1/100 (0/246 failed runs) — completed in 150m 3s
13. **haiku-4-5** — global score 63.8/100 (0/246 failed runs) — completed in 10m 34s
14. **gpt-4o** — global score 61.0/100 (0/246 failed runs) — completed in 15m 21s
15. **fable-5-low** — global score 60.3/100 (48/246 failed runs) — completed in 21m 8s
16. **qwen3-coder-30b** — global score 56.9/100 (5/192 failed runs) — completed in 4m 50s
17. **gemma-3-12B** — global score 50.6/100 (0/246 failed runs) — completed in 237m 39s
18. **qwen3.8-27b** — global score 45.1/100 (114/246 failed runs) — completed in 3m 46s
19. **gemma-4-26B-a4b** — global score 15.7/100 (87/114 failed runs) — completed in 6m 24s
20. **mock-heuristic** — global score 0.0/100 (26/26 failed runs) — completed in 0.5s
21. **mock-naive** — global score 0.0/100 (26/26 failed runs) — completed in 1.7s

## Category Leaders

- **Log Parsing**: fable-5 with 92.1 (next: gpt-5.6-terra at 91.9)
- **Anomaly Detection**: qwen3.8-27b with 69.3 (next: opus-4.8 at 68.8)
- **Pattern & Correlation**: opus-4.8 with 90.7 (next: gpt-5.6-terra at 86.0)
- **Metrics Time-Series**: opus-4.8 with 100.0 (next: fable-5 at 100.0)
- **Root Cause & Summary**: fable-5 with 60.3 (next: opus-4.8 at 57.8)
- **Multi-modal RCA**: grok-4.6-low with 68.8 (next: grok-4.5-low at 65.9)
- **Efficiency & Consistency**: qwen3.8-27b with 85.5 (next: qwen3-coder-30b at 78.6)

## Efficiency Details

- **opus-4.8**: avg latency 4.40s, avg tokens/call 2769, score stddev across runs 0.8 points, full set: 14m 4s
- **grok-4.6-low**: avg latency 7.93s, avg tokens/call 1984, score stddev across runs 2.0 points, full set: 32m 31s
- **fable-5**: avg latency 11.42s, avg tokens/call 2993, score stddev across runs 1.3 points, full set: 36m 32s
- **grok-4.6**: avg latency 55.02s, avg tokens/call 2310, score stddev across runs 3.3 points, full set: 176m 3s
- **gpt-5.6-terra**: avg latency 3.92s, avg tokens/call 1917, score stddev across runs 3.1 points, full set: 16m 5s
- **grok-4.5-low**: avg latency 10.32s, avg tokens/call 2234, score stddev across runs 4.0 points, full set: 42m 18s
- **grok-4.5**: avg latency 33.03s, avg tokens/call 1183, score stddev across runs 4.3 points, full set: 62m 44s
- **grok-4**: avg latency 8.09s, avg tokens/call 1903, score stddev across runs 5.5 points, full set: 33m 10s
- **sonnet-5**: avg latency 7.68s, avg tokens/call 2819, score stddev across runs 4.0 points, full set: 31m 20s
- **gpt-5.6-sol**: avg latency 6.53s, avg tokens/call 1957, score stddev across runs 2.8 points, full set: 26m 46s
- **gpt-5.6-luna**: avg latency 4.91s, avg tokens/call 2092, score stddev across runs 3.1 points, full set: 20m 9s
- **gemma-4-31b**: avg latency 36.60s, avg tokens/call 3642, score stddev across runs 1.7 points, full set: 150m 3s
- **haiku-4-5**: avg latency 2.58s, avg tokens/call 1994, score stddev across runs 2.8 points, full set: 10m 34s
- **gpt-4o**: avg latency 3.74s, avg tokens/call 1756, score stddev across runs 1.7 points, full set: 15m 21s
- **fable-5-low**: avg latency 6.41s, avg tokens/call 2671, score stddev across runs 1.8 points, full set: 21m 8s
- **qwen3-coder-30b**: avg latency 1.09s, avg tokens/call 2463, score stddev across runs 0.6 points, full set: 4m 50s
- **gemma-3-12B**: avg latency 57.97s, avg tokens/call 2162, score stddev across runs 1.1 points, full set: 237m 39s
- **qwen3.8-27b**: avg latency 1.72s, avg tokens/call 1471, score stddev across runs 0.0 points, full set: 3m 46s
- **gemma-4-26B-a4b**: avg latency 14.25s, avg tokens/call 3377, score stddev across runs 0.2 points, full set: 6m 24s
- **mock-heuristic**:, full set: 0.5s
- **mock-naive**:, full set: 1.7s

## Reliability

- qwen3.8-27b: 114 failed run(s) (API errors or invalid JSON output)
- gemma-4-26B-a4b: 87 failed run(s) (API errors or invalid JSON output)
- fable-5-low: 48 failed run(s) (API errors or invalid JSON output)
- mock-heuristic: 26 failed run(s) (API errors or invalid JSON output)
- mock-naive: 26 failed run(s) (API errors or invalid JSON output)
- qwen3-coder-30b: 5 failed run(s) (API errors or invalid JSON output)
- sonnet-5: 3 failed run(s) (API errors or invalid JSON output)

## Recommendations

- **opus-4.8** is the strongest overall pick for log/metrics analysis workloads in this run (global score 76.0).
- For **log parsing** specifically, consider **fable-5** (92.1 vs 91.9).
- For **anomaly detection** specifically, consider **qwen3.8-27b** (69.3 vs 68.8).
- For **root cause & summary** specifically, consider **fable-5** (60.3 vs 57.8).
- For **multi-modal rca** specifically, consider **grok-4.6-low** (68.8 vs 60.6).
- For **efficiency & consistency** specifically, consider **qwen3.8-27b** (85.5 vs 69.5).
