import time

from fastapi.testclient import TestClient

from verdictpilot.api import create_app
from verdictpilot.models import CaseResult, ExecutionReport


def await_run(client, run_id, learner="alice"):
    for _ in range(100):
        response = client.get(f"/v1/runs/{run_id}?learner_id={learner}")
        assert response.status_code == 200
        run = response.json()
        if run["status"] not in {"queued", "running"}:
            return run
        time.sleep(0.01)
    raise AssertionError("Background task did not finish")


class DeterministicRunner:
    backend_name = "test-runner"

    def run(self, code, cases):
        status = "passed" if code == "correct" else "wrong_answer"
        return ExecutionReport(
            status=status,
            backend=self.backend_name,
            cases=[
                CaseResult(
                    name=case.name,
                    status=status,
                    stdout="5" if status == "passed" else "-1",
                    expected_output=case.expected_output,
                )
                for case in cases
            ],
        )


def test_catalog_hides_answers_and_judge_material(settings):
    with TestClient(create_app(settings)) as client:
        catalog = client.get("/v1/catalog").json()
        assert len(catalog["tracks"]) == 6
        assert len(catalog["lessons"]) == 24
        lesson = client.get("/v1/lessons/complexity").json()
        assert all("answer" not in q and "explanation" not in q for q in lesson["quiz"])
        problem = client.get("/v1/problems/sum").json()
        assert "judge_cases" not in problem and "reference_solution" not in problem
        assert client.get("/v1/lessons/missing").status_code == 404
        assert client.get("/v1/problems/missing").status_code == 404


def test_quiz_progress_note_and_best_score_are_persistent(settings):
    with TestClient(create_app(settings)) as client:
        endpoint = "/v1/lessons/complexity"
        correct = [
            q["answer"]
            for q in client.app.state.services.platform.catalog.lesson("complexity")["quiz"]
        ]
        assert (
            client.post(endpoint + "/quiz?learner_id=alice", json={"answers": correct}).json()[
                "score"
            ]
            == 100
        )
        assert (
            client.put(
                endpoint + "/note?learner_id=alice",
                json={"note": "总工作量必须考虑每个测试组", "exercise_done": True},
            ).status_code
            == 200
        )
        wrong = [(a + 1) % 4 for a in correct]
        assert (
            client.post(endpoint + "/quiz?learner_id=alice", json={"answers": wrong}).json()[
                "score"
            ]
            == 0
        )
        assert client.post(endpoint + "/quiz", json={"answers": [99]}).status_code == 422
        assert client.post(endpoint + "/quiz", json={"answers": [-1, -1]}).status_code == 422
    with TestClient(create_app(settings)) as client:
        progress = client.get(endpoint + "?learner_id=alice").json()["progress"]
        assert progress["best_score"] == 100 and progress["last_score"] == 0
        assert progress["exercise_done"] == 1 and "测试组" in progress["note"]
        dashboard = client.get("/v1/dashboard?learner_id=alice").json()
        assert dashboard["metrics"]["lessons_passed"] == 1
        assert dashboard["metrics"]["activity_total"] == 2
        assert client.get("/v1/dashboard?learner_id=bob").json()["metrics"]["lessons_passed"] == 0


def test_submission_drafts_evidence_and_review_flow(settings):
    with TestClient(create_app(settings)) as client:
        client.app.state.services.platform.runner = DeterministicRunner()
        response = client.post("/v1/problems/sum/submit?learner_id=alice", json={"code": "wrong"})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        run = await_run(client, run_id)
        assert run["verdict"] == "wrong_answer" and run["result"]["case_count"] == 5
        assert client.get(f"/v1/runs/{run_id}?learner_id=bob").status_code == 404
        assert client.get("/v1/problems/sum?learner_id=alice").json()["draft"]["code"] == "wrong"
        assert client.get("/v1/problems/sum?learner_id=bob").json()["draft"] is None
        mistake = {
            "run_id": run_id,
            "category": "implementation",
            "lesson": "加法题误写成减法，应核对运算符",
        }
        saved = client.post("/v1/reviews?learner_id=alice", json=mistake)
        assert saved.status_code == 201
        identifier = saved.json()["id"]
        assert client.post("/v1/reviews?learner_id=alice", json=mistake).json()["id"] == identifier
        assert len(client.get("/v1/reviews?learner_id=alice").json()["items"]) == 1
        assert client.get("/v1/dashboard?learner_id=alice").json()["metrics"]["due_reviews"] == 1
        review = client.post(
            f"/v1/reviews/{identifier}/practice?learner_id=alice", json={"rating": "good"}
        )
        assert review.json()["interval_days"] == 2
        assert client.get("/v1/dashboard?learner_id=alice").json()["metrics"]["due_reviews"] == 0
        assert (
            client.post(
                f"/v1/reviews/{identifier}/practice?learner_id=bob", json={"rating": "easy"}
            ).status_code
            == 404
        )
        assert "加法题" in client.get("/v1/mistakes?session_id=alice").json()[0]["lesson"]
        good_id = client.post(
            "/v1/problems/sum/submit?learner_id=alice", json={"code": "correct"}
        ).json()["run_id"]
        assert await_run(client, good_id)["verdict"] == "passed"
        mistake["run_id"] = good_id
        assert client.post("/v1/reviews?learner_id=alice", json=mistake).status_code == 409
        assert (
            client.get("/v1/dashboard?learner_id=alice").json()["metrics"]["problems_passed"] == 1
        )
        export = client.get("/v1/export?learner_id=alice").json()
        assert len(export["runs"]) == 2 and len(export["reviews"]) == 1


