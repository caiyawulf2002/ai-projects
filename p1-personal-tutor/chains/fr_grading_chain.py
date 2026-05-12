"""Free response grading chain.

Grades a learner's free-text answer against a question's key_concepts and
sample_answer.  Returns a GradeResult with a 0.0–1.0 score, direct feedback,
and lists of matched vs. missing concepts.

Chain: ChatPromptTemplate | llm | OutputFixingParser[GradeResult]
"""
from __future__ import annotations

from langchain_classic.output_parsers import OutputFixingParser
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from models.quiz_models import GradeResult

_GRADING_TEMPLATE = """\
You are grading a free response answer from a learner.

Question: {question}

Key concepts the ideal answer must address:
{key_concepts}

Sample ideal answer:
{sample_answer}

Learner's answer:
{user_answer}

---
Grade the learner's answer strictly:
1. matched_concepts: key concepts they correctly addressed
2. missing_concepts: key concepts they missed or got wrong
3. score: 0.0–1.0 (1.0 = all key concepts correctly addressed; partial credit allowed)
4. feedback: 1-2 sentences — direct, specific, no padding

{format_instructions}

Respond with ONLY the JSON object — no prose, no markdown fences."""


def build_fr_grading_chain(llm: ChatOpenAI) -> Runnable:
    primary: PydanticOutputParser[GradeResult] = PydanticOutputParser(pydantic_object=GradeResult)
    fixing = OutputFixingParser.from_llm(parser=primary, llm=llm)
    prompt = ChatPromptTemplate.from_template(_GRADING_TEMPLATE)
    return prompt | llm | fixing


def grade_fr_answer(
    question: str,
    key_concepts: list[str],
    sample_answer: str,
    user_answer: str,
    llm: ChatOpenAI,
) -> GradeResult:
    """Grade a free response answer and return a validated GradeResult."""
    chain = build_fr_grading_chain(llm)
    primary: PydanticOutputParser[GradeResult] = PydanticOutputParser(pydantic_object=GradeResult)
    return chain.invoke({
        "question": question,
        "key_concepts": "\n".join(f"- {c}" for c in key_concepts),
        "sample_answer": sample_answer,
        "user_answer": user_answer,
        "format_instructions": primary.get_format_instructions(),
    })
