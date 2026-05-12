"""Quiz generation chains.

Two LCEL chains: MC (multiple choice) and FR (free response).
Each chain is: ChatPromptTemplate | llm | OutputFixingParser[MCQuiz | FRQuiz].

The learner's weak areas (from past quiz_results) and learning style are
injected so generated questions target actual gaps and match how they learn.
"""
from __future__ import annotations

from langchain_classic.output_parsers import OutputFixingParser
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from models.quiz_models import FRQuiz, MCQuiz

_MC_TEMPLATE = """\
Generate a multiple choice quiz about: {topic}

Learner context:
- Learning style: {learning_style}
- Past weak areas to prioritise: {weak_areas}

Create exactly {n_questions} questions. Requirements for each:
- One clear, specific question (no trivially obvious answers)
- Exactly 4 options with keys A, B, C, D — one correct, three plausible distractors
- correct_key field set to the right option key
- A 1-2 sentence explanation of WHY the correct answer is right

Cover different facets of {topic}. Do not repeat questions.

{format_instructions}

Respond with ONLY the JSON object — no prose, no markdown fences."""

_FR_TEMPLATE = """\
Generate a free response quiz about: {topic}

Learner context:
- Learning style: {learning_style}
- Past weak areas to prioritise: {weak_areas}

Create exactly {n_questions} questions. Requirements for each:
- One clear, specific question requiring a few sentences to answer well
- 3-5 key_concepts the ideal answer must address
- A sample_answer (2-4 sentences demonstrating an ideal response)

Cover different facets of {topic}. Do not repeat questions.

{format_instructions}

Respond with ONLY the JSON object — no prose, no markdown fences."""


def build_mc_quiz_chain(llm: ChatOpenAI) -> Runnable:
    primary: PydanticOutputParser[MCQuiz] = PydanticOutputParser(pydantic_object=MCQuiz)
    fixing = OutputFixingParser.from_llm(parser=primary, llm=llm)
    prompt = ChatPromptTemplate.from_template(_MC_TEMPLATE)
    return prompt | llm | fixing


def build_fr_quiz_chain(llm: ChatOpenAI) -> Runnable:
    primary: PydanticOutputParser[FRQuiz] = PydanticOutputParser(pydantic_object=FRQuiz)
    fixing = OutputFixingParser.from_llm(parser=primary, llm=llm)
    prompt = ChatPromptTemplate.from_template(_FR_TEMPLATE)
    return prompt | llm | fixing


def generate_mc_quiz(
    topic: str,
    n_questions: int,
    llm: ChatOpenAI,
    learning_style: str = "reading",
    weak_areas: list[str] | None = None,
) -> MCQuiz:
    """Generate an MCQuiz for the given topic and return validated Pydantic model."""
    chain = build_mc_quiz_chain(llm)
    primary: PydanticOutputParser[MCQuiz] = PydanticOutputParser(pydantic_object=MCQuiz)
    return chain.invoke({
        "topic": topic,
        "n_questions": n_questions,
        "learning_style": learning_style,
        "weak_areas": ", ".join(weak_areas) if weak_areas else "none identified yet",
        "format_instructions": primary.get_format_instructions(),
    })


def generate_fr_quiz(
    topic: str,
    n_questions: int,
    llm: ChatOpenAI,
    learning_style: str = "reading",
    weak_areas: list[str] | None = None,
) -> FRQuiz:
    """Generate an FRQuiz for the given topic and return validated Pydantic model."""
    chain = build_fr_quiz_chain(llm)
    primary: PydanticOutputParser[FRQuiz] = PydanticOutputParser(pydantic_object=FRQuiz)
    return chain.invoke({
        "topic": topic,
        "n_questions": n_questions,
        "learning_style": learning_style,
        "weak_areas": ", ".join(weak_areas) if weak_areas else "none identified yet",
        "format_instructions": primary.get_format_instructions(),
    })
