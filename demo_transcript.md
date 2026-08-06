# Demo Transcript — Copperleaf Kitchens MCP Server

Full run of `python agent/client.py --token tok_mona_mgr_9f2a`.
Each section corresponds to one of the 8 protocol concerns.

---

```
===========================================================================
 COPPERLEAF KITCHENS MCP SERVER — PROTOCOL CONCERNS DEMO
===========================================================================
Connecting with API Token: tok_mona_mgr_9f2a

--- [1. CAPABILITY NEGOTIATION & HANDSHAKE] ---
  Protocol Version : 2025-06-18
  Server Name      : copperleaf-kitchens (v1.10.0)
  Server Caps      : experimental={} logging=None
                     prompts=PromptsCapability(listChanged=False)
                     resources=ResourcesCapability(subscribe=False, listChanged=False)
                     tools=ToolsCapability(listChanged=False)
  Negotiated Capabilities Check: tools=True, resources=True, prompts=True
```

**What happened:** The client called `initialize`. The MCP library auto-advertised `sampling`
and `elicitation` capabilities because non-default callbacks were registered. The server
confirmed `tools`, `resources`, and `prompts` are available.

---

```
--- [2. RESOURCES — DISCOVERY & READING] ---
  Available Resources (2):
    - copperleaf://policy/waste_management (get_waste_management_policy)
    - copperleaf://policy/approval_thresholds (get_approval_thresholds_policy)

  [Fetched Resource: copperleaf://policy/waste_management]:
    # Copperleaf Kitchens Waste Management Policy

    1. **Loss Ceilings**: No single write-off may exceed 500 units.
    2. **High-Value Sign-off Requirement (Elicitation)**: Any write-off involving
    ...
```

**What happened:** Client called `list_resources`, then `read_resource` on the waste policy URI.
The server returned the static policy document as a `copperleaf://` scheme resource.

---

```
--- [3. PROMPTS — TEMPLATE DISCOVERY & FETCHING] ---
  Available Prompts (2):
    - draft_waste_investigation: Prompt template to assist kitchen managers ...
    - supplier_order_inquiry: Prompt template for drafting an inquiry ...

  [Fetched Prompt Template 'draft_waste_investigation']:
    Generate a comprehensive waste investigation report for Copperleaf Kitchens
    Branch 1 between 2026-07-01 and 2026-07-31.
    1. Call `generate_waste_report`...
```

**What happened:** Client called `list_prompts`, then `get_prompt` with arguments
`{branch_id: "1", date_from: "2026-07-01", date_to: "2026-07-31"}`.

---

```
--- [4. DEFENSIVE TOOL DESIGN — HARDENED SCHEMAS] ---
  Discovered Tools (7):
    - elevate_to_manager        required=['manager_passcode'], additionalProperties=False
    - get_inventory             required=['branch_id'], additionalProperties=False
    - get_low_stock_items       required=['branch_id'], additionalProperties=False
    - get_supplier_orders       required=['branch_id'], additionalProperties=False
    - get_transaction_history   required=['item_id'], additionalProperties=False
    - write_off_inventory       required=['item_id', 'quantity', 'reason'], additionalProperties=False
    - generate_waste_report     required=['branch_id', 'date_from', 'date_to'], additionalProperties=False
```

**What happened:** Client called `list_tools` and inspected each tool's `inputSchema`.
All 7 tools have `additionalProperties: false` (blocks extra fields) and explicit `required` lists.
`write_off_inventory` also has `enum` constraints on the `reason` field.

---

```
--- [5. READ-ONLY TOOL CALL: get_inventory] ---
  Result: {
    "item_id": 1,
    "name": "Roma Tomatoes",
    "category": "produce",
    "unit": "kg",
    "current_quantity": 4.5,
    "reorder_threshold": 10.0,
    "unit_cost": 1.2
  }
```

**What happened:** Client called `get_inventory` with `{branch_id: 1, item_name: "Roma"}`.
Tool executed auth check (staff can read), queried SQLite, returned structured result.

---

