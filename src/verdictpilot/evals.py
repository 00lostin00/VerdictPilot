from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

from .config import Settings
from .knowledge import KnowledgeStore
from .models import TestCase
from .sandbox import LocalCppRunner


def _load_cases(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def run_offline_evals(settings: Settings) -> dict[str, Any]:
    settings.ensure_directories()
    store = KnowledgeStore(settings.database_path)
    store.bootstrap(settings.knowledge_dir)
    cases = _load_cases(settings.project_root / "evals" / "cases.jsonl")
    details: list[dict[str, Any]] = []
    retrieval_total = retrieval_hits = 0
    execution_total = execution_hits = 0

    local_settings = replace(
        settings,
        execution_backend="local",
        allow_unsafe_local_execution=True,
    )
    runner = LocalCppRunner(local_settings)

    for case in cases:
        if case["kind"] == "retrieval":
            retrieval_total += 1
            results = store.search(case["query"], limit=3)
            returned = [result.doc_id for result in results]
            passed = case["expected_doc_id"] in returned
            retrieval_hits += int(passed)
            details.append(
                {
                    "id": case["id"],
                    "kind": "retrieval",
                    "passed": passed,
                    "returned": returned,
                }
            )
        elif case["kind"] == "execution":
            execution_total += 1
            report = runner.run(
                case["source_code"],
                [TestCase.model_validate(item) for item in case["test_cases"]],
            )
            passed = report.status == case["expected_status"]
            execution_hits += int(passed)
            details.append(
                {
                    "id": case["id"],
                    "kind": "execution",
                    "passed": passed,
                    "expected": case["expected_status"],
                    "actual": report.status,
                }
            )

    compiler_available = shutil.which("g++") is not None
    passed_count = sum(int(item["passed"]) for item in details)
    return {
        "cases": len(details),
        "passed": passed_count,
        "pass_rate": round(passed_count / max(len(details), 1), 4),
        "retrieval_hit_at_3": round(retrieval_hits / max(retrieval_total, 1), 4),
        "execution_classification_accuracy": round(execution_hits / max(execution_total, 1), 4),
        "compiler_available": compiler_available,
        "details": details,
    }
