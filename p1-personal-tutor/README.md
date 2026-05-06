# P1 — Personal Learning Tutor
> A Socratic AI tutor that adapts its teaching style per topic in real time, built as the human-facing layer of a 5-project financial AI system.

**Live demo:** https://tutor-app-474302100622.us-central1.run.app

---

## What it does

P1 teaches through questions rather than lectures. It builds personalized syllabi, runs Socratic sessions, quizzes learners on material, and automatically infers preferred learning style by watching how they ask follow-up questions. When a learner scores below 70% on a topic, it flags it for spaced resurfacing. It operates in two modes: **Teach** (direct learning sessions) and **Explain** (translating structured output from downstream financial agents into plain English anchored to what the learner already knows).

---

## Why it exists

P1 is the first project in the portfolio and the natural-language interface for the entire system. When P3 (financial analyzer), P5 (comps agent), and P4 (portfolio optimizer) produce structured outputs — ratio flags, EV/EBITDA tables, weight vectors — P1 receives them and explains them in the learner's vocabulary, at their level, using their preferred style. Without P1, the financial agents have no human-facing layer. It also establishes the LangChain LCEL + Pydantic + Cloud Run patterns that every other project reuses.

---

## System flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 1: App Startup                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
[streamlit run app.py]
     │
     ▼
[load_dotenv()]  ───► READ  .env (OPENAI_API_KEY)
     │
     ▼
[@st.cache_resource get_llm()]
     └─► ChatOpenAI(model="gpt-4o", temperature=0.7)
     │
     ▼
[@st.cache_resource get_profile_store()]
     └─► [ProfileStore.__init__()]
              └─► [_init_table()]  ───► WRITE  SQLite data/tutor.db
                       ├─► ? user_profile table missing
                       │        └─► CREATE TABLE user_profile (session_id PK, ...)
                       └─► ? old CHECK(id=1) schema detected
                                └─► RENAME → recreate → INSERT 'legacy' row → DROP old
     │
     ▼
[@st.cache_resource get_score_tracker()]
     └─► [ScoreTracker.__init__()]  ───► WRITE  SQLite data/tutor.db
              └─► CREATE TABLE IF NOT EXISTS quiz_results + ALTER TABLE (session_id)
     │
     ▼
? "session_id" not in st.session_state
     └─► YES: st.session_state.session_id = str(uuid.uuid4())
     │
     ▼
? "memory" not in st.session_state
     └─► YES: [load_memory(llm, session_id)]
                   │
                   ▼
              ? memory/<uuid>/session_memory.json exists
                   ├─► YES: json.load() → SessionMemory.from_dict()
                   └─► NO:  SessionMemory(llm, max_token_limit=2000)
     │
     ▼
? "page" not in st.session_state
     └─► [profile_store.load(session_id)]  ───► READ  SQLite WHERE session_id = ?
              ├─► row found:  page = "chat"
              └─► None:       page = "profile_setup"
     │
     ▼
[Render sidebar + route to page]


┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 2: Profile Setup (first-time user)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
[render_profile_setup(editing=False)]
     │
     ▼
[profile_store.load(session_id)]  ───► READ  SQLite
     │
     ▼
[st.form("profile_form")]
     ├─► selectbox: learning_style  [visual|auditory|reading|kinesthetic]
     ├─► selectbox: preferred_pace  [fast|medium|slow]
     └─► selectbox: explanation_style  [analogies|step_by_step|examples_first|theory_first]
     │
     ▼
? submitted
     └─► [UserProfile(learning_style, preferred_pace, explanation_style, ...)]
              └─► Pydantic validation
     │
     ▼
[profile_store.save(profile, session_id)]  ───► WRITE  SQLite
     └─► INSERT ... ON CONFLICT(session_id) DO UPDATE SET ...
     │
     ▼
[st.session_state.page = "chat"] → st.rerun()


┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 3: User sends a chat message                                          │
└─────────────────────────────────────────────────────────────────────────────┘
[st.chat_input("Ask me to teach you something…")]
     │
     ▼
