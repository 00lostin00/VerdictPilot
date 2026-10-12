from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request

from .platform_models import (
    CodeSubmission,
    DraftUpdate,
    LessonNote,
    MistakeCreate,
    ProfileUpdate,
    ProjectEvidence,
    QuizSubmission,
    ReviewSubmission,
)
from .platform_service import LearningPlatform, QueueFullError

router = APIRouter(prefix="/v1", tags=["Learning platform"])
Learner = Annotated[str, Query(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")]


def platform(request: Request) -> LearningPlatform:
    return request.app.state.services.platform


def require_lesson(service: LearningPlatform, lesson_id: str) -> None:
    if lesson_id not in service.catalog.lessons:
        raise HTTPException(404, "课程不存在")


def require_problem(service: LearningPlatform, problem_id: str) -> None:
    if problem_id not in service.catalog.problems:
        raise HTTPException(404, "题目不存在")


@router.get("/dashboard")
def dashboard(request: Request, learner_id: Learner = "local"):
    service = platform(request)
    return service.store.dashboard(learner_id, service.catalog)


@router.get("/catalog")
def catalog(request: Request, learner_id: Learner = "local"):
    service = platform(request)
    return {
        "version": service.catalog.version,
        "tracks": service.catalog.tracks,
        "lessons": service.catalog.lesson_summaries(),
        "progress": service.store.progress(learner_id),
    }


@router.get("/lessons/{lesson_id}")
def lesson(lesson_id: str, request: Request, learner_id: Learner = "local"):
    service = platform(request)
    require_lesson(service, lesson_id)
    return {
        **service.catalog.public_lesson(lesson_id),
        "progress": service.store.progress(learner_id).get(lesson_id),
    }


@router.post("/lessons/{lesson_id}/quiz")
def quiz(lesson_id: str, payload: QuizSubmission, request: Request, learner_id: Learner = "local"):
    service = platform(request)
    require_lesson(service, lesson_id)
    try:
        result = service.catalog.grade(lesson_id, payload.answers)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    service.store.record_quiz(learner_id, lesson_id, result["score"])
    return result


@router.put("/lessons/{lesson_id}/note")
def note(lesson_id: str, payload: LessonNote, request: Request, learner_id: Learner = "local"):
    service = platform(request)
    require_lesson(service, lesson_id)
    service.store.save_note(learner_id, lesson_id, payload.note, payload.exercise_done)
    return {"saved": True}


@router.get("/problems")
def problems(request: Request, learner_id: Learner = "local", q: str = "", tag: str = ""):
    service = platform(request)
    items = [
        p
        for p in service.catalog.problem_summaries()
        if (not q or q.lower() in (p["title"] + " ".join(p["tags"])).lower())
        and (not tag or tag in p["tags"])
    ]
    return {"items": items, "progress": service.store.problem_status(learner_id)}


@router.get("/problems/{problem_id}")
def problem(problem_id: str, request: Request, learner_id: Learner = "local"):
    service = platform(request)
    require_problem(service, problem_id)
    return {
        **service.catalog.public_problem(problem_id),
        "draft": service.store.draft(learner_id, problem_id),
    }


@router.put("/problems/{problem_id}/draft")
def draft(problem_id: str, payload: DraftUpdate, request: Request, learner_id: Learner = "local"):
    service = platform(request)
    require_problem(service, problem_id)
    service.store.save_draft(learner_id, problem_id, payload.code)
    return {"saved": True}


@router.post("/problems/{problem_id}/submit", status_code=202)
def submit(
    problem_id: str, payload: CodeSubmission, request: Request, learner_id: Learner = "local"
):
    service = platform(request)
    require_problem(service, problem_id)
    try:
        return service.submit(learner_id, problem_id, payload.code)
    except QueueFullError as error:
        raise HTTPException(429, str(error), headers={"Retry-After": "3"}) from error


@router.get("/runs")
def runs(
    request: Request,
    learner_id: Learner = "local",
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return platform(request).store.runs(learner_id, limit, offset)


@router.get("/runs/{run_id}")
def run(run_id: str, request: Request, learner_id: Learner = "local"):
    try:
        item = platform(request).store.run(learner_id, run_id)
    except KeyError as error:
        raise HTTPException(404, "运行记录不存在") from error
    trace_id = (item["result"] or {}).get("run_id")
    events: list[dict[str, Any]] = []
    path = request.app.state.services.settings.trace_path
    if trace_id and path.exists():
        # Bounded tail: large logs never become an unbounded read on a web request.
        with path.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - 2_000_000))
            if size > 2_000_000:
                stream.readline()
            for line in stream:
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                if event.get("run_id") == trace_id:
                    events.append(event)
    item["events"] = events[-100:]
    return item


@router.get("/reviews")
def reviews(request: Request, learner_id: Learner = "local"):
    return {"items": platform(request).store.reviews(learner_id)}


@router.post("/reviews", status_code=201)
def save_mistake(payload: MistakeCreate, request: Request, learner_id: Learner = "local"):
    try:
        identifier = platform(request).store.add_mistake(
            learner_id, payload.run_id, payload.category, payload.lesson
        )
    except KeyError as error:
        raise HTTPException(404, "运行记录不存在") from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return {"id": identifier}


@router.post("/reviews/{mistake_id}/practice")
def review(
    mistake_id: int, payload: ReviewSubmission, request: Request, learner_id: Learner = "local"
):
    try:
        return platform(request).store.review(learner_id, mistake_id, payload.rating)
    except KeyError as error:
        raise HTTPException(404, "错题不存在") from error


@router.get("/profile")
def profile(request: Request, learner_id: Learner = "local"):
    return platform(request).store.profile(learner_id)


@router.put("/profile")
def update_profile(payload: ProfileUpdate, request: Request, learner_id: Learner = "local"):
    return platform(request).store.update_profile(learner_id, payload.model_dump())


@router.get("/export")
def export(request: Request, learner_id: Learner = "local"):
    return platform(request).store.export(learner_id)


@router.get("/projects")
def projects(request: Request, learner_id: Learner = "local"):
    service = platform(request)
    return {
        "items": list(service.catalog.projects.values()),
        "evidence": service.store.project_evidence(learner_id),
    }


@router.put("/projects/{project_id}/milestones/{milestone_id}")
def project_evidence(
    project_id: str,
    milestone_id: str,
    payload: ProjectEvidence,
    request: Request,
    learner_id: Learner = "local",
):
    service = platform(request)
    project = service.catalog.projects.get(project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    milestone = next((m for m in project["milestones"] if m["id"] == milestone_id), None)
    if milestone is None:
        raise HTTPException(404, "里程碑不存在")
    if set(payload.metrics) != set(milestone["metrics"]):
        raise HTTPException(422, "请记录该里程碑要求的全部指标，且不要添加未知指标")
    if any(value < 0 for value in payload.metrics.values()):
        raise HTTPException(422, "指标不能为负数")
    for name, value in payload.metrics.items():
        if (
            "rate" in name
            or "accuracy" in name
            or "coverage" in name
            or name in {"hit_at_3", "mrr", "reduction_ratio"}
        ) and value > 1:
            raise HTTPException(422, "比例指标请填写 0 到 1 的值")
    service.store.save_project_evidence(learner_id, project_id, milestone_id, payload.model_dump())
    return {"saved": True, "verification": "learner_reported"}


@router.get("/knowledge/documents")
def knowledge_documents(request: Request):
    documents = request.app.state.services.knowledge.documents()
    return {"items": [{k: v for k, v in doc.items() if k != "body"} for doc in documents]}


@router.get("/knowledge/documents/{doc_id}")
def knowledge_document(doc_id: str, request: Request):
    # Lookup by indexed ID, never interpolate a client path into filesystem access.
    for document in request.app.state.services.knowledge.documents():
        if document["id"] == doc_id:
            return document
    raise HTTPException(404, "知识文档不存在")
