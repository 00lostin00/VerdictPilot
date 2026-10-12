from __future__ import annotations

import pytest

from verdictpilot.models import AnalyzeRequest
from verdictpilot.offline import OfflineCoach
from verdictpilot.services import AppServices


@pytest.mark.asyncio
async def test_offline_coach_returns_sources_and_trace(settings) -> None:
    services = AppServices.create(settings)
    response = await OfflineCoach(services).analyze(
        AnalyzeRequest(
            title="网格最短路",
            statement="在 0/1 网格中上下左右移动，求最少步数。",
            mode="hint",
            provider="offline",
        )
    )
    assert response.provider == "offline"
    assert any(document.doc_id == "graphs" for document in response.retrieved)
    assert "检索依据" in response.answer_markdown
    assert settings.trace_path.exists()
    assert response.run_id in settings.trace_path.read_text(encoding="utf-8")
