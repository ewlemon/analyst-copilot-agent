# Methodology: Analyst Copilot Agent

*Compiled 2026-06-17*

---

## Goal

Explain *how* the Analyst Copilot reaches an answer, where the human analyst
stays in control, and what the system can and cannot be trusted to do. This is
the document that lets a reader judge whether a given answer is decision-grade.

---

## How the agent reaches a conclusion

The agent is a loop (`src/agent.py`) over the Claude API with three tools:

| Step | What happens |
|---|---|
| 1. Understand | The model reads the question and, if unsure, calls `get_schema` to learn the tables and columns - it does not guess the schema. |
| 2. Query | It writes a single read-only `SELECT`/`WITH` query and runs it with `run_sql`. It may iterate - refining the query if the first result is incomplete or surprising. |
| 3. Visualize | For rankings, trends, and comparisons it calls `make_chart`, which re-runs a validated query and renders a PNG. |
| 4. Explain | It writes a plain-English answer for a non-technical reader, ending with a short **Caveats** section. |

Every figure in an answer must come from a query the agent actually ran - the
system prompt forbids estimating or inventing numbers.

---

## Definitions used

| Metric | Definition |
|---|---|
| Revenue | `SUM(order_items.price * order_items.quantity)` |
| Gross profit | `SUM((order_items.price - products.unit_cost) * order_items.quantity)` |
| Region | `customers.customer_state` (join `orders` → `customers`) |

These conventions are stated in the system prompt so the agent applies them
consistently rather than choosing its own each time.

---

## The human-in-the-loop step (where judgment lives)

The agent is a copilot, not an oracle. Two design choices keep a person in
control:

- **Transparency.** The CLI and UI surface the exact SQL the agent ran. The
  analyst reads it and decides whether the logic is sound before trusting the
  number.
- **Caveats.** Each answer ends with assumptions/limitations the analyst should
  check.

The recommended verification habit: for any answer that will inform a decision,
re-run (or read) the agent's SQL and confirm the number independently. The
project's end-to-end test does exactly this - it checks the agent's figure
against a hand-written query.

---

## Safety / inclusion constraints

- **Read-only only.** `src/guardrails.py` rejects any non-`SELECT` query and
  opens the database read-only. The agent cannot modify data under any prompt.
- **Bounded results.** Query results returned to the model are capped
  (`MAX_ROWS`) so a large result set can't distort the answer or balloon cost.

---

## Limitations

- **The model can write wrong-but-valid SQL.** A query can run cleanly yet
  answer a subtly different question than intended (e.g. counting orders vs.
  line items). This is precisely why the SQL is surfaced for human review.
- **Synthetic data by default.** Conclusions describe the generated dataset, not
  a real business, unless the real Olist data is loaded (see `data/README.md`).
- **Cheaper models trade accuracy for cost.** Development uses Haiku; complex
  multi-join questions are more reliable on Sonnet.
- **No statistical inference.** The agent reports descriptive figures; it does
  not test significance or build forecasts.

---

## Suggested improvements for future versions

- A second "auditor" model pass that critiques the first answer's SQL.
- A `describe_column` tool so the agent can inspect value distributions before
  querying.
- Prompt caching of the schema to cut per-question cost.
