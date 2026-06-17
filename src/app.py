"""Streamlit UI for the Analyst Copilot.

Run it with:

    streamlit run src/app.py

A text box takes a business question; the agent answers with a narrative, any
charts it produced, and an expandable panel showing the exact SQL it ran (the
analyst-in-the-loop verification surface).
"""

from __future__ import annotations

import os
from pathlib import Path

import anthropic
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agent import DEFAULT_MODEL, api_key_problem, run_analysis
from guardrails import DB_PATH, readonly_connection

load_dotenv()

st.set_page_config(page_title="Analyst Copilot", page_icon="📊", layout="centered")

# --- Cloud setup ---------------------------------------------------------
# On Streamlit Community Cloud there is no .env; the API key is provided via
# the app's "Secrets" setting. Bridge it into the environment so the Anthropic
# client (and api_key_problem) can read it. Locally this is a harmless no-op.
try:
    if not os.environ.get("ANTHROPIC_API_KEY") and "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass


@st.cache_resource
def _ensure_database() -> bool:
    """Build the synthetic database once if it isn't present (e.g. on first
    run in the cloud, where the .db file isn't committed to the repo)."""
    if not Path(DB_PATH).exists():
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))
        import build_db

        build_db.build()
    return True


_ensure_database()


@st.cache_data
def _list_tables() -> list[str]:
    """Names of all tables in the database."""
    conn = readonly_connection()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


@st.cache_data
def _load_table(table: str) -> pd.DataFrame:
    """Every row of one table, read-only, as a DataFrame."""
    conn = readonly_connection()
    try:
        return pd.read_sql_query(f"SELECT * FROM {table}", conn)
    finally:
        conn.close()

st.title("📊 Analyst Copilot")
st.caption(
    "Ask a business question in plain English. The agent writes its own "
    "read-only SQL, runs it, charts the result, and explains the finding. "
    "It shows you every query it ran, so **you** stay the analyst in the loop."
)

# --- Preflight checks, surfaced as friendly banners ----------------------
problems = []
if api_key_problem():
    problems.append(
        "**Your API key isn't set up yet.** Open `.env`, replace "
        "`sk-ant-your-key-here` with a real key from "
        "https://console.anthropic.com, then **restart the app** (the key is "
        "read at startup)."
    )
if not Path(DB_PATH).exists():
    problems.append(
        "**Database not found.** Build it first: `python data/build_db.py`."
    )
for problem in problems:
    st.warning(problem)

# --- Browse the underlying data ------------------------------------------
with st.expander("📂 Browse the data the agent queries"):
    st.caption(
        "This is **synthetic sample** e-commerce data (no real customers). "
        "Pick a table to see its columns and every row the agent can query, "
        "so you can check the agent's answers against the source yourself."
    )
    _table = st.selectbox("Table", _list_tables())
    _df = _load_table(_table)
    st.write(f"**{_table}**: {len(_df):,} rows × {_df.shape[1]} columns")
    st.caption(
        "Columns: "
        + ", ".join(
            f"{c} ({t})" for c, t in zip(_df.columns, _df.dtypes.astype(str))
        )
    )
    st.dataframe(_df, use_container_width=True, hide_index=True)

EXAMPLES = [
    "Which states generate the most revenue? Show the top 5.",
    "How did monthly order volume trend over time?",
    "Which product categories have the highest gross profit?",
    "What is the average review score by order status?",
]

with st.sidebar:
    st.header("Try an example")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True):
            st.session_state["question"] = ex
    st.divider()
    st.caption(f"Model: `{DEFAULT_MODEL}`")

question = st.text_input(
    "Your question",
    key="question",
    placeholder="e.g. Which states generate the most revenue?",
)

if st.button("Analyze", type="primary", disabled=bool(problems)) and question:
    try:
        with st.spinner("The copilot is working…"):
            result = run_analysis(question)
    except anthropic.AuthenticationError:
        st.error(
            "Authentication failed: the API key in `.env` was rejected. Check "
            "it's a valid, active key, then restart the app."
        )
        st.stop()

    st.subheader("Answer")
    st.markdown(result.answer or "_(no answer produced)_")

    for chart in result.charts:
        if Path(chart).exists():
            st.image(chart)

    if result.sql_queries:
        with st.expander(f"🔍 SQL the agent ran ({len(result.sql_queries)})"):
            for i, q in enumerate(result.sql_queries, 1):
                st.code(q, language="sql")

    with st.expander("🪜 Steps the agent took"):
        for i, step in enumerate(result.steps, 1):
            st.markdown(f"**{i}.** {step}")
