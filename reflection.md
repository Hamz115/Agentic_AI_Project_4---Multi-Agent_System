# Reflection Report — Munder Difflin Multi-Agent System

## 1. Agent Workflow Architecture

### Overview

The system uses 4 agents (within the 5-agent maximum) built with the smolagents framework, each backed by GPT-4o via the Vocareum API proxy:

| Agent | Role |
|-------|------|
| **Orchestrator** | Top-level coordinator. Receives each customer request and delegates to the 3 worker agents in a fixed sequence. Combines their results into a final customer-facing response. |
| **Inventory Agent** | Checks warehouse stock levels and restocks from suppliers when needed. Has access to the product catalog to map customer item names to exact catalog names. |
| **Quoting Agent** | Looks up historical quotes for similar orders, retrieves the product catalog, and calculates itemized price quotes with tiered bulk discounts. |
| **Order Agent** | Processes sale transactions, checks delivery estimates, monitors the cash balance, and generates financial reports. |

### Why This Architecture?

**Separation of concerns.** Each agent only has the tools relevant to its job — the inventory agent cannot process sales, and the order agent cannot restock items. This mirrors how a real business operates (warehouse staff, sales reps, cashiers) and prevents any single agent from making uncoordinated changes.

**Sequential orchestration.** The orchestrator always calls agents in order: Inventory → Quoting → Order. This ensures:
1. Items are in stock *before* generating a quote (no quoting items I can't deliver)
2. Prices are calculated *before* processing the sale (no selling at wrong prices)
3. Each agent receives context from the previous agent's output

**Why not more agents?** I considered a separate Financial Agent, but the financial tools (balance check, financial report) naturally fit with the order agent since they're needed at the point of sale. Adding more agents would increase latency (more LLM calls) without improving functionality.

**Why ToolCallingAgent?** I chose `ToolCallingAgent` over `CodeAgent` because the workflow is tool-driven — each step involves calling a specific database function, not generating arbitrary code. Tool calling is more predictable and safer for a system that modifies a database.

### Tool-to-Helper-Function Mapping

Each tool wraps one or more starter code helper functions:

| Tool | Helper Function(s) Used | Purpose |
|------|------------------------|---------|
| `check_inventory` | `get_all_inventory` | See all stock levels, flag items below minimum |
| `check_item_stock` | `get_stock_level` | Check stock for one specific item |
| `restock_item` | `create_transaction`, `get_cash_balance`, `get_supplier_delivery_date` | Order from supplier — checks funds first |
| `search_past_quotes` | `search_quote_history` | Find similar past quotes for pricing reference |
| `get_product_catalog` | `paper_supplies` list | List all 42 items with names and prices |
| `calculate_quote` | `paper_supplies` list | Calculate itemized pricing with bulk discounts |
| `process_sale` | `get_stock_level`, `create_transaction` | Record a sale — checks stock first |
| `check_delivery_estimate` | `get_supplier_delivery_date` | Estimate when a supplier order arrives |
| `get_balance` | `get_cash_balance` | Check current company cash |
| `get_financial_report` | `generate_financial_report` | Full financial snapshot: cash, inventory, top sellers |

---

## 2. Evaluation Results

### Test Run Summary

The system was evaluated against all 20 customer requests in `quote_requests_sample.csv`, dated April 1–17, 2025. Results are saved in `test_results.csv`.

- **Starting state:** Cash: $45,059.70 | Inventory: $4,940.30
- **Final state:** Cash: $43,672.98 | Inventory: $5,000.75
- **Requests fully processed:** 20 of 20 (all completed successfully)

### Key Metrics

**Cash balance changed in 12 out of 20 requests**, including:
- Request 3: -$39.15 (restocking for large A4/poster/copy paper order)
- Request 4: +$11.88 (sale of 250 sheets A4 paper)
- Request 5: +$45.00 (sale of 500 sheets Colored paper)
- Request 8: +$90.00 (sale of 500 sheets Glossy paper)
- Request 9: -$16.50 (net of sales for A4, Glossy, Envelopes and restocking)
- Request 13: +$28.50 (sale of 200 sheets Cardstock)
- Request 10: -$30.00 (restocking for Glossy paper and 250gsm cardstock)
- Request 11: -$5.00 (restocking for Glossy and A4 paper)
- Request 15: -$271.00 (restocking large A4, Colored paper, 250gsm cardstock order)
- Request 17: -$151.20 (restocking for reception supplies)
- Request 18: +$19.00 (sale of Colored paper)
- Request 19: -$1,068.25 (sales of Matte paper and 250gsm cardstock + restocking)

**At least 8 quote requests were successfully fulfilled** (fully or partially), including:
- Request 4: 250 sheets A4 paper ($11.88)
- Request 5: 500 sheets Colored paper ($45.00)
- Request 8: 500 sheets Glossy paper ($90.00)
- Request 9: 200 sheets A4 paper, 100 sheets Glossy paper, 50 Envelopes ($33.50 total)
- Request 13: 200 sheets Cardstock ($28.50)
- Request 16: 500 A4 paper, 100 Poster paper, 200 Construction paper ($64.00 total)
- Request 18: Colored paper sale processed ($19.00)
- Request 19: Matte paper and 250gsm cardstock processed ($824.50 quoted)

**Not all requests were fully fulfilled.** Reasons included:
- Items not in the product catalog (e.g., "balloons", "streamers", "tickets") — customers requested items Munder Difflin doesn't sell
- Insufficient stock for large orders (e.g., 10,000 sheets when only ~1,100 in stock) — restocking was initiated but delivery would exceed the customer's deadline
- Item name mismatches (e.g., "A4 glossy paper" not found, "Construction paper (paper)" vs "Construction paper") — the agent sometimes couldn't map informal names or appended the category
- Insufficient funds for restocking in request 14 — company cash was too low to cover the restock cost

### Strengths

1. **Successful catalog name resolution.** After adding the product catalog to the inventory agent, it successfully mapped customer names to exact catalog names in most cases (e.g., "A4 printer paper" → "A4 paper", "heavy cardstock" → "Cardstock", "colorful construction paper" → "Construction paper").

2. **Consistent agent coordination.** The orchestrator called all 3 agents in the correct sequence (Inventory → Quoting → Order) for every request. The orchestrator also passed exact catalog names from the inventory agent to downstream agents.

3. **Bulk discount logic.** The quoting agent correctly applied the tiered discount structure (5% for 100-499 units, 10% for 500-999, 15% for 1000+) in every quote.

4. **Transparent customer responses.** Responses included clear explanations: what items were available, the price breakdown, why items couldn't be fulfilled, and estimated delivery timelines.

5. **Safety checks.** The `process_sale` tool prevented selling items without sufficient stock, and `restock_item` prevented spending more cash than available. No invalid transactions were created.

### Areas of Improvement

1. **Partial name matching failures.** While the catalog lookup greatly improved name resolution, the inventory agent occasionally appended the category to item names (e.g., "Construction paper (paper)" instead of "Construction paper"), causing restocking to fail. A fuzzy matching layer would fix this.

2. **Date hallucination.** The LLM occasionally used incorrect dates (e.g., 2023 instead of 2025) when calling tools, despite the correct date being in the request. This affected delivery estimates in a few requests.

3. **Restocking timing.** The system treats restocking as instantaneous in the database (the transaction is recorded immediately), but delivery estimates show future dates. The order agent sometimes tried to sell before the restock "arrived," leading to stock shortage errors even after restocking was initiated.

---

## 3. Suggestions for Improvement

### Improvement 1: Fuzzy Name Resolution Layer

Add a dedicated name-matching utility that maps customer item names to the closest catalog match using string similarity (e.g., Levenshtein distance or token overlap). Instead of relying on the LLM to guess the right catalog name, the tool itself could suggest the top 3 closest matches when an exact match isn't found. For example, if a customer asks for "glossy A4 paper," the tool could return: "Did you mean 'Glossy paper' ($0.20/unit) or 'A4 paper' ($0.05/unit)?" This would dramatically improve order fulfillment rates.

### Improvement 2: Business Advisor Agent

Add a 5th agent (still within the max) that analyzes transaction patterns and proactively recommends business decisions. For example, it could:
- Identify which items are frequently requested but out of stock, and pre-order them
- Flag items with low sales that are tying up cash in inventory
- Suggest optimal reorder quantities based on historical demand patterns
- Alert when cash balance is getting low relative to upcoming expected orders

This would transform the system from purely reactive (handling one request at a time) to strategic (optimizing the business over time).