[_get_system_prompt()]
     │
     ├─► [profile_store.load(session_id)]  ───► READ  SQLite
     │        │
     │        ▼
     │   ? profile is None
     │        ├─► YES: TUTOR_SYSTEM_PROMPT with fallback learner_profile text
     │        └─► NO:  [build_system_prompt(profile, topic)]
     │                      │
     │                      ├─► [_resolve_styles(profile, topic)]
     │                      │        └─► ? topic_styles[topic] exists
     │                      │                 ├─► YES: use per-topic overrides (learning_style, pace, explanation)
     │                      │                 └─► NO:  use global profile defaults
     │                      │
     │                      └─► [_render_profile_block(profile, topic)]
     │                               └─► Returns: multi-line string with labels + confidence note
     │                      │
     │                      └─► TUTOR_SYSTEM_PROMPT.replace("{learner_profile}", block)
     │                               └─► Returns: str (complete system prompt)
     │
     ▼
[memory.to_langchain_messages()]
     └─► Returns: [SystemMessage(summary)] + [HumanMessage, AIMessage, ...]
     │
     ▼
[llm.invoke([SystemMessage(prompt)] + history + [HumanMessage(user_input)])]
     └─►  ═══► OpenAI gpt-4o  (~1K–4K tokens)
     │         └─► Returns: AIMessage
     │
     ▼
[memory.save_context(user_input, response.content)]
     ├─► Append HumanMessage + AIMessage to buffer
     └─► ? _estimate_tokens() > 2000
              └─► [_summarize_oldest()]
                       ├─► Slice oldest half of messages
                       └─► [llm.invoke([HumanMessage("Summarize...")])]  ═══► OpenAI gpt-4o
                                └─► self.summary = result.content  (cumulative)
     │
     ▼
[save_memory(memory, session_id)]  ───► WRITE  memory/<uuid>/session_memory.json
     │
     ▼
[st.session_state.turn_count += 1]
     │
     ▼
[_maybe_run_inference()]  ← SUB-FLOW A


┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 3A: Style inference (every 3 turns, topic set, ≥4 messages)           │
└─────────────────────────────────────────────────────────────────────────────┘
[_maybe_run_inference()]
     │
     ▼
? topic set  AND  turn_count % 3 == 0  AND  len(messages) >= 4
     └─► YES: [infer_style(topic, messages[-8:], llm)]
                   │
                   ▼
              [build_style_inference_chain(llm)]
                   └─► ChatPromptTemplate | llm | PydanticOutputParser[StyleSignal]
                   │
                   ▼
              [chain.invoke({topic, conversation, format_instructions})]
                   └─►  ═══► OpenAI gpt-4o  (~500–1K tokens)
                   │         └─► Returns: StyleSignal
                   │                  (inferred_learning_style | None,
                   │                   inferred_pace | None,
                   │                   inferred_explanation_style | None,
                   │                   reasoning: str)
                   │
                   ▼
              [profile_store.update_topic_style(topic, signal, session_id)]
                   ├─► [profile_store.load(session_id)]  ───► READ  SQLite
                   ├─► Merge non-None signal fields into TopicStyle
                   ├─► sample_count += 1
                   ├─► confidence = min(sample_count / 5, 1.0)
                   └─► [profile_store.save(profile, session_id)]  ───► WRITE  SQLite
                   │
                   ▼
              st.session_state.last_inference = signal.reasoning  (sidebar display)


┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 4: Score a quiz (sidebar button)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
[st.button("Score & Save")]
     │
     ▼
[score_quiz(topic, memory.messages, llm)]
     │
     ▼
[build_quiz_scoring_chain(llm)]
     └─► ChatPromptTemplate | llm | OutputFixingParser[QuizResult]
              └─► OutputFixingParser wraps PydanticOutputParser:
                  if primary parse fails → one re-prompt to LLM to correct JSON
     │
     ▼
[chain.invoke({topic, today, conversation, format_instructions})]
     └─►  ═══► OpenAI gpt-4o  (~1K–3K tokens)
     │         └─► Returns: QuizResult(topic, score 0-100, date, question_count, weak_areas[])
     │
     ▼
