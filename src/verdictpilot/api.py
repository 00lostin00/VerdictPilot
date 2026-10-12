from __future__ import annotations

import logging
import mimetypes
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .coach import VerdictPilotCoach
from .config import Settings
from .models import AnalyzeRequest, AnalyzeResponse, MistakeRecord
from .openai_agent import OpenAIConfigurationError
from .platform_api import Learner, router
from .services import AppServices


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    # Windows registry MIME values can override the standard SVG media type.
    mimetypes.add_type("image/svg+xml", ".svg")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = AppServices.create(resolved_settings)
        app.state.services.platform.store.recover_interrupted_runs()
        try:
            yield
        finally:
            app.state.services.platform.close()

    app = FastAPI(
        title="VerdictPilot API",
        version="0.2.0",
        description="Agentic algorithm coaching with retrieval, execution, memory, and traces.",
        lifespan=lifespan,
    )
    app.mount(
        "/assets", StaticFiles(directory=resolved_settings.project_root / "web"), name="assets"
    )
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(resolved_settings.project_root / "web" / "index.html")

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        services: AppServices = request.app.state.services
        return {
            "status": "ok",
            "provider": services.settings.provider,
            "execution_backend": services.runner.backend_name,
            "version": "0.2.0",
        }

    @app.post("/v1/analyze", response_model=AnalyzeResponse)
    async def analyze(
        payload: AnalyzeRequest, request: Request, learner_id: Learner = "local"
    ) -> AnalyzeResponse:
        services: AppServices = request.app.state.services
        if not services.platform.diagnosis_capacity.acquire(blocking=False):
            raise HTTPException(429, "诊断服务忙，请稍后再试", headers={"Retry-After": "3"})
        run_id = None
        try:
            # Preserve legacy API clients that identify memory by the payload's session_id.
            identity = learner_id if "learner_id" in request.query_params else payload.session_id
            run_id = services.platform.store.create_run(
                identity, "diagnosis", payload.title, payload.code
            )
            services.platform.store.start_run(run_id)
            start = time.perf_counter()
            payload = payload.model_copy(update={"session_id": identity})
            response = await VerdictPilotCoach(services).analyze(payload)
            services.platform.store.finish_run(
                run_id,
                response.model_dump(mode="json"),
                round((time.perf_counter() - start) * 1000, 2),
            )
            return response.model_copy(update={"platform_run_id": run_id})
        except OpenAIConfigurationError as error:
            if run_id is not None:
                services.platform.store.fail_run(run_id, str(error))
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            logging.getLogger(__name__).exception("Diagnosis failed for run %s", run_id)
            if run_id is not None:
                services.platform.store.fail_run(run_id, "诊断服务异常，请检查配置与服务日志")
            raise HTTPException(502, "诊断服务异常，请检查配置与服务日志") from error
        finally:
            services.platform.diagnosis_capacity.release()

    @app.get("/v1/knowledge/search")
    def search_knowledge(
        request: Request,
        q: str = Query(min_length=1, max_length=300),
        limit: int = Query(default=4, ge=1, le=10),
    ):
        services: AppServices = request.app.state.services
        return services.knowledge.search(q, limit=limit)

    @app.get("/v1/mistakes", response_model=list[MistakeRecord])
    def list_mistakes(
        request: Request,
        session_id: str = Query(default="default", min_length=1),
        topic: str = Query(default=""),
    ) -> list[MistakeRecord]:
        services: AppServices = request.app.state.services
        return services.memory.search(session_id, topic)

    return app


app = create_app()
