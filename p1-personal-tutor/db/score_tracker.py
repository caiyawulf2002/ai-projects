"""SQLite persistence for quiz scores.

ScoreTracker appends a new row for every scored quiz session and exposes
query helpers used by the sidebar to show recent performance.
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
    """Persists and retrieves QuizResult records via SQLite."""

    def __init__(self) -> None:
        self._init_table()

    def _init_table(self) -> None:
        """Create the quiz_results table if it does not exist."""
        with _get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic     TEXT    NOT NULL,
                    score     REAL    NOT NULL,
                    date      TEXT    NOT NULL,
                    question_count INTEGER NOT NULL,
                    weak_areas TEXT   NOT NULL  -- JSON array
                )
                """
            )

    def save(self, result: QuizResult) -> None:
        """Insert a new quiz result row.

        Args:
            result: Validated QuizResult from the scoring chain.

        Side effects:
            Writes to data/tutor.db.  weak_areas list is JSON-serialised.
        """
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO quiz_results (topic, score, date, question_count, weak_areas)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    result.topic,
                    result.score,
                    result.date,
                    result.question_count,
                    json.dumps(result.weak_areas),
                ),
            )

    def load_all(self) -> list[QuizResult]:
        """Return all quiz results, newest first."""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_results ORDER BY date DESC"
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def load_by_topic(self, topic: str) -> list[QuizResult]:
        """Return all quiz results for a specific topic, newest first."""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_results WHERE topic = ? ORDER BY date DESC",
                (topic,),
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def load_recent(self, n: int = 10) -> list[QuizResult]:
        """Return the n most recent quiz results, newest first."""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_results ORDER BY date DESC LIMIT ?", (n,)
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
