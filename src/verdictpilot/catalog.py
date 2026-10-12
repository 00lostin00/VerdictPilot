from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class LearningCatalog:
    """Versioned learning material; answers and judge cases stay on the server."""

    def __init__(self, directory: Path) -> None:
        curriculum = json.loads((directory / "curriculum.json").read_text(encoding="utf-8"))
        problems = json.loads((directory / "problems.json").read_text(encoding="utf-8"))
        self.version: str = curriculum["version"]
        self.tracks: list[dict[str, Any]] = curriculum["tracks"]
        self.lessons = {item["id"]: item for item in curriculum["lessons"]}
        self.problems = {item["id"]: item for item in problems["problems"]}
        projects = json.loads((directory / "projects.json").read_text(encoding="utf-8"))
        self.projects = {item["id"]: item for item in projects["projects"]}
        for lesson in self.lessons.values():
            if lesson["track_id"] not in {t["id"] for t in self.tracks}:
                raise ValueError(f"Unknown track in {lesson['id']}")
            if not set(lesson["prerequisites"]) <= self.lessons.keys():
                raise ValueError(f"Unknown prerequisite in {lesson['id']}")

    def lesson(self, lesson_id: str) -> dict[str, Any]:
        return self.lessons[lesson_id]

    def public_lesson(self, lesson_id: str) -> dict[str, Any]:
        result = deepcopy(self.lesson(lesson_id))
        for question in result["quiz"]:
            question.pop("answer")
            question.pop("explanation")
        return result

    def lesson_summaries(self) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in lesson.items() if k not in {"body", "quiz", "exercise"}}
            for lesson in self.lessons.values()
        ]

    def public_problem(self, problem_id: str) -> dict[str, Any]:
        return {
            key: deepcopy(value)
            for key, value in self.problems[problem_id].items()
            if key not in {"judge_cases", "reference_solution"}
        }

    def problem_summaries(self) -> list[dict[str, Any]]:
        keys = {"id", "title", "difficulty", "tags", "lesson_id", "description"}
        return [{k: v for k, v in p.items() if k in keys} for p in self.problems.values()]

    def grade(self, lesson_id: str, answers: list[int]) -> dict[str, Any]:
        quiz = self.lesson(lesson_id)["quiz"]
        if len(answers) != len(quiz):
            raise ValueError(f"请回答全部 {len(quiz)} 道题")
        if any(
            answer < 0 or answer >= len(q["options"])
            for q, answer in zip(quiz, answers, strict=True)
        ):
            raise ValueError("无效的答案选项")
        results = [
            {
                "correct": answer == q["answer"],
                "answer": q["answer"],
                "explanation": q["explanation"],
            }
            for q, answer in zip(quiz, answers, strict=True)
        ]
        score = round(100 * sum(q["correct"] for q in results) / len(results))
        return {"score": score, "passed": score >= 80, "questions": results}
