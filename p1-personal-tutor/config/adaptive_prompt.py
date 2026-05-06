"""Adaptive system prompt builder.

build_system_prompt() performs a targeted string substitution of
{learner_profile} inside TUTOR_SYSTEM_PROMPT, leaving every other {…} token
untouched (they are syllabus format hints shown to the LLM, not Python format
fields).

When a topic is supplied and the profile has observed style data for that
topic, the per-topic overrides replace the global defaults.  The LLM is also
told the confidence level so it understands whether the per-topic style is
established (high confidence) or still provisional (low confidence).
"""
from __future__ import annotations

from config.prompts import TUTOR_SYSTEM_PROMPT
from models.style_models import TopicStyle
from models.user_profile import UserProfile

_PACE_LABELS: dict[str, str] = {
    "fast": "Move quickly — skip basics I already know, challenge me.",
    "medium": "Balanced pace — explain the why but don't over-explain.",
    "slow": "Go slowly — check my understanding at every step.",
}

_STYLE_LABELS: dict[str, str] = {
    "analogies": "Use real-world analogies before introducing formal terms.",
    "step_by_step": "Walk through every step sequentially with no jumps.",
    "examples_first": "Show a working example first, then explain the mechanics.",
    "theory_first": "Give me the theory and motivation before any code.",
}

_LEARNING_LABELS: dict[str, str] = {
    "visual": "Prefer diagrams, tables, and structured layouts when possible.",
    "auditory": "Explain as if talking aloud — conversational and rhythmic.",
    "reading": "Dense, precise text is fine — I learn by reading carefully.",
    "kinesthetic": "Give me things to build or break immediately.",
}


def build_system_prompt(profile: UserProfile, topic: str | None = None) -> str:
    """Inject UserProfile fields into the TUTOR_SYSTEM_PROMPT template.

    Args:
        profile: The full UserProfile (global defaults + per-topic overrides).
        topic:   The topic currently being studied, if known.  When supplied
                 and a TopicStyle exists for that topic, per-topic values
                 replace global defaults.  Pass None to use global defaults
                 unconditionally.

    Returns:
        Fully rendered system prompt string ready to pass to the LLM.
    """
    profile_block = _render_profile_block(profile, topic)
    return TUTOR_SYSTEM_PROMPT.replace("{learner_profile}", profile_block)


# ── resolution ─────────────────────────────────────────────────────────────────

def _resolve_styles(
    profile: UserProfile, topic: str | None
) -> tuple[str, str, str, TopicStyle | None]:
    """Return (learning_style, pace, explanation_style, topic_style_or_None).

    Each dimension is taken from the topic-specific override if one exists and
    is non-None; otherwise the global default is used.
    """
    ts: TopicStyle | None = None
    if topic:
        ts = profile.topic_styles.get(topic.lower().strip())

    ls = (ts.learning_style if ts and ts.learning_style else None) or profile.learning_style
    pace = (ts.preferred_pace if ts and ts.preferred_pace else None) or profile.preferred_pace
    es = (
        (ts.explanation_style if ts and ts.explanation_style else None)
        or profile.explanation_style
    )

    return ls, pace, es, ts


# ── rendering ──────────────────────────────────────────────────────────────────

def _render_profile_block(profile: UserProfile, topic: str | None = None) -> str:
    """Render the learner profile as a multi-line plain-text block for the LLM.

    Resolves effective style values (topic override > global default), formats
    them with human-readable label text, and appends a per-topic confidence
    note when a topic override exists.

    Args:
        profile: Full UserProfile (global defaults + per-topic overrides).
        topic:   Current topic, or None to use global defaults only.

    Returns:
        Multi-line string injected into the {learner_profile} slot of the
        system prompt.
    """
    ls, pace, es, ts = _resolve_styles(profile, topic)

    weak = (
        "None identified yet."
        if not profile.weak_topics
        else ", ".join(profile.weak_topics)
    )
    strong = (
        "None recorded yet."
        if not profile.strong_topics
        else ", ".join(profile.strong_topics)
    )

    lines = [
        f"Learning style: {ls} — {_LEARNING_LABELS[ls]}",
        f"Preferred pace: {pace} — {_PACE_LABELS[pace]}",
        f"Explanation style: {es} — {_STYLE_LABELS[es]}",
        f"Weak topics (score < 70, resurface these): {weak}",
        f"Strong topics (learner has demonstrated mastery): {strong}",
    ]

    # Append per-topic context so the LLM understands the source and certainty.
    if topic and ts:
        confidence_pct = int(ts.confidence * 100)
        overridden_dims = [
            dim
            for dim, val in [
                ("learning style", ts.learning_style),
                ("pace", ts.preferred_pace),
                ("explanation style", ts.explanation_style),
            ]
            if val is not None
        ]
        if overridden_dims:
            certainty = (
                "established from repeated observation"
                if ts.confidence >= 0.8
                else f"provisional — only {ts.sample_count} observation(s) so far"
            )
            lines.append(
                f"\nCurrent topic: {topic}"
            )
            lines.append(
                f"Topic-specific overrides ({certainty}, confidence {confidence_pct}%): "
                + ", ".join(overridden_dims)
            )
            lines.append(
                "Apply the overrides above for this topic. "
                "If confidence is low, lean toward them but stay flexible."
            )
        else:
            lines.append(
                f"\nCurrent topic: {topic} — no topic-specific style data yet "
                f"(global defaults in use; will adapt as conversation continues)."
            )

    return "\n".join(lines)
