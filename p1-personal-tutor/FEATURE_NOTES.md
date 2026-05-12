# P1 Feature Notes — Pydantic Output Parsers, Score Tracking & Adaptive Prompting

**Branch:** `feature/pydantic-output-parsers`
**Written:** 2026-04-30

This document is a deep technical walkthrough of every file added in this feature
branch. It covers the design decisions behind each piece, how the components
connect, and what to watch out for when extending them.

---

## Table of Contents

1. [Models](#1-models)
   - [QuizResult](#11-quizresult--modelsquiz_modelspy)
   - [UserProfile](#12-userprofile--modelsuser_profilepy)
2. [Database Layer](#2-database-layer)
   - [ScoreTracker](#21-scoretracker--dbscore_trackerpy)
   - [ProfileStore](#22-profilestore--dbprofile_storepy)
3. [Quiz Scoring Chain](#3-quiz-scoring-chain--chainsquiz_chainpy)
4. [Adaptive Prompt Builder](#4-adaptive-prompt-builder--configadaptive_promptpy)
5. [Streamlit App](#5-streamlit-app--apppy)
6. [Supporting Changes](#6-supporting-changes)
7. [Data Flow End-to-End](#7-data-flow-end-to-end)
8. [Extension Guide](#8-extension-guide)

---

## 1. Models

### 1.1 `QuizResult` — `models/quiz_models.py`

```python
class QuizResult(BaseModel):
    topic: str
    score: float = Field(ge=0, le=100)
    date: str
    question_count: int = Field(gt=0)
    weak_areas: list[str]
```

**What it is.** A Pydantic v2 `BaseModel` that represents the output of one
complete quiz session. Every quiz the tutor runs is eventually serialised into
this shape before being saved to SQLite.

**Field-by-field breakdown:**

- `topic` — Free-text label for the subject. The user provides this in the
  Streamlit sidebar before clicking "Score & Save". It's also what gets
  stored in `user_profile.weak_topics` if the score is below 70, so it's the
  key that links quiz results to the adaptive prompting layer. Keep it concise
  (e.g. "Python generators", not "Chapter 3: Advanced Python Concepts").

- `score` — A float constrained to `[0, 100]` by Pydantic's `Field(ge=0,
  le=100)`. `ge` means "greater than or equal to", `le` means "less than or
  equal to". If the LLM returns 105 or -3, Pydantic raises a
  `ValidationError` before the object is constructed — this is exactly the
  behaviour you want. The `OutputFixingParser` then catches that error and
  asks the LLM to correct itself.

- `date` — ISO 8601 string (e.g. `"2026-04-30"`). It's a `str`, not a
  `datetime`, because SQLite stores it as text and round-tripping a
  `datetime` object through JSON and SQLite requires extra serialisation
  code for no real benefit at this stage. The `score_quiz()` function injects
  `date.today().isoformat()` into the scoring prompt so the LLM always uses
  today's date rather than inventing one.

- `question_count` — `Field(gt=0)` means it must be strictly positive.
  The LLM counts how many distinct questions appeared in the conversation.
  This isn't used in the UI yet but is available for future analytics (e.g.
  "show me my score trend on Python generators over time").

- `weak_areas` — A list of strings naming the specific sub-topics the learner
  struggled with, as assessed by the LLM. These are finer-grained than
  `topic` — e.g. topic might be "Python generators" and weak_areas might be
  `["yield from", "generator expressions", "StopIteration"]`. They're stored
  in SQLite as a JSON array and surfaced in the sidebar after scoring.

**Why Pydantic v2, not a dataclass.** The `PydanticOutputParser` in LangChain
requires a Pydantic `BaseModel` — it calls `.schema()` on the class to generate
the JSON schema that gets injected into the prompt as format instructions. A
plain dataclass won't work here.

---

### 1.2 `UserProfile` — `models/user_profile.py`

```python
class UserProfile(BaseModel):
    learning_style: Literal["visual", "auditory", "reading", "kinesthetic"]
    preferred_pace: Literal["fast", "medium", "slow"]
    explanation_style: Literal["analogies", "step_by_step", "examples_first", "theory_first"]
    weak_topics: list[str] = Field(default_factory=list)
    strong_topics: list[str] = Field(default_factory=list)
```

**What it is.** A Pydantic v2 model representing the learner's preferences and
current performance state. It has two kinds of fields: static preferences set
once by the user in the profile setup form, and dynamic lists that update
automatically as quizzes are scored.

**Field-by-field breakdown:**

- `learning_style` — Uses `Literal[...]` from `typing`. Pydantic v2 enforces
  that the value must be exactly one of the four strings. The four options map
  to the VARK model (Visual, Auditory, Reading/Writing, Kinesthetic), which is
  the same framework referenced in the tutor's intake protocol. Injected into
  the system prompt with a one-line behavioural instruction (e.g. "reading —
  Dense, precise text is fine — I learn by reading carefully.").

- `preferred_pace` — Controls how quickly the tutor moves. Injected verbatim
  into the system prompt so the LLM knows to skip preamble (fast), balance
  explanation (medium), or check comprehension at every step (slow).

- `explanation_style` — The four options represent fundamentally different
  pedagogical approaches. `analogies` works well for abstract concepts.
  `step_by_step` is best for procedural skills. `examples_first` mirrors how
  most engineers actually learn. `theory_first` suits learners who need the
  mental model before touching code. The tutor system prompt already has a
  strong pedagogical framework — this field nudges the LLM's emphasis within
  that framework.

- `weak_topics` / `strong_topics` — These are the dynamic fields. They are
  never set by the user directly; they are always set by `ProfileStore`
  methods in response to quiz scores. The invariant maintained by
  `add_weak_topic` and `add_strong_topic` is that a topic cannot appear in
  both lists simultaneously — moving to strong removes from weak and vice
  versa. These lists feed directly into the `{learner_profile}` block of the
  system prompt so the tutor knows what to resurface.

**Default values.** `weak_topics` and `strong_topics` use `default_factory=list`
rather than `default=[]`. This is a Pydantic (and Python) best practice —
`default=[]` shares the same list object across all instances, which causes
subtle mutation bugs. `default_factory=list` creates a fresh list for each
instance.

---

## 2. Database Layer

Both DB modules use Python's built-in `sqlite3` — no ORM, no additional
dependency. The database file lives at `p1-personal-tutor/data/tutor.db`
and is gitignored. Both modules reference the same file path, so SQLite's
file-level locking means only one write happens at a time (fine for a
single-user local app).

### 2.1 `ScoreTracker` — `db/score_tracker.py`

**Responsibility:** Write `QuizResult` objects to SQLite; read them back.

**Table schema:**

```sql
CREATE TABLE IF NOT EXISTS quiz_results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    topic          TEXT    NOT NULL,
    score          REAL    NOT NULL,
    date           TEXT    NOT NULL,
    question_count INTEGER NOT NULL,
    weak_areas     TEXT    NOT NULL  -- JSON array
)
```

`weak_areas` is stored as a `TEXT` column containing a JSON-serialised list
(e.g. `'["closures", "yield from"]'`). SQLite doesn't have a native array
type. The alternative would be a separate `weak_area_tags` join table, but
that's premature — a JSON column is readable, queryable in a pinch (SQLite
supports `json_each()`), and trivially deserialised with `json.loads()`.

**`_get_conn()`** is a module-level private function (not a method) because
both `ScoreTracker` and — in a future refactor — any script that needs a raw
connection can call it without instantiating the class. It also ensures the
`data/` directory exists before opening the connection, which matters on
first run.

**`conn.row_factory = sqlite3.Row`** makes rows accessible by column name
(e.g. `row["topic"]`) rather than index (e.g. `row[1]`). This prevents
brittle positional access that breaks if the schema changes.

**`_row_to_model()`** is a `@staticmethod` because it doesn't touch instance
state — it's a pure `sqlite3.Row → QuizResult` conversion. Keeping it static
makes it trivial to call in list comprehensions: `[self._row_to_model(r) for r
in rows]`.

**Available read methods:**

| Method | Use case |
|---|---|
| `load_all()` | Export / analytics |
| `load_by_topic(topic)` | "How am I trending on Python generators?" |
| `load_recent(n=10)` | Sidebar "Recent Scores" panel (default 5) |

---

### 2.2 `ProfileStore` — `db/profile_store.py`

**Responsibility:** Store exactly one `UserProfile` row; update it safely.

**Table schema:**

```sql
CREATE TABLE IF NOT EXISTS user_profile (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    learning_style    TEXT NOT NULL,
    preferred_pace    TEXT NOT NULL,
    explanation_style TEXT NOT NULL,
    weak_topics       TEXT NOT NULL,
    strong_topics     TEXT NOT NULL
)
```

The `CHECK (id = 1)` constraint enforces that only one row can ever exist.
Any attempt to insert a second row fails at the database level, not just the
application level. Combined with the upsert pattern, this makes the table
behave like a typed key-value store.

**Upsert pattern:**

```sql
INSERT INTO user_profile (id, ...)
VALUES (1, ...)
ON CONFLICT(id) DO UPDATE SET
    learning_style    = excluded.learning_style,
    ...
```

`ON CONFLICT(id) DO UPDATE SET` is SQLite's upsert syntax (available since
SQLite 3.24, 2018). `excluded.*` refers to the values that were being
inserted before the conflict was detected. This is atomic — there's no
read-modify-write race condition that could corrupt the profile if two
Streamlit browser tabs are open simultaneously.

**`add_weak_topic()` and `add_strong_topic()`** are the only places in the
codebase that should modify `weak_topics` and `strong_topics`. They enforce
the mutual-exclusivity invariant:

```python
def add_weak_topic(self, topic: str) -> None:
    profile = self.load()
    if topic not in profile.weak_topics:
        profile.weak_topics.append(topic)
    profile.strong_topics = [t for t in profile.strong_topics if t != topic]
    self.save(profile)
```

This is a read-modify-write — it loads the whole profile, mutates the Python
object, then saves. This is safe here because `ProfileStore` is used as a
`@st.cache_resource` singleton in the Streamlit app, so there's only one
instance, and Streamlit's execution model means only one script run is active
at a time per user session.

---

## 3. Quiz Scoring Chain — `chains/quiz_chain.py`

This is the most complex piece. It wraps LangChain's structured output parsing
into a callable function that takes raw conversation history and returns a
validated `QuizResult`.

### The parsing stack

```
LLM output (str)
    ↓
PydanticOutputParser          ← primary parser
    ↓  (if ValidationError or OutputParserException)
OutputFixingParser             ← fallback: asks the LLM to repair its own output
    ↓
QuizResult                    ← validated Pydantic object
```

`PydanticOutputParser` works by:
1. Generating a JSON Schema from `QuizResult.schema()`
2. Injecting that schema as format instructions into the prompt
3. Calling `.parse(llm_output_str)` which does `json.loads()` then
   `QuizResult.model_validate(parsed_dict)`

If the LLM returns malformed JSON, or valid JSON that fails Pydantic
validation (e.g. `score: 105`), `PydanticOutputParser.parse()` raises an
`OutputParserException`.

`OutputFixingParser` catches that exception and constructs a follow-up prompt
to the same LLM:
```
Instructions were: <original format instructions>
Completion was: <the bad output>
Error: <the validation error message>
Please try again.
```

This second call usually succeeds because the error message tells the LLM
exactly what was wrong. If it fails again, `OutputFixingParser` re-raises —
the `except Exception` in `app.py`'s sidebar catches it and shows an error
message to the user.

**Why not `with_structured_output()`?** LangChain's newer
`llm.with_structured_output(QuizResult)` would also work and is cleaner, but
it requires the LLM to support function/tool calling for guaranteed JSON
(GPT-4o does), and it bypasses the explicit `OutputFixingParser` fallback.
`PydanticOutputParser` + `OutputFixingParser` is more transparent — you can
see the repair happening in LangSmith traces — and is the pattern the CLAUDE_p1
design doc specifies.

**Version note.** In `langchain >= 1.0`, `OutputFixingParser` moved from
`langchain.output_parsers` (the old path) to `langchain_classic.output_parsers`.
This was discovered by testing imports in the venv and confirmed with
`pip list`. The `langchain-classic` package is a compatibility shim that
preserves the classic API surface while `langchain` itself was restructured.
`requirements.txt` now declares `langchain-classic>=1.0.0` explicitly.

### The prompt template

```python
_SCORING_TEMPLATE = """\
You are evaluating a quiz conversation between a learner and an AI tutor.

Topic: {topic}
Today's date: {today}
Quiz conversation:
{conversation}
---
...
{format_instructions}

Respond with ONLY the JSON object — no prose, no markdown fences."""
```

Key decisions in this prompt:

- **"Respond with ONLY the JSON object — no markdown fences."** LLMs
  frequently wrap JSON in ` ```json ... ``` ` blocks. `PydanticOutputParser`
  can handle this (it strips fences before parsing), but it's better to
  prevent it outright.

- **`{today}` is injected from Python, not left to the LLM.** If you let the
  LLM fill in the date it will hallucinate one, or use its training cutoff.

- **`{format_instructions}` comes from `primary_parser.get_format_instructions()`.**
  This is the full JSON Schema for `QuizResult`, plus instructions like "Return
  a JSON object that matches this schema". It's injected at call time in
  `score_quiz()`, not baked into the chain, because the schema could
  theoretically change between invocations (though in practice it won't).

### `format_conversation()`

```python
def format_conversation(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        role = "Learner" if m.get("role") == "human" else "Tutor"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)
```

This converts the raw `session_memory.messages` list (which uses `{"role":
"human"|"ai", "content": str}` dicts from `memory_manager.py`) into a
readable transcript. "Learner" and "Tutor" are used instead of "human" and
"AI" because they're more semantically meaningful to the LLM in this scoring
context.

---

## 4. Adaptive Prompt Builder — `config/adaptive_prompt.py`

**Responsibility:** Inject a `UserProfile` into the existing `TUTOR_SYSTEM_PROMPT`
template and return a complete, LLM-ready system prompt string.

### The substitution approach

The existing `TUTOR_SYSTEM_PROMPT` in `config/prompts.py` contains one placeholder:

```
<learner_profile>
{learner_profile}
</learner_profile>
```

It also contains many other `{...}` tokens that are part of the syllabus
format template shown to the LLM, e.g. `{TOPIC}`, `{what the learner can DO}`,
`{diagnostic question 1}`. These are NOT Python format fields — they're
instructional text telling the LLM what to put in its own output.

Using `str.format()` would cause a `KeyError` on the first non-profile
placeholder. The solution is a targeted `str.replace()`:

```python
return TUTOR_SYSTEM_PROMPT.replace("{learner_profile}", profile_block)
```

This touches exactly one token and leaves everything else intact.

### The rendered profile block

`_render_profile_block()` builds a short, dense text description of the
profile:

```
Learning style: reading — Dense, precise text is fine — I learn by reading carefully.
Preferred pace: fast — Move quickly — skip basics I already know, challenge me.
Explanation style: examples_first — Show a working example first, then explain the mechanics.
Weak topics (score < 70, resurface these): Python generators, closures
Strong topics (learner has demonstrated mastery): decorators
```

This goes inside the `<learner_profile>` XML tags in the system prompt, which
the tutor is already instructed to read and apply. The LLM sees the profile as
part of its identity context on every turn.

The three `_*_LABELS` dicts (`_PACE_LABELS`, `_STYLE_LABELS`,
`_LEARNING_LABELS`) translate the short enum values into behavioural
instructions. This matters because "reading" alone doesn't tell the LLM
much — "Dense, precise text is fine — I learn by reading carefully" does.

### Fallback behaviour

If no profile is saved yet (first-run before the user completes the setup
form), `_get_system_prompt()` in `app.py` calls:

```python
TUTOR_SYSTEM_PROMPT.replace(
    "{learner_profile}",
    "No profile set yet — ask the learner about their background."
)
```

This means the LLM always gets a valid system prompt and can still run the
intake protocol from `<intake_protocol>` in the prompt.

---

## 5. Streamlit App — `app.py`

The app was significantly restructured. Here's what changed and why.

### Singletons with `@st.cache_resource`

```python
@st.cache_resource
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o", temperature=0.7)

@st.cache_resource
def get_profile_store() -> ProfileStore:
    return ProfileStore()

@st.cache_resource
def get_score_tracker() -> ScoreTracker:
    return ScoreTracker()
```

`@st.cache_resource` is Streamlit's way of creating true singletons — objects
that are instantiated once and shared across all reruns and users of the app.
Without it, Streamlit would recreate `ChatOpenAI`, `ProfileStore`, and
`ScoreTracker` on every script rerun (which happens after every widget
interaction). That would mean a new database connection and a new LLM client
object dozens of times per session — wasteful and potentially buggy.

### Page router

```python
if "page" not in st.session_state:
    st.session_state.page = "chat" if profile_store.load() else "profile_setup"
```

On first run, `profile_store.load()` returns `None` (no row in the DB),
so the app starts on `"profile_setup"`. After the form is submitted,
`st.session_state.page` is set to `"chat"` and `st.rerun()` triggers a clean
redraw. On subsequent runs, the profile exists, so the app starts directly
on chat.

The `⚙️ Profile Settings` sidebar button can flip the page back to
`"profile_setup"` at any time for editing. The form pre-populates with the
existing profile values.

### Profile setup form

```python
with st.form("profile_form"):
    learning_style = st.selectbox("Learning style", options=[...], index=...)
    preferred_pace = st.selectbox("Preferred pace", options=[...], index=...)
    explanation_style = st.selectbox("Explanation style", options=[...], index=...)
    submitted = st.form_submit_button(...)
```

Using `st.form` is important here. Without it, every `st.selectbox` change
triggers a rerun, which would try to save a partial profile mid-selection.
`st.form` batches all widget interactions and only submits when the user
clicks the button.

The `index=` parameter on each selectbox pre-selects the current value when
editing. If there's no existing profile (first run), it falls back to sensible
defaults (`"reading"`, `"medium"`, `"examples_first"`).

`weak_topics` and `strong_topics` are **not** user-editable in the form — they
are set exclusively by quiz results. This is intentional: the lists should
reflect actual performance, not self-assessment.

### Adaptive system prompt on every turn

```python
system_prompt = _get_system_prompt()
history = st.session_state.memory.to_langchain_messages()
messages = [SystemMessage(content=system_prompt)] + history + [HumanMessage(content=prompt)]
```

`_get_system_prompt()` is called on every chat submission, not once at
startup. This means if the user runs a quiz mid-session, the newly added
`weak_topics` appear in the system prompt on the very next chat turn — no
restart required.

### Quiz scoring sidebar

```python
with st.expander("📊 Score a Quiz", expanded=False):
    quiz_topic = st.text_input("Quiz topic", ...)
    if st.button("Score & Save"):
        result = score_quiz(topic=quiz_topic, messages=..., llm=llm)
        score_tracker.save(result)
        if result.score < 70:
            profile_store.add_weak_topic(result.topic)
        else:
            profile_store.add_strong_topic(result.topic)
```

The threshold of 70 for weak vs strong is the same threshold referenced in the
tutor's `<pedagogy>` block ("Track concepts scoring below 70%"). The two
systems are now numerically consistent.

`st.expander(..., expanded=False)` keeps the sidebar clean by default — the
user has to opt in to see the quiz scoring controls.

### Recent scores panel

```python
with st.expander("🏆 Recent Scores", expanded=False):
    recent = score_tracker.load_recent(5)
    for r in recent:
        colour = "🟢" if r.score >= 70 else "🔴"
        st.write(f"{colour} **{r.topic}** — {r.score:.0f}% ({r.date})")
```

Green/red dots give instant visual feedback. `:.0f` rounds the float to a
whole number for display without storing it rounded in the DB.

### Profile summary expander in main area

```python
with st.expander("Your profile", expanded=False):
    cols = st.columns(3)
    cols[0].metric("Learning style", profile.learning_style)
    cols[1].metric("Pace", profile.preferred_pace)
    cols[2].metric("Style", profile.explanation_style)
    if weak_label:
        st.caption(f"⚠️ {weak_label}")
```

This gives the user visibility into what the tutor "sees" about them. The
`st.metric()` component is a clean way to display label/value pairs. The weak
topics warning only appears if there are any.

---

## 6. Supporting Changes

### `p1-personal-tutor/.gitignore`

Added `data/` to exclude the SQLite database from git. The `data/` directory
is created at runtime by `_get_conn()` when first needed — it doesn't need to
be committed.

### `requirements.txt`

Added `langchain-classic>=1.0.0` and `langchain-community>=0.4.0` explicitly.
In `langchain >= 1.0`, the library was split: core abstractions live in
`langchain-core`, the main `langchain` package is now a thin orchestration
layer, classic/deprecated-but-still-needed pieces live in `langchain-classic`,
and integrations with external services live in `langchain-community`.
`OutputFixingParser` is in `langchain-classic`.

### Root `.gitignore`

Added `!p1-personal-tutor/models/` as an exception to the `models/` rule that
was blocking the Pydantic models package from being staged. The root
`.gitignore` uses `models/` to exclude trained ML model artifact directories —
it shouldn't catch a Python package called `models/`.

---

## 7. Data Flow End-to-End

```
┌─────────────────────────────────────────────────────────────────────┐
│ STARTUP                                                             │
│                                                                     │
│  ProfileStore.load()                                                │
│       │                                                             │
│       ├── None → page = "profile_setup"                             │
│       └── UserProfile → page = "chat"                              │
│                │                                                    │
│                └── build_system_prompt(profile)                     │
│                         → TUTOR_SYSTEM_PROMPT with profile injected │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ CHAT TURN                                                           │
│                                                                     │
│  user types message                                                 │
│       │                                                             │
│       ├── _get_system_prompt()  ← rebuilds from current profile     │
│       ├── memory.to_langchain_messages()                            │
│       └── llm.invoke([SystemMessage, *history, HumanMessage])       │
│                │                                                    │
│                └── response displayed + saved to memory             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ QUIZ SCORING                                                        │
│                                                                     │
│  user enters topic + clicks "Score & Save"                          │
│       │                                                             │
│       └── score_quiz(topic, memory.messages, llm)                  │
│                │                                                    │
│                ├── format_conversation(messages) → transcript str   │
│                ├── build_quiz_scoring_chain(llm).invoke(...)        │
│                │        │                                           │
│                │        ├── ChatPromptTemplate → formatted prompt   │
│                │        ├── llm.invoke(prompt) → raw str            │
│                │        ├── PydanticOutputParser.parse(str)         │
│                │        │        ├── OK → QuizResult                │
│                │        │        └── FAIL → OutputFixingParser      │
│                │        │                    └── llm repair call    │
│                │        └── QuizResult                              │
│                │                                                    │
│                ├── ScoreTracker.save(result)  → quiz_results table  │
│                │                                                    │
│                ├── score < 70?                                      │
│                │     ├── YES → ProfileStore.add_weak_topic(topic)   │
│                │     └── NO  → ProfileStore.add_strong_topic(topic) │
│                │                                                    │
│                └── next chat turn: system prompt rebuilt with       │
│                    updated weak_topics already applied              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Extension Guide

**Add a new field to `QuizResult`.**
1. Add the field to `models/quiz_models.py`.
2. Add a column to the `quiz_results` table in `db/score_tracker.py` (remember
   to handle existing rows — SQLite's `ALTER TABLE ADD COLUMN` supports a
   default value).
3. Update `_row_to_model()` to include the new field.
4. Update the scoring prompt in `chains/quiz_chain.py` to ask the LLM to
   populate it.

**Add a new profile field.**
1. Add the field to `models/user_profile.py`.
2. Add a column to the `user_profile` table in `db/profile_store.py` with a
   sensible default (`DEFAULT 'none'` or similar) so existing rows don't break.
3. Add the corresponding `ALTER TABLE` migration if the DB already exists, or
   delete `data/tutor.db` on dev to rebuild from scratch.
4. Add a widget for it in `render_profile_setup()` in `app.py`.
5. Add a label mapping in `config/adaptive_prompt.py` and include it in
   `_render_profile_block()`.

**Add a quiz history page.**
- Use `score_tracker.load_all()` in a new expander or Streamlit page.
- Group by topic with a dict comprehension.
- Plot score trends with `st.line_chart()`.

**Move from SQLite to Postgres (Cloud Run).**
- Both `_get_conn()` functions use a file path. Replace them with a
  `psycopg2.connect(DATABASE_URL)` call reading from environment.
- The SQL in both modules is ANSI-compatible except for the upsert — Postgres
  uses the same `ON CONFLICT DO UPDATE` syntax so no changes needed there.
- `sqlite3.Row` → `psycopg2.extras.RealDictRow` for named column access.

---

# P1 Feature Notes — Quiz Tab, Streaming, Socratic Opener & Cloud Run Fixes

**Branch:** `feature/p1-quiz-tab-streaming-fixes`
**Written:** 2026-05-11

---

## Table of Contents

1. [New Pydantic Models](#1-new-pydantic-models)
2. [Quiz Generation Chains](#2-quiz-generation-chains)
3. [Free Response Grading Chain](#3-free-response-grading-chain)
4. [Socratic Opener Chain](#4-socratic-opener-chain)
5. [Streaming Chat Responses](#5-streaming-chat-responses)
6. [Returning-User System Prompt](#6-returning-user-system-prompt)
7. [Cloud Run Storage Fix](#7-cloud-run-storage-fix)
8. [New Chat Button Fix](#8-new-chat-button-fix)
9. [Quiz Tab UI State Machine](#9-quiz-tab-ui-state-machine)
10. [Data Flow End-to-End](#10-data-flow-end-to-end)

---

## 1. New Pydantic Models

Added to `models/quiz_models.py`. Three groups:

**MC (Multiple Choice):**

```python
class MCOption(BaseModel):
    key: Literal["A", "B", "C", "D"]
    text: str

class MCQuestion(BaseModel):
    question: str
    options: list[MCOption]   # min_length=4, max_length=4 enforced
    correct_key: Literal["A", "B", "C", "D"]
    explanation: str

class MCQuiz(BaseModel):
    topic: str
    questions: list[MCQuestion]
```

`min_length=4, max_length=4` on `options` means Pydantic will reject any LLM
response that doesn't provide exactly four options. The `OutputFixingParser`
then asks the LLM to repair rather than silently accepting a malformed quiz.

**FR (Free Response):**

```python
class FRQuestion(BaseModel):
    question: str
    key_concepts: list[str]   # min_length=2 — forces at least 2 grading anchors
    sample_answer: str

class FRQuiz(BaseModel):
    topic: str
    questions: list[FRQuestion]
```

`key_concepts` is the grading rubric. The `grade_fr_answer()` chain compares
the learner's answer against these concepts explicitly, so grading is
structured rather than vibes-based.

**Grading:**

```python
class GradeResult(BaseModel):
    score: float               # 0.0–1.0, ge/le enforced
    feedback: str              # 1-2 sentences
    matched_concepts: list[str]
    missing_concepts: list[str]
```

`score` is in `[0, 1]` (not 0–100) so it's directly usable for averaging
across questions without a division step.

---

## 2. Quiz Generation Chains

`chains/quiz_generation_chain.py` — two LCEL chains, one per question type.

```
ChatPromptTemplate | llm | OutputFixingParser[MCQuiz | FRQuiz]
```

Both chains receive:
- `topic` — subject to quiz on
- `n_questions` — exact count (the prompt says "exactly N")
- `learning_style` — from the learner's profile, so question framing matches
  how they learn (e.g. a kinesthetic learner gets questions framed around what
  something *does*, not what it *is*)
- `weak_areas` — from the most recent `QuizResult` for this topic; the prompt
  asks the LLM to prioritise these so the quiz targets actual gaps

**Why `OutputFixingParser` here too?** Quiz generation is a larger JSON object
than quiz scoring — more fields, more nesting, more opportunities for the LLM
to drop a field or mis-type a key. The one-repair fallback is worth the extra
LLM call on the rare failure.

**Separate chains for MC and FR** (rather than a discriminated union) keeps the
prompts tight and unambiguous. A single mixed-type prompt is harder for the LLM
to follow reliably.

---

## 3. Free Response Grading Chain

`chains/fr_grading_chain.py`

```
ChatPromptTemplate | llm | OutputFixingParser[GradeResult]
```

Inputs:
- `question` — the original question
- `key_concepts` — the rubric (from `FRQuestion.key_concepts`)
- `sample_answer` — the gold standard (from `FRQuestion.sample_answer`)
- `user_answer` — the learner's text

The prompt instructs the LLM to grade **strictly against key_concepts**, not
holistically. This prevents inflated scores from fluent but shallow answers.

`matched_concepts` and `missing_concepts` are shown in the results expander
so the learner sees exactly what they got right and what they missed — not just
a number. This is more actionable than a percentage alone.

---

## 4. Socratic Opener Chain

`chains/socratic_opener_chain.py`

```
ChatPromptTemplate | llm | StrOutputParser
```

Fires once when the user loads an **archived conversation** and their profile
has `weak_topics`. The chain generates one retrieval question targeting the
most specific concept from the first weak topic.

**Why not `PydanticOutputParser`?** The output is a single sentence — there's
no structure to validate. `StrOutputParser` returns the raw string, which is
exactly what's needed.

**Trigger mechanic in `app.py`:**

1. Sidebar conversation button sets `st.session_state.pending_opener = True`
2. After `st.rerun()`, the chat tab checks the flag on render
3. If True: generates the opener, writes it to `display_messages` and
   `memory.messages`, saves memory to disk, clears the flag
4. The opener persists in the conversation as a regular AI message — if the
   user replies, the tutor continues naturally

The opener is generated in the main content area (not the sidebar) so the
spinner appears where the user is looking.

---

## 5. Streaming Chat Responses

Changed in `app.py`:

```python
# Before
response = llm.invoke(messages)
st.write(response.content)

# After
response_content: str = st.write_stream(
    chunk.content for chunk in llm.stream(messages)
)
```

`llm.stream()` returns a generator of `AIMessageChunk` objects. Each chunk's
`.content` is a partial string. `st.write_stream()` accepts a generator of
strings and renders them incrementally — first token appears in ~300ms,
perceived latency drops significantly even though total generation time is
the same.

`st.write_stream()` returns the full accumulated string, which is stored in
`response_content` and then saved to memory — same as before.

**Why not streaming for quiz generation/grading?** Those chains use Pydantic
parsers that require the full output before validation. Streaming is only
appropriate when you can display partial content meaningfully.

---

## 6. Returning-User System Prompt

Added `TUTOR_SYSTEM_PROMPT_RETURNING` to `config/prompts.py`.

**Problem:** The original `TUTOR_SYSTEM_PROMPT` contains an `<intake_protocol>`
block that says "On first session only, ask Q1–Q5". But the LLM has no
persistent state — on every new chat (new `SessionMemory`), the conversation
history is blank, which looks like a first session. So the tutor re-ran intake
on every new topic or chat reset.

**Fix:** Two prompt variants:
- `TUTOR_SYSTEM_PROMPT` — includes `<intake_protocol>`. Used when no profile
  exists (true first-time user).
- `TUTOR_SYSTEM_PROMPT_RETURNING` — identical except the `<intake_protocol>`
  block is replaced with: *"The learner has an established profile — do NOT run
  intake. Jump straight into teaching."* Used by `build_system_prompt()` which
  is only called when a profile exists.

The profile's existence is the signal that intake is complete. No extra DB
column or flag needed.

---

## 7. Cloud Run Storage Fix

**Problem:** `_MEMORY_BASE` in `memory_manager.py` was `Path(__file__).parent`
— inside the app's installed package directory. On Cloud Run, this directory
may be part of the read-only container image layer. Write calls silently failed,
meaning session files were never persisted. Because of this: (a) all users
appeared to have the same empty state, and (b) the new chat button appeared
broken because `load_memory` loaded stale data from a file that was never
cleared.

**Fix:** Both storage paths now read from environment variables with local
fallbacks:

```python
# memory/memory_manager.py
_MEMORY_BASE = Path(os.environ.get("TUTOR_MEMORY_PATH", str(Path(__file__).parent)))

# db/profile_store.py + db/score_tracker.py
_DB_PATH = Path(os.environ.get("TUTOR_DB_PATH", str(Path(__file__).parent.parent / "data" / "tutor.db")))
```

In `Dockerfile`:

```dockerfile
ENV TUTOR_DB_PATH=/tmp/tutor-data/tutor.db
ENV TUTOR_MEMORY_PATH=/tmp/tutor-memory
```

`/tmp` is Cloud Run's guaranteed-writable ephemeral disk. The `_get_conn()`
and `save_memory()` functions already call `mkdir(parents=True, exist_ok=True)`
before writing, so `/tmp/tutor-data/` and `/tmp/tutor-memory/<uuid>/` are
created on first use.

**Trade-off:** `/tmp` is ephemeral — it resets on container replacement. This
is documented in the README under "Known limitation." The proper fix is GCS
(for JSON files) and Cloud SQL (for SQLite), deferred to a later milestone.
`--min-instances 1` keeps one container warm to avoid cold-start data loss
between user visits.

---

## 8. New Chat Button Fix

Two root causes:

**Cause 1 — Stale topic widget.** `st.text_input` with `key="current_topic_input"`
persists its value in `st.session_state` across reruns. When "New Chat" was
clicked, `display_messages` and `memory` were reset, but the topic input
retained its old value. The system prompt on the next turn still referenced the
old topic, making the chat feel stuck in the old context.

**Fix:** Explicitly clear the widget value before rerun:

```python
st.session_state["current_topic_input"] = ""
```

**Cause 2 — Writes silently failing.** `archive_and_reset()` writes the cleared
`session_memory.json`. If writes were going to a non-writable path (the image
layer), the file was never cleared. `load_memory()` then read stale data and
returned the old conversation. Fixed by the storage path change in §7.

---

## 9. Quiz Tab UI State Machine

The quiz tab uses `st.session_state.quiz_phase` to drive a three-phase UI.
Streamlit rerenders on every widget interaction, so state must live in
`st.session_state` — not local variables.

```
"setup" ──(generate clicked)──► "in_progress" ──(last Q answered)──► "complete"
   ▲                                   │                                   │
   └──────────────(abandon)────────────┘           (New Quiz clicked) ─────┘
```

**State keys:**

| Key | Type | Purpose |
|---|---|---|
| `quiz_phase` | str | Current phase |
| `quiz_data` | MCQuiz \| FRQuiz | Generated quiz |
| `quiz_type` | "mc" \| "fr" | Question type |
| `quiz_q_idx` | int | Current question index |
| `quiz_answers` | list | User's answers (one per question) |
| `quiz_grade_results` | list | bool (MC) or GradeResult (FR) per question |

**MC grading** is instant — no LLM call. `selected_key == q.correct_key` is
evaluated in Python.

**FR grading** fires one LLM call per answer (immediately on Submit). This
means the learner gets feedback question-by-question rather than only at the
end, which is more pedagogically useful.

**Score saving** is explicit (a button click), not automatic. This lets the
learner review results before committing them to their history — they might
want to retake a poorly generated quiz without it hurting their record.

---

## 10. Data Flow End-to-End

```
┌─────────────────────────────────────────────────────────────────────┐
│ QUIZ TAB — GENERATION                                               │
│                                                                     │
│  user selects topic + question type + n_questions                   │
│       │                                                             │
│       └── generate_mc_quiz() or generate_fr_quiz()                  │
│                │                                                    │
│                ├── inject: topic, n, learning_style, weak_areas     │
│                ├── ChatPromptTemplate → prompt                       │
│                ├── llm.invoke(prompt) → raw str                     │
│                ├── PydanticOutputParser[MCQuiz | FRQuiz]            │
│                │        └── fail → OutputFixingParser → repair call  │
│                └── MCQuiz | FRQuiz → st.session_state.quiz_data     │
│                                                                     │
│  quiz_phase = "in_progress" → st.rerun()                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ QUIZ TAB — ANSWERING                                                │
│                                                                     │
│  user submits answer                                                │
│       │                                                             │
│       ├── MC: selected_key == correct_key → bool saved              │
│       └── FR: grade_fr_answer(question, key_concepts,               │
│                    sample_answer, user_answer, llm)                 │
│                │                                                    │
│                ├── ChatPromptTemplate → grading prompt              │
│                ├── llm.invoke() → raw str                           │
│                └── PydanticOutputParser[GradeResult]                │
│                         └── GradeResult saved to quiz_grade_results │
│                                                                     │
│  quiz_q_idx += 1 → st.rerun() (or quiz_phase = "complete")         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ CHAT TAB — CONVERSATION REVISIT                                     │
│                                                                     │
│  user clicks archived conversation in sidebar                       │
│       │                                                             │
│       ├── load_conversation() → restores memory + display_messages  │
│       ├── pending_opener = True (if weak_topics exist)              │
│       └── st.rerun()                                                │
│                                                                     │
│  chat tab renders:                                                  │
│       │                                                             │
│       ├── display existing messages                                 │
│       └── pending_opener == True?                                   │
│                │                                                    │
│                └── generate_socratic_opener(weak_topics, llm)       │
│                         → single retrieval question string          │
│                         → appended to display_messages + memory     │
│                         → memory saved to disk                      │
│                         → pending_opener = False                    │
└─────────────────────────────────────────────────────────────────────┘
```
