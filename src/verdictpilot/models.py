from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    name: str = "sample"
    input: str = Field(default="", max_length=20000)
    expected_output: str | None = Field(default=None, max_length=20000)


class AnalyzeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=30000)
    code: str | None = Field(default=None, max_length=60000)
    test_cases: list[TestCase] = Field(default_factory=list, max_length=30)
    mode: Literal["hint", "diagnose", "review"] = "diagnose"
    provider: Literal["offline", "openai"] | None = None
    session_id: str = Field(default="default", min_length=1, max_length=100)


class RetrievedDocument(BaseModel):
    doc_id: str
    title: str
    source: str
    score: float
    snippet: str


class CaseResult(BaseModel):
    name: str
    status: Literal["passed", "wrong_answer", "runtime_error", "time_limit", "output_limit"]
    stdout: str = ""
    stderr: str = ""
    elapsed_ms: float = 0.0
    expected_output: str | None = None


class ExecutionReport(BaseModel):
    status: Literal[
        "disabled",
        "compile_error",
        "passed",
        "wrong_answer",
        "runtime_error",
        "time_limit",
        "internal_error",
        "output_limit",
    ]
    backend: str
    compile_output: str = ""
    cases: list[CaseResult] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    run_id: str
    provider: Literal["offline", "openai"]
    answer_markdown: str
    retrieved: list[RetrievedDocument] = Field(default_factory=list)
    execution: ExecutionReport | None = None
    trace_path: str
    platform_run_id: str | None = None


class MistakeRecord(BaseModel):
    id: int
    session_id: str
    problem_title: str
    category: str
    symptom: str
    lesson: str
    created_at: datetime


class NewMistake(BaseModel):
    session_id: str
    problem_title: str
    category: str
    symptom: str
    lesson: str
