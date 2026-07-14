# LLM Observability Benchmark — Summary Report

Generated: 2026-07-13 21:25:50 UTC

## Overall Ranking

1. **gemma-3-12b** — global score 85.4/100 (0/1 failed runs) — completed in 1m 36s
2. **claude-opus-4-8** — global score 82.2/100 (0/138 failed runs) — completed in 7m 9s
3. **gpt-5.6-terra** — global score 76.2/100 (0/138 failed runs) — completed in 3.3s
4. **mock-heuristic** — global score 76.0/100 (0/20 failed runs) — completed in 0.7s
5. **gpt-5.6-luna** — global score 75.6/100 (1/138 failed runs) — completed in 0.8s
6. **gpt-5.6-sol** — global score 73.5/100 (0/138 failed runs) — completed in 7.1s
7. **grok-4** — global score 72.0/100 (0/138 failed runs) — completed in 24m 59s
8. **gemma-4-31b** — global score 68.5/100 (4/138 failed runs) — completed in 0.8s
9. **gpt-4o** — global score 65.6/100 (0/138 failed runs) — completed in 3m 41s
10. **gemma** — global score 58.5/100 (0/138 failed runs) — completed in 14m 13s
11. **mock-naive** — global score 39.6/100 (0/20 failed runs) — completed in <0.1s
12. **grok-4.5** — global score 0.0/100 (138/138 failed runs) — completed in 1.1s
13. **llama-3.3-70b** — global score 0.0/100 (138/138 failed runs) — completed in 51m 26s

## Category Leaders

- **Log Parsing**: gemma-3-12b with 93.4 (next: gpt-5.6-terra at 91.9)
- **Anomaly Detection**: claude-opus-4-8 with 68.8 (next: gpt-5.6-luna at 63.1)
- **Pattern & Correlation**: claude-opus-4-8 with 90.7 (next: gpt-5.6-luna at 85.3)
- **Metrics Time-Series**: claude-opus-4-8 with 100.0 (next: gemma-4-31b at 86.7)
- **Root Cause & Summary**: claude-opus-4-8 with 57.8 (next: gpt-5.6-sol at 54.3)
- **Efficiency & Consistency**: mock-heuristic with 98.7 (next: mock-naive at 98.2)

## Efficiency Details

- **gemma-3-12b**: avg latency 96.91s, avg tokens/call 892, score stddev across runs 0.0 points, full set: 1m 36s
- **claude-opus-4-8**: avg latency 3.11s, avg tokens/call 892, score stddev across runs 0.8 points, full set: 7m 9s
- **gpt-5.6-terra**: avg latency 2.91s, avg tokens/call 753, score stddev across runs 3.0 points, full set: 3.3s
- **mock-heuristic**: avg latency 0.11s, avg tokens/call 147, score stddev across runs 0.0 points, full set: 0.7s
- **gpt-5.6-luna**: avg latency 3.46s, avg tokens/call 909, score stddev across runs 1.9 points, full set: 0.8s
- **gpt-5.6-sol**: avg latency 5.88s, avg tokens/call 791, score stddev across runs 2.4 points, full set: 7.1s
- **grok-4**: avg latency 10.86s, avg tokens/call 791, score stddev across runs 2.8 points, full set: 24m 59s
- **gemma-4-31b**: avg latency 22.41s, avg tokens/call 2035, score stddev across runs 0.5 points, full set: 0.8s
- **gpt-4o**: avg latency 1.74s, avg tokens/call 631, score stddev across runs 0.4 points, full set: 3m 41s
- **gemma**: avg latency 6.18s, avg tokens/call 793, score stddev across runs 1.3 points, full set: 14m 13s
- **mock-naive**: avg latency 0.34s, avg tokens/call 146, score stddev across runs 0.0 points, full set: <0.1s
- **grok-4.5**:, full set: 1.1s
- **llama-3.3-70b**:, full set: 51m 26s

## Reliability

- grok-4.5: 138 failed run(s) (API errors or invalid JSON output)
- llama-3.3-70b: 138 failed run(s) (API errors or invalid JSON output)
- gemma-4-31b: 4 failed run(s) (API errors or invalid JSON output)
- gpt-5.6-luna: 1 failed run(s) (API errors or invalid JSON output)

## Recommendations

- **gemma-3-12b** is the strongest overall pick for log/metrics analysis workloads in this run (global score 85.4).
- For **anomaly detection** specifically, consider **claude-opus-4-8** (68.8 vs 0.0).
- For **pattern & correlation** specifically, consider **claude-opus-4-8** (90.7 vs 0.0).
- For **metrics time-series** specifically, consider **claude-opus-4-8** (100.0 vs 0.0).
- For **root cause & summary** specifically, consider **claude-opus-4-8** (57.8 vs 0.0).
- For **efficiency & consistency** specifically, consider **mock-heuristic** (98.7 vs 53.3).
