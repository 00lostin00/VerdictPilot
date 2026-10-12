from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .models import MistakeRecord, NewMistake


class MistakeMemory:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=15000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mistakes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    problem_title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    symptom TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mistakes_session ON mistakes(session_id)"
            )

    def add(self, mistake: NewMistake) -> MistakeRecord:
        self.initialize()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO mistakes
                    (session_id, problem_title, category, symptom, lesson)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    mistake.session_id,
                    mistake.problem_title,
                    mistake.category,
                    mistake.symptom,
                    mistake.lesson,
                ),
            )
            row = connection.execute(
                "SELECT * FROM mistakes WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        assert row is not None
        return MistakeRecord.model_validate(dict(row))

    def search(self, session_id: str, topic: str = "", limit: int = 10) -> list[MistakeRecord]:
        self.initialize()
        pattern = f"%{topic}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM mistakes
                WHERE session_id = ?
                  AND (? = '' OR category LIKE ? OR problem_title LIKE ? OR lesson LIKE ?)
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, topic, pattern, pattern, pattern, max(1, min(limit, 50))),
            ).fetchall()
        return [MistakeRecord.model_validate(dict(row)) for row in rows]
