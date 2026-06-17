# 📊 Analyst Copilot Agent

Ask a business question in plain English and this agent works out the SQL for
you. It checks the database schema, writes a read-only query, runs it, charts
the result, and explains what it found. It also shows you every query it ran, so
nothing is a black box.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Claude API](https://img.shields.io/badge/Claude-API%20(tool%20use)-orange)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)

**▶️ [Try the live demo](https://analyst-copilot-agent-5gpanuic33nqb66wxlvcrd.streamlit.app/)**

---

## Why I built it

I'm a business analytics grad student and I wanted to actually build with AI
agents instead of just reading about them. A lot of everyday analysis is the
same handful of question types asked over and over, so I made something that
handles the first pass (writing the query, pulling the numbers, sketching a
chart) while keeping the whole thing transparent. Every answer comes with the
exact SQL behind it and a short "caveats" note, so I can always check the logic
before trusting a number.

---

## How it works

```
  Your question
       │
       ▼
  ┌──────────────────────── agent loop (src/agent.py) ────────────────────────┐
  │  Claude decides which tool to call ──► your code runs it ──► result back   │
  │      │  get_schema   →  what tables/columns exist                          │
  │      │  run_sql      →  a single READ-ONLY SELECT (validated)              │
  │      │  make_chart   →  render a PNG from a query                          │
  │  …loop until Claude writes a final answer                                  │
  └────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
  Plain-English answer  +  chart(s)  +  the exact SQL it ran  +  caveats
```

It only ever reads data. Two separate guardrails in
[`src/guardrails.py`](src/guardrails.py) enforce that: every query has to be a
single `SELECT`/`WITH` with no write keywords, and the database is opened in
read-only mode on top of that.

---

## Quick start

```bash
# 1. Install dependencies (a virtual environment is recommended)
pip install -r requirements.txt

# 2. Build the local database (synthetic e-commerce data, no download needed)
python data/build_db.py

# 3. Add your Anthropic API key
cp .env.example .env          # then paste your key into .env
#   Windows PowerShell: Copy-Item .env.example .env

# 4a. Ask a question from the command line
python src/agent.py "Which states generate the most revenue? Top 5."

# 4b. …or run the web app
streamlit run src/app.py
```

Grab an API key at <https://console.anthropic.com>. It runs on the cheap
**Haiku** model by default, so a full round of testing only costs a dollar or two.

---

## Example questions

- *Which states generate the most revenue? Show the top 5.*
- *How did monthly order volume trend over time?*
- *Which product categories have the highest gross profit?*
- *What is the average review score by order status?*

There are saved runs with their charts in [`output/examples/`](output/examples/).

---

## What's in here

| Path | What's there |
|---|---|
| [`src/agent.py`](src/agent.py) | The agent loop, tool definitions, and system prompt |
| [`src/tools.py`](src/tools.py) | `get_schema`, `run_sql`, `make_chart` |
| [`src/guardrails.py`](src/guardrails.py) | Read-only SQL validation + read-only connection |
| [`src/app.py`](src/app.py) | The Streamlit web app |
| [`data/build_db.py`](data/build_db.py) | Builds the synthetic database |
| [`output/methodology.md`](output/methodology.md) | How the agent reaches its answers, and the limits |
| [`tests/`](tests/) | Guardrail + tool tests (no API key needed) |

---

## Tests

```bash
python -m pytest tests/
```

These run without an API key. They check that the guardrails reject writes and
that the tools behave against the synthetic database.

---

## Tech

Python · [Anthropic Claude API](https://docs.claude.com) (tool use) · SQLite ·
pandas · matplotlib · Streamlit

---

## A note on the data

The database is synthetic e-commerce data by default, so the repo runs with zero
external downloads. If you want something closer to the real world, you can swap
in the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(~100k orders) without changing any of the agent code. Details are in
[data/README.md](data/README.md).
