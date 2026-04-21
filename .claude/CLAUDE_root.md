# AI Projects — Caiya Wulf
*Claude Code reads this file at the start of every session.*

---

## Who I am + why this exists

Industrial engineer + data scientist. Currently finishing a rotational consulting
program at FORTNA (supply chain / automation). Background: Walmart process
engineering, deep learning research, GenAI tools built at FORTNA.

Long-term goal: C-suite / founder. Near-term goal: land an AI Product Manager or
Solutions Engineer role at an early-stage AI company before rotation ends.

These 5 projects are my proof of work. They are not toy demos. They are a
coherent system — each one feeds the next. They ship on GCP, use real data,
and are deployed with production patterns (Docker, Cloud Run, Vertex AI,
monitoring). By end of Month 4 every project is live, documented, and
demonstrable in an interview.

---

## The 5 projects — what they are and how they connect

| ID  | Name                        | Ships   | Depends on         | Status       |
|-----|-----------------------------|---------|--------------------|--------------|
| P1  | Personal learning tutor     | Week 4  | —                  | 🔴 NOT STARTED |
| P2  | Domain intelligence agent   | Week 8  | P1 patterns        | 🔴 NOT STARTED |
| P3  | Financial statements analyzer | Week 12 | shared schema     | 🔴 NOT STARTED |
| P5  | Comps analysis agent        | Week 12 | P3 ratio engine    | 🔴 NOT STARTED |
| P4  | Portfolio optimizer         | Week 16 | P3 + P5 outputs    | 🔴 NOT STARTED |

**Data flow:** P3 extracts financial ratios → P5 runs comps across peers →
P4 ingests both as signals → P4 optimizer weights assets using P3 quality flags.

The shared financial ratio schema lives in `.claude/skills/finance-schema.md`.
All agents that touch financial data MUST use the Pydantic models defined there.
Do not invent new field names — check the schema first.

---

## Tech stack

**Languages:** Python 3.11 (primary), SQL (SQLite local, BigQuery later)
**AI/ML:** LangChain LCEL, LangGraph, LangSmith, OpenAI GPT-4o, HuggingFace
**Cloud:** GCP (Cloud Run, Cloud Functions, Cloud Scheduler, Vertex AI,
           GCS, Artifact Registry, Secret Manager, Cloud Monitoring)
**ML:** XGBoost, PyTorch/Keras (LSTM), scipy/cvxpy (optimization)
**Data:** SEC EDGAR, yfinance, Tavily, NewsAPI
**Infra:** Docker, FastAPI, Streamlit, Pydantic v2, SQLite → Postgres later

**GCP project ID:** [UPDATE WHEN CREATED]
**GCP region:** us-central1 (default — update if changed)
All deployed resource URLs and bucket names live in `.claude/skills/gcp-context.md`.

---

## Coordination rules (read before every task)

1. **Check the registry first.** Before writing any code, read `registry.md`.
   Know what is built, what is broken, and what is in progress.

2. **Update the registry after every session.** When you finish a task, update
   the relevant project's status block in `registry.md`. Be specific — not
   "P3 in progress" but "P3: ratio engine done, XGBoost not trained, GCS
   bucket created at gs://[name]."

3. **Never invent infrastructure.** If a Cloud Run URL, GCS bucket, or API key
   is needed and not in `gcp-context.md`, stop and ask. Don't hardcode guesses.

4. **Use the shared schema.** Pydantic models for financial data are in
   `finance-schema.md`. If you need a new field, add it there first, then
   use it everywhere.

5. **One source of truth per concern:**
   - Project status → `registry.md`
   - Cloud infra → `gcp-context.md`
   - Data contracts → `finance-schema.md`
   - Coordination protocol → `agent-coordination.md`

6. **Prefer explicit over clever.** These projects will be shown in interviews.
   Code should be readable. Add docstrings. Write READMEs as you go.

---

## File structure convention

```
p[N]-[project-name]/
├── .claude/CLAUDE.md       # project-specific context (overrides root where noted)
├── README.md               # architecture diagram + deploy instructions
├── Dockerfile
├── requirements.txt
├── src/
│   ├── chains/             # LangChain chains and agents
│   ├── tools/              # custom LangChain tools
│   ├── models/             # Pydantic models (import from shared schema)
│   └── utils/
├── tests/
├── notebooks/              # exploration only — nothing deployed from here
└── infra/
    └── cloudbuild.yaml     # GCP deployment config
```

---

## Session startup checklist

Every time Claude Code opens a session in this repo:
- [ ] Read this file (CLAUDE.md)
- [ ] Read registry.md — know current project states
- [ ] Read gcp-context.md if the task touches cloud infra
- [ ] Read finance-schema.md if the task touches financial data
- [ ] Confirm which project(s) this session will touch

---

## Notes for future Claude sessions

- Caiya is early in the plan. Don't assume things are built that aren't in registry.
- She is learning GCP in parallel with building — explain infra decisions briefly.
- LangSmith tracing should be on for every agent from day one. Don't skip it.
- Every deployed project needs a GitHub README with architecture diagram.
  Remind her if one is missing when shipping.
