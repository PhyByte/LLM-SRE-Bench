# LLM Observability Benchmark — Summary Report

Generated: 2026-08-18 00:00:31 UTC

## Overall Ranking

1. **opus-4.8** — global score 76.0/100 (0/192 failed runs) — completed in 14m 4s
2. **grok-4.6-low** — global score 74.7/100 (0/192 failed runs) — completed in 25m 4s
3. **fable-5-low** — global score 73.4/100 (0/192 failed runs) — completed in 20m 57s
4. **grok-4.5-low** — global score 72.8/100 (0/192 failed runs) — completed in 32m 42s
5. **fable-5** — global score 71.7/100 (0/192 failed runs) — completed in 36m 32s
6. **gpt-5.6-terra** — global score 71.3/100 (0/192 failed runs) — completed in 11m 27s
7. **grok-4.6** — global score 70.7/100 (0/192 failed runs) — completed in 176m 3s
8. **sonnet-5** — global score 69.7/100 (0/192 failed runs) — completed in 23m 57s
9. **gpt-5.6-luna** — global score 69.2/100 (0/192 failed runs) — completed in 13m 4s
10. **grok-4** — global score 69.0/100 (0/192 failed runs) — completed in 30m 55s
11. **gpt-5.6-sol** — global score 68.6/100 (0/192 failed runs) — completed in 21m 21s
12. **haiku-4-5** — global score 65.9/100 (0/192 failed runs) — completed in 8m 28s
13. **gpt-4o** — global score 62.1/100 (0/192 failed runs) — completed in 13m 11s
14. **gemma-3-12B** — global score 52.1/100 (0/192 failed runs) — completed in 232m 23s

## Category Leaders

- **Log Parsing**: fable-5 with 92.1 (next: gpt-5.6-terra at 91.9)
- **Anomaly Detection**: opus-4.8 with 68.8 (next: fable-5-low at 67.4)
- **Pattern & Correlation**: opus-4.8 with 90.7 (next: grok-4.5-low at 85.3)
- **Metrics Time-Series**: opus-4.8 with 100.0 (next: grok-4.6-low at 100.0)
- **Root Cause & Summary**: fable-5-low with 62.3 (next: fable-5 at 60.3)
- **Multi-modal RCA**: grok-4.6-low with 68.8 (next: grok-4.5-low at 65.9)
- **Efficiency & Consistency**: gpt-4o with 76.1 (next: haiku-4-5 at 74.2)

## Efficiency Details

- **opus-4.8**: avg latency 4.40s, avg tokens/call 2769, score stddev across runs 0.8 points, full set: 14m 4s
- **grok-4.6-low**: avg latency 7.84s, avg tokens/call 2290, score stddev across runs 1.6 points, full set: 25m 4s
- **fable-5-low**: avg latency 6.55s, avg tokens/call 2743, score stddev across runs 1.6 points, full set: 20m 57s
- **grok-4.5-low**: avg latency 10.22s, avg tokens/call 2521, score stddev across runs 3.4 points, full set: 32m 42s
- **fable-5**: avg latency 11.42s, avg tokens/call 2993, score stddev across runs 1.3 points, full set: 36m 32s
- **gpt-5.6-terra**: avg latency 3.58s, avg tokens/call 2199, score stddev across runs 3.7 points, full set: 11m 27s
- **grok-4.6**: avg latency 55.02s, avg tokens/call 2310, score stddev across runs 3.3 points, full set: 176m 3s
- **sonnet-5**: avg latency 7.48s, avg tokens/call 3144, score stddev across runs 4.4 points, full set: 23m 57s
- **gpt-5.6-luna**: avg latency 4.09s, avg tokens/call 2337, score stddev across runs 1.9 points, full set: 13m 4s
- **grok-4**: avg latency 9.67s, avg tokens/call 2195, score stddev across runs 4.1 points, full set: 30m 55s
- **gpt-5.6-sol**: avg latency 6.67s, avg tokens/call 2234, score stddev across runs 2.2 points, full set: 21m 21s
- **haiku-4-5**: avg latency 2.65s, avg tokens/call 2320, score stddev across runs 2.6 points, full set: 8m 28s
- **gpt-4o**: avg latency 4.12s, avg tokens/call 2050, score stddev across runs 0.3 points, full set: 13m 11s
- **gemma-3-12B**: avg latency 72.62s, avg tokens/call 2470, score stddev across runs 1.0 points, full set: 232m 23s

## Reliability

- All runs completed and produced parseable, schema-valid JSON.

## Recommendations

- **opus-4.8** is the strongest overall pick for log/metrics analysis workloads in this run (global score 76.0).
- For **log parsing** specifically, consider **fable-5** (92.1 vs 91.9).
- For **root cause & summary** specifically, consider **fable-5-low** (62.3 vs 57.8).
- For **multi-modal rca** specifically, consider **grok-4.6-low** (68.8 vs 60.6).
- For **efficiency & consistency** specifically, consider **gpt-4o** (76.1 vs 69.5).
