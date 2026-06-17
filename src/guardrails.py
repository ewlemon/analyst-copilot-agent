"""Safety layer: keep the agent's database access strictly read-only.

Two independent defenses (defense in depth):

1. ``validate_sql`` rejects anything that isn't a single ``SELECT`` / ``WITH``
   query *before* it runs, with a clear reason. This is the layer that teaches
   the model what it may do and gives a friendly error when it strays.
2. ``readonly_connection`` opens SQLite in read-only mode, so even if a write
   slipped past the validator the database itself would refuse it.

This module is the heart of the "human stays in control of the AI" story: the
agent can read and reason over data, but it can never modify it.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "analytics.db"

# Statement keywords that must never appear. These are matched as whole tokens,
# so a column named ``update_date`` or the scalar function ``replace(...)`` is
# unaffected; only the standalone keywords are blocked. ``replace`` and other
# common scalar-function names are deliberately *not* here; the "must start with
# SELECT/WITH" rule already blocks ``REPLACE INTO`` and friends.
_FORBIDDEN = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "attach", "detach", "pragma", "vacuum", "reindex", "grant", "revoke",
}

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"--[^\n]*")
_WORD = re.compile(r"[a-zA-Z_]+")


class UnsafeQueryError(ValueError):
    """Raised when a query is not a safe, single, read-only statement."""


def _strip_comments(sql: str) -> str:
    """Remove ``/* */`` and ``--`` comments so they can't hide keywords."""
    return _LINE_COMMENT.sub(" ", _BLOCK_COMMENT.sub(" ", sql))


def validate_sql(sql: str) -> str:
    """Return an executable, read-only query or raise ``UnsafeQueryError``.

    Rules:
    - non-empty
    - a single statement (no stray semicolons separating statements)
    - begins with ``SELECT`` or ``WITH`` (CTEs are allowed)
    - contains none of the forbidden write/DDL keywords
    """
    if not sql or not sql.strip():
        raise UnsafeQueryError("Query is empty.")

    cleaned = _strip_comments(sql).strip()
    # Allow exactly one optional trailing semicolon.
    body = cleaned.rstrip(";").strip()
    if ";" in body:
        raise UnsafeQueryError(
            "Only one statement is allowed; remove the extra ';'."
        )

    lowered = body.lower()
    first_word = lowered.split(None, 1)[0] if lowered.split() else ""
    if first_word not in ("select", "with"):
        raise UnsafeQueryError(
            "Only read-only queries are allowed: a query must start with "
            "SELECT (or WITH ... SELECT)."
        )

    tokens = set(_WORD.findall(lowered))
    forbidden = sorted(tokens & _FORBIDDEN)
    if forbidden:
        raise UnsafeQueryError(
            f"Query contains forbidden keyword(s): {', '.join(forbidden)}. "
            "The agent may only read data."
        )

    return body


def readonly_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the analytics database read-only (writes raise at the DB level)."""
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. Build it first with: "
            "python data/build_db.py"
        )
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
