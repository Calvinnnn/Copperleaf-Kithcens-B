# Copperleaf Kitchens — MCP Server Lab

A production-grade **Model Context Protocol (MCP)** server built for the Copperleaf Kitchens restaurant chain, demonstrating all 8 protocol concerns required by the lab specification.

---

## Protocol Concerns — At a Glance

| # | Concern | Where Implemented |
|---|---------|------------------|
| 1 | **Capability Negotiation** | `ClientSession` handshake; server checks `sampling` + `elicitation` caps before using them |
| 2 | **Notifications** | `tools/list_changed` pushed via `ctx.session.send_tool_list_changed()` when role is elevated |
| 3 | **Elicitation** | `elicitation/create` mid-call sign-off for high-value write-offs (>= $100 or unit cost >= $50) |
| 4 | **Resources** | `copperleaf://policy/waste_management` and `copperleaf://policy/approval_thresholds` |
| 5 | **Prompts** | `draft_waste_investigation` and `supplier_order_inquiry` parameterized templates |
| 6 | **Transport** | stdio (default) or Streamable HTTP / SSE (`--transport sse --port 8000`) |
| 7 | **Progress Tracking** | `ctx.report_progress()` at each step of `generate_waste_report` and `write_off_inventory` |
| 8 | **Defensive Tool Design** | Hardened JSON schemas (`required`, `additionalProperties: false`, `enum`), independent `validation.py` layer, role+branch authorization |

---

## Project Layout

```
copperleaf-mcp/
├── agent/
│   └── client.py          # End-to-end demo client exercising all 8 concerns
├── db/
│   ├── schema.sql          # SQLite schema (branches, staff, inventory, transactions)
│   ├── seed.sql            # Seed data (includes Wagyu Beef Ribeye for elicitation demo)
│   └── ERD.mmd             # Entity-relationship diagram (Mermaid)
├── mcp_server/
│   ├── server.py           # FastMCP server -- 8 protocol concerns wired together
│   ├── auth.py             # Token -> Session resolution; AuthError
│   ├── db.py               # SQLite connection factory
│   ├── tools.py            # Business logic (get_inventory, write_off, etc.)
│   └── validation.py       # Independent server-side validation (schema != validation)
└── requirements.txt
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the full protocol demo

```bash
python agent/client.py --token tok_mona_mgr_9f2a
```

This exercises all 8 protocol concerns and prints a step-by-step transcript.

### 3. Run the server standalone (stdio)

```bash
COPPERLEAF_API_TOKEN=tok_mona_mgr_9f2a python mcp_server/server.py
```

### 4. Run the server in SSE / Streamable HTTP mode

```bash
COPPERLEAF_API_TOKEN=tok_mona_mgr_9f2a python mcp_server/server.py --transport sse --port 8000
```

---

## API Tokens (Seed Data)

| Token | Staff | Role | Branch |
|-------|-------|------|--------|
| `tok_ali_stf_3c1b` | Ali Hassan | staff | 1 |
| `tok_mona_mgr_9f2a` | Mona Farid | manager | 1 |
| `tok_riya_stf_7d4e` | Riya Patel | staff | 2 |
| `tok_omar_mgr_5f8c` | Omar Khalil | manager | 2 |

---

## Protocol Concern Deep Dives

### 1. Capability Negotiation

The client registers `sampling_callback` and `elicitation_callback` when creating `ClientSession`. The MCP library automatically advertises the corresponding capabilities (`sampling` and `elicitation`) during the `initialize` handshake. The server then gates tool behaviour on what the client actually declared:

```python
# server.py -- gate before using elicitation
supports_elicitation = ctx.session.check_client_capability(
    ClientCapabilities(elicitation=ElicitationCapability())
)
```

### 2. Notifications (tools/list_changed)

`elevate_to_manager` mutates the in-process `SESSION` object to `role="manager"` and immediately pushes a notification:

```python
await ctx.session.send_tool_list_changed()
```

The client receives this as a standard MCP notification, prompting it to call `list_tools` again to discover the updated toolset.

### 3. Elicitation (Mid-Call Human Sign-Off)

`write_off_inventory` pauses mid-execution when the financial risk threshold is breached and sends an `elicitation/create` message to the client using the MCP `elicit_with_validation` helper with a typed Pydantic schema:

```python
result = await elicit_with_validation(
    session=ctx.session,
    message=elicitation_message,
    schema=WriteOffSignOffSchema,   # { confirmation: str, authorized_by: str }
)
```

The client's `elicitation_handler` returns `ElicitResult(action="accept", content={...})`, which unblocks the tool to proceed with the write-off.

### 4. Resources

Two static policy documents are exposed as MCP resources:

- `copperleaf://policy/waste_management` -- loss ceilings, elicitation thresholds, branch scope rules
- `copperleaf://policy/approval_thresholds` -- role permission levels

### 5. Prompts

Two parameterized prompt templates are available:

- `draft_waste_investigation(branch_id, date_from, date_to)` -- manager investigation workflow
- `supplier_order_inquiry(order_id)` -- supplier email drafting

### 6. Transport

The server supports both transports via a CLI flag:

```
python mcp_server/server.py --transport stdio   # default
python mcp_server/server.py --transport sse --port 8000
```

### 7. Progress Tracking

`generate_waste_report` emits progress at 0%, 40%, 75%, 85%, and 100%, giving the client real-time feedback on a multi-step, I/O-bound operation. `write_off_inventory` also emits a progress event at the elicitation gate (50%).

### 8. Defensive Tool Design

Three independent layers of defence:

1. **JSON Schema hardening**: `required`, `additionalProperties: false`, and `enum` constraints on all tool input schemas (applied via `_harden_tool_schemas()` at startup).
2. **Independent validation layer** (`validation.py`): Checks positive quantity, max write-off ceiling (500 units), valid reason strings, and sufficient stock -- completely separate from the schema.
3. **Handler-level authorization**: Every write tool verifies session role (`manager`) and branch ownership before touching the database.

---

## Architecture

```
+----------------------+        MCP Protocol        +-----------------------------+
|  agent/client.py     |<-------------------------->|  mcp_server/server.py       |
|                      |                             |  (FastMCP)                  |
|  sampling_handler()  |    create_message <------   |  generate_waste_report()    |
|  elicitation_handler |<-- elicitation/create ----  |  write_off_inventory()      |
|  progress_handler()  |<-- progress notifications   |  elevate_to_manager()       |
+----------------------+                             |                             |
                                                     |  +----------------------+  |
                                                     |  |  validation.py        |  |
                                                     |  |  auth.py              |  |
                                                     |  |  tools.py             |  |
                                                     |  |  db.py -> SQLite      |  |
                                                     |  +----------------------+  |
                                                     +-----------------------------+
```
