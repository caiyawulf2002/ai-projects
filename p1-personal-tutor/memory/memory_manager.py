import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

MEMORY_DIR = Path(__file__).parent
ACTIVE_PATH = MEMORY_DIR / "session_memory.json"
CONVERSATIONS_DIR = MEMORY_DIR / "conversations"


@dataclass
class SessionMemory:
    """
    Summary-buffer hybrid memory. Keeps recent exchanges verbatim; once the
    buffer exceeds max_token_limit, oldest messages are compressed into a
    running summary via LLM call. Mirrors the behavior of the removed
    LangChain ConversationSummaryBufferMemory.
    """
    llm: ChatOpenAI
    max_token_limit: int = 2000
    summary: str = ""
    messages: list[dict] = field(default_factory=list)  # {"role": "human"|"ai", "content": str}

    def _estimate_tokens(self) -> int:
        total = len(self.summary)
        for m in self.messages:
            total += len(m["content"])
        return total // 4  # rough 4-chars-per-token estimate

    def _summarize_oldest(self) -> None:
        """Compress the oldest half of the buffer into the running summary."""
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
        return {"summary": self.summary, "messages": self.messages}

    @classmethod
    def from_dict(cls, data: dict, llm: ChatOpenAI, max_token_limit: int = 2000) -> "SessionMemory":
        return cls(
            llm=llm,
            max_token_limit=max_token_limit,
            summary=data.get("summary", ""),
            messages=data.get("messages", []),
        )


# ── persistence ────────────────────────────────────────────────────────────────

def load_memory(llm: ChatOpenAI, max_token_limit: int = 2000) -> SessionMemory:
    if ACTIVE_PATH.exists():
        data = json.loads(ACTIVE_PATH.read_text())
        return SessionMemory.from_dict(data, llm, max_token_limit)
    return SessionMemory(llm=llm, max_token_limit=max_token_limit)


def save_memory(memory: SessionMemory) -> None:
    ACTIVE_PATH.write_text(json.dumps(memory.to_dict(), indent=2))


def archive_and_reset(memory: SessionMemory) -> None:
    if not memory.messages:
        return
    CONVERSATIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    first_human = next((m["content"] for m in memory.messages if m["role"] == "human"), "Untitled")
    archive = {
        "id": timestamp,
        "title": first_human[:80],
        "created_at": datetime.now().isoformat(),
        **memory.to_dict(),
    }
    (CONVERSATIONS_DIR / f"{timestamp}.json").write_text(json.dumps(archive, indent=2))
    ACTIVE_PATH.write_text(json.dumps({"summary": "", "messages": []}, indent=2))


def list_conversations() -> list[dict]:
    if not CONVERSATIONS_DIR.exists():
        return []
    results = []
    for f in sorted(CONVERSATIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            results.append({"id": data["id"], "title": data["title"], "created_at": data["created_at"]})
        except Exception:
            continue
    return results


def load_conversation(conv_id: str, llm: ChatOpenAI, max_token_limit: int = 2000) -> SessionMemory:
    path = CONVERSATIONS_DIR / f"{conv_id}.json"
    data = json.loads(path.read_text())
    memory = SessionMemory.from_dict(data, llm, max_token_limit)
    ACTIVE_PATH.write_text(json.dumps(memory.to_dict(), indent=2))
    return memory
