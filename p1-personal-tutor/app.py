from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from chains.quiz_chain import score_quiz
from chains.style_inference_chain import infer_style
from config.adaptive_prompt import build_system_prompt
from config.prompts import TUTOR_SYSTEM_PROMPT
from db.profile_store import ProfileStore
from db.score_tracker import ScoreTracker
from memory.memory_manager import (
    SessionMemory,
    archive_and_reset,
    list_conversations,
    load_conversation,
    load_memory,
    save_memory,
)
from models.user_profile import UserProfile

load_dotenv()

st.set_page_config(page_title="P1 — Personal Tutor", layout="wide")

# Run style inference every N user turns when a topic is set.
_INFERENCE_EVERY_N_TURNS = 3

# ── singletons ─────────────────────────────────────────────────────────────────

@st.cache_resource
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o", temperature=0.7)


@st.cache_resource
def get_profile_store() -> ProfileStore:
    return ProfileStore()


@st.cache_resource
def get_score_tracker() -> ScoreTracker:
    return ScoreTracker()


llm = get_llm()
profile_store = get_profile_store()
score_tracker = get_score_tracker()

# ── session state init ─────────────────────────────────────────────────────────

if "memory" not in st.session_state:
    st.session_state.memory: SessionMemory = load_memory(llm)

if "display_messages" not in st.session_state:
    st.session_state.display_messages: list[tuple[str, str]] = []
    for msg in st.session_state.memory.messages:
        role = "user" if msg["role"] == "human" else "assistant"
        st.session_state.display_messages.append((role, msg["content"]))

if "page" not in st.session_state:
    st.session_state.page = "chat" if profile_store.load() else "profile_setup"

if "quiz_saved" not in st.session_state:
    st.session_state.quiz_saved: bool = False

# Counts user turns this session — controls inference trigger frequency.
if "turn_count" not in st.session_state:
    st.session_state.turn_count: int = 0

# Last inference result for display; reset when topic changes.
if "last_inference" not in st.session_state:
    st.session_state.last_inference: str = ""


# ── helpers ────────────────────────────────────────────────────────────────────

def _current_topic() -> str:
    """Return the normalised current topic, or empty string."""
    return st.session_state.get("current_topic_input", "").strip()


def _get_system_prompt() -> str:
    profile = profile_store.load()
    topic = _current_topic() or None
    if profile is None:
        return TUTOR_SYSTEM_PROMPT.replace(
            "{learner_profile}",
            "No profile set yet — ask the learner about their background.",
        )
    return build_system_prompt(profile, topic=topic)


def _maybe_run_inference() -> None:
    """Run the style inference chain if conditions are met; silently swallow all errors."""
    topic = _current_topic()
    if not topic:
        return
    if st.session_state.turn_count % _INFERENCE_EVERY_N_TURNS != 0:
        return
    if len(st.session_state.memory.messages) < 4:
        # Not enough conversation to infer from yet.
        return
    try:
        signal = infer_style(
            topic=topic,
            messages=st.session_state.memory.messages,
            llm=llm,
        )
        profile_store.update_topic_style(topic, signal)
        # Store reasoning for sidebar display.
        st.session_state.last_inference = signal.reasoning
    except Exception:
        pass  # inference must never break the chat


# ── profile setup page ─────────────────────────────────────────────────────────

