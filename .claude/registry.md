# Project Registry
*Updated by Claude Code after every session. Do not edit manually mid-session.*
*Last updated: [DATE] | Updated by: [session context]*

---

## How to use this file

Before starting any task: read all status blocks below.
After completing any task: find the relevant block and update it.
Be specific. "Done" is not a status. "Ratio engine complete, returns Dict[str, float],
tested on AAPL 10-K, XGBoost not yet trained" is a status.

---

## P1 — Personal Learning Tutor

**Status:** 🔴 NOT STARTED
**Ships:** Week 4
**Deploy target:** GCP Cloud Run

```
Local:   not running
Docker:  no image built
GCP:     not deployed
GitHub:  no README
```

**What's built:**
- nothing yet

**What's broken / blocked:**
- n/a

**Last session notes:**
- n/a

**Next steps:**
- Set up LangChain env + Streamlit skeleton
- Build basic chat chain (GPT-4o via API)
- Get running locally end-to-end

---

## P2 — Domain Intelligence Agent

**Status:** 🔴 NOT STARTED
**Ships:** Week 8
**Deploy target:** GCP Cloud Functions + Cloud Scheduler

```
Local:   not running
Docker:  no image built
GCP:     not deployed
GitHub:  no README
Vector store: not set up (target: Vertex AI Vector Search)
```

**What's built:**
- nothing yet

**What's broken / blocked:**
- depends on P1 LangChain patterns being solid first

**Last session notes:**
- n/a

**Next steps:**
- Set up LangChain AgentExecutor
- Connect Tavily search + NewsAPI as tools
- Write sector config file

---

## P3 — Financial Statements Analyzer

**Status:** 🔴 NOT STARTED
**Ships:** Week 12
**Deploy target:** GCP Cloud Run + Cloud Run Jobs

```
Local:   not running
Docker:  no image built
GCP:     not deployed
GCS:     no bucket created
XGBoost: not trained
GitHub:  no README
```

**What's built:**
- nothing yet

**What's broken / blocked:**
- finance-schema.md Pydantic models needed before any code is written

**Last session notes:**
- n/a

**Next steps:**
- Define Pydantic models in finance-schema.md first
- Set up LlamaParse for 10-K PDF extraction
- Parent-child chunking strategy

---

## P5 — Comps Analysis Agent

**Status:** 🔴 NOT STARTED
**Ships:** Week 12 (same sprint as P3)
**Deploy target:** GCP Cloud Run Jobs

```
Local:   not running
GCP:     not deployed
GCS:     shares bucket with P3 (not created yet)
GitHub:  no README
```

**What's built:**
- nothing yet

**What's broken / blocked:**
- P3 ratio engine must be complete before P5 can batch-pull peer comps
- P3 and P5 share the same GCS bucket and Pydantic schema

**Last session notes:**
- n/a

**Next steps:**
- Build peer identification chain from any ticker
- Batch EDGAR pull for 5-10 peer companies
- Use P3's ratio engine to extract same metrics across all peers

---

## P4 — Portfolio Optimizer

**Status:** 🔴 NOT STARTED
**Ships:** Week 16
**Deploy target:** GCP Vertex AI (LSTM training) + Cloud Run (Streamlit)

```
Local:   not running
Docker:  no image built
Vertex AI: no training job submitted
GCP:     not deployed
GitHub:  no README
```

**What's built:**
- nothing yet

**What's broken / blocked:**
- Depends on P3 ratio engine (quality signals as optimizer constraints)
- Depends on P5 comps output (peer universe)
- LSTM training requires Vertex AI custom training job setup

**Last session notes:**
- n/a

**Next steps:**
- Build mean-variance optimization engine (scipy + cvxpy)
- yfinance data pipeline: historical prices for any ticker list
- Efficient frontier plot with Plotly

---

## Shared infrastructure

**GCP project ID:** [UPDATE WHEN CREATED]
**GCP region:** us-central1
**Artifact Registry repo:** [UPDATE WHEN CREATED]
**GCS bucket (P3/P5 10-Ks):** [UPDATE WHEN CREATED]
**GCS bucket (P4 model artifacts):** [UPDATE WHEN CREATED]

See `.claude/skills/gcp-context.md` for full infra details.

---

## Session log

| Date | Projects touched | What was done | Who |
|------|-----------------|---------------|-----|
| —    | —               | Repo initialized | Caiya |
