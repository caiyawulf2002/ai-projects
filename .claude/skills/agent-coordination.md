# Agent Coordination Protocol
*Adapted from Ilyas Ibrahim's 4-step coordination protocol for this project.*

---

## The core problem this solves

Claude Code agents have no memory between sessions. Without this protocol,
a new session will:
- Re-build things that already exist
- Overwrite files that other sessions completed
- Invent GCS bucket names or API endpoints that don't match reality
- Lose track of which Pydantic models are canonical

This protocol gives every session institutional memory via shared files.

---

## The 4-step protocol (run in this order, every session)

### Step 1 — Registry check
Before writing a single line of code, read `registry.md`.
Answer these questions:
- What is the current status of the project(s) I'm touching?
- Is anything I'm about to build already done?
- Are there any blockers or dependencies noted from prior sessions?
- What exact file paths, bucket names, or endpoints exist?

### Step 2 — Context injection
Load the skill files relevant to this session's task:
- Touching cloud infra? → read `gcp-context.md`
- Touching financial data? → read `finance-schema.md`
- Building an agent or chain? → re-read the relevant project's CLAUDE.md

Don't assume you remember these from earlier in the session. Load them explicitly.

### Step 3 — Sequencing
For tasks that span multiple files or components, plan the order before executing:
- What must exist before I can build X?
- What will break if I change Y?
- If running parallel agents (e.g. P3 PDF parser + P3 XGBoost in parallel),
  define the interface contract between them before either starts.

### Step 4 — Verification + registry update
After completing a task:
1. Verify the output actually works (run it, test it, don't assume)
2. Update `registry.md` with specific, accurate status
3. If new infrastructure was created (bucket, endpoint, Cloud Run service),
   add it to `gcp-context.md` immediately
4. If a new Pydantic model was created, add it to `finance-schema.md`

---

## Parallel agent rules

When running multiple Claude Code sessions simultaneously (e.g. one building
P3's analyzer while another builds P5's comps agent):

- Each session MUST read registry.md before starting
- Sessions working on shared schema (P3 + P5) must coordinate:
  - One session owns schema changes at a time
  - The other session is read-only on finance-schema.md until the first commits
- Both sessions MUST update registry.md when done
- Never have two sessions write to the same Python file simultaneously

**Recommended parallel pairs (safe to run together):**
- P1 (Streamlit/chains) + P2 setup (AgentExecutor config)
- P3 PDF parser + P3 XGBoost classifier (different files, shared schema)
- P3 ratio engine + P5 comps agent (P5 is read-only on P3's ratio engine)
- P4 optimizer core + P4 LSTM training code (different files)

**Never run in parallel:**
- Any two sessions editing finance-schema.md
- Any two sessions deploying to the same Cloud Run service
- P3 ratio engine (writing) + P5 (reading P3's output) simultaneously

---

## Context window management

When a session is getting long and context is compressing:
1. Run `/compact` in Claude Code (compresses context, keeps gist)
2. Immediately re-read CLAUDE.md and registry.md after compacting
3. Do NOT use `/clear` mid-build — you'll lose critical state
4. Use `/clear` only at the start of a brand new isolated task

Signs you need to compact:
- Claude starts suggesting things that are already done
- Claude forgets a file path you mentioned earlier in the session
- Responses are getting slower

---

## What NOT to do

- Don't start a session without reading registry.md first
- Don't finish a session without updating registry.md
- Don't hardcode infrastructure values — they go in gcp-context.md
- Don't create new Pydantic models without adding them to finance-schema.md
- Don't mark something as "done" in the registry without testing it
