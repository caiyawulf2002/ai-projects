#!/usr/bin/env python3
"""
Documentation Agent
===================
Triggered automatically by Claude Code after every Write / Edit / MultiEdit.
Reads the changed file, reads the current README, and rewrites the README
to reflect the new state of the project.

Environment:
  ANTHROPIC_API_KEY  — set in your shell or GCP Secret Manager
  CLAUDE_TOOL_INPUT_FILE_PATH — injected by Claude Code hook

Usage (manual):
  python .claude/scripts/doc_agent.py path/to/changed/file.py
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime

# ── skip list ─────────────────────────────────────────────────────────────────
# Don't update README when these files change — they're meta, not code
SKIP_PATTERNS = [
    r"README\.md$",
    r"\.claude/",
    r"\.git/",
    r"__pycache__",
    r"\.pyc$",
    r"\.env",
    r"notebooks/",
    r"\.gitignore$",
    r"requirements\.txt$",
    r"setup-repo\.sh$",
]

# ── project roots ──────────────────────────────────────────────────────────────
PROJECT_DIRS = [
    "p1-personal-tutor",
    "p2-domain-intelligence",
    "p3-statements-analyzer",
    "p4-portfolio-optimizer",
    "p5-comps-agent",
    "edgar-mcp-server",
]


def should_skip(file_path: str) -> bool:
    """Return True if this file change should NOT trigger a README update."""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, file_path):
            return True
    return False


def find_project_root(file_path: str) -> Path | None:
    """
    Walk up from the changed file to find which project it belongs to.
    Returns the project root Path, or None if not inside a known project.
    """
    path = Path(file_path).resolve()
    for parent in [path] + list(path.parents):
        if parent.name in PROJECT_DIRS:
            return parent
    return None


def collect_project_context(project_root: Path) -> str:
    """
    Build a snapshot of the project's current source files for the LLM.
    Reads src/ and any top-level .py files. Truncates large files.
    """
    MAX_FILE_CHARS = 3000
    MAX_TOTAL_CHARS = 20000
    context_parts = []
    total = 0

    # Collect all Python files in src/ and project root
    src_dirs = [project_root / "src", project_root]
    seen = set()

    for base in src_dirs:
        if not base.exists():
            continue
        for py_file in sorted(base.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            if py_file in seen:
                continue
            seen.add(py_file)

            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            rel = py_file.relative_to(project_root)
            snippet = content[:MAX_FILE_CHARS]
            if len(content) > MAX_FILE_CHARS:
                snippet += f"\n... [{len(content) - MAX_FILE_CHARS} chars truncated]"

            entry = f"### {rel}\n```python\n{snippet}\n```\n"
            if total + len(entry) > MAX_TOTAL_CHARS:
                context_parts.append(
                    f"### {rel}\n[file exists but omitted — context limit reached]\n"
                )
                break
            context_parts.append(entry)
            total += len(entry)

    return "\n".join(context_parts) if context_parts else "[no source files found yet]"


def read_existing_readme(project_root: Path) -> str:
    readme_path = project_root / "README.md"
    if readme_path.exists():
        return readme_path.read_text(encoding="utf-8")
    return "[README does not exist yet — generate from scratch using the template]"


def call_anthropic(prompt: str) -> str:
    """Call Anthropic API directly (no LangChain dependency in this utility)."""
    import urllib.request
    import json

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Export it in your shell:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )

    payload = {
        "model": "claude-opus-4-5",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read())

    return body["content"][0]["text"]


def build_prompt(
    project_name: str,
    changed_file: str,
    project_context: str,
    existing_readme: str,
) -> str:
    return f"""You are a technical documentation agent. Your job is to maintain a living README.md for a software project.

A file was just modified:
  Changed file: {changed_file}
  Project: {project_name}
  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Here is the current source code of the project:
<source_code>
{project_context}
</source_code>

Here is the current README (may be empty or outdated):
<current_readme>
{existing_readme}
</current_readme>

Rewrite the README.md to reflect the current state of the project. Follow this structure exactly:

---

# [Project name]
> One sentence: what this project does and who it's for.

## What it does
2-3 sentences explaining the core capability. Plain English. No jargon.

