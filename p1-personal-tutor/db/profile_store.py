"""SQLite persistence for the learner's UserProfile.

Each browser session gets its own row keyed by a UUID (session_id).  Per-topic
style data is serialised as a JSON blob in the topic_styles column so no schema
migration is needed when new topic keys are added.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from models.style_models import StyleSignal, TopicStyle
from models.user_profile import UserProfile

_DB_PATH = Path(__file__).parent.parent / "data" / "tutor.db"

# After this many observations, confidence reaches 1.0.
_CONFIDENCE_SATURATION = 5


def _get_conn() -> sqlite3.Connection:
    """Open and return a SQLite connection to the shared tutor.db.

    Creates the data/ directory if it does not exist.  row_factory is set to
    sqlite3.Row so columns can be accessed by name.
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalise_topic(topic: str) -> str:
    """Return a canonical topic key: lowercased and stripped of whitespace."""
    return topic.lower().strip()


class ProfileStore:
    """SQLite store for learner UserProfiles, scoped per session_id."""

    def __init__(self) -> None:
        self._init_table()

    def _init_table(self) -> None:
        """Create the user_profile table and apply idempotent migrations.

        Detects the old single-row schema (CHECK id = 1) and migrates it to
        the multi-session schema keyed by session_id TEXT PRIMARY KEY.  The
        old id=1 row is preserved under the sentinel key 'legacy'.
        """
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='user_profile'"
            ).fetchone()

            if row is None:
                # Fresh database: create the multi-session schema directly.
                conn.execute(
                    """
                    CREATE TABLE user_profile (
                        session_id        TEXT NOT NULL PRIMARY KEY,
                        learning_style    TEXT NOT NULL,
                        preferred_pace    TEXT NOT NULL,
                        explanation_style TEXT NOT NULL,
                        weak_topics       TEXT NOT NULL,
                        strong_topics     TEXT NOT NULL,
                        topic_styles      TEXT NOT NULL DEFAULT '{}'
                    )
                    """
                )
            elif "CHECK" in (row[0] or ""):
                # Old single-row schema: rename, recreate, copy with 'legacy' key.
                conn.execute("ALTER TABLE user_profile RENAME TO user_profile_old")
                conn.execute(
                    """
                    CREATE TABLE user_profile (
                        session_id        TEXT NOT NULL PRIMARY KEY,
                        learning_style    TEXT NOT NULL,
                        preferred_pace    TEXT NOT NULL,
                        explanation_style TEXT NOT NULL,
                        weak_topics       TEXT NOT NULL,
                        strong_topics     TEXT NOT NULL,
                        topic_styles      TEXT NOT NULL DEFAULT '{}'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO user_profile
                        (session_id, learning_style, preferred_pace, explanation_style,
                         weak_topics, strong_topics, topic_styles)
                    SELECT 'legacy', learning_style, preferred_pace, explanation_style,
                           weak_topics, strong_topics, topic_styles
                    FROM user_profile_old WHERE id = 1
                    """
                )
                conn.execute("DROP TABLE user_profile_old")
            # else: new schema already present, nothing to do.

    # ── persistence ────────────────────────────────────────────────────────────

    def save(self, profile: UserProfile, session_id: str) -> None:
        """Upsert the learner profile for the given session.

        Args:
            profile:    The UserProfile to persist; replaces any existing row
                        for this session_id.
            session_id: UUID identifying the browser session.

        Side effects:
            Writes to data/tutor.db.  topic_styles dict is JSON-serialised.
        """
        serialised_topic_styles = json.dumps(
            {
                topic: ts.model_dump()
                for topic, ts in profile.topic_styles.items()
            }
        )
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO user_profile
                    (session_id, learning_style, preferred_pace, explanation_style,
                     weak_topics, strong_topics, topic_styles)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    learning_style    = excluded.learning_style,
                    preferred_pace    = excluded.preferred_pace,
                    explanation_style = excluded.explanation_style,
                    weak_topics       = excluded.weak_topics,
                    strong_topics     = excluded.strong_topics,
                    topic_styles      = excluded.topic_styles
                """,
                (
                    session_id,
                    profile.learning_style,
                    profile.preferred_pace,
                    profile.explanation_style,
                    json.dumps(profile.weak_topics),
                    json.dumps(profile.strong_topics),
                    serialised_topic_styles,
                ),
            )

    def load(self, session_id: str) -> UserProfile | None:
        """Load the learner profile for the given session.

        Args:
            session_id: UUID identifying the browser session.

        Returns:
            The stored UserProfile, or None if no profile has been saved yet
            for this session.
        """
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM user_profile WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None

        raw_topic_styles: dict = json.loads(row["topic_styles"] or "{}")
        topic_styles = {
            topic: TopicStyle.model_validate(data)
            for topic, data in raw_topic_styles.items()
        }

        return UserProfile(
            learning_style=row["learning_style"],
            preferred_pace=row["preferred_pace"],
            explanation_style=row["explanation_style"],
            weak_topics=json.loads(row["weak_topics"]),
            strong_topics=json.loads(row["strong_topics"]),
            topic_styles=topic_styles,
        )

    # ── quiz result helpers ───────────────────────────────────────────────────

    def add_weak_topic(self, topic: str, session_id: str) -> None:
        """Idempotently add a topic to weak_topics for this session."""
        profile = self.load(session_id)
        if profile is None:
            return
        if topic not in profile.weak_topics:
            profile.weak_topics.append(topic)
        profile.strong_topics = [t for t in profile.strong_topics if t != topic]
        self.save(profile, session_id)

    def add_strong_topic(self, topic: str, session_id: str) -> None:
        """Idempotently add a topic to strong_topics and remove from weak."""
        profile = self.load(session_id)
        if profile is None:
            return
        if topic not in profile.strong_topics:
            profile.strong_topics.append(topic)
        profile.weak_topics = [t for t in profile.weak_topics if t != topic]
        self.save(profile, session_id)

    # ── dynamic style inference helpers ───────────────────────────────────────

    def update_topic_style(self, topic: str, signal: StyleSignal, session_id: str) -> None:
        """Merge a StyleSignal into the stored TopicStyle for the given topic.

        Only non-None inferred fields in the signal overwrite the stored
        value, so a signal that only detected pace preference won't clear a
        previously inferred explanation style.

        Confidence grows linearly with sample_count up to _CONFIDENCE_SATURATION
        observations, after which it saturates at 1.0.
        """
        profile = self.load(session_id)
        if profile is None:
            return

        key = _normalise_topic(topic)
        existing = profile.topic_styles.get(key, TopicStyle())

        if signal.inferred_learning_style is not None:
            existing.learning_style = signal.inferred_learning_style
        if signal.inferred_pace is not None:
            existing.preferred_pace = signal.inferred_pace
        if signal.inferred_explanation_style is not None:
            existing.explanation_style = signal.inferred_explanation_style

        existing.sample_count += 1
        existing.confidence = min(
            existing.sample_count / _CONFIDENCE_SATURATION, 1.0
        )

        profile.topic_styles[key] = existing
        self.save(profile, session_id)

    def get_topic_style(self, topic: str, session_id: str) -> TopicStyle | None:
        """Return the stored TopicStyle for a topic, or None if unseen."""
        profile = self.load(session_id)
        if profile is None:
            return None
        return profile.topic_styles.get(_normalise_topic(topic))
