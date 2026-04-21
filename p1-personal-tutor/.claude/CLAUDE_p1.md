# P1 — Personal Learning Tutor
*Project-specific context. Root .claude/CLAUDE.md applies first — read that first.*

---

## What this project is

A Streamlit chatbot tutor powered by LangChain + GPT-4o. Given a topic, it:
1. Generates a structured 5-module syllabus
2. Teaches interactively via Socratic Q&A
3. Tracks quiz scores in SQLite (topic, score, date)
4. Flags topics where you're scoring under 70%
5. Remembers prior sessions via ConversationSummaryBufferMemory

Deployed on GCP Cloud Run via Docker + Artifact Registry.

---

## Ships: Week 4

Week 1: Basic chat chain running locally, Streamlit skeleton
Week 2: Syllabus generation + memory
Week 3: Quiz chain + score tracking + SQLite + deployed to Cloud Run (test)
Week 4: Polish, Secret Manager for keys, monitoring, README, LinkedIn post

---

## Stack (P1-specific)

- LangChain LCEL (chains, runnables, pipe operator)
- ConversationSummaryBufferMemory
- Pydantic output parsers (structured quiz scores)
- Streamlit (UI)
- SQLite (score persistence)
- Docker → GCP Artifact Registry → Cloud Run
- GCP Secret Manager (OPENAI_API_KEY)
- LangSmith (tracing — on from day one)

---

## Key file locations

```
p1-personal-tutor/
├── src/
│   ├── chains/
│   │   ├── syllabus_chain.py     # topic → 5-module curriculum
│   │   ├── tutor_chain.py        # main conversational chain
│   │   └── quiz_chain.py         # Socratic Q&A + scoring
│   ├── memory/
│   │   └── session_memory.py     # ConversationSummaryBufferMemory wrapper
│   ├── models/
│   │   └── quiz_models.py        # Pydantic: QuizScore, TopicProgress
│   └── db/
│       └── score_tracker.py      # SQLite read/write for quiz scores
├── app.py                        # Streamlit entry point
├── Dockerfile
└── requirements.txt
```

---

## Design decisions (don't re-debate these)

- **SQLite not Postgres** for Week 1–4: simplicity, no infra cost, works in
  Cloud Run with volume mount. Can migrate later.
- **GPT-4o not Claude** for the tutor: using the Anthropic API would work,
  but GPT-4o via OpenAI is the canonical LangChain path and better documented.
- **Streamlit not FastAPI** for UI: fastest to ship, sufficient for portfolio demo.
  P3 and P4 may use FastAPI for APIs.

---

## LangSmith setup (do this first in Week 1)

```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "p1-personal-tutor"
os.environ["LANGCHAIN_API_KEY"] = "ls-..."  # from Secret Manager in prod
```

Every chain run should appear in LangSmith. If it doesn't, something is wrong.

---

## Current status (update each session)

See root `registry.md` → P1 block.
