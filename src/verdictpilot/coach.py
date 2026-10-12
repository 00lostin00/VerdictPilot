from __future__ import annotations

import asyncio

from starlette.concurrency import run_in_threadpool

from .models import AnalyzeRequest, AnalyzeResponse
from .offline import OfflineCoach
from .openai_agent import OpenAICoach
from .services import AppServices


class VerdictPilotCoach:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        provider = request.provider or self.services.settings.provider
        if provider == "openai":
            return await OpenAICoach(self.services).analyze(request)
        # Offline tools are synchronous (SQLite and compiler processes); keep the ASGI loop free.
        return await run_in_threadpool(
            lambda: asyncio.run(OfflineCoach(self.services).analyze(request))
        )
