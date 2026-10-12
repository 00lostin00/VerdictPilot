from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .catalog import LearningCatalog

LOCAL_TIMEZONE = timezone(timedelta(hours=8))


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class PlatformStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS vp_schema (version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO vp_schema VALUES (1);
                CREATE TABLE IF NOT EXISTS vp_profiles (
                    learner_id TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '学习者',
                    goal TEXT NOT NULL DEFAULT '把算法与 Agent 工程能力做成可验证的作品',
                    daily_minutes INTEGER NOT NULL DEFAULT 45
                );
                CREATE TABLE IF NOT EXISTS vp_progress (
                    learner_id TEXT NOT NULL, lesson_id TEXT NOT NULL, best_score INTEGER,
                    last_score INTEGER, note TEXT NOT NULL DEFAULT '',
                    exercise_done INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
                    PRIMARY KEY (learner_id, lesson_id)
                );
                CREATE TABLE IF NOT EXISTS vp_quiz_attempts (
                    id INTEGER PRIMARY KEY, learner_id TEXT NOT NULL, lesson_id TEXT NOT NULL,
                    score INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vp_runs (
                    id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, kind TEXT NOT NULL,
                    title TEXT NOT NULL, problem_id TEXT, status TEXT NOT NULL,
                    verdict TEXT, code TEXT, result_json TEXT, error TEXT,
                    elapsed_ms REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                    finished_at TEXT
                );
                CREATE INDEX IF NOT EXISTS vp_runs_learner ON vp_runs(learner_id, created_at);
                CREATE TABLE IF NOT EXISTS vp_drafts (
                    learner_id TEXT NOT NULL, problem_id TEXT NOT NULL, code TEXT NOT NULL,
                    updated_at TEXT NOT NULL, PRIMARY KEY (learner_id, problem_id)
                );
                CREATE TABLE IF NOT EXISTS vp_reviews (
                    mistake_id INTEGER PRIMARY KEY REFERENCES mistakes(id),
                    learner_id TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES vp_runs(id),
                    problem_id TEXT, due_at TEXT NOT NULL, interval_days INTEGER NOT NULL,
                    repetitions INTEGER NOT NULL DEFAULT 0, last_rating TEXT,
                    UNIQUE (learner_id, run_id)
                );
                CREATE INDEX IF NOT EXISTS vp_reviews_due ON vp_reviews(learner_id, due_at);
                CREATE TABLE IF NOT EXISTS vp_project_evidence (
                    learner_id TEXT NOT NULL, project_id TEXT NOT NULL, milestone_id TEXT NOT NULL,
                    summary TEXT NOT NULL, command TEXT NOT NULL, artifact TEXT NOT NULL,
                    metrics_json TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(learner_id,project_id,milestone_id)
                );
                """
            )

    def recover_interrupted_runs(self) -> None:
        # Called once by the server lifespan, not by ordinary CLI service construction.
        with self.connect() as db:
            db.execute(
                "UPDATE vp_runs SET status='interrupted', error=?, finished_at=? "
                "WHERE status IN ('queued','running')",
                ("服务重启中断了任务，请重新提交", now_iso()),
            )

    def profile(self, learner_id: str) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO vp_profiles(learner_id) VALUES (?)", (learner_id,))
            row = db.execute(
                "SELECT * FROM vp_profiles WHERE learner_id=?", (learner_id,)
            ).fetchone()
        return dict(row)

    def update_profile(self, learner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.profile(learner_id)
        with self.connect() as db:
            db.execute(
                "UPDATE vp_profiles SET display_name=?, goal=?, daily_minutes=? WHERE learner_id=?",
                (data["display_name"], data["goal"], data["daily_minutes"], learner_id),
            )
        return self.profile(learner_id)

    def progress(self, learner_id: str) -> dict[str, dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM vp_progress WHERE learner_id=?", (learner_id,)
            ).fetchall()
        return {row["lesson_id"]: dict(row) for row in rows}

    def save_note(self, learner_id: str, lesson_id: str, note: str, exercise_done: bool) -> None:
        with self.connect() as db:
            db.execute(
                """INSERT INTO vp_progress
                   (learner_id,lesson_id,note,exercise_done,updated_at) VALUES (?,?,?,?,?)
                   ON CONFLICT(learner_id,lesson_id) DO UPDATE SET
                   note=excluded.note,exercise_done=excluded.exercise_done,
                   updated_at=excluded.updated_at""",
                (learner_id, lesson_id, note, int(exercise_done), now_iso()),
            )

    def record_quiz(self, learner_id: str, lesson_id: str, score: int) -> None:
        stamp = now_iso()
        with self.connect() as db:
            db.execute(
                "INSERT INTO vp_quiz_attempts(learner_id,lesson_id,score,created_at) "
                "VALUES (?,?,?,?)",
                (learner_id, lesson_id, score, stamp),
            )
            db.execute(
                """INSERT INTO vp_progress
                   (learner_id,lesson_id,best_score,last_score,updated_at) VALUES (?,?,?,?,?)
                   ON CONFLICT(learner_id,lesson_id) DO UPDATE SET
                   best_score=MAX(COALESCE(best_score,0),excluded.best_score),
                   last_score=excluded.last_score,updated_at=excluded.updated_at""",
                (learner_id, lesson_id, score, score, stamp),
            )

    def create_run(
        self,
        learner_id: str,
        kind: str,
        title: str,
        code: str | None,
        problem_id: str | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute(
                """INSERT INTO vp_runs
                   (id,learner_id,kind,title,problem_id,status,code,created_at)
                   VALUES (?,?,?,?,?,'queued',?,?)""",
                (run_id, learner_id, kind, title, problem_id, code, now_iso()),
            )
        return run_id

    def start_run(self, run_id: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE vp_runs SET status='running' WHERE id=?", (run_id,))

    def finish_run(self, run_id: str, result: dict[str, Any], elapsed_ms: float) -> None:
        execution = result.get("execution")
        verdict = execution["status"] if execution else None
        with self.connect() as db:
            db.execute(
                """UPDATE vp_runs SET status='completed',verdict=?,result_json=?,elapsed_ms=?,
                   finished_at=? WHERE id=?""",
                (verdict, json.dumps(result, ensure_ascii=False), elapsed_ms, now_iso(), run_id),
            )

    def fail_run(self, run_id: str, error: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE vp_runs SET status='failed',error=?,finished_at=? WHERE id=?",
                (error, now_iso(), run_id),
            )

    def run(self, learner_id: str, run_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM vp_runs WHERE learner_id=? AND id=?", (learner_id, run_id)
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        result = dict(row)
        raw_result = result.pop("result_json")
        result["result"] = json.loads(raw_result) if raw_result else None
        return result

    def runs(self, learner_id: str, limit: int = 30, offset: int = 0) -> dict[str, Any]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT id,kind,title,problem_id,status,verdict,elapsed_ms,created_at,finished_at
                   FROM vp_runs WHERE learner_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (learner_id, limit, offset),
            ).fetchall()
            total = db.execute(
                "SELECT COUNT(*) FROM vp_runs WHERE learner_id=?", (learner_id,)
            ).fetchone()[0]
        return {"items": [dict(row) for row in rows], "total": total}

    def problem_status(self, learner_id: str) -> dict[str, Any]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT problem_id,COUNT(*) AS attempts,
                   MAX(CASE WHEN verdict='passed' THEN 1 ELSE 0 END) AS passed
                   FROM vp_runs WHERE learner_id=? AND kind='submission' GROUP BY problem_id""",
                (learner_id,),
            ).fetchall()
        return {row["problem_id"]: dict(row) for row in rows}

    def save_draft(self, learner_id: str, problem_id: str, code: str) -> None:
        with self.connect() as db:
            db.execute(
                """INSERT INTO vp_drafts VALUES (?,?,?,?) ON CONFLICT(learner_id,problem_id)
                   DO UPDATE SET code=excluded.code, updated_at=excluded.updated_at""",
                (learner_id, problem_id, code, now_iso()),
            )

    def draft(self, learner_id: str, problem_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT code,updated_at FROM vp_drafts WHERE learner_id=? AND problem_id=?",
                (learner_id, problem_id),
            ).fetchone()
        return dict(row) if row else None

    def add_mistake(self, learner_id: str, run_id: str, category: str, lesson: str) -> int:
        run = self.run(learner_id, run_id)
        if run["verdict"] not in {
            "wrong_answer",
            "compile_error",
            "time_limit",
            "runtime_error",
            "output_limit",
        }:
            raise ValueError("只能将有执行错误证据的记录加入错题本")
        with self.connect() as db:
            previous = db.execute(
                "SELECT mistake_id FROM vp_reviews WHERE learner_id=? AND run_id=?",
                (learner_id, run_id),
            ).fetchone()
            if previous:
                db.execute(
                    "UPDATE mistakes SET category=?,lesson=? WHERE id=?",
                    (category, lesson, previous[0]),
                )
                return previous[0]
            cursor = db.execute(
                """INSERT INTO mistakes(session_id,problem_title,category,symptom,lesson)
                   VALUES (?,?,?,?,?)""",
                (learner_id, run["title"], category, run["verdict"], lesson),
            )
            mistake_id = cursor.lastrowid
            db.execute(
                "INSERT INTO vp_reviews VALUES (?,?,?,?,?,1,0,NULL)",
                (mistake_id, learner_id, run_id, run["problem_id"], now_iso()),
            )
        return int(mistake_id)

    def reviews(self, learner_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT m.*,r.run_id,r.problem_id,r.due_at,r.interval_days,r.repetitions,
                   r.last_rating FROM vp_reviews r JOIN mistakes m ON m.id=r.mistake_id
                   WHERE r.learner_id=? ORDER BY r.due_at ASC""",
                (learner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def review(self, learner_id: str, mistake_id: int, rating: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM vp_reviews WHERE learner_id=? AND mistake_id=?",
                (learner_id, mistake_id),
            ).fetchone()
            if row is None:
                raise KeyError(mistake_id)
            old = row["interval_days"]
            interval = {"again": 1, "hard": max(1, old), "good": old * 2, "easy": old * 3}[rating]
            interval = min(interval, 90)
            due = (datetime.now(UTC) + timedelta(days=interval)).isoformat()
            db.execute(
                """UPDATE vp_reviews SET due_at=?,interval_days=?,repetitions=repetitions+1,
                   last_rating=? WHERE mistake_id=?""",
                (due, interval, rating, mistake_id),
            )
        return {"id": mistake_id, "due_at": due, "interval_days": interval}

    def dashboard(self, learner_id: str, catalog: LearningCatalog) -> dict[str, Any]:
        progress = self.progress(learner_id)
        passed = {key for key, value in progress.items() if (value["best_score"] or 0) >= 80}
        problems = self.problem_status(learner_id)
        now = datetime.now(UTC)
        reviews = self.reviews(learner_id)
        due = sum(datetime.fromisoformat(r["due_at"]) <= now for r in reviews)
        with self.connect() as db:
            records = db.execute(
                """SELECT created_at FROM vp_quiz_attempts WHERE learner_id=?
                   UNION ALL SELECT created_at FROM vp_runs WHERE learner_id=?""",
                (learner_id, learner_id),
            ).fetchall()
            verdicts = db.execute(
                "SELECT verdict,COUNT(*) AS count FROM vp_runs WHERE learner_id=? "
                "AND verdict IS NOT NULL GROUP BY verdict",
                (learner_id,),
            ).fetchall()
        days: dict[str, int] = {}
        for record in records:
            day = datetime.fromisoformat(record[0]).astimezone(LOCAL_TIMEZONE).date().isoformat()
            days[day] = days.get(day, 0) + 1
        today = now.astimezone(LOCAL_TIMEZONE).date()
        streak = 0
        cursor = today if today.isoformat() in days else today - timedelta(days=1)
        while cursor.isoformat() in days:
            streak += 1
            cursor -= timedelta(days=1)
        recommendations = [
            item
            for item in catalog.lesson_summaries()
            if item["id"] not in passed and set(item["prerequisites"]) <= passed
        ][:3]
        tracks = []
        for track in catalog.tracks:
            lessons = [item for item in catalog.lessons.values() if item["track_id"] == track["id"]]
            tracks.append(
                {
                    **track,
                    "total": len(lessons),
                    "passed": sum(item["id"] in passed for item in lessons),
                }
            )
        return {
            "profile": self.profile(learner_id),
            "metrics": {
                "lessons_passed": len(passed),
                "lessons_total": len(catalog.lessons),
                "problems_passed": sum(v["passed"] for v in problems.values()),
                "problems_total": len(catalog.problems),
                "due_reviews": due,
                "streak": streak,
                "activity_total": len(records),
            },
            "tracks": tracks,
            "recommendations": recommendations,
            "activity": [
                {
                    "date": (today - timedelta(days=13 - i)).isoformat(),
                    "count": days.get((today - timedelta(days=13 - i)).isoformat(), 0),
                }
                for i in range(14)
            ],
            "verdicts": [dict(r) for r in verdicts],
            "recent_runs": self.runs(learner_id, 5)["items"],
            "progress": progress,
        }

    def export(self, learner_id: str) -> dict[str, Any]:
        with self.connect() as db:
            runs = db.execute(
                "SELECT * FROM vp_runs WHERE learner_id=? ORDER BY created_at", (learner_id,)
            ).fetchall()
            attempts = db.execute(
                "SELECT * FROM vp_quiz_attempts WHERE learner_id=?", (learner_id,)
            ).fetchall()
            drafts = db.execute(
                "SELECT * FROM vp_drafts WHERE learner_id=?", (learner_id,)
            ).fetchall()
        return {
            "format_version": 1,
            "exported_at": now_iso(),
            "profile": self.profile(learner_id),
            "progress": self.progress(learner_id),
            "runs": [dict(r) for r in runs],
            "quiz_attempts": [dict(r) for r in attempts],
            "drafts": [dict(r) for r in drafts],
            "reviews": self.reviews(learner_id),
            "project_evidence": self.project_evidence(learner_id),
        }

    def project_evidence(self, learner_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM vp_project_evidence WHERE learner_id=?", (learner_id,)
            ).fetchall()
        result = []
        for row in rows:
            record = dict(row)
            record["metrics"] = json.loads(record.pop("metrics_json"))
            result.append(record)
        return result

    def save_project_evidence(
        self, learner_id: str, project_id: str, milestone_id: str, data: dict[str, Any]
    ) -> None:
        with self.connect() as db:
            db.execute(
                """INSERT INTO vp_project_evidence VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(learner_id,project_id,milestone_id) DO UPDATE SET
                   summary=excluded.summary,command=excluded.command,artifact=excluded.artifact,
                   metrics_json=excluded.metrics_json,updated_at=excluded.updated_at""",
                (
                    learner_id,
                    project_id,
                    milestone_id,
                    data["summary"],
                    data["command"],
                    data["artifact"],
                    json.dumps(data["metrics"]),
                    now_iso(),
                ),
            )
