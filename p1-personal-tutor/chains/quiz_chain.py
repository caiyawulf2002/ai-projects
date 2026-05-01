"""Quiz scoring chain.

Given a topic and a formatted quiz conversation, asks the LLM to evaluate
the learner's performance and returns a validated QuizResult via
PydanticOutputParser.  OutputFixingParser is registered as the fallback —
if the primary parse fails, the chain re-prompts the LLM to correct its own
malformed JSON before raising.
"""
from __future__ import annotations

from datetime import date

from langchain_classic.output_parsers import OutputFixingParser
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from models.quiz_models import QuizResult

_SCORING_TEMPLATE = """\
You are evaluating a quiz conversation between a learner and an AI tutor.

Topic: {topic}
Today's date: {today}

Quiz conversation:
{conversation}

---
Analyse the conversation above and produce a structured evaluation.
Count how many distinct questions were asked and estimate the learner's
percentage score (0–100) based on correctness, completeness, and reasoning
quality.  List the specific sub-topics or concepts the learner struggled
with in weak_areas (empty list if none).

{format_instructions}

Respond with ONLY the JSON object — no prose, no markdown fences."""


def build_quiz_scoring_chain(llm: ChatOpenAI) -> Runnable:
    """Return a runnable chain: dict → QuizResult.

    Input keys expected:
        topic        (str)  — the subject being quizzed
        conversation (str)  — newline-joined "Role: message" pairs

    OutputFixingParser wraps PydanticOutputParser so a single malformed LLM
    response triggers one repair attempt before raising OutputParserException.
    """
    primary_parser: PydanticOutputParser[QuizResult] = PydanticOutputParser(
        pydantic_object=QuizResult
    )
    fixing_parser: OutputFixingParser = OutputFixingParser.from_llm(
        parser=primary_parser, llm=llm
    )

    prompt = ChatPromptTemplate.from_template(_SCORING_TEMPLATE)

    chain: Runnable = prompt | llm | fixing_parser
    return chain


def format_conversation(messages: list[dict]) -> str:
    """Convert the session_memory message list into a readable transcript."""
    lines: list[str] = []
    for m in messages:
        role = "Learner" if m.get("role") == "human" else "Tutor"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def score_quiz(
    topic: str,
    messages: list[dict],
    llm: ChatOpenAI,
) -> QuizResult:
    """Run the scoring chain and return a QuizResult.

    Args:
        topic:    Subject label for this quiz (e.g. "Python generators").
        messages: Raw session_memory message dicts with 'role' and 'content'.
        llm:      Shared ChatOpenAI instance.
    """
    chain = build_quiz_scoring_chain(llm)
    primary_parser: PydanticOutputParser[QuizResult] = PydanticOutputParser(
        pydantic_object=QuizResult
    )
    result: QuizResult = chain.invoke(
        {
            "topic": topic,
            "today": date.today().isoformat(),
            "conversation": format_conversation(messages),
            "format_instructions": primary_parser.get_format_instructions(),
        }
    )
    return result
