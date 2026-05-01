from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TopicStyle(BaseModel):
    """Inferred style preferences for one specific topic.

    Fields are Optional — None means "no signal observed yet for this
    dimension". The prompt builder falls back to the global UserProfile
    default for any None field.
    """

    learning_style: Literal["visual", "auditory", "reading", "kinesthetic"] | None = None
    preferred_pace: Literal["fast", "medium", "slow"] | None = None
    explanation_style: (
        Literal["analogies", "step_by_step", "examples_first", "theory_first"] | None
    ) = None
    # 0.0–1.0: reaches 1.0 after 5 observations; used by the prompt to
    # signal whether this override is established or still provisional.
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sample_count: int = Field(default=0, ge=0)


class StyleSignal(BaseModel):
    """Structured output from the style inference chain.

    Each inferred_* field is None when the LLM found no clear signal for
    that dimension in the recent conversation.  The chain is instructed to
    prefer None over a low-confidence guess.
    """

    inferred_learning_style: (
        Literal["visual", "auditory", "reading", "kinesthetic"] | None
    ) = Field(
        default=None,
        description=(
            "Inferred learning style from behavioral cues, or null if no clear signal"
        ),
    )
    inferred_pace: Literal["fast", "medium", "slow"] | None = Field(
        default=None,
        description="Inferred pace preference, or null if no clear signal",
    )
    inferred_explanation_style: (
        Literal["analogies", "step_by_step", "examples_first", "theory_first"] | None
    ) = Field(
        default=None,
        description="Inferred explanation style preference, or null if no clear signal",
    )
    reasoning: str = Field(
        description=(
            "Brief one-sentence explanation of which specific signals led to each "
            "inference. If all fields are null, explain why no signal was found."
        )
    )
