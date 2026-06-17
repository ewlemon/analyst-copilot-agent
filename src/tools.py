"""The three tools the agent can call.

Each function here is the *implementation* the harness runs when Claude asks to
use a tool. They are plain Python functions with no Claude dependency, so they
are easy to test on their own (see ``tests/``).

- ``get_schema``  - describe the database so the agent knows what it can query.
- ``run_sql``     - run a validated, read-only query and return a readable table.
- ``make_chart``  - run a query and save a chart image; return its file path.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: render to files, never pop a window
import matplotlib.pyplot as plt  # noqa: E402

from guardrails import readonly_connection, validate_sql  # noqa: E402

MAX_ROWS = 100  # cap rows returned to the model so we don't flood its context
CHARTS_DIR = Path(__file__).resolve().parents[1] / "charts"


def _execute(sql: str) -> tuple[list[str], list[tuple]]:
    """Validate, run read-only, and return (column_names, rows)."""
    safe_sql = validate_sql(sql)
    conn = readonly_connection()
    try:
        cur = conn.execute(safe_sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(MAX_ROWS)
    finally:
        conn.close()
    return columns, rows


def get_schema() -> str:
    """Return a human-readable description of every table and its columns."""
    conn = readonly_connection()
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "ORDER BY name"
            ).fetchall()
        ]
        lines: list[str] = []
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            lines.append(f"\nTABLE {table}  ({count:,} rows)")
            for col in conn.execute(f"PRAGMA table_info({table})").fetchall():
                # col = (cid, name, type, notnull, dflt, pk)
                pk = "  PRIMARY KEY" if col[5] else ""
                lines.append(f"  - {col[1]} ({col[2]}){pk}")
    finally:
        conn.close()
    return "\n".join(lines).strip()


def _format_table(columns: list[str], rows: list[tuple]) -> str:
    """Render rows as a compact pipe-delimited table for the model to read."""
    if not columns:
        return "(query returned no columns)"
    if not rows:
        return "(0 rows)"
    header = " | ".join(columns)
    sep = " | ".join("---" for _ in columns)
    body = "\n".join(
        " | ".join("" if v is None else str(v) for v in row) for row in rows
    )
    note = ""
    if len(rows) == MAX_ROWS:
        note = f"\n(showing first {MAX_ROWS} rows)"
    return f"{header}\n{sep}\n{body}{note}"


def run_sql(query: str) -> str:
    """Run a read-only query and return the results as a text table."""
    columns, rows = _execute(query)
    return _format_table(columns, rows)


def make_chart(
    sql: str,
    chart_type: str = "bar",
    x: str | None = None,
    y: str | None = None,
    title: str = "",
) -> str:
    """Run ``sql``, plot column ``x`` against ``y``, save a PNG, return its path.

    ``chart_type`` is "bar" or "line". ``x`` and ``y`` must be column names in
    the query result (defaults to the first and second columns).
    """
    columns, rows = _execute(sql)
    if not columns or not rows:
        raise ValueError("The query returned no data to chart.")

    x = x or columns[0]
    y = y or (columns[1] if len(columns) > 1 else columns[0])
    for axis_name, col in (("x", x), ("y", y)):
        if col not in columns:
            raise ValueError(
                f"{axis_name}={col!r} is not a column in the result "
                f"(available: {', '.join(columns)})."
            )
    xi, yi = columns.index(x), columns.index(y)

    labels = [str(r[xi]) for r in rows]
    try:
        values = [float(r[yi]) for r in rows]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"y-axis column {y!r} is not numeric.") from exc

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if chart_type == "line":
        ax.plot(labels, values, marker="o")
    else:
        ax.bar(labels, values)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.set_title(title or f"{y} by {x}")
    if len(labels) > 6:
        plt.xticks(rotation=45, ha="right")
    fig.tight_layout()

    # Deterministic-ish filename based on the title/axes so reruns overwrite.
    slug = "".join(c if c.isalnum() else "_" for c in (title or f"{y}_by_{x}"))
    path = CHARTS_DIR / f"{slug[:50]}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return str(path)
