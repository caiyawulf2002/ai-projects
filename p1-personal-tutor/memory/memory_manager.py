"""Conversation memory management for P1.

Implements a summary-buffer hybrid: recent exchanges are kept verbatim in
memory.messages; once the buffer exceeds max_token_limit the oldest half is
compressed into a running summary via an LLM call.

Persistence layout (per session UUID):
  memory/<session_id>/session_memory.json       — active session
  memory/<session_id>/conversations/<ts>.json   — archived past sessions
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

# TUTOR_MEMORY_PATH is set in Dockerfile to /tmp/tutor-memory so Cloud Run's
# ephemeral /tmp (always writable) is used instead of the app image directory.
_MEMORY_BASE = Path(os.environ.get("TUTOR_MEMORY_PATH", str(Path(__file__).parent)))


def _session_paths(session_id: str) -> tuple[Path, Path]:
    """Return (active_path, conversations_dir) scoped to this session's UUID.

    Args:
        session_id: UUID string identifying the browser session.

    Returns:
        Tuple of (session_memory.json path, conversations/ directory path),
        both rooted under memory/<session_id>/.
    """
    session_dir = _MEMORY_BASE / session_id
    return session_dir / "session_memory.json", session_dir / "conversations"


@dataclass
class SessionMemory:
    """Summary-buffer hybrid memory.

    Keeps recent exchanges verbatim; once the buffer exceeds max_token_limit,
    oldest messages are compressed into a running summary via LLM call.
    Mirrors the behaviour of the removed LangChain ConversationSummaryBufferMemory.
    """
    llm: ChatOpenAI
    max_token_limit: int = 2000
    summary: str = ""
    messages: list[dict] = field(default_factory=list)  # {"role": "human"|"ai", "content": str}

    def _estimate_tokens(self) -> int:
        """Rough token estimate: (summary chars + all message chars) / 4."""
        total = len(self.summary)
        for m in self.messages:
            total += len(m["content"])
        return total // 4  # rough 4-chars-per-token estimate

    def _summarize_oldest(self) -> None:
        """Compress the oldest half of the buffer into the running summary.

        Makes one LLM call to produce a concise summary of the oldest half of
        self.messages, appends it to self.summary, and drops those messages
        from the buffer.  The LLM is given the existing summary as context so
        the new summary is cumulative, not a replacement.
        """
        half = len(self.messages) // 2
        to_compress = self.messages[:half]
        self.messages = self.messages[half:]

        history_text = "\n".join(
            f"{'User' if m['role'] == 'human' else 'Assistant'}: {m['content']}"
            for m in to_compress
        )
        prompt = (
            f"Summarize this conversation excerpt concisely, preserving key facts "
            f"and concepts the learner demonstrated or asked about.\n\n"
            f"Existing summary: {self.summary or '(none)'}\n\n"
            f"New exchanges to incorporate:\n{history_text}"
        )
        result = self.llm.invoke([HumanMessage(content=prompt)])
        self.summary = result.content

    def save_context(self, user_input: str, ai_output: str) -> None:
        """Append a user/assistant exchange and compress if over the token limit.

        Args:
            user_input: The raw user message text.
            ai_output:  The assistant reply text.

        Side effects:
            May trigger an LLM call to summarise overflow messages.
        """
        self.messages.append({"role": "human", "content": user_input})
        self.messages.append({"role": "ai", "content": ai_output})
        if self._estimate_tokens() > self.max_token_limit:
            self._summarize_oldest()

    def to_langchain_messages(self) -> list:
        """Return [SystemMessage(summary)] + buffer as LangChain message objects."""
        result = []
        if self.summary:
            result.append(SystemMessage(content=f"[Prior conversation summary: {self.summary}]"))
        for m in self.messages:
            if m["role"] == "human":
                result.append(HumanMessage(content=m["content"]))
            else:
                result.append(AIMessage(content=m["content"]))
        return result

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict (summary + messages)."""
        return {"summary": self.summary, "messages": self.messages}

    @classmethod
    def from_dict(cls, data: dict, llm: ChatOpenAI, max_token_limit: int = 2000) -> "SessionMemory":
        """Reconstruct a SessionMemory from a previously serialised dict.

        Args:
            data:            Dict with 'summary' and 'messages' keys.
            llm:             ChatOpenAI instance for future compression calls.
            max_token_limit: Token threshold before compression triggers.
        """
        return cls(
            llm=llm,
            max_token_limit=max_token_limit,
            summary=data.get("summary", ""),
            messages=data.get("messages", []),
        )


