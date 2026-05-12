"""Socratic opener chain.

When a learner revisits an archived conversation, generates one targeted
retrieval question about their weakest topic.  Fires once per revisit so
the learner is immediately challenged to recall rather than just re-read.

Chain: ChatPromptTemplate | llm | StrOutputParser
"""
from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

_OPENER_TEMPLATE = """\
You are a Socratic tutor. The learner has returned to a past conversation.
They previously scored below 70% on these topics: {weak_topics}

Generate ONE concise retrieval question targeting the most specific concept
from the first topic in that list. Do not quiz the entire topic — pick one
concrete thing they likely half-remember.

Rules:
- Ask about ONE specific concept, not the whole topic
- Phrase it as a genuine question, not a quiz header
- Do not explain, hint, or preface — just ask
- 1-2 sentences maximum

Respond with ONLY the question text — no preamble, no label."""


def build_socratic_opener_chain(llm: ChatOpenAI):
    prompt = ChatPromptTemplate.from_template(_OPENER_TEMPLATE)
    return prompt | llm | StrOutputParser()


def generate_socratic_opener(weak_topics: list[str], llm: ChatOpenAI) -> str:
    """Return a single Socratic retrieval question for the learner's weakest topic."""
    chain = build_socratic_opener_chain(llm)
    return chain.invoke({"weak_topics": ", ".join(weak_topics)})