[score_tracker.save(result, session_id)]  ───► WRITE  SQLite quiz_results
     │
     ▼
? result.score < 70
     ├─► YES: [profile_store.add_weak_topic(topic, session_id)]  ───► READ+WRITE  SQLite
     └─► NO:  [profile_store.add_strong_topic(topic, session_id)]  ───► READ+WRITE  SQLite


┌─────────────────────────────────────────────────────────────────────────────┐
│  FLOW 5: New Chat                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
[st.button("＋ New Chat")]
     │
     ▼
[archive_and_reset(memory, session_id)]
     ├─► ? memory.messages is empty → return (nothing to archive)
     ├─► conversations_dir = memory/<uuid>/conversations/
     ├─► WRITE  memory/<uuid>/conversations/<timestamp>.json  (archive)
     └─► WRITE  memory/<uuid>/session_memory.json  ← cleared to {summary:"", messages:[]}
     │
     ▼
[load_memory(llm, session_id)]  ───► READ  memory/<uuid>/session_memory.json
     └─► Returns: fresh SessionMemory
     │
     ▼
[Reset session_state: display_messages=[], turn_count=0, last_inference=""]


┌─────────────────────────────────────────────────────────────────────────────┐
│  COMPONENT MAP                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
app.py
  ├── chains/quiz_chain.py          build_quiz_scoring_chain, score_quiz
  ├── chains/style_inference_chain.py  build_style_inference_chain, infer_style
  ├── config/adaptive_prompt.py     build_system_prompt, _resolve_styles, _render_profile_block
  ├── config/prompts.py             TUTOR_SYSTEM_PROMPT (constant)
  ├── db/profile_store.py           ProfileStore (save, load, add_weak/strong_topic, update_topic_style)
  ├── db/score_tracker.py           ScoreTracker (save, load_recent, load_by_topic)
  ├── memory/memory_manager.py      SessionMemory, load_memory, save_memory,
  │                                 archive_and_reset, list_conversations, load_conversation
  └── models/
        ├── user_profile.py         UserProfile  (learning_style, pace, explanation, weak/strong, topic_styles)
        ├── style_models.py         TopicStyle, StyleSignal
        └── quiz_models.py          QuizResult