```
--- [6. PROGRESS TRACKING & SAMPLING: generate_waste_report] ---
  [PROGRESS] [  0%] (0.0/100.0) -> Querying write-off transactions...
  [PROGRESS] [ 40%] (40.0/100.0) -> Found 2 write-off records, computing costs...
  [PROGRESS] [ 75%] (75.0/100.0) -> Checking sampling support...
  [PROGRESS] [ 85%] (85.0/100.0) -> Requesting AI summary via sampling...

  [SAMPLING REQUEST FROM SERVER]:
    Inventory write-offs for branch 1 between 2026-07-01 and 2026-07-31:
    - Roma Tomatoes (produce): 2.0 units, reason=spoiled_before_use, cost=2.40
    - Whole Milk (dairy): 3.0 units, reason=past_expiry, cost=2.85

    In 2-3 sentences, summarize the likely causes and flag any pattern a manager should look into.
  [CLIENT DECISION]: Generating sampling summary response.

  [PROGRESS] [100%] (100.0/100.0) -> Report complete.
  Waste Report Result:
    {
      "branch_id": 1,
      "date_from": "2026-07-01",
      "date_to": "2026-07-31",
      "total_write_off_events": 2,
      "total_cost_impact": 5.25,
      "cost_by_reason": {
        "spoiled_before_use": 2.4,
        "past_expiry": 2.85
      },
      "ai_summary": "AI Summary: Spoilage pattern concentrated around perishable produce.
                     Recommend adjusting reorder schedule."
    }
```

**What happened:**
- Server emitted 5 progress events via `ctx.report_progress()`.
- Server checked `sampling` capability (positive), then sent `create_message` to the client.
- Client's `sampling_handler` received the prompt and returned a `CreateMessageResult`.
- Server incorporated the AI summary into the report.

---

```
--- [7. NOTIFICATIONS & DYNAMIC TOOLSET: elevate_to_manager] ---
  Elevation Result: {
    "status": "elevated",
    "staff_name": "Mona Farid",
    "new_role": "manager",
    "notification_sent": "tools/list_changed"
  }
```

**What happened:** `elevate_to_manager` with passcode `MGR2026` elevated the in-process
`SESSION.role` to `manager` and called `ctx.session.send_tool_list_changed()`, pushing a
`notifications/tools/list_changed` message to the client.

---

```
--- [8. MID-CALL ELICITATION: High-Value Inventory Write-Off] ---
  Writing off 2kg of Wagyu Beef Ribeye (item_id=10, unit_cost=$85.00)...

  [PROGRESS] [ 50%] (50.0/100.0) -> High-value write-off detected — requesting mid-call
                                     human sign-off via elicitation...

  [ELICITATION REQUEST FROM SERVER]: HIGH RISK WRITE-OFF SIGN-OFF REQUIRED:
    Item: Wagyu Beef Ribeye (ID 10)
    Quantity: 2.0
    Unit Cost: $85.00
    Total Cost Impact: $170.00
    Reason: spoiled_before_use
    Requested by: Mona Farid

    Please fill in the form below to authorize or reject this write-off.

  [ELICITATION SCHEMA]: {
    'properties': {
      'confirmation': {'description': "Type 'CONFIRM' to approve or 'REJECT' to cancel.", ...},
      'authorized_by': {'description': 'Full name of the authorizing supervisor.', ...}
    },
    'required': ['confirmation', 'authorized_by']
  }

  [CLIENT DECISION]: Elicitation triggered mid-call. Human supervisor approves write-off.

  Write-off Final Result:
    {
      "item_id": 10,
      "quantity_written_off": 2.0,
      "reason": "spoiled_before_use",
      "new_stock_level": 23.0,
      "recorded_by": "Mona Farid"
    }
```

**What happened:**
- Server fetched item details, detected that 2 × $85 = $170 >= $100 threshold.
- Server checked `elicitation` capability (positive — client declared it).
- Server called `elicit_with_validation()` with a `WriteOffSignOffSchema` Pydantic model, sending `elicitation/create` to the client.
- Client's `elicitation_handler` returned `ElicitResult(action="accept", content={confirmation: "CONFIRM", ...})`.
- Server validated the confirmation, then executed the write-off via `tools.write_off_inventory()`.

---

```
===========================================================================
 ALL 8 PROTOCOL CONCERNS SUCCESSFULLY VERIFIED!
===========================================================================
```
