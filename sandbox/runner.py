from __future__ import annotations

import json
import os
import resource
import subprocess
import time
from pathlib import Path

SUBMISSION_DIR = Path("/submission")
BUILD_DIR = Path("/tmp")
RUN_TIMEOUT_SECONDS = float(os.getenv("RUN_TIMEOUT_SECONDS", "2"))
MAX_OUTPUT_BYTES = int(os.getenv("MAX_OUTPUT_BYTES", "65536"))


def truncate(value: str) -> str:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return value
    return encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace") + "\n...[truncated]"


def normalize(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").strip().splitlines())


def restrict_child() -> None:
    cpu_seconds = max(1, int(RUN_TIMEOUT_SECONDS) + 1)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))


def main() -> None:
    source = SUBMISSION_DIR / "main.cpp"
    executable = BUILD_DIR / "main"
    cases_path = SUBMISSION_DIR / "cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8")) if cases_path.exists() else []
    if not cases:
        cases = [{"name": "empty-input", "input": "", "expected_output": None}]

    compiled = subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-O2",
            "-pipe",
            "-Wall",
            "-Wextra",
            str(source),
            "-o",
            str(executable),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    compile_output = truncate((compiled.stdout + compiled.stderr).strip())
    if compiled.returncode != 0:
        print(
            json.dumps(
                {
                    "status": "compile_error",
                    "backend": "docker-restricted",
                    "compile_output": compile_output,
                    "cases": [],
                },
                ensure_ascii=False,
            )
        )
        return

    results = []
    for case in cases:
        started = time.perf_counter()
        process = subprocess.Popen(
            [str(executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            preexec_fn=restrict_child,
        )
        try:
            stdout, stderr = process.communicate(
                input=case.get("input", ""), timeout=RUN_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            status = "time_limit"
        else:
            expected = case.get("expected_output")
            if process.returncode != 0:
                status = "runtime_error"
            elif expected is not None and normalize(stdout) != normalize(expected):
                status = "wrong_answer"
            else:
                status = "passed"
        results.append(
            {
                "name": case.get("name", "sample"),
                "status": status,
                "stdout": truncate(stdout),
                "stderr": truncate(stderr),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "expected_output": case.get("expected_output"),
            }
        )

    overall = "passed"
    for candidate in ("time_limit", "runtime_error", "wrong_answer"):
        if any(result["status"] == candidate for result in results):
            overall = candidate
            break
    print(
        json.dumps(
            {
                "status": overall,
                "backend": "docker-restricted",
                "compile_output": compile_output,
                "cases": results,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
