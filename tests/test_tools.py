"""Tests for the agent's tools (run against the synthetic database)."""

from __future__ import annotations

from pathlib import Path

import pytest

import tools
from guardrails import UnsafeQueryError


def test_get_schema_lists_all_tables() -> None:
    schema = tools.get_schema()
    for table in (
        "customers", "products", "orders", "order_items", "payments", "reviews"
    ):
        assert table in schema


def test_run_sql_returns_a_table() -> None:
    out = tools.run_sql("SELECT COUNT(*) AS n FROM orders")
    assert "n" in out
    # The synthetic generator makes 4,000 orders.
    assert "4000" in out.replace(",", "")


def test_run_sql_blocks_writes() -> None:
    with pytest.raises(UnsafeQueryError):
        tools.run_sql("DELETE FROM orders")


def test_run_sql_caps_rows() -> None:
    # Two columns so each rendered line contains a "|" delimiter.
    out = tools.run_sql("SELECT order_id, status FROM orders")
    data_lines = [ln for ln in out.splitlines() if "|" in ln]
    # header + separator + at most MAX_ROWS data rows.
    assert len(data_lines) <= tools.MAX_ROWS + 2
    assert "showing first" in out  # the truncation note appears


def test_make_chart_writes_png() -> None:
    path = tools.make_chart(
        sql="SELECT customer_state, COUNT(*) AS n FROM customers "
        "GROUP BY customer_state ORDER BY n DESC",
        chart_type="bar",
        x="customer_state",
        y="n",
        title="Customers by state",
    )
    assert Path(path).exists()
    assert path.endswith(".png")


def test_make_chart_rejects_bad_column() -> None:
    with pytest.raises(ValueError):
        tools.make_chart(
            sql="SELECT customer_state FROM customers",
            chart_type="bar",
            x="customer_state",
            y="does_not_exist",
        )
