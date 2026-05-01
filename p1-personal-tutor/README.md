# Personal Learning Tutor (P1)
> An AI-powered Socratic tutor that adapts to your learning style and remembers your progress across sessions.

## What it does
P1 is a conversational learning assistant that teaches concepts through questions rather than lectures. It generates personalized syllabi, runs Socratic teaching sessions, tracks knowledge gaps, and resurfaces weak concepts using spaced repetition. It also translates complex outputs from other AI agents into plain English based on what you already know.

## Why it exists
This is the first project in a 5-project AI portfolio system. P1 serves as the "natural language interface" for the entire system—when other agents (financial analyzers, optimizers, LSTM models) produce structured outputs, P1 translates them into explanations anchored to the learner's existing knowledge. It's both a standalone learning tool and the human-facing layer for a multi-agent financial AI system.

## Architecture

### Key components

**app.py** — Streamlit chat interface. Handles message display, user input, and orchestrates the conversation loop. Loads memory on startup, persists after each exchange.

**config/prompts.py** — Contains the system prompt defining P1's personality and pedagogy. Includes two modes: TEACH MODE (generating syllabi, running Socratic sessions) and EXPLAIN MODE (translating structured agent outputs). The prompt encodes specific pedagogical principles like "retrieval over recognition" and "problem first."

**memory/memory_manager.py** — Persistence layer using LangChain's ConversationSummaryBufferMemory. Stores both a running summary of older context and recent message history to a JSON file. This lets conversations resume across sessions without exploding token costs.

### Data flow
1. User sends message via Streamlit chat input
2. Memory manager loads conversation history (summary + recent messages)
3. System prompt + history + new message sent to GPT-4o
4. Response displayed and both sides saved to memory
5. Memory persisted to JSON for next session

### Design decisions
- **JSON file storage** — SQLite would be overkill for single-user local development. JSON is human-readable for debugging and trivial to implement.
- **ConversationSummaryBufferMemory** — Hybrid approach: keeps recent messages verbatim for accuracy, summarizes older context to stay within token limits. Better than pure buffer (loses old context) or pure summary (loses recent detail).
- **GPT-4o with temperature 0.7** — Needs to be smart enough for Socratic questioning but creative enough to generate varied teaching approaches.

## Tech stack
- `streamlit` — Fastest way to build a chat UI without frontend code. Hot reload for rapid iteration.
- `langchain` — Memory abstractions (ConversationSummaryBufferMemory) handle the hard parts of context management. Overkill for simple chat but essential for the memory system.
- `langchain-openai` — Clean interface to OpenAI models with LangChain message types.
- `python-dotenv` — Keep API keys out of code. Standard practice.
- `openai` (via langchain-openai) — GPT-4o chosen for reasoning quality needed for Socratic teaching.

## Key decisions

**Hybrid memory over pure conversation buffer**
- Decided: Use ConversationSummaryBufferMemory with 2000 token limit
- Alternatives: Simple buffer (loses old context), full history (token explosion), vector retrieval (complexity overkill)
- Why: Tutoring requires remembering what was taught weeks ago while keeping recent exchanges accurate. Summary handles the former, buffer handles the latter.

**Single JSON file for persistence**
- Decided: Store memory state in `session_memory.json`
- Alternatives: SQLite, Redis, cloud database
- Why: This is a single-user local tool. JSON is debuggable, portable, and has zero setup. Can upgrade later if needed.

**System prompt encodes full pedagogy**
- Decided: Put all teaching methodology in one large system prompt
- Alternatives: Multiple smaller prompts, RAG over teaching principles
- Why: The pedagogy is stable and needs to be applied consistently. One prompt means one source of truth. RAG would add latency and complexity for content that rarely changes.

## How to run locally

```bash
# Clone and enter project
cd p1-personal-tutor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install streamlit langchain langchain-openai python-dotenv

# Set up environment variables
echo "OPENAI_API_KEY=your-key-here" > .env

# Run the app
streamlit run app.py
```

App opens at `http://localhost:8501`

## How to deploy
[not yet built] — Cloud Run deployment planned. Will need to swap JSON persistence for Cloud Storage or Firestore.

## Project status

**Working:**
- Chat interface with message history display
- GPT-4o integration with full system prompt
- Session memory that persists across restarts
- Summary buffer to manage long conversations

**In progress:**
- Learner profile system (referenced in prompts but not yet populated)
- Spaced repetition tracking (pedagogy defined, implementation pending)

**Not started:**
- Integration with other portfolio agents (P2-P5)
- Knowledge gap database
- Quiz and assessment system
- Cloud deployment

## Part of a larger system
P1 is the human interface layer for a 5-project AI portfolio:
- **P1 (this project)** — Teaches concepts, explains outputs from other agents
- **P2-P5** — [not yet built] Financial analysis agents that will send structured outputs to P1 for translation

P1 has no upstream dependencies. All other projects will depend on P1 for user-facing explanations. The `EXPLAIN MODE` in the system prompt is specifically designed to receive structured JSON from other agents and translate it based on the learner's knowledge state.