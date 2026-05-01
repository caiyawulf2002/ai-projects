from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from models.style_models import TopicStyle


class UserProfile(BaseModel):
    """Learner profile that drives adaptive system prompt generation.

    Global fields (learning_style, preferred_pace, explanation_style) are the
    baseline set once during profile setup.  topic_styles holds per-topic
    overrides inferred automatically from conversation behaviour — these take
    precedence over the globals when the current topic is known.
    """

    learning_style: Literal["visual", "auditory", "reading", "kinesthetic"] = Field(
        description="How the learner best absorbs new material (global default)"
    )
    preferred_pace: Literal["fast", "medium", "slow"] = Field(
        description="How quickly to progress through new concepts (global default)"
    )
    explanation_style: Literal[
        "analogies", "step_by_step", "examples_first", "theory_first"
    ] = Field(description="Preferred explanation approach (global default)")
    weak_topics: list[str] = Field(
        default_factory=list,
        description="Topics scoring below 70% — updated automatically after each quiz",
    )
    strong_topics: list[str] = Field(
        default_factory=list,
        description="Topics the learner has demonstrated mastery in",
    )
    # Keys are normalised topic names (lower-stripped). Values override the
    # global defaults for that topic only.
    topic_styles: dict[str, TopicStyle] = Field(
        default_factory=dict,
        description="Per-topic style overrides inferred from conversation behaviour",
    )
