from __future__ import annotations

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
