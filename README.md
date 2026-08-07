# Copperleaf Kitchens — MCP Server & Long-Term Memory Lab

A production-grade **Model Context Protocol (MCP)** server and **Long-Term Memory Subsystem** built for the Copperleaf Kitchens restaurant chain. Demonstrates all protocol concerns, long-term memory tiering, promote-or-drop routing, semantic consolidation with contradiction resolution, and empirical context management evaluation.

---

## 1. Problem Framing & Real Business Need

Copperleaf Kitchens operates multiple restaurant branches with complex daily operations. Prior to adding this memory subsystem, the agent suffered from two major operational flaws:
1. **Session Amnesia**: Whenever an assistant session ended, the agent forgot branch preferences (e.g. preferred emergency suppliers, manager overrides, and past waste incident resolution patterns).
2. **Context Inflation & Information Loss**: Large tool output payloads (JSON responses from inventory checks and waste report generations) quickly flooded the short-term context window. Truncating context naively caused critical instructions (like emergency supplier preferences or manager sign-offs) to be lost.

---

## 2. Memory Architecture (`memory/`)

The system implements a tiered long-term memory architecture persisted directly to `copperleaf.db`:

```
+---------------------------------------------------------------------------------+
|                              MemoryEnabledAgent                                 |
+---------------------------------------------------------------------------------+
                                      |
                       1. Append Message / Tool Output
                                      v
+---------------------------------------------------------------------------------+
|  ShortTermMemory (Rolling FIFO Buffer + Active Scratchpad)                       |
+---------------------------------------------------------------------------------+
                                      |
                       2. Overflow Eviction Trigger
                                      v
+---------------------------------------------------------------------------------+
|  PromoteOrDropRouter (Evaluates Heuristics; Logs to `router_decisions` table)  |
+---------------------------------------------------------------------------------+
                                      |
                       3. Promoted Experience Logs
                                      v
+---------------------------------------------------------------------------------+
|  EpisodicMemory (Structured Event Logs in `episodic_events` SQLite table)        |
+---------------------------------------------------------------------------------+
                                      |
                       4. Periodic Background Pass
                                      v
+---------------------------------------------------------------------------------+
|  SemanticConsolidationEngine (Versioned Knowledge in `semantic_facts` table)   |
|  - Auto-Expires TTLs (`valid_until`)                                            |
|  - Explicit Contradiction Handling (`SUPERSEDE` / `MARK_CONTRADICTION`)        |
+---------------------------------------------------------------------------------+
```

### Components Summary
- **Short-Term Memory & Scratchpad (`memory/short_term.py`, `memory/scratchpad.py`)**: A rolling FIFO message buffer paired with an isolated `Scratchpad` holding active goal state, sub-goals, and reasoning steps. Pruning the context buffer never destroys the scratchpad.
- **Promote-or-Drop Router (`memory/router.py`)**: Evaluates evicted short-term items against heuristic rules. Decides whether to **FORGET** or **PROMOTE** to Episodic Memory. Does NOT write directly to Semantic Memory. Every decision is logged to SQLite (`router_decisions`).
- **Episodic Memory Store (`memory/episodic.py`)**: Stores long-term structured experience events in `episodic_events`.
- **Semantic Memory Store (`memory/semantic.py`)**: Holds versioned entity facts (`active`, `superseded`, `contradicted`, `expired`) in `semantic_facts`. Written **only** by the Consolidation Engine.
- **Semantic Consolidation Engine (`memory/consolidation.py`)**: Runs periodic background passes over unconsolidated episodic events. Resolves real conflicts (e.g. manager supplier preference vs corporate override) and auto-expires facts past their `valid_until` timestamp.
- **Self-RAG Verification (`memory/verification.py`)**: Verifies relevance (`IS_REL`) and factual support grounding (`IS_SUP`) before recalled memories reach downstream logic.

---

## 3. Context Management Benchmark (`context_eval/`)

We implemented all **4 Context Window Management Strategies** plus a **PII Masking Strategy** and benchmarked them against long, tool-heavy transcripts containing buried needle facts.

### Empirical Evaluation Results

| Strategy Name | Scenario | Orig Tokens | Retained | Saved | Reduction | Needle Accuracy (%) | Latency | Retrieval Saturation |
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

### Strategy Choice & Justification

**Selected Strategy**: **Observation Masking** (`ObservationMaskingStrategy`)

**Data-Driven Justification**:
1. **100% Needle Fact Recall**: As shown in the comparison table, Observation Masking was the **only** strategy that achieved **100.0% needle accuracy** across both multi-turn benchmarks. Sliding Window, Zone Pruning, and Recursive Summarization all lost the early critical decision under tool noise.
2. **Targeted Token Reduction**: The primary source of context bloat in Copperleaf Kitchens' workflows is raw JSON tool observations (SQL query results, inventory lists). Observation Masking targets raw tool outputs while preserving user and assistant dialogue turns.
3. **Low Latency & Zero Sub-Call Overhead**: Observation Masking operates in under **0.08ms** without making external LLM calls (unlike Recursive Summarization which increases output token costs and latency).

---

## 4. MCP Protocol Concerns — Quick Reference

| # | Concern | Where Implemented |
|---|---------|------------------|
| 1 | **Capability Negotiation** | `ClientSession` handshake checking `sampling` + `elicitation` |
| 2 | **Notifications** | `tools/list_changed` pushed via `send_tool_list_changed()` on role elevation |
| 3 | **Elicitation** | `elicitation/create` mid-call sign-off for high-value write-offs |
| 4 | **Resources** | `copperleaf://policy/waste_management` and `copperleaf://policy/approval_thresholds` |
| 5 | **Prompts** | `draft_waste_investigation` and `supplier_order_inquiry` templates |
| 6 | **Transport** | stdio (default) or SSE (`--transport sse --port 8000`) |
| 7 | **Progress Tracking** | `ctx.report_progress()` emitted during multi-step tools |
| 8 | **Defensive Design** | Hardened JSON schemas, independent `validation.py`, role+branch check |

---

## 5. Quick Start & Demonstration Scripts

### 1. Run the Integrated Agent Demo (`agent/agent.py`)
Executes conversation turns, triggering Short-Term Memory overflow routing and background Semantic Consolidation:
```bash
python -m agent.agent
```

### 2. Run the Contradiction & Expiration Demo (`memory/demo_contradiction.py`)
Demonstrates explicit conflict resolution (`SUPERSEDE` and `MARK_CONTRADICTION`) and auto-expiration:
```bash
python -m memory.demo_contradiction
```

### 3. Run Context Evaluation Benchmark (`context_eval/evaluate.py`)
Runs all 4 context strategies + PII masking against long-context test suites:
```bash
python -m context_eval.evaluate
```

### 4. Run MCP Protocol Demo Client (`agent/client.py`)
```bash
python agent/client.py --token tok_mona_mgr_9f2a
```
