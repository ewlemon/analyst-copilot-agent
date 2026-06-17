"""Tests for the read-only SQL guardrails."""

from __future__ import annotations

import pytest

from guardrails import UnsafeQueryError, validate_sql


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM orders",
        "select customer_state, count(*) from customers group by 1",
        "WITH t AS (SELECT 1 AS n) SELECT n FROM t",
        "SELECT replace(category, '_', ' ') FROM products",  # scalar fn, not stmt
        "SELECT order_date FROM orders ORDER BY order_date",  # 'order_date' != ORDER kw issue
        "SELECT * FROM orders;",  # one trailing semicolon is fine
    ],
)
def test_accepts_read_only_queries(query: str) -> None:
    assert validate_sql(query)


@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO orders VALUES (1)",
        "UPDATE orders SET status = 'x'",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "ALTER TABLE orders ADD COLUMN x INT",
        "CREATE TABLE t (a INT)",
        "PRAGMA table_info(orders)",
        "ATTACH DATABASE 'x.db' AS y",
        "SELECT 1; DROP TABLE orders",  # piggy-backed second statement
        "SELECT * FROM orders; SELECT * FROM customers",  # two SELECTs
        "",  # empty
        "   ",  # whitespace only
    ],
)
def test_rejects_unsafe_queries(query: str) -> None:
    with pytest.raises(UnsafeQueryError):
        validate_sql(query)


def test_comment_cannot_hide_a_write() -> None:
    # A block comment must not be able to smuggle in a second statement.
    with pytest.raises(UnsafeQueryError):
        validate_sql("SELECT 1 /* */ ; DROP TABLE orders")


def test_returns_query_without_trailing_semicolon() -> None:
    assert validate_sql("SELECT 1;") == "SELECT 1"
