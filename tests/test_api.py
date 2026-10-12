from types import SimpleNamespace

from fastapi.testclient import TestClient

from verdictpilot.api import create_app


def test_health_and_offline_analysis(settings) -> None:
    with TestClient(create_app(settings)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["execution_backend"] == "disabled"

        response = client.post(
            "/v1/analyze",
            json={
                "title": "01 背包",
                "statement": "每个物品最多选择一次，求容量限制下最大价值。",
                "mode": "hint",
                "provider": "offline",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "offline"
        assert any(item["doc_id"] == "dynamic-programming" for item in payload["retrieved"])


def test_openai_mode_requires_key(settings, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/analyze",
            json={
                "title": "Graph",
                "statement": "Find the shortest path.",
                "provider": "openai",
            },
        )
        assert response.status_code == 400
        assert "OPENAI_API_KEY" in response.json()["detail"]


def test_openai_agent_constructs_tools_without_network(settings, monkeypatch) -> None:
    from agents import Runner

    async def fake_run(agent, input):
        assert agent.name == "VerdictPilot"
        assert len(agent.tools) == 4
        assert "Graph" in input
        return SimpleNamespace(final_output="diagnosis from stub")

    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setattr(Runner, "run", fake_run)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/analyze",
            json={
                "title": "Graph",
                "statement": "Find the shortest path.",
                "provider": "openai",
            },
        )
        assert response.status_code == 200
        assert response.json()["provider"] == "openai"
        assert response.json()["answer_markdown"] == "diagnosis from stub"
