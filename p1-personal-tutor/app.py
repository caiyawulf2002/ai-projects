"""P1 — Personal Learning Tutor.

Streamlit entry point. Two tabs: Chat (Socratic teaching) and Quiz (topic-based
question generation). Session memory, profile, and scores are all scoped to a
per-tab UUID so multiple users on the same Cloud Run container are isolated.
"""
from __future__ import annotations

import uuid
from datetime import date

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from chains.fr_grading_chain import grade_fr_answer
from chains.quiz_chain import score_quiz
from chains.quiz_generation_chain import generate_fr_quiz, generate_mc_quiz
from chains.socratic_opener_chain import generate_socratic_opener
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
from models.quiz_models import FRQuiz, MCQuiz, QuizResult
from models.user_profile import UserProfile

load_dotenv()

st.set_page_config(page_title="P1 — Personal Tutor", layout="wide")

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

if "session_id" not in st.session_state:
    st.session_state.session_id: str = str(uuid.uuid4())

if "memory" not in st.session_state:
    st.session_state.memory: SessionMemory = load_memory(llm, st.session_state.session_id)

if "display_messages" not in st.session_state:
    st.session_state.display_messages: list[tuple[str, str]] = []
    for msg in st.session_state.memory.messages:
        role = "user" if msg["role"] == "human" else "assistant"
        st.session_state.display_messages.append((role, msg["content"]))

if "page" not in st.session_state:
    st.session_state.page = (
        "chat" if profile_store.load(st.session_state.session_id) else "profile_setup"
    )

if "quiz_saved" not in st.session_state:
    st.session_state.quiz_saved: bool = False

if "turn_count" not in st.session_state:
    st.session_state.turn_count: int = 0

if "last_inference" not in st.session_state:
    st.session_state.last_inference: str = ""

# pending_opener: set to True when loading an archived conversation with weak topics.
# The chat tab generates and shows the Socratic opener on the next render.
if "pending_opener" not in st.session_state:
    st.session_state.pending_opener: bool = False


# ── helpers ────────────────────────────────────────────────────────────────────

def _current_topic() -> str:
    return st.session_state.get("current_topic_input", "").strip()


def _get_system_prompt() -> str:
    """Build system prompt: no intake block when a profile exists."""
    profile = profile_store.load(st.session_state.session_id)
    topic = _current_topic() or None
    if profile is None:
        return TUTOR_SYSTEM_PROMPT.replace(
            "{learner_profile}",
            "No profile set yet — ask the learner about their background.",
        )
    return build_system_prompt(profile, topic=topic)


def _maybe_run_inference() -> None:
    topic = _current_topic()
    if not topic:
        return
    if st.session_state.turn_count % _INFERENCE_EVERY_N_TURNS != 0:
        return
    if len(st.session_state.memory.messages) < 4:
        return
    try:
        signal = infer_style(
            topic=topic,
            messages=st.session_state.memory.messages,
            llm=llm,
        )
        profile_store.update_topic_style(topic, signal, st.session_state.session_id)
        st.session_state.last_inference = signal.reasoning
    except Exception:
        pass


# ── profile setup page ─────────────────────────────────────────────────────────

