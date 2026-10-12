from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat

LearnerId = str


class QuizSubmission(BaseModel):
    answers: list[int] = Field(min_length=1, max_length=20)


class LessonNote(BaseModel):
    note: str = Field(default="", max_length=10000)
    exercise_done: bool = False


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)
    goal: str = Field(max_length=200)
    daily_minutes: int = Field(ge=15, le=240)


class CodeSubmission(BaseModel):
    code: str = Field(min_length=1, max_length=60000)


class DraftUpdate(BaseModel):
    code: str = Field(default="", max_length=60000)


class MistakeCreate(BaseModel):
    run_id: str = Field(min_length=1, max_length=64)
    category: Literal["boundary", "complexity", "implementation", "modeling", "other"]
    lesson: str = Field(min_length=3, max_length=3000)


class ReviewSubmission(BaseModel):
    rating: Literal["again", "hard", "good", "easy"]


class ProjectEvidence(BaseModel):
    summary: str = Field(min_length=10, max_length=10000)
    command: str = Field(min_length=3, max_length=2000)
    artifact: str = Field(min_length=3, max_length=1000)
    metrics: dict[str, FiniteFloat] = Field(default_factory=dict, max_length=20)
