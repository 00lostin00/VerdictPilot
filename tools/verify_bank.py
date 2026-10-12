"""Run every reference solution against the versioned problem-bank cases."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from verdictpilot.catalog import LearningCatalog
from verdictpilot.config import Settings
from verdictpilot.models import TestCase
from verdictpilot.sandbox import LocalCppRunner


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = LearningCatalog(root / "content")
    runner = LocalCppRunner(replace(Settings.from_env(root), allow_unsafe_local_execution=True))
    failures = []
    count = 0
    for problem in catalog.problems.values():
        cases = [TestCase.model_validate(case) for case in problem["judge_cases"]]
        report = runner.run(problem["reference_solution"], cases)
        count += len(cases)
        print(f"{problem['id']}: {report.status}", flush=True)
        if report.status != "passed":
            failures.append(problem["id"])
            print(report.model_dump_json(indent=2), flush=True)
    if failures:
        raise SystemExit(f"Problem bank validation failed: {failures}")
    print(f"Passed: {len(catalog.problems)} reference programs, {count} test cases.")


if __name__ == "__main__":
    main()