def render_profile_setup(*, editing: bool = False) -> None:
    st.title("👤 Learner Profile Setup" if not editing else "⚙️ Edit Profile")
    st.caption(
        "These are your **global defaults** — the baseline the tutor uses for any topic. "
        "The tutor will infer per-topic preferences automatically as you learn."
    )

    existing = profile_store.load(st.session_state.session_id)

    with st.form("profile_form"):
        learning_style = st.selectbox(
            "Learning style (default)",
            options=["visual", "auditory", "reading", "kinesthetic"],
            index=["visual", "auditory", "reading", "kinesthetic"].index(
                existing.learning_style if existing else "reading"
            ),
        )
        preferred_pace = st.selectbox(
            "Preferred pace (default)",
            options=["fast", "medium", "slow"],
            index=["fast", "medium", "slow"].index(
                existing.preferred_pace if existing else "medium"
            ),
        )
        explanation_style = st.selectbox(
            "Explanation style (default)",
            options=["analogies", "step_by_step", "examples_first", "theory_first"],
            index=["analogies", "step_by_step", "examples_first", "theory_first"].index(
                existing.explanation_style if existing else "examples_first"
            ),
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
        profile_store.save(profile, st.session_state.session_id)
        st.success("Profile saved!")
        st.session_state.page = "chat"
        st.rerun()

    if editing and existing and existing.topic_styles:
        st.divider()
        st.subheader("Learned topic styles")
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
        archive_and_reset(st.session_state.memory, st.session_state.session_id)
        st.session_state.memory = load_memory(llm, st.session_state.session_id)
        st.session_state.display_messages = []
        st.session_state.quiz_saved = False
        st.session_state.turn_count = 0
        st.session_state.last_inference = ""
        st.session_state.pending_opener = False
        st.session_state.page = "chat"
        # Clear topic widget so new chat starts without stale topic context.
        st.session_state["current_topic_input"] = ""
        st.rerun()

    if st.button("⚙️ Profile Settings", use_container_width=True):
        st.session_state.page = "profile_setup"
        st.rerun()

    st.divider()

    st.text_input(
        "Current topic",
        placeholder="e.g. Python generators",
        key="current_topic_input",
        help=(
            "Set this while studying. The tutor infers your style every "
            f"{_INFERENCE_EVERY_N_TURNS} turns and adapts explanations accordingly."
        ),
    )

    if st.session_state.last_inference:
        st.caption(f"🔍 Last inference: {st.session_state.last_inference}")

    st.divider()

    with st.expander("📊 Score a Quiz", expanded=False):
        st.caption("Uses the topic set above — fill that in first.")
        if st.button("Score & Save", use_container_width=True, key="score_quiz_btn"):
            quiz_topic = _current_topic()
            if not quiz_topic:
                st.warning("Set the current topic above first.")
            elif not st.session_state.memory.messages:
                st.warning("No conversation to score yet.")
            else:
                with st.spinner("Scoring…"):
                    try:
                        result = score_quiz(
                            topic=quiz_topic,
                            messages=st.session_state.memory.messages,
                            llm=llm,
                        )
                        score_tracker.save(result, st.session_state.session_id)
                        if result.score < 70:
                            profile_store.add_weak_topic(result.topic, st.session_state.session_id)
                        else:
                            profile_store.add_strong_topic(result.topic, st.session_state.session_id)
                        st.session_state.quiz_saved = True
                        st.success(f"Score: **{result.score:.0f}%** on *{result.topic}*")
                        if result.weak_areas:
                            st.caption("Weak areas: " + ", ".join(result.weak_areas))
                    except Exception as exc:
                        st.error(f"Scoring failed: {exc}")

    with st.expander("🏆 Recent Scores", expanded=False):
        recent = score_tracker.load_recent(5, st.session_state.session_id)
        if not recent:
            st.caption("No quiz scores yet.")
        else:
            for r in recent:
                colour = "🟢" if r.score >= 70 else "🔴"
                st.write(f"{colour} **{r.topic}** — {r.score:.0f}% ({r.date})")

    st.divider()

    past = list_conversations(st.session_state.session_id)
    if not past:
        st.caption("No past conversations yet.")
    else:
        for conv in past:
            dt = conv["created_at"][:10]
            label = f"{dt} — {conv['title'][:40]}{'…' if len(conv['title']) > 40 else ''}"
            if st.button(label, key=conv["id"], use_container_width=True):
                st.session_state.memory = load_conversation(
                    conv["id"], llm, st.session_state.session_id
                )
                st.session_state.display_messages = []
                for msg in st.session_state.memory.messages:
                    role = "user" if msg["role"] == "human" else "assistant"
                    st.session_state.display_messages.append((role, msg["content"]))
                # Flag a Socratic opener if there are weak topics to resurface.
                loaded_profile = profile_store.load(st.session_state.session_id)
                st.session_state.pending_opener = bool(
                    loaded_profile and loaded_profile.weak_topics
                )
                st.session_state.page = "chat"
                st.rerun()


# ── page router ────────────────────────────────────────────────────────────────

if st.session_state.page == "profile_setup":
    render_profile_setup(editing=profile_store.load(st.session_state.session_id) is not None)
    st.stop()

# ── tabs ───────────────────────────────────────────────────────────────────────

chat_tab, quiz_tab = st.tabs(["💬 Chat", "📝 Quiz"])


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT TAB
# ═══════════════════════════════════════════════════════════════════════════════

with chat_tab:
    st.title("Personal Learning Tutor")

    # Profile summary expander.
    profile = profile_store.load(st.session_state.session_id)
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
                    f"Inferred from {ts.sample_count} observation(s) about *{topic}*. "
                    f"Confidence: {int(ts.confidence * 100)}%."
                )
            elif topic:
                st.caption("No topic-specific data yet — using global defaults.")
            if profile.weak_topics:
                st.caption(f"⚠️ Resurface: {', '.join(profile.weak_topics)}")

    # Render conversation history.
    for role, content in st.session_state.display_messages:
        with st.chat_message(role):
            st.write(content)

    # Socratic opener — fires once when an archived conversation is revisited
    # and the learner has weak topics that need resurfacing.
    if st.session_state.pending_opener:
        opener_profile = profile_store.load(st.session_state.session_id)
        if opener_profile and opener_profile.weak_topics:
            with st.chat_message("assistant"):
                with st.spinner("Preparing a review question…"):
                    opener = generate_socratic_opener(opener_profile.weak_topics, llm)
                st.write(opener)
            st.session_state.display_messages.append(("assistant", opener))
            st.session_state.memory.messages.append({"role": "ai", "content": opener})
            save_memory(st.session_state.memory, st.session_state.session_id)
        st.session_state.pending_opener = False

    # Chat input with streaming response.
    if prompt := st.chat_input("Ask me to teach you something…"):
        st.session_state.display_messages.append(("user", prompt))
        with st.chat_message("user"):
            st.write(prompt)

        system_prompt = _get_system_prompt()
        history = st.session_state.memory.to_langchain_messages()
        messages = [SystemMessage(content=system_prompt)] + history + [HumanMessage(content=prompt)]

        with st.chat_message("assistant"):
            response_content: str = st.write_stream(
                chunk.content for chunk in llm.stream(messages)
            )

        st.session_state.display_messages.append(("assistant", response_content))
        st.session_state.memory.save_context(prompt, response_content)
        save_memory(st.session_state.memory, st.session_state.session_id)

        st.session_state.turn_count += 1
        _maybe_run_inference()


