#!/usr/bin/env python3
"""
Registry Agent
==============
Triggered automatically by Claude Code after every git commit (PostToolUse:Bash).
Reads the changed files, current registry.md, and recent git log, then calls
the Anthropic API to update the relevant project status blocks in registry.md.
Also syncs the project status table in CLAUDE_root.md.

Environment:
  ANTHROPIC_API_KEY — set in your shell or GCP Secret Manager

Usage (manual):
  python .claude/scripts/registry_agent.py
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent.parent
REGISTRY_PATH = REPO_ROOT / ".claude" / "registry.md"
CLAUDE_ROOT_PATH = REPO_ROOT / ".claude" / "CLAUDE_root.md"

PROJECT_DIRS = [
    "p1-personal-tutor",
    "p2-domain-intelligence",
    "p3-statements-analyzer",
    "p4-portfolio-optimizer",
    "p5-comps-agent",
    "edgar-mcp-server",
    "personal-os",
]

# Don't trigger on changes to these — they're meta or auto-generated
SKIP_PATTERNS = [
    "registry.md",
    "CLAUDE_root.md",
    "CLAUDE.md",
    ".claude/",
    ".git/",
    "__pycache__",
    ".pyc",
    ".env",
    "README.md",
]


def should_skip(file_path: str) -> bool:
    return any(p in file_path for p in SKIP_PATTERNS)


def get_changed_projects(files: list[str]) -> set[str]:
    projects = set()
    for f in files:
        for p in PROJECT_DIRS:
            if f.startswith(p + "/") or f.startswith(p + "\\"):
                projects.add(p)
    return projects


def git_log(n: int = 5) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", f"-{n}", "--oneline"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def git_last_commit_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "diff-tree", "--no-commit-id", "-r",
             "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return [l.strip() for l in result.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def git_last_commit_message() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "-1", "--pretty=%B"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def call_anthropic(prompt: str) -> str:
    import urllib.request

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")

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


def build_registry_prompt(
    projects_touched: set[str],
    changed_files: list[str],
    commit_message: str,
    recent_log: str,
    current_registry: str,
    today: str,
) -> str:
    return f"""You are a project registry agent. Your job is to keep registry.md accurate
after every git commit. You will update the status blocks for the projects that
were just touched.

Today's date: {today}
Commit message: {commit_message}

Files changed in this commit:
{chr(10).join(changed_files)}

Projects touched: {', '.join(projects_touched) if projects_touched else 'none identified'}

Recent git log:
{recent_log}

Current registry.md:
<registry>
{current_registry}
</registry>

Instructions:
- Update the status block for each project listed under "Projects touched"
- Update the Status line, the deployment table (Local/Docker/GCP/GitHub), and
  the "What's built" component table to reflect what was just committed
- Add a new bullet under "Last session notes" with today's date ({today}) and
  a concise description of what changed — one or two sentences max
- Update "Next steps" to remove anything that was just completed
- Do NOT touch status blocks for projects not in "Projects touched"
- Do NOT change the registry structure, headings, or any other sections
- Do NOT add commentary or explanation — output ONLY the updated registry.md,
  nothing else, no code fences
- Be specific: "Cloud Run deployed" not "deployment complete"

Output the full updated registry.md."""


def build_claude_root_prompt(
    current_claude_root: str,
    current_registry: str,
) -> str:
    return f"""You are a documentation sync agent. Your job is to keep the project status
table in CLAUDE_root.md in sync with the current state of registry.md.

Current CLAUDE_root.md:
<claude_root>
{current_claude_root}
</claude_root>

Current registry.md (source of truth for status):
<registry>
{current_registry}
</registry>

Instructions:
- Find the project status table in CLAUDE_root.md (the one with columns:
  ID | Name | Ships | Depends on | Status)
- Update the Status column for each project to match the current status emoji
  and label from registry.md
- Do NOT change anything else in CLAUDE_root.md — not the coordination rules,
  not the file structure, not the session checklist, nothing
- Output ONLY the updated CLAUDE_root.md, no preamble, no code fences"""


def update_registry(changed_files: list[str], commit_message: str) -> None:
    projects_touched = get_changed_projects(changed_files)
    meaningful_files = [f for f in changed_files if not should_skip(f)]

    if not meaningful_files and not projects_touched:
        print("[registry-agent] No project files changed — skipping registry update.")
        return

    print(f"[registry-agent] Projects touched: {projects_touched or 'inferring from commit'}")

    current_registry = REGISTRY_PATH.read_text(encoding="utf-8")
    recent_log = git_log(5)
    today = datetime.now().strftime("%Y-%m-%d")

    # Update registry.md
    registry_prompt = build_registry_prompt(
        projects_touched=projects_touched,
        changed_files=meaningful_files,
        commit_message=commit_message,
        recent_log=recent_log,
        current_registry=current_registry,
        today=today,
    )

    print("[registry-agent] Calling API to update registry.md...")
    updated_registry = call_anthropic(registry_prompt)
    REGISTRY_PATH.write_text(updated_registry, encoding="utf-8")
    print(f"[registry-agent] registry.md updated.")

    # Sync CLAUDE_root.md status table
    current_claude_root = CLAUDE_ROOT_PATH.read_text(encoding="utf-8")
    claude_root_prompt = build_claude_root_prompt(
        current_claude_root=current_claude_root,
        current_registry=updated_registry,
    )

    print("[registry-agent] Syncing CLAUDE_root.md status table...")
    updated_claude_root = call_anthropic(claude_root_prompt)
    CLAUDE_ROOT_PATH.write_text(updated_claude_root, encoding="utf-8")
    print("[registry-agent] CLAUDE_root.md synced.")


def main():
    import json

    # ── Mode 1: manual run ────────────────────────────────────────────────────
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        print("[registry-agent] Manual run — pulling files from last commit.")
        changed_files = git_last_commit_files()
        commit_message = git_last_commit_message()
        try:
            update_registry(changed_files, commit_message)
        except Exception as e:
            print(f"[registry-agent] ERROR: {e}")
        sys.exit(0)

    # ── Mode 2: Claude Code PostToolUse:Bash hook ─────────────────────────────
    # Only fires on git commit commands
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    command = data.get("command", "")
    is_commit = "git" in command and "commit" in command
    if not is_commit:
        sys.exit(0)

    print("[registry-agent] git commit detected — updating registry...")

    changed_files = git_last_commit_files()
    commit_message = git_last_commit_message()

    try:
        update_registry(changed_files, commit_message)
    except RuntimeError as e:
        print(f"[registry-agent] WARNING: {e}")
    except Exception as e:
        print(f"[registry-agent] ERROR: {e}")


if __name__ == "__main__":
    main()