def render_profile_setup(*, editing: bool = False) -> None:
    st.title("👤 Learner Profile Setup" if not editing else "⚙️ Edit Profile")
    st.caption(
        "These are your **global defaults** — the baseline the tutor uses for any topic. "
        "The tutor will also infer per-topic preferences automatically as you learn, "
        "and those override these defaults for that topic."
    )

    existing = profile_store.load()

    with st.form("profile_form"):
        learning_style = st.selectbox(
            "Learning style (default)",
            options=["visual", "auditory", "reading", "kinesthetic"],
            index=["visual", "auditory", "reading", "kinesthetic"].index(
                existing.learning_style if existing else "reading"
            ),
            help="How you best absorb new material — overridden per topic as the tutor learns your behaviour",
        )

        preferred_pace = st.selectbox(
            "Preferred pace (default)",
            options=["fast", "medium", "slow"],
            index=["fast", "medium", "slow"].index(
                existing.preferred_pace if existing else "medium"
            ),
            help="How quickly to move through new concepts",
        )

        explanation_style = st.selectbox(
            "Explanation style (default)",
            options=["analogies", "step_by_step", "examples_first", "theory_first"],
            index=["analogies", "step_by_step", "examples_first", "theory_first"].index(
                existing.explanation_style if existing else "examples_first"
            ),
            help="Preferred teaching approach",
        )

        submitted = st.form_submit_button("Save Profile", type="primary", use_container_width=True)

    if submitted:
        profile = UserProfile(
            learning_style=learning_style,  # type: ignore[arg-type]
            preferred_pace=preferred_pace,  # type: ignore[arg-type]
            explanation_style=explanation_style,  # type: ignore[arg-type]
            weak_topics=existing.weak_topics if existing else [],
            strong_topics=existing.strong_topics if existing else [],
            topic_styles=existing.topic_styles if existing else {},
        )
        profile_store.save(profile)
        st.success("Profile saved!")
        st.session_state.page = "chat"
        st.rerun()

    # Show learned topic styles for reference if editing.
    if editing and existing and existing.topic_styles:
        st.divider()
        st.subheader("Learned topic styles")
        st.caption(
            "These were inferred automatically from your conversation behaviour. "
            "They override the defaults above for each topic."
        )
        for topic, ts in existing.topic_styles.items():
            confidence_pct = int(ts.confidence * 100)
            overrides = {
                k: v
                for k, v in [
                    ("learning style", ts.learning_style),
                    ("pace", ts.preferred_pace),
                    ("explanation", ts.explanation_style),
                ]
                if v is not None
            }
            if overrides:
                with st.expander(f"**{topic.title()}** — {confidence_pct}% confidence"):
                    for dim, val in overrides.items():
                        st.write(f"- **{dim}:** {val}")
                    st.caption(f"{ts.sample_count} observation(s)")


# ── sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Conversations")

    if st.button("＋ New Chat", use_container_width=True):
        archive_and_reset(st.session_state.memory)
        st.session_state.memory = load_memory(llm)
        st.session_state.display_messages = []
        st.session_state.quiz_saved = False
        st.session_state.turn_count = 0
        st.session_state.last_inference = ""
        st.session_state.page = "chat"
        st.rerun()

    if st.button("⚙️ Profile Settings", use_container_width=True):
        st.session_state.page = "profile_setup"
        st.rerun()

    st.divider()

    # ── current topic (shared by quiz scoring + inference) ─────────────────────
    st.text_input(
        "Current topic",
        placeholder="e.g. Python generators",
        key="current_topic_input",
        help=(
            "Set this while studying a topic. "
            "The tutor will infer your preferred style for it automatically every "
            f"{_INFERENCE_EVERY_N_TURNS} turns, and use it to adapt explanations."
        ),
    )

    # Show what the tutor last inferred (visible feedback for the learner).
    if st.session_state.last_inference:
        st.caption(f"🔍 Last inference: {st.session_state.last_inference}")

    st.divider()

    # ── quiz scoring ───────────────────────────────────────────────────────────
    with st.expander("📊 Score a Quiz", expanded=False):
        st.caption("Uses the topic set above — fill that in first.")
        if st.button("Score & Save", use_container_width=True, key="score_quiz_btn"):
            quiz_topic = _current_topic()
            if not quiz_topic:
                st.warning("Set the current topic above first.")
            elif not st.session_state.memory.messages:
                st.warning("No conversation to score yet.")
            else:
                with st.spinner("Scoring quiz…"):
                    try:
                        result = score_quiz(
                            topic=quiz_topic,
                            messages=st.session_state.memory.messages,
                            llm=llm,
                        )
                        score_tracker.save(result)

                        if result.score < 70:
                            profile_store.add_weak_topic(result.topic)
                        else:
                            profile_store.add_strong_topic(result.topic)

                        st.session_state.quiz_saved = True
                        st.success(f"Score: **{result.score:.0f}%** on *{result.topic}*")
                        if result.weak_areas:
                            st.caption("Weak areas: " + ", ".join(result.weak_areas))
                    except Exception as exc:
                        st.error(f"Scoring failed: {exc}")

    # ── recent scores ──────────────────────────────────────────────────────────
    with st.expander("🏆 Recent Scores", expanded=False):
        recent = score_tracker.load_recent(5)
        if not recent:
            st.caption("No quiz scores yet.")
        else:
            for r in recent:
                colour = "🟢" if r.score >= 70 else "🔴"
                st.write(f"{colour} **{r.topic}** — {r.score:.0f}% ({r.date})")

    st.divider()

    # ── conversation history ───────────────────────────────────────────────────
    past = list_conversations()
    if not past:
        st.caption("No past conversations yet.")
    else:
        for conv in past:
            dt = conv["created_at"][:10]
            label = f"{dt} — {conv['title'][:40]}{'…' if len(conv['title']) > 40 else ''}"
            if st.button(label, key=conv["id"], use_container_width=True):
                st.session_state.memory = load_conversation(conv["id"], llm)
                st.session_state.display_messages = []
                for msg in st.session_state.memory.messages:
                    role = "user" if msg["role"] == "human" else "assistant"
                    st.session_state.display_messages.append((role, msg["content"]))
                st.session_state.page = "chat"
                st.rerun()


