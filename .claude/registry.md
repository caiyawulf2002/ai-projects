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

**Status:** 🟢 LIVE on GCP Cloud Run
**Ships:** Week 4 ✅
**Branch:** `main` (commit 163b271)
**Deploy target:** GCP Cloud Run ✅

```
Local:   runnable — streamlit run p1-personal-tutor/app.py (set OPENAI_API_KEY)
Docker:  Dockerfile present, image built and pushed to Artifact Registry
GCP:     🟢 LIVE — https://tutor-app-474302100622.us-central1.run.app
GitHub:  README updated with live URL and architecture
```

**What's built:**

| Component | File | Status |
|---|---|---|
| Streamlit chat app + page router | `app.py` | ✅ |
| Session memory (summary-buffer hybrid) | `memory/memory_manager.py` | ✅ |
| Tutor system prompt (VARK intake, syllabus, Socratic pedagogy) | `config/prompts.py` | ✅ |
| QuizResult Pydantic model | `models/quiz_models.py` | ✅ |
| UserProfile Pydantic model (global defaults) | `models/user_profile.py` | ✅ |
| TopicStyle + StyleSignal models (per-topic inference) | `models/style_models.py` | ✅ |
| ScoreTracker — SQLite quiz results | `db/score_tracker.py` | ✅ |
| ProfileStore — SQLite profile + topic_styles (with migration) | `db/profile_store.py` | ✅ |
| Quiz scoring chain (PydanticOutputParser + OutputFixingParser) | `chains/quiz_chain.py` | ✅ |
| Style inference chain (runs every 3 turns, updates per-topic style) | `chains/style_inference_chain.py` | ✅ |
| Adaptive prompt builder (global + per-topic style resolution) | `config/adaptive_prompt.py` | ✅ |
| GCP Secret Manager for OPENAI_API_KEY | stored as OPENAI_API_KEY in Secret Manager, linked to Cloud Run | ✅ |
| Cloud Run deployment | live at https://tutor-app-474302100622.us-central1.run.app | ✅ |
| Prompt engineering experiments | `experiments/` | ✅ |
| 4-pattern prompt comparison | `experiments/prompt_comparison.py` | ✅ |
| 5-topic teaching quality audit | `experiments/tutor_topic_test.py` | ✅ |
| Prompt engineering write-up | `PROMPT_ENGINEERING_WRITEUP.md` | ✅ |
| LangSmith tracing | not wired yet | 🔴 |

**What's broken / blocked:**
- Session isolation bug: SQLite DB at /app/data/ shared across all users. Tracked as GitHub issue. Fix: scope queries to st.session_state.session_id UUID.
- LangSmith tracing not wired (LANGCHAIN_TRACING_V2 / LANGCHAIN_API_KEY not set)

**Last session notes:**
- 2026-05-05: Deployed to GCP Cloud Run via gcloud run deploy --source. IAM grants required for compute and cloudbuild service accounts. OPENAI_API_KEY stored in Secret Manager. Session isolation bug identified — all users share same SQLite DB.
- 2026-05-12: prompt engineering session — 4-pattern comparison on gross margin,
  5-topic audit found two bugs in `<explain_mode>`: (1) numbered steps leaking as
  output headers, (2) passive "want to see?" offer substituting for retrieval question.
  Both fixed in config/prompts.py (both prompt variants). Cloud Run + Secret Manager
  confirmed deployed.
- 2026-04-30: full feature layer built and committed on feature/pydantic-output-parsers
- OutputFixingParser lives in langchain_classic (not langchain) in v1.x stack
- topic_styles stored as JSON TEXT in user_profile table; ALTER TABLE migration
  handles existing databases on first boot

**Next steps:**
1. Fix session isolation: scope SQLite queries to st.session_state.session_id
2. Wire LangSmith tracing
3. Always use --set-secrets=OPENAI_API_KEY=OPENAI_API_KEY:latest in deploy command to prevent secret binding loss on new revisions

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

## personal-os — Persistent learning layer

**Status:** 🟡 IN PROGRESS
**Entry point:** `python personal-os/cli/app.py`
**DB:** `personal-os/data/tutor.db` (gitignored via root `*.db` rule)
**Session reports:** `personal-os/session_reports/`

```
Local:  runnable once deps installed (pip install -r personal-os/requirements.txt)
GCP:    not deployed — fully local by design
GitHub: no README yet (doc agent will generate)
```

**Components:**

| Component | File | Status |
|-----------|------|--------|
| SQLite helpers + report writer | `core/db.py` | ✅ Written |
| Tutor tools (explain/scaffold/hint/check/log_gap) | `agents/tutor/tools.py` | ✅ Written |
| Tutor LCEL chains + VARK intake | `agents/tutor/chains.py` | ✅ Written |
| Tutor AgentExecutor | `agents/tutor/agent.py` | ✅ Written |
| Tester tools (scenarios/run/counterfactual/report) | `agents/tester/tools.py` | ✅ Written |
| Tester AgentExecutor | `agents/tester/agent.py` | ✅ Written |
| Textual terminal UI | `cli/app.py` | ✅ Written |
| Session reports index | `session_reports/INDEX.md` | auto-generated at first session close |
| Google Calendar MCP integration | `cli/app.py` line with `# SWAP:` | 🔴 Not yet |

**What's blocked:**
- Deps not installed yet — run `pip install -r personal-os/requirements.txt`
- Google Calendar MCP not wired (stub event used until then)
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGCHAIN_API_KEY` must be set

**Last session notes:**
- 2026-04-28: full personal-os scaffold written in one session
- session_initializer.py was already at .claude/scripts/ — no move needed
- sys.path insert pattern used to import from .claude/scripts/

**Next steps:**
1. `pip install -r personal-os/requirements.txt`
2. Set env vars and run smoke test: `python personal-os/cli/app.py`
3. Complete VARK intake on first run to populate learner profile
4. Wire Google Calendar MCP when ready (see `# SWAP:` comment in cli/app.py)

---

## Session log

| Date | Projects touched | What was done | Who |
|------|-----------------|---------------|-----|
| 2026-04-28 | personal-os | Full personal-os scaffold: db, tutor agent, tester agent, Textual CLI | Claude |
| 2026-05-05 | P1 | GCP Cloud Run deployment: Artifact Registry, Cloud Build, Secret Manager, IAM grants, live URL verified. Session isolation bug identified. | Caiya + Claude |
| —    | —               | Repo initialized | Caiya |