# ── persistence ────────────────────────────────────────────────────────────────

def load_memory(llm: ChatOpenAI, session_id: str, max_token_limit: int = 2000) -> SessionMemory:
    """Load the active session from disk, or return a fresh SessionMemory.

    Args:
        llm:             ChatOpenAI instance attached to the SessionMemory.
        session_id:      UUID identifying the browser session.
        max_token_limit: Token budget before the buffer is compressed.

    Returns:
        Reconstructed SessionMemory if the session file exists, else empty.
    """
    active_path, _ = _session_paths(session_id)
    if active_path.exists():
        data = json.loads(active_path.read_text())
        return SessionMemory.from_dict(data, llm, max_token_limit)
    return SessionMemory(llm=llm, max_token_limit=max_token_limit)


def save_memory(memory: SessionMemory, session_id: str) -> None:
    """Overwrite the session's active memory file with the current state.

    Args:
        memory:     The active SessionMemory to persist.
        session_id: UUID identifying the browser session.
    """
    active_path, _ = _session_paths(session_id)
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(json.dumps(memory.to_dict(), indent=2))


def archive_and_reset(memory: SessionMemory, session_id: str) -> None:
    """Move the current session to the session's conversations/ dir and clear it.

    The archive filename is an ISO timestamp; the title is the first 80 chars
    of the first human message.  Does nothing if the session has no messages.

    Args:
        memory:     The SessionMemory to archive.
        session_id: UUID identifying the browser session.

    Side effects:
        Writes a new file under memory/<session_id>/conversations/ and clears
        memory/<session_id>/session_memory.json.
    """
    if not memory.messages:
        return
    active_path, conversations_dir = _session_paths(session_id)
    conversations_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    first_human = next((m["content"] for m in memory.messages if m["role"] == "human"), "Untitled")
    archive = {
        "id": timestamp,
        "title": first_human[:80],
        "created_at": datetime.now().isoformat(),
        **memory.to_dict(),
    }
    (conversations_dir / f"{timestamp}.json").write_text(json.dumps(archive, indent=2))
    active_path.write_text(json.dumps({"summary": "", "messages": []}, indent=2))


def list_conversations(session_id: str) -> list[dict]:
    """Return metadata for this session's archived conversations, newest first.

    Args:
        session_id: UUID identifying the browser session.

    Returns:
        List of dicts with keys: id, title, created_at.  Malformed files are
        silently skipped.  Only this session's conversations are returned.
    """
    _, conversations_dir = _session_paths(session_id)
    if not conversations_dir.exists():
        return []
    results = []
    for f in sorted(conversations_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            results.append({"id": data["id"], "title": data["title"], "created_at": data["created_at"]})
        except Exception:
            continue
    return results


def load_conversation(conv_id: str, llm: ChatOpenAI, session_id: str, max_token_limit: int = 2000) -> SessionMemory:
    """Load an archived conversation and make it the active session.

    Copies the archive's messages and summary into the session's active file
    so subsequent saves preserve the loaded context.

    Args:
        conv_id:         Timestamp-based ID (filename stem) of the archive.
        llm:             ChatOpenAI instance for the reconstructed SessionMemory.
        session_id:      UUID identifying the browser session.
        max_token_limit: Token budget for future compression.

    Returns:
        SessionMemory populated with the archived conversation.
    """
    active_path, conversations_dir = _session_paths(session_id)
    path = conversations_dir / f"{conv_id}.json"
    data = json.loads(path.read_text())
    memory = SessionMemory.from_dict(data, llm, max_token_limit)
    active_path.write_text(json.dumps(memory.to_dict(), indent=2))
    return memory
