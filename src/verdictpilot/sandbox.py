from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Protocol

from .config import Settings
from .models import CaseResult, ExecutionReport, TestCase
from .process_io import bounded_process


def _truncate(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return value
    clipped = encoded[:max_bytes].decode("utf-8", errors="replace")
    return clipped + "\n...[output truncated]"


def _normalize_output(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").strip().splitlines())


class CppRunner(Protocol):
    backend_name: str

    def run(self, source_code: str, test_cases: list[TestCase]) -> ExecutionReport: ...


class DisabledCppRunner:
    backend_name = "disabled"

    def run(self, source_code: str, test_cases: list[TestCase]) -> ExecutionReport:
        return ExecutionReport(
            status="disabled",
            backend=self.backend_name,
            compile_output=(
                "Code execution is disabled. Set VERDICTPILOT_EXECUTION_BACKEND=docker, "
                "or explicitly opt into the unsafe local teaching backend."
            ),
        )


class LocalCppRunner:
    """Run trusted teaching examples on the host.

    This backend is deliberately opt-in and must never be exposed to untrusted users.
    Untrusted code requires a separately isolated judge with deployment-specific controls.
    """

    backend_name = "local-unsafe"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, source_code: str, test_cases: list[TestCase]) -> ExecutionReport:
        if not self.settings.allow_unsafe_local_execution:
            return ExecutionReport(
                status="disabled",
                backend=self.backend_name,
                compile_output=(
                    "Local execution requires VERDICTPILOT_ALLOW_UNSAFE_LOCAL_EXECUTION=true."
                ),
            )
        compiler = shutil.which("g++")
        if compiler is None:
            return ExecutionReport(
                status="internal_error",
                backend=self.backend_name,
                compile_output="g++ was not found on PATH.",
            )

        with tempfile.TemporaryDirectory(prefix="verdictpilot-") as temporary:
            working_dir = Path(temporary)
            source_path = working_dir / "main.cpp"
            executable_path = working_dir / ("main.exe" if os.name == "nt" else "main")
            source_path.write_text(source_code, encoding="utf-8")
            compile_command = [
                compiler,
                "-std=c++20",
                "-O2",
                "-pipe",
                "-Wall",
                "-Wextra",
                str(source_path),
                "-o",
                str(executable_path),
            ]
            compiled = bounded_process(
                compile_command,
                "",
                self.settings.compile_timeout_seconds,
                self.settings.max_output_bytes,
                working_dir,
            )
            if compiled.timed_out or compiled.output_limited:
                return ExecutionReport(
                    status="compile_error",
                    backend=self.backend_name,
                    compile_output=(
                        "Compilation timed out."
                        if compiled.timed_out
                        else "Compiler output exceeded the output limit."
                    ),
                )

            compile_output = _truncate(
                (compiled.stdout + compiled.stderr).strip(), self.settings.max_output_bytes
            )
            if compiled.returncode != 0:
                return ExecutionReport(
                    status="compile_error",
                    backend=self.backend_name,
                    compile_output=compile_output,
                )

            results = [
                self._run_case(executable_path, case)
                for case in (test_cases or [TestCase(name="empty-input")])
            ]
            return ExecutionReport(
                status=_aggregate_status(results),
                backend=self.backend_name,
                compile_output=compile_output,
                cases=results,
            )

    def _run_case(self, executable_path: Path, test_case: TestCase) -> CaseResult:
        started = time.perf_counter()
        result = bounded_process(
            [str(executable_path)],
            test_case.input,
            self.settings.run_timeout_seconds,
            self.settings.max_output_bytes,
        )
        stdout, stderr = result.stdout, result.stderr
        if result.output_limited:
            status = "output_limit"
        elif result.timed_out:
            status = "time_limit"
        elif result.returncode != 0:
            status = "runtime_error"
        elif test_case.expected_output is not None and _normalize_output(
            stdout
        ) != _normalize_output(test_case.expected_output):
            status = "wrong_answer"
        else:
            status = "passed"
        return CaseResult(
            name=test_case.name,
            status=status,
            stdout=stdout,
            stderr=stderr,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            expected_output=test_case.expected_output,
        )


class DockerCppRunner:
    backend_name = "docker-restricted"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, source_code: str, test_cases: list[TestCase]) -> ExecutionReport:
        docker = shutil.which("docker")
        if docker is None:
            return ExecutionReport(
                status="internal_error",
                backend=self.backend_name,
                compile_output="Docker was not found on PATH.",
            )

        with tempfile.TemporaryDirectory(prefix="verdictpilot-docker-") as temporary:
            submission_dir = Path(temporary).resolve()
            (submission_dir / "main.cpp").write_text(source_code, encoding="utf-8")
            (submission_dir / "cases.json").write_text(
                json.dumps([case.model_dump() for case in test_cases], ensure_ascii=False),
                encoding="utf-8",
            )
            mount = f"type=bind,source={submission_dir},target=/submission,readonly"
            command = [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                "--cpus",
                "1",
                "--memory",
                "256m",
                "--pids-limit",
                "64",
                "--read-only",
                "--security-opt",
                "no-new-privileges",
                "--tmpfs",
                "/tmp:rw,exec,nosuid,size=64m",
                "--mount",
                mount,
                "-e",
                f"RUN_TIMEOUT_SECONDS={self.settings.run_timeout_seconds}",
                "-e",
                f"MAX_OUTPUT_BYTES={self.settings.max_output_bytes}",
                self.settings.docker_image,
            ]
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.settings.compile_timeout_seconds
                    + self.settings.run_timeout_seconds * max(len(test_cases), 1)
                    + 5,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return ExecutionReport(
                    status="time_limit",
                    backend=self.backend_name,
                    compile_output="The Docker sandbox exceeded its total timeout.",
                )
            if completed.returncode != 0:
                return ExecutionReport(
                    status="internal_error",
                    backend=self.backend_name,
                    compile_output=_truncate(
                        completed.stderr or completed.stdout,
                        self.settings.max_output_bytes,
                    ),
                )
            try:
                return ExecutionReport.model_validate_json(completed.stdout.strip())
            except ValueError as error:
                return ExecutionReport(
                    status="internal_error",
                    backend=self.backend_name,
                    compile_output=f"Invalid sandbox response: {error}",
                )


def _aggregate_status(results: list[CaseResult]) -> str:
    for status in ("time_limit", "output_limit", "runtime_error", "wrong_answer"):
        if any(result.status == status for result in results):
            return status
    return "passed"


def build_cpp_runner(settings: Settings) -> CppRunner:
    if settings.execution_backend == "docker":
        return DockerCppRunner(settings)
    if settings.execution_backend == "local":
        return LocalCppRunner(settings)
    return DisabledCppRunner()