# ── page router ────────────────────────────────────────────────────────────────

if st.session_state.page == "profile_setup":
    render_profile_setup(editing=profile_store.load() is not None)
    st.stop()

# ── main chat area ─────────────────────────────────────────────────────────────

st.title("Personal Learning Tutor")

# Profile summary — shows effective (resolved) styles for the current topic.
profile = profile_store.load()
if profile:
    topic = _current_topic()
    ts = profile.topic_styles.get(topic.lower().strip()) if topic else None
    eff_ls = (ts.learning_style if ts and ts.learning_style else None) or profile.learning_style
    eff_pace = (ts.preferred_pace if ts and ts.preferred_pace else None) or profile.preferred_pace
    eff_es = (
        (ts.explanation_style if ts and ts.explanation_style else None)
        or profile.explanation_style
    )

    expander_label = (
        f"Your profile — {topic} (topic-specific, {int(ts.confidence * 100)}% confidence)"
        if ts and any([ts.learning_style, ts.preferred_pace, ts.explanation_style])
        else "Your profile — global defaults"
    )

    with st.expander(expander_label, expanded=False):
        cols = st.columns(3)
        cols[0].metric("Learning style", eff_ls)
        cols[1].metric("Pace", eff_pace)
        cols[2].metric("Style", eff_es)

        if topic and ts and ts.sample_count > 0:
            st.caption(
                f"Inferred from {ts.sample_count} observation(s) in conversations "
                f"about *{topic}*. Confidence: {int(ts.confidence * 100)}%."
            )
        elif topic:
            st.caption("No topic-specific data yet — using global defaults.")

        if profile.weak_topics:
            st.caption(f"⚠️ Resurface: {', '.join(profile.weak_topics)}")

for role, content in st.session_state.display_messages:
    with st.chat_message(role):
        st.write(content)

if prompt := st.chat_input("Ask me to teach you something…"):
    st.session_state.display_messages.append(("user", prompt))
    with st.chat_message("user"):
        st.write(prompt)

    system_prompt = _get_system_prompt()
    history = st.session_state.memory.to_langchain_messages()
    messages = [SystemMessage(content=system_prompt)] + history + [HumanMessage(content=prompt)]

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            response = llm.invoke(messages)
        st.write(response.content)

    st.session_state.display_messages.append(("assistant", response.content))
    st.session_state.memory.save_context(prompt, response.content)
    save_memory(st.session_state.memory)

    # Increment turn counter and run inference if due.
    st.session_state.turn_count += 1
    _maybe_run_inference()