# ═══════════════════════════════════════════════════════════════════════════════
# QUIZ TAB
# ═══════════════════════════════════════════════════════════════════════════════

def _reset_quiz() -> None:
    for key in ["quiz_phase", "quiz_data", "quiz_q_idx", "quiz_answers",
                "quiz_grade_results", "quiz_type"]:
        st.session_state.pop(key, None)


with quiz_tab:
    st.title("Quiz Yourself")

    quiz_phase = st.session_state.get("quiz_phase", "setup")

    # ── setup phase ────────────────────────────────────────────────────────────

    if quiz_phase == "setup":
        st.caption("Select a topic, pick a question type, and generate a quiz.")

        all_results = score_tracker.load_all(st.session_state.session_id)
        scored_topics = sorted({r.topic for r in all_results})

        col_topic, col_n = st.columns([3, 1])
        with col_topic:
            if scored_topics:
                topic_options = scored_topics + ["✏️ Enter a new topic…"]
                sel = st.selectbox("Topic", topic_options, key="quiz_topic_sel")
                if sel == "✏️ Enter a new topic…":
                    quiz_topic = st.text_input("Topic name", key="quiz_topic_custom").strip()
                else:
                    quiz_topic = sel
            else:
                quiz_topic = st.text_input(
                    "Topic", placeholder="e.g. Python generators", key="quiz_topic_custom"
                ).strip()

        with col_n:
            n_q = st.number_input("Questions", min_value=3, max_value=10, value=5, key="quiz_n_q")

        if quiz_topic:
            st.write("**Question type:**")
            col_mc, col_fr = st.columns(2)
            mc_clicked = col_mc.button("📋 Multiple Choice", use_container_width=True, key="quiz_btn_mc")
            fr_clicked = col_fr.button("✍️ Free Response", use_container_width=True, key="quiz_btn_fr")

            q_type = "mc" if mc_clicked else ("fr" if fr_clicked else None)

            if q_type:
                qz_profile = profile_store.load(st.session_state.session_id)
                learning_style = qz_profile.learning_style if qz_profile else "reading"
                past = score_tracker.load_by_topic(quiz_topic, st.session_state.session_id)
                weak_areas = past[0].weak_areas if past else []

                with st.spinner(f"Generating {n_q} questions on *{quiz_topic}*…"):
                    try:
                        if q_type == "mc":
                            quiz_data = generate_mc_quiz(quiz_topic, n_q, llm, learning_style, weak_areas)
                        else:
                            quiz_data = generate_fr_quiz(quiz_topic, n_q, llm, learning_style, weak_areas)

                        st.session_state.quiz_phase = "in_progress"
                        st.session_state.quiz_data = quiz_data
                        st.session_state.quiz_type = q_type
                        st.session_state.quiz_q_idx = 0
                        st.session_state.quiz_answers = [None] * len(quiz_data.questions)
                        st.session_state.quiz_grade_results = [None] * len(quiz_data.questions)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to generate quiz: {exc}")
        else:
            st.caption("Enter a topic above to continue.")

    # ── in_progress phase ──────────────────────────────────────────────────────

    elif quiz_phase == "in_progress":
        quiz_data = st.session_state.quiz_data
        q_type: str = st.session_state.quiz_type
        idx: int = st.session_state.quiz_q_idx
        questions = quiz_data.questions
        n_total = len(questions)

        st.progress((idx) / n_total, text=f"Question {idx + 1} of {n_total} — *{quiz_data.topic}*")
        st.subheader(f"Q{idx + 1}. {questions[idx].question}")

        if q_type == "mc":
            q = questions[idx]
            option_map = {opt.key: f"**{opt.key}.** {opt.text}" for opt in q.options}
            choice = st.radio(
                "Select your answer:",
                list(option_map.values()),
                key=f"mc_radio_{idx}",
                index=None,
            )

            if st.button("Submit Answer", key=f"mc_submit_{idx}", type="primary"):
                if choice is None:
                    st.warning("Select an option first.")
                else:
                    selected_key = choice.split(".")[0].strip("*").strip()
                    st.session_state.quiz_answers[idx] = selected_key
                    st.session_state.quiz_grade_results[idx] = (selected_key == q.correct_key)
                    if idx + 1 < n_total:
                        st.session_state.quiz_q_idx += 1
                    else:
                        st.session_state.quiz_phase = "complete"
                    st.rerun()

        elif q_type == "fr":
            q = questions[idx]
            user_ans = st.text_area(
                "Your answer:", key=f"fr_area_{idx}", height=150,
                placeholder="Write a few sentences…"
            )

            if st.button("Submit Answer", key=f"fr_submit_{idx}", type="primary"):
                if not user_ans.strip():
                    st.warning("Write something before submitting.")
                else:
                    st.session_state.quiz_answers[idx] = user_ans
                    with st.spinner("Grading…"):
                        try:
                            grade = grade_fr_answer(
                                q.question, q.key_concepts, q.sample_answer, user_ans, llm
                            )
                            st.session_state.quiz_grade_results[idx] = grade
                        except Exception:
                            st.session_state.quiz_grade_results[idx] = None
                    if idx + 1 < n_total:
                        st.session_state.quiz_q_idx += 1
                    else:
                        st.session_state.quiz_phase = "complete"
                    st.rerun()

        if st.button("← Abandon Quiz", key="quiz_abandon"):
            _reset_quiz()
            st.rerun()

    # ── complete phase ─────────────────────────────────────────────────────────

    elif quiz_phase == "complete":
        quiz_data = st.session_state.quiz_data
        q_type = st.session_state.quiz_type
        answers = st.session_state.quiz_answers
        grades = st.session_state.quiz_grade_results
        questions = quiz_data.questions

        if q_type == "mc":
            correct_count = sum(1 for g in grades if g is True)
            score_pct = correct_count / len(questions) * 100
        else:
            valid = [g.score for g in grades if g is not None]
            score_pct = (sum(valid) / len(valid) * 100) if valid else 0.0

        colour = "🟢" if score_pct >= 70 else "🔴"
        st.subheader(f"{colour} {score_pct:.0f}% on *{quiz_data.topic}*")

        for i, (q, ans, grade) in enumerate(zip(questions, answers, grades)):
            if q_type == "mc":
                is_correct: bool = grade is True
                icon = "✅" if is_correct else "❌"
                with st.expander(f"{icon} Q{i+1}: {q.question[:70]}{'…' if len(q.question) > 70 else ''}"):
                    st.write(f"**Your answer:** {ans}")
                    if not is_correct:
                        st.write(f"**Correct answer:** {q.correct_key}")
                    st.write(f"**Why:** {q.explanation}")
            else:
                score_val = grade.score if grade else 0.0
                icon = "✅" if score_val >= 0.7 else "❌"
                with st.expander(f"{icon} Q{i+1}: {q.question[:70]}{'…' if len(q.question) > 70 else ''}"):
                    st.write(f"**Your answer:** {ans}")
                    if grade:
                        st.write(f"**Score:** {score_val * 100:.0f}%")
                        st.write(f"**Feedback:** {grade.feedback}")
                        if grade.missing_concepts:
                            st.caption("Missing: " + ", ".join(grade.missing_concepts))

        st.divider()
        col_save, col_again = st.columns(2)

        if col_save.button("💾 Save Score", use_container_width=True, key="quiz_save_btn"):
            if q_type == "mc":
                weak_areas = [
                    q.question[:60] for q, g in zip(questions, grades) if g is not True
                ]
            else:
                weak_areas = [
                    q.question[:60] for q, g in zip(questions, grades)
                    if g is None or g.score < 0.7
                ]

            result = QuizResult(
                topic=quiz_data.topic,
                score=score_pct,
                date=date.today().isoformat(),
                question_count=len(questions),
                weak_areas=weak_areas,
            )
            score_tracker.save(result, st.session_state.session_id)
            if score_pct < 70:
                profile_store.add_weak_topic(quiz_data.topic, st.session_state.session_id)
            else:
                profile_store.add_strong_topic(quiz_data.topic, st.session_state.session_id)
            st.success("Score saved! It will appear in Recent Scores in the sidebar.")

        if col_again.button("🔄 New Quiz", use_container_width=True, key="quiz_again_btn"):
            _reset_quiz()
            st.rerun()
