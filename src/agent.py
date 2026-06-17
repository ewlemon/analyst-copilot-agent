"""The Analyst Copilot agent loop.

Given a plain-English business question, this drives Claude through an agentic
loop: Claude inspects the schema, writes read-only SQL, looks at the results,
optionally charts them, and finally writes a plain-English answer, always
showing the exact SQL it ran so a human analyst can verify it.

Run from the command line:

    python src/agent.py "Which states generate the most revenue?"

Requires ANTHROPIC_API_KEY in your environment (or a .env file).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

import tools

load_dotenv()

DEFAULT_MODEL = os.environ.get("ANALYST_MODEL", "claude-haiku-4-5")
MAX_ITERATIONS = 12  # safety stop so the loop can never run forever
PLACEHOLDER_KEY = "sk-ant-your-key-here"  # the value shipped in .env.example


def api_key_problem() -> str | None:
    """Return a human-readable problem with the API key, or None if it looks ok."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or key == PLACEHOLDER_KEY:
        return (
            "ANTHROPIC_API_KEY is missing or still the placeholder. Open .env "
            "and replace 'sk-ant-your-key-here' with a real key from "
            "https://console.anthropic.com (Settings -> API keys), and add a "
            "little credit under Billing."
        )
    return None

SYSTEM_PROMPT = """\
You are an analyst copilot for an e-commerce business. A human business analyst \
asks you questions in plain English. You answer by querying a SQLite database \
with read-only SQL and explaining what you find. You are a tool the analyst \
supervises. They will read the SQL you ran and decide whether to trust it, so \
make your work transparent.

How to work:
1. If you are unsure of table or column names, call get_schema first. Do not \
guess at the schema.
2. Write a single read-only SELECT (CTEs with WITH are fine) and run it with \
run_sql. Iterate: if a result is surprising or incomplete, refine the query.
3. When a result is worth visualizing (a ranking, a trend over time, a \
comparison), call make_chart.
4. Finish with a short, plain-English answer for a non-technical reader.

Conventions for this database:
- Revenue = SUM(order_items.price * order_items.quantity).
- Gross profit = SUM((order_items.price - products.unit_cost) * order_items.quantity).
- Region = customers.customer_state (join orders -> customers).

Rules:
- Only ever read data. You cannot modify the database.
- Every number you state must come from a query you actually ran. Never \
estimate or invent figures.
- End your final answer with a short "Caveats" section (1-3 bullets) noting \
assumptions or data limitations, so the analyst knows what to double-check.
"""

# Tool schemas advertised to Claude. Names and shapes must match the functions
# in tools.py.
TOOL_SCHEMAS = [
    {
        "name": "get_schema",
        "description": "List all tables in the database with their columns and "
        "row counts. Call this first if unsure about the schema.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_sql",
        "description": "Run a single read-only SQL SELECT query against the "
        "database and return the rows as a text table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A single read-only SELECT query.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "make_chart",
        "description": "Run a query and save a chart image of the result. Use "
        "for rankings, trends, and comparisons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Read-only SELECT producing the chart data.",
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line"],
                    "description": "Bar for comparisons/rankings, line for trends.",
                },
                "x": {
                    "type": "string",
                    "description": "Result column for the x-axis (categories/dates).",
                },
                "y": {
                    "type": "string",
                    "description": "Result column for the y-axis (a numeric measure).",
                },
                "title": {"type": "string", "description": "Chart title."},
            },
            "required": ["sql", "chart_type"],
        },
    },
]


@dataclass
class AnalysisResult:
    """Everything a caller (CLI or UI) needs to display a run."""

    answer: str
    sql_queries: list[str] = field(default_factory=list)
    charts: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


def _dispatch(name: str, args: dict, result: AnalysisResult) -> tuple[str, bool]:
    """Run one tool call. Returns (content_for_model, is_error)."""
    try:
        if name == "get_schema":
            result.steps.append("Looked up the database schema.")
            return tools.get_schema(), False
        if name == "run_sql":
            query = args["query"]
            result.sql_queries.append(query)
            result.steps.append(f"Ran SQL:\n{query}")
            return tools.run_sql(query), False
        if name == "make_chart":
            result.sql_queries.append(args["sql"])
            path = tools.make_chart(
                sql=args["sql"],
                chart_type=args.get("chart_type", "bar"),
                x=args.get("x"),
                y=args.get("y"),
                title=args.get("title", ""),
            )
            result.charts.append(path)
            result.steps.append(f"Made a chart: {path}")
            return f"Chart saved to {path}", False
        return f"Unknown tool: {name}", True
    except Exception as exc:  # surface the error to the model so it can adapt
        message = f"{type(exc).__name__}: {exc}"
        result.steps.append(f"Tool error ({name}): {message}")
        return message, True


def run_analysis(question: str, model: str | None = None) -> AnalysisResult:
    """Drive the agent loop to completion and return the result."""
    # Imported here so importing this module never requires the SDK / a key
    # (handy for tests that only touch tools/guardrails).
    import anthropic

    client = anthropic.Anthropic()
    model = model or DEFAULT_MODEL
    result = AnalysisResult(answer="")
    messages: list[dict] = [{"role": "user", "content": question}]

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            result.answer = "".join(
                b.text for b in response.content if b.type == "text"
            ).strip()
            return result

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                content, is_error = _dispatch(block.name, block.input, result)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                        "is_error": is_error,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    result.answer = (
        "Stopped after the maximum number of steps without a final answer. "
        "Try rephrasing the question or narrowing its scope."
    )
    return result


def _main() -> int:
    parser = argparse.ArgumentParser(description="Ask the analyst copilot a question.")
    parser.add_argument("question", help="The business question, in quotes.")
    parser.add_argument("--model", default=None, help="Override the model id.")
    args = parser.parse_args()

    problem = api_key_problem()
    if problem:
        print(problem, file=sys.stderr)
        return 1

    import anthropic

    try:
        result = run_analysis(args.question, model=args.model)
    except anthropic.AuthenticationError:
        print(
            "Authentication failed (401): the API key in .env was rejected. "
            "Check that you pasted the full key correctly and that it is active "
            "in the Anthropic Console.",
            file=sys.stderr,
        )
        return 1

    print("\n=== Steps ===")
    for i, step in enumerate(result.steps, 1):
        print(f"{i}. {step}")
    print("\n=== Answer ===")
    print(result.answer)
    if result.charts:
        print("\n=== Charts ===")
        for path in result.charts:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