```

---

## Architecture

**State management:** Three independent stores, all scoped to a per-tab `session_id` UUID generated in `st.session_state`:
- SQLite `user_profile` row — learner preferences and per-topic inferences
- SQLite `quiz_results` rows — scored quiz history
- JSON `memory/<uuid>/session_memory.json` — active conversation (summary + recent buffer)

**Adaptive prompt resolution:** Every chat turn resolves the effective style for the current topic: topic-specific overrides (if confidence > 0) take precedence over the global profile defaults. The LLM is told the confidence level so it weights established vs provisional preferences appropriately.

**Memory compression:** `SessionMemory` is a summary-buffer hybrid. Recent messages stay verbatim; once the rough token estimate exceeds 2000, the oldest half is compressed into a cumulative `summary` string via an LLM call. This prevents unbounded context growth while keeping recent turns precise.

**Why SQLite not Postgres:** SQLite runs in-process, needs no managed infra, and works in Cloud Run with an ephemeral filesystem. Quiz scores and profiles are low-write, low-read — Postgres adds nothing at this scale. Postgres is the natural upgrade path if this goes multi-tenant.

**Why summary-buffer not plain buffer:** Plain buffer grows unbounded and will eventually overflow the context window. Pure summarization loses recent detail. Summary-buffer keeps both: a compressed history for background and verbatim recent turns for precision.

---

## Tech stack

| Tool | Why this tool |
|------|--------------|
| `Streamlit` | Fastest path to a working UI with no JS; `st.cache_resource` handles singleton LLM/DB objects cleanly |
| `LangChain LCEL` | Composable `prompt \| llm \| parser` chains; `OutputFixingParser` adds one free retry on malformed JSON |
| `OpenAI gpt-4o` | Best reasoning for Socratic teaching, quiz scoring, and style inference — quality matters more than cost here |
| `Pydantic v2` | Strict type enforcement on all LLM outputs; `PydanticOutputParser` guarantees structured results |
| `SQLite` | Zero-config, in-process persistence; no managed infra; upgrade path to Postgres is one connection string change |
| `GCP Cloud Run` | Scales to zero (no idle cost), managed HTTPS, rollback via Artifact Registry |
| `GCP Secret Manager` | `OPENAI_API_KEY` injected at runtime via `--set-secrets`; never in the image or env files |

---

## Key decisions

### Why session isolation via UUID in `st.session_state`?
**Decision:** Generate `str(uuid.uuid4())` once per browser tab; scope all SQLite queries and JSON file paths to that UUID.
**Alternatives considered:** Server-side session tokens (requires auth layer), Streamlit's built-in user identity (not available on community Streamlit), single-user assumption (breaks in Cloud Run where multiple requests hit the same container).
**Why this choice:** `st.session_state` is per-tab and persists across Streamlit re-runs — it's the correct isolation boundary with zero infrastructure overhead.

### Why SQLite rename-recreate for the `user_profile` migration?
**Decision:** Detect `CHECK (id = 1)` in `sqlite_master`, rename the old table, recreate with `session_id TEXT PRIMARY KEY`, copy the old row under key `'legacy'`, drop the backup.
**Alternatives considered:** `ALTER TABLE DROP CONSTRAINT` (not supported in SQLite), fresh DB wipe (destroys existing data).
**Why this choice:** Non-destructive, idempotent, and detectable from the DDL string — no version table needed.

### Why `OutputFixingParser` on the quiz chain?
**Decision:** Wrap `PydanticOutputParser[QuizResult]` with `OutputFixingParser` which re-prompts the LLM once if the primary parse fails.
**Alternatives considered:** Retry logic in application code, `with_structured_output()` (less portable across LangChain versions).
**Why this choice:** One automatic repair attempt handles the common "LLM added prose around the JSON" failure mode without any custom retry code.

---

## How to run locally

```bash
git clone https://github.com/caiyawulf2002/ai-projects.git
cd ai-projects/p1-personal-tutor

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Set your OpenAI key
echo OPENAI_API_KEY=sk-... > .env

streamlit run app.py
```

App opens at `http://localhost:8501`. SQLite (`data/tutor.db`) and session JSON files (`memory/<uuid>/`) are created automatically on first run.

**Environment variables**

| Variable | Where to get it | Required |
|---|---|---|
| `OPENAI_API_KEY` | platform.openai.com | Yes |

---

## How to deploy

```bash
gcloud run deploy tutor-app \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest \
  --memory 512Mi
```

`--source .` builds via Cloud Build using the project `Dockerfile`. `OPENAI_API_KEY` must already exist in Secret Manager. Live URL: https://tutor-app-474302100622.us-central1.run.app

---

## Project status

| Component | Status | Notes |
|---|---|---|
| Streamlit UI + chat | 🟢 Complete | Deployed on Cloud Run |
| Learner profile setup | 🟢 Complete | SQLite, per-session |
| Conversation memory | 🟢 Complete | Summary-buffer hybrid, per-session JSON |
| Quiz scoring chain | 🟢 Complete | GPT-4o + OutputFixingParser |
| Style inference chain | 🟢 Complete | Fires every 3 turns |
| Adaptive system prompt | 🟢 Complete | Topic overrides + confidence labels |
| Session isolation | 🟢 Complete | UUID-scoped SQLite + JSON |
| LangSmith tracing | 🔴 Not started | Add `LANGCHAIN_API_KEY` + `LANGCHAIN_PROJECT` env vars |
| Explain mode (agent output) | 🔴 Not started | Receives structured output from P3/P4/P5 |

---

## Part of a larger system

```
P1 (tutor / NL interface)
  ▲
  │  structured output translated into plain English
  │
P3 (financial statements analyzer) → ratio flags, anomalies
P5 (comps agent)                  → peer EV/EBITDA tables
P4 (portfolio optimizer)          → weight vectors, risk contributions
```

**This project depends on:** nothing (first in the chain)
**Other projects depend on this for:** human-facing explanation of all structured financial output; the LangChain LCEL + Cloud Run deployment pattern used by P2–P5