def test_disabled_execution_does_not_count_as_solved(settings):
    with TestClient(create_app(settings)) as client:
        run_id = client.post("/v1/problems/sum/submit", json={"code": "int main(){}"}).json()[
            "run_id"
        ]
        run = await_run(client, run_id, "local")
        assert run["verdict"] == "disabled"
        assert client.get("/v1/dashboard").json()["metrics"]["problems_passed"] == 0
        assert client.post("/v1/problems/sum/submit", json={"code": ""}).status_code == 422


def test_queue_backpressure_creates_no_orphan_task(settings):
    with TestClient(create_app(settings)) as client:
        service = client.app.state.services.platform
        for _ in range(16):
            assert service.capacity.acquire(blocking=False)
        try:
            response = client.post("/v1/problems/sum/submit", json={"code": "int main(){}"})
            assert response.status_code == 429 and response.headers["retry-after"] == "3"
            assert client.get("/v1/runs").json()["total"] == 0
        finally:
            for _ in range(16):
                service.capacity.release()


def test_run_recovery_profile_and_knowledge(settings):
    with TestClient(create_app(settings)) as client:
        store = client.app.state.services.platform.store
        run_id = store.create_run("alice", "submission", "interrupted", "code", "sum")
        profile = {"display_name": "留安", "goal": "建立自己的评测集", "daily_minutes": 60}
        assert (
            client.put("/v1/profile?learner_id=alice", json=profile).json()["display_name"]
            == "留安"
        )
        assert client.get("/v1/knowledge/documents").json()["items"]
        assert "BFS" in client.get("/v1/knowledge/documents/graphs").json()["body"]
        assert client.get("/v1/knowledge/documents/not-indexed").status_code == 404
        assert client.get("/assets/app.js").status_code == 200
        for name in ("logo.svg", "favicon.svg"):
            response = client.get(f"/assets/{name}")
            assert response.status_code == 200
            assert response.headers["content-type"].split(";")[0] == "image/svg+xml"
    with TestClient(create_app(settings)) as client:
        interrupted = client.get(f"/v1/runs/{run_id}?learner_id=alice").json()
        assert interrupted["status"] == "interrupted"
        assert interrupted["result"] is None and "result_json" not in interrupted
        assert client.get("/v1/profile?learner_id=alice").json()["daily_minutes"] == 60


def test_diagnosis_saves_history_and_trace(settings):
    with TestClient(create_app(settings)) as client:
        payload = {"title": "BFS", "statement": "无权图最短路与入队标记", "provider": "offline"}
        response = client.post("/v1/analyze?learner_id=alice", json=payload)
        assert response.status_code == 200
        identifier = response.json()["platform_run_id"]
        run = client.get(f"/v1/runs/{identifier}?learner_id=alice").json()
        assert run["result"]["answer_markdown"] == response.json()["answer_markdown"]
        assert run["events"] and run["events"][0]["event"] == "workflow.started"
        assert run["events"][-1]["event"] == "workflow.completed"


def test_queue_worker_failure_is_recorded_and_capacity_released(settings):
    class BrokenRunner:
        def run(self, code, cases):
            raise RuntimeError("private internal details")

    with TestClient(create_app(settings)) as client:
        service = client.app.state.services.platform
        service.runner = BrokenRunner()
        identifier = client.post("/v1/problems/sum/submit", json={"code": "code"}).json()["run_id"]
        run = await_run(client, identifier, "local")
        assert run["status"] == "failed" and "private" not in run["error"]
        for _ in range(16):
            assert service.capacity.acquire(blocking=False)
        for _ in range(16):
            service.capacity.release()


def test_diagnosis_backpressure_and_legacy_session_identity(settings):
    with TestClient(create_app(settings)) as client:
        service = client.app.state.services.platform
        payload = {"title": "BFS", "statement": "无权图最短路", "session_id": "legacy"}
        for _ in range(4):
            assert service.diagnosis_capacity.acquire(blocking=False)
        try:
            response = client.post("/v1/analyze", json=payload)
            assert response.status_code == 429 and response.headers["retry-after"] == "3"
            assert client.get("/v1/runs?learner_id=legacy").json()["total"] == 0
        finally:
            for _ in range(4):
                service.diagnosis_capacity.release()
        response = client.post("/v1/analyze", json=payload)
        assert response.status_code == 200
        identifier = response.json()["platform_run_id"]
        assert client.get(f"/v1/runs/{identifier}?learner_id=legacy").status_code == 200
        assert client.get(f"/v1/runs/{identifier}?learner_id=local").status_code == 404


def test_project_evidence_requires_reproducible_fields_and_valid_metrics(settings):
    with TestClient(create_app(settings)) as client:
        projects = client.get("/v1/projects").json()
        assert len(projects["items"]) == 4
        path = "/v1/projects/retrieval-engine/milestones/dataset?learner_id=alice"
        evidence = {
            "summary": "完成三十篇算法资料入库，标注六十条查询并冻结测试划分。",
            "command": "python ingest.py && python validate_queries.py",
            "artifact": "reports/dataset-v1.json · commit abc123",
            "metrics": {"documents": 30, "queries": 60},
        }
        assert client.put(path, json=evidence).json()["verification"] == "learner_reported"
        evidence["metrics"] = {"documents": 30}
        assert client.put(path, json=evidence).status_code == 422
        evidence["metrics"] = {"documents": -1, "queries": 60}
        assert client.put(path, json=evidence).status_code == 422
        baseline = "/v1/projects/retrieval-engine/milestones/baseline?learner_id=alice"
        evidence["metrics"] = {"hit_at_3": 80, "mrr": 0.7, "p95_ms": 12}
        assert client.put(baseline, json=evidence).status_code == 422
        assert client.get("/v1/projects?learner_id=bob").json()["evidence"] == []
        exported = client.get("/v1/export?learner_id=alice").json()
        assert exported["project_evidence"][0]["metrics"]["documents"] == 30
