# Context Window Management Strategy Comparison Report

**Evaluation Timestamp**: 2026-08-07T01:11:46.949917+00:00

**Max Token Budget Limit**: 1200 tokens

| Strategy Name | Scenario | Orig Tokens | Retained | Saved | Reduction | Needle % | Latency | Retrieval Saturation |
|---|---|---|---|---|---|---|---|---|
| **Sliding Window** | Inventory Waste Investigation Benchmark | 1522 | 1196 | 326 | 21.4% | **0.0%** | 0.04ms | 99.7% |
| **Observation Masking** | Inventory Waste Investigation Benchmark | 1522 | 1082 | 440 | 28.9% | **100.0%** | 0.08ms | 90.2% |
| **PII Masking** | Inventory Waste Investigation Benchmark | 1522 | 1522 | 0 | 0.0% | **100.0%** | 0.64ms | 126.8% |
| **Recursive Summarization** | Inventory Waste Investigation Benchmark | 1522 | 263 | 1259 | 82.7% | **0.0%** | 0.05ms | 21.9% |
| **Zone-Based Pruning** | Inventory Waste Investigation Benchmark | 1522 | 1196 | 326 | 21.4% | **0.0%** | 0.03ms | 99.7% |
| **Sliding Window** | 50-Turn Extreme Scale Benchmark | 1204 | 1189 | 15 | 1.2% | **0.0%** | 0.03ms | 99.1% |
| **Observation Masking** | 50-Turn Extreme Scale Benchmark | 1204 | 937 | 267 | 22.2% | **100.0%** | 0.06ms | 78.1% |
| **PII Masking** | 50-Turn Extreme Scale Benchmark | 1204 | 1204 | 0 | 0.0% | **100.0%** | 0.38ms | 100.3% |
| **Recursive Summarization** | 50-Turn Extreme Scale Benchmark | 1204 | 234 | 970 | 80.6% | **0.0%** | 0.04ms | 19.5% |
| **Zone-Based Pruning** | 50-Turn Extreme Scale Benchmark | 1204 | 1193 | 11 | 0.9% | **0.0%** | 0.03ms | 99.4% |