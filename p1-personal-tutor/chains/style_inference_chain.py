"""Style inference chain.

After every N conversation turns, this chain analyses the learner's recent
follow-up questions to detect behavioural signals about their preferred
learning style, pace, and explanation style *for the current topic*.

Signals it looks for:
  - "give me an example" / "show me" / "demo"     → examples_first
  - "why does this work" / "what's the theory"     → theory_first
  - "step by step" / "break it down"               → step_by_step
  - "like X" / "an analogy"                        → analogies
  - "draw" / "diagram" / "visualise"               → visual
  - "let me read" / "link me"                      → reading
  - "let me try" / "let me build"                  → kinesthetic
  - Short acks ("got it", "ok", "next")            → fast pace
  - "explain more" / "I'm confused" / long Qs      → slow pace

The chain uses PydanticOutputParser so the result is always a validated
StyleSignal, never a raw string.  Inference failures are caught by the caller
and silently discarded — they must never surface to the user.
"""
from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from models.style_models import StyleSignal

_INFERENCE_TEMPLATE = """\
You are a learning-style analyst embedded inside an AI tutoring system.

Your job: given a short excerpt of a tutoring conversation, detect \
behavioural signals that reveal how this particular learner prefers to \
learn THIS specific topic.  You are NOT asking the learner — you are \
reading their behaviour.

Topic being studied: {topic}

Recent conversation (learner messages are the primary signal; \
tutor messages give context):
{conversation}

---
Analyse only the LEARNER'S messages.  Look for these signals:

Explanation style:
  - "give me an example", "show me", "demo" → examples_first
  - "why does this work?", "what's the motivation / theory behind?" → theory_first
  - "can you walk me through step by step?", "break it down" → step_by_step
  - "like X?", "is it similar to?", "an analogy" → analogies

Pace:
  - Short acks ("got it", "ok", "next", "makes sense, continue") → fast
  - "explain more", "I'm lost", "can you go slower", long clarification Qs → slow
  - Moderate engagement, occasional Qs → medium

Learning style:
  - "can you draw / diagram / visualise / show a table" → visual
  - "let me read more", "link me to", preferring written explanations → reading
  - "let me try", "let me build", "give me an exercise" → kinesthetic
  - Prefers conversational back-and-forth with no code → auditory

Rules:
  1. Only infer a field if there is a CLEAR, DIRECT signal.  One ambiguous
     message is not enough — you need at least two consistent signals.
  2. If unsure about a dimension, set it to null.  A wrong inference is
     worse than no inference.
  3. The reasoning field must name the SPECIFIC learner messages that
     produced each inference (quote a short phrase).

{format_instructions}

Respond with ONLY the JSON object — no prose, no markdown fences."""


def build_style_inference_chain(llm: ChatOpenAI) -> Runnable:
    """Return a runnable: dict → StyleSignal.

    Input keys:
        topic        (str) — the subject being studied
        conversation (str) — formatted transcript of recent messages
    """
    parser: PydanticOutputParser[StyleSignal] = PydanticOutputParser(
        pydantic_object=StyleSignal
    )
    prompt = ChatPromptTemplate.from_template(_INFERENCE_TEMPLATE)
    return prompt | llm | parser


def _format_recent(messages: list[dict], n_exchanges: int = 4) -> str:
    """Return the last n_exchanges (user + assistant pairs) as a readable string."""
    recent = messages[-(n_exchanges * 2):]
    lines: list[str] = []
    for m in recent:
        role = "Learner" if m.get("role") == "human" else "Tutor"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def infer_style(
    topic: str,
    messages: list[dict],
    llm: ChatOpenAI,
) -> StyleSignal:
    """Run the style inference chain and return a StyleSignal.

    Args:
        topic:    The topic currently being studied (e.g. "Python generators").
        messages: Raw session_memory message dicts with 'role' and 'content'.
        llm:      Shared ChatOpenAI instance.

    Raises:
        OutputParserException: if the LLM produces unparseable output.
        Any LLM / network error is propagated to the caller, which should
        catch and discard it silently.
    """
    chain = build_style_inference_chain(llm)
    parser: PydanticOutputParser[StyleSignal] = PydanticOutputParser(
        pydantic_object=StyleSignal
    )
    return chain.invoke(
        {
            "topic": topic,
            "conversation": _format_recent(messages, n_exchanges=4),
            "format_instructions": parser.get_format_instructions(),
        }
    )
