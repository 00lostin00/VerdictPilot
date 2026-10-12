from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .catalog import LearningCatalog
from .models import TestCase
from .platform_store import PlatformStore
from .sandbox import CppRunner

logger = logging.getLogger(__name__)


class QueueFullError(RuntimeError):
    pass


class LearningPlatform:
    def __init__(self, store: PlatformStore, catalog: LearningCatalog, runner: CppRunner) -> None:
        self.store = store
        self.catalog = catalog
        self.runner = runner
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="verdictpilot-judge")
        self.capacity = threading.BoundedSemaphore(16)
        self.diagnosis_capacity = threading.BoundedSemaphore(4)

    def close(self) -> None:
        self.executor.shutdown(wait=True)

    def submit(self, learner_id: str, problem_id: str, code: str) -> dict[str, Any]:
        problem = self.catalog.problems[problem_id]
        if not self.capacity.acquire(blocking=False):
            raise QueueFullError("提交队列已满，请稍后再试")
        run_id = None
        try:
            run_id = self.store.create_run(
                learner_id, "submission", problem["title"], code, problem_id
            )
            self.store.save_draft(learner_id, problem_id, code)
            self.executor.submit(self._judge, run_id, problem_id, code)
        except Exception:
            self.capacity.release()
            if run_id is not None:
                self.store.fail_run(run_id, "任务未能进入执行队列，请重新提交")
            raise
        return {"run_id": run_id, "status": "queued"}

    def _judge(self, run_id: str, problem_id: str, code: str) -> None:
        start = time.perf_counter()
        try:
            self.store.start_run(run_id)
            problem = self.catalog.problems[problem_id]
            report = self.runner.run(
                code, [TestCase.model_validate(case) for case in problem["judge_cases"]]
            )
            # Return evidence for this bank's cases, never an unverifiable OJ acceptance claim.
            self.store.finish_run(
                run_id,
                {
                    "execution": report.model_dump(),
                    "case_count": len(problem["judge_cases"]),
                    "catalog_version": self.catalog.version,
                },
                round((time.perf_counter() - start) * 1000, 2),
            )
        except Exception:
            logger.exception("Judge failed for run %s", run_id)
            self.store.fail_run(run_id, "执行服务发生异常，请检查服务日志后重试")
        finally:
            self.capacity.release()
