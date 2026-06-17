# Sources

Reference material for the Analyst Copilot Agent project.

---

## Cited Sources

### 1. Olist Brazilian E-Commerce Public Dataset
- **URL:** https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- **Publisher:** Olist (via Kaggle)
- **Accessed:** 2026-06-17
- **Contributed:** The real-world dataset this project's schema mirrors and can
  optionally load (~100k orders across related tables). Informed the synthetic
  generator's structure (Brazilian states, product categories, review scores).

### 2. Anthropic Claude API — Tool Use
- **URL:** https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview
- **Publisher:** Anthropic
- **Accessed:** 2026-06-17
- **Contributed:** The tool-use / function-calling pattern and the agent-loop
  structure (`tool_use` stop reason, `tool_result` messages) used in
  `src/agent.py`.

### 3. Anthropic Claude API — Messages
- **URL:** https://docs.claude.com/en/api/messages
- **Publisher:** Anthropic
- **Accessed:** 2026-06-17
- **Contributed:** The Messages API request/response shape used throughout.

---

## Additional Background (not directly cited)

| Source | Notes |
|---|---|
| Streamlit docs (https://docs.streamlit.io) | Building the web UI in `src/app.py`. |
| matplotlib docs (https://matplotlib.org/stable/) | Chart rendering in `make_chart`. |
| Python `sqlite3` docs (https://docs.python.org/3/library/sqlite3.html) | Read-only URI connection used in the guardrails. |