## Why it exists
Explain the purpose within the 5-project portfolio system. How does it connect to other projects? What problem does it solve?

## System flow

Produce a complete ASCII diagram of how the entire application works. This is the most important section — do it thoroughly.

The diagram must trace EVERY path through the code:
- All entry points (HTTP endpoints, UI events, button clicks, CLI commands)
- Every function that is called, in order, for each path
- All branching logic (if/else, conditionals) shown as decision points
- Recursive calls and loops explicitly labelled
- Every LangChain chain: show each step in the chain (prompt → LLM → parser)
- Every external API call labelled with the provider and model (e.g. ═══► OpenAI gpt-4o)
- Every read from or write to a database or file, labelled with the storage target
- Data transformations: show what type goes in and what type comes out at key steps

Use this symbol set consistently:

  [Component / Function]        — a box for any named function, class, or UI element
  ──────────────────────        — a horizontal separator between flows
  │                             — vertical flow (down)
  ▼                             — arrow pointing down (next step)
  ├─►  [Branch]                 — a branch that also continues below
  └─►  [Terminal branch]        — the last branch (nothing below)
  ═══► ExternalService          — external API call (OpenAI, etc.)
  ───► file/db                  — storage read or write
  ? condition                   — a decision point / conditional
  ↩ recurse                     — recursive call back to a previous step
  [not yet built]               — placeholder for components that don't exist yet

Draw a SEPARATE flow for each distinct entry point. For example:

  ┌─────────────────────────────────────────────────┐
  │  FLOW 1: User sends a chat message              │
  └─────────────────────────────────────────────────┘
  [User types in st.chat_input]
       │
       ▼
  [_get_system_prompt()]
       ├─► [profile_store.load()]  ───► READ  SQLite user_profile
       └─► [build_system_prompt(profile, topic)]
                │
                ▼
           Returns: str (system prompt with learner profile injected)
       │
       ▼
  [memory.to_langchain_messages()]
       └─► Returns: [SystemMessage(summary)] + [HumanMessage, AIMessage, ...]
       │
       ▼
  [llm.invoke(messages)]  ═══► OpenAI gpt-4o  (~1K–2K tokens)
       └─► Returns: AIMessage
       │
       ▼
  [memory.save_context(user_input, response)]
       ├─► Appends HumanMessage + AIMessage to buffer
       └─► ? buffer tokens > 2000
              └─► [_summarize_oldest()]
                       └─► [llm.invoke([HumanMessage("Summarize...")])]  ═══► OpenAI gpt-4o
                                └─► Replaces oldest messages with summary string
       │
       ▼
  [save_memory(memory)]  ───► WRITE  memory/session_memory.json
       │
       ▼
  [_maybe_run_inference()]
       └─► ? turn_count % 3 == 0  AND  len(messages) >= 4  AND  topic set
              └─► [infer_style(topic, messages, llm)]
                       ... (continue tracing this sub-flow)

Draw each flow completely. Don't stop mid-chain. Don't summarise with "etc."
After all the individual flows, add a COMPONENT MAP that shows every module and
what it imports/calls, laid out as a dependency tree.

## Architecture
High-level description of the system design. Refer back to the flow diagram above.
Include:
- Why major design decisions were made (e.g. "SQLite not Postgres because...")
- How state is managed across requests

## Tech stack
List every tool/library used with a one-line reason WHY it was chosen over alternatives.
Format: `tool` — reason it was chosen

## Key decisions
For each non-obvious technical choice, explain:
- What was decided
- What alternatives were considered
- Why this choice was made

## How to run locally
Step-by-step. Assume a fresh machine. Include env var setup.

## How to deploy
GCP deployment steps. Include Cloud Run URL once deployed.

## Project status
Current state: what works, what's in progress, what's not started yet.

## Part of a larger system
How this project fits into the ai-projects portfolio. What it depends on, what depends on it.

---

