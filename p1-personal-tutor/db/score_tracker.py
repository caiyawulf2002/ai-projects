"""SQLite persistence for quiz scores.

ScoreTracker appends a new row for every scored quiz session and exposes
query helpers used by the sidebar to show recent performance.  All queries
are scoped to the caller's session_id so sessions don't see each other's scores.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from models.quiz_models import QuizResult

_DB_PATH = Path(__file__).parent.parent / "data" / "tutor.db"


def _get_conn() -> sqlite3.Connection:
    """Open and return a SQLite connection to the shared tutor.db."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class ScoreTracker:
    """Persists and retrieves QuizResult records via SQLite, scoped per session_id."""

    def __init__(self) -> None:
        self._init_table()

    def _init_table(self) -> None:
        """Create the quiz_results table and apply idempotent session_id migration.

        New databases get the session_id column from the start.  Existing
        databases receive it via ALTER TABLE with DEFAULT 'legacy' so old rows
        are preserved and never surface for new sessions.
        """
        with _get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id     TEXT    NOT NULL DEFAULT 'legacy',
                    topic          TEXT    NOT NULL,
                    score          REAL    NOT NULL,
                    date           TEXT    NOT NULL,
                    question_count INTEGER NOT NULL,
                    weak_areas     TEXT    NOT NULL
                )
                """
            )
            # Idempotent migration for existing DBs that lack the column.
            try:
                conn.execute(
                    "ALTER TABLE quiz_results ADD COLUMN session_id TEXT NOT NULL DEFAULT 'legacy'"
                )
            except sqlite3.OperationalError:
                pass  # column already exists

    def save(self, result: QuizResult, session_id: str) -> None:
        """Insert a new quiz result row for the given session.

        Args:
            result:     Validated QuizResult from the scoring chain.
            session_id: UUID identifying the browser session.

        Side effects:
            Writes to data/tutor.db.  weak_areas list is JSON-serialised.
        """
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO quiz_results (session_id, topic, score, date, question_count, weak_areas)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    result.topic,
                    result.score,
                    result.date,
                    result.question_count,
                    json.dumps(result.weak_areas),
                ),
            )

    def load_all(self, session_id: str) -> list[QuizResult]:
        """Return all quiz results for this session, newest first."""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_results WHERE session_id = ? ORDER BY date DESC",
                (session_id,),
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def load_by_topic(self, topic: str, session_id: str) -> list[QuizResult]:
        """Return all quiz results for a specific topic in this session, newest first."""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_results WHERE session_id = ? AND topic = ? ORDER BY date DESC",
                (session_id, topic),
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def load_recent(self, n: int, session_id: str) -> list[QuizResult]:
        """Return the n most recent quiz results for this session, newest first."""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_results WHERE session_id = ? ORDER BY date DESC LIMIT ?",
                (session_id, n),
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> QuizResult:
        """Deserialise a sqlite3.Row into a QuizResult model."""
        return QuizResult(
            topic=row["topic"],
            score=row["score"],
            date=row["date"],
            question_count=row["question_count"],
            weak_areas=json.loads(row["weak_areas"]),
        )
