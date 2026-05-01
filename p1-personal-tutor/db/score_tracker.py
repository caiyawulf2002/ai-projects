from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from models.quiz_models import QuizResult

_DB_PATH = Path(__file__).parent.parent / "data" / "tutor.db"


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class ScoreTracker:
    """Persists and retrieves QuizResult records via SQLite."""

    def __init__(self) -> None:
        self._init_table()

    def _init_table(self) -> None:
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
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_results ORDER BY date DESC"
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def load_by_topic(self, topic: str) -> list[QuizResult]:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_results WHERE topic = ? ORDER BY date DESC",
                (topic,),
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def load_recent(self, n: int = 10) -> list[QuizResult]:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_results ORDER BY date DESC LIMIT ?", (n,)
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> QuizResult:
        return QuizResult(
            topic=row["topic"],
            score=row["score"],
            date=row["date"],
            question_count=row["question_count"],
            weak_areas=json.loads(row["weak_areas"]),
        )