Rules:
- Write in plain English. Explain the WHY behind every decision, not just the WHAT.
- The System flow section is REQUIRED and must be complete — do not skip or abbreviate it.
- If a component doesn't exist yet, say "[not yet built]" — don't invent things.
- If you're updating an existing README, always regenerate the System flow from scratch using the current source code. Never copy the old diagram — it may be stale.
- Output ONLY the raw markdown. No preamble, no explanation, no code fences around the whole thing.
"""


def update_readme(project_root: Path, changed_file: str) -> None:
    project_name = project_root.name
    print(f"[doc-agent] Updating README for {project_name} (triggered by {changed_file})")

    project_context = collect_project_context(project_root)
    existing_readme = read_existing_readme(project_root)

    prompt = build_prompt(
        project_name=project_name,
        changed_file=changed_file,
        project_context=project_context,
        existing_readme=existing_readme,
    )

    new_readme = call_anthropic(prompt)

    readme_path = project_root / "README.md"
    readme_path.write_text(new_readme, encoding="utf-8")
    print(f"[doc-agent] README updated: {readme_path}")


def get_files_from_last_commit() -> list[str]:
    """
    Ask git for the list of files that were part of the most recent commit.
    Returns a list of file path strings, e.g. ["p1-personal-tutor/chains/quiz_chain.py"].
    If git isn't available or there are no commits yet, returns an empty list.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def was_git_commit(stdin_json: dict) -> bool:
    """
    The Bash hook passes {"command": "git commit ..."} in its stdin JSON.
    Return True if the command was a git commit (any form).
    """
    command = stdin_json.get("command", "")
    return "git commit" in command or "git" in command and "commit" in command


def main():
    import json

    # ── Mode 1: manual run ────────────────────────────────────────────────────
    # User ran:  python .claude/scripts/doc_agent.py path/to/file.py
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        changed_file = sys.argv[1].strip()
        if should_skip(changed_file):
            print(f"[doc-agent] Skipping {changed_file} (matches skip list)")
            sys.exit(0)
        project_root = find_project_root(changed_file)
        if project_root is None:
            print(f"[doc-agent] {changed_file} is not inside a known project — skipping.")
            sys.exit(0)
        try:
            update_readme(project_root, changed_file)
        except RuntimeError as e:
            print(f"[doc-agent] WARNING: {e}")
        except Exception as e:
            print(f"[doc-agent] ERROR: {e}")
        sys.exit(0)

    # ── Mode 2: Claude Code PostToolUse hook ──────────────────────────────────
    # Claude Code sends the tool's input as JSON via stdin for every hook call.
    #
    # Write / Edit / MultiEdit → stdin contains {"file_path": "...", ...}
    # Bash (git commit)        → stdin contains {"command": "git commit ..."}
    #
    # We handle both here. The $CLAUDE_TOOL_INPUT_FILE_PATH env-var approach
    # was removed because it does not expand reliably on Windows.
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    # ── Write / Edit / MultiEdit path ─────────────────────────────────────────
    file_path = data.get("file_path", "").strip()
    if file_path:
        if should_skip(file_path):
            print(f"[doc-agent] Skipping {file_path} (matches skip list)")
            sys.exit(0)
        project_root = find_project_root(file_path)
        if project_root is None:
            print(f"[doc-agent] {file_path} is not inside a known project — skipping.")
            sys.exit(0)
        try:
            update_readme(project_root, file_path)
        except RuntimeError as e:
            print(f"[doc-agent] WARNING: {e}")
        except Exception as e:
            print(f"[doc-agent] ERROR: {e}")
        sys.exit(0)

    # ── Bash / git commit path ────────────────────────────────────────────────
    if not was_git_commit(data):
        sys.exit(0)

    print("[doc-agent] git commit detected — checking for project file changes...")

    changed_files = get_files_from_last_commit()
    if not changed_files:
        print("[doc-agent] No changed files found in last commit — skipping.")
        sys.exit(0)

    projects_to_update: dict[Path, str] = {}
    for f in changed_files:
        if should_skip(f):
            continue
        root = find_project_root(f)
        if root is not None and root not in projects_to_update:
            projects_to_update[root] = f

    if not projects_to_update:
        print("[doc-agent] No known-project files in this commit — skipping.")
        sys.exit(0)

    for project_root, representative_file in projects_to_update.items():
        try:
            update_readme(project_root, representative_file)
        except RuntimeError as e:
            print(f"[doc-agent] WARNING: {e}")
        except Exception as e:
            print(f"[doc-agent] ERROR: {e}")


if __name__ == "__main__":
    main()
