# P1 — Personal Learning Tutor

P1 is a Socratic AI tutor that adapts its teaching style to each learner in real time. It maintains a persistent learner profile (learning style, pace, explanation preference), automatically infers per-topic preferences by analysing how you ask follow-up questions, scores quiz conversations using GPT-4o, and persists full conversation history across sessions. It is also the natural-language interface for the broader multi-agent financial AI system — when downstream agents (financial analyser, portfolio optimiser, LSTM model) produce structured output, P1 translates it into plain English anchored to what the learner already knows.

**Live demo:** [https://tutor-app-474302100622.us-central1.run.app](https://tutor-app-474302100622.us-central1.run.app)

---

## Architecture

```
Browser
  │
  ▼
Streamlit (app.py)
  ├── ProfileStore  ──► SQLite (data/tutor.db)   user_profile table
  ├── ScoreTracker  ──► SQLite (data/tutor.db)   quiz_results table
  ├── SessionMemory ──► JSON  (memory/)           session_memory.json + conversations/
  │
  ├── chat turn
  │     ├── build_system_prompt()  ← adaptive_prompt.py  resolves topic overrides
  │     └── ChatOpenAI (gpt-4o)   ← OpenAI API
  │
  ├── every 3 turns (topic set)
  │     └── infer_style()          ← style_inference_chain.py  → StyleSignal → ProfileStore
  │
  └── on demand (sidebar)
        └── score_quiz()           ← quiz_chain.py  → QuizResult → ScoreTracker + ProfileStore
```

| Component | Purpose |
|---|---|
| `app.py` | Streamlit UI, session state, page routing |
| `chains/quiz_chain.py` | LangChain LCEL chain: conversation → GPT-4o → `QuizResult` |
| `chains/style_inference_chain.py` | LangChain LCEL chain: conversation → GPT-4o → `StyleSignal` |
| `config/adaptive_prompt.py` | Resolves per-topic style overrides; injects into system prompt |
| `config/prompts.py` | `TUTOR_SYSTEM_PROMPT` — Socratic pedagogy instructions |
| `db/profile_store.py` | SQLite single-row upsert for `UserProfile` |
| `db/score_tracker.py` | SQLite append-only log for `QuizResult` |
| `memory/memory_manager.py` | Summary-buffer hybrid memory; JSON persistence |
| `models/` | Pydantic v2 models: `UserProfile`, `TopicStyle`, `StyleSignal`, `QuizResult` |

**Tech stack:**

| Tool | Why |
|---|---|
| Streamlit | Rapid UI with no JS; supports `st.cache_resource` for singleton LLM/DB objects |
| LangChain LCEL | Composable chains with `PydanticOutputParser` + `OutputFixingParser` for reliable structured output |
| OpenAI gpt-4o | Best reasoning quality for Socratic teaching and quiz scoring |
| SQLite | Zero-config persistence; acceptable for single-user local/Cloud Run deployment |
| Pydantic v2 | Strict type enforcement on all LLM outputs and stored data |
| GCP Cloud Run | Serverless container — scales to zero when idle, no VM to manage |
| GCP Secret Manager | `OPENAI_API_KEY` injected at runtime; never stored in the container image |

---

## Run locally

```bash
git clone https://github.com/caiyawulf2002/ai_projects.git
cd ai_projects/p1-personal-tutor

pip install -r requirements.txt

# Create a .env file with your OpenAI key
echo "OPENAI_API_KEY=sk-..." > .env

streamlit run app.py
```

The app opens at `http://localhost:8501`.  SQLite and JSON files are created automatically under `data/` and `memory/` on first run.

---

## Deploy to Cloud Run

```bash
gcloud run deploy tutor-app \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest \
  --memory 512Mi
```

The `--source .` flag builds the container via Cloud Build using the project `Dockerfile`.  The `OPENAI_API_KEY` secret must already exist in Secret Manager for the target project.

---

## Known issues

**Session isolation — conversation history is shared across all users.**
Conversation history is stored in flat JSON files under `memory/` at the container filesystem level. All browser sessions read from and write to the same files. In a multi-user or redeployed environment this means sessions collide.

Fix: add a `session_id` column to the SQLite tables, generate a UUID per `st.session_state`, and scope all queries to that ID. Tracked in GitHub Issues.
