from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QuizResult(BaseModel):
    """Structured output from a single quiz session."""

    topic: str = Field(description="The subject that was quizzed")
    score: float = Field(ge=0, le=100, description="Percentage score 0–100")
    date: str = Field(description="ISO 8601 date string, e.g. 2026-04-28")
    question_count: int = Field(gt=0, description="Number of questions asked")
    weak_areas: list[str] = Field(
        default_factory=list,
        description="Specific sub-topics or concepts the learner struggled with",
    )


class MCOption(BaseModel):
    key: Literal["A", "B", "C", "D"]
    text: str


class MCQuestion(BaseModel):
    question: str
    options: list[MCOption] = Field(min_length=4, max_length=4)
    correct_key: Literal["A", "B", "C", "D"]
    explanation: str


class FRQuestion(BaseModel):
    question: str
    key_concepts: list[str] = Field(
        min_length=2,
        description="Concepts the ideal answer must address",
    )
    sample_answer: str


class MCQuiz(BaseModel):
    topic: str
    questions: list[MCQuestion]


class FRQuiz(BaseModel):
    topic: str
    questions: list[FRQuestion]


class GradeResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Score from 0.0 (wrong) to 1.0 (perfect)")
    feedback: str = Field(description="1-2 sentence direct, specific feedback")
    matched_concepts: list[str] = Field(
        default_factory=list,
        description="Key concepts the learner correctly addressed",
    )
    missing_concepts: list[str] = Field(
        default_factory=list,
        description="Key concepts the learner missed or got wrong",
    )
