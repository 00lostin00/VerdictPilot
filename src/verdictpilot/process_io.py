from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    output_limited: bool


def bounded_process(
    command: list[str],
    input_text: str,
    timeout: float,
    output_limit: int,
    cwd: Path | None = None,
) -> ProcessResult:
    """Drain both streams while enforcing memory bounds; never wait with unbounded capture."""
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    exceeded = threading.Event()
    buffers = [bytearray(), bytearray()]

    def read_stream(stream, buffer: bytearray) -> None:
        try:
            while chunk := stream.read1(4096):
                remaining = max(0, output_limit - len(buffer))
                buffer.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    exceeded.set()
        finally:
            stream.close()

    def write_input() -> None:
        try:
            process.stdin.write(input_text.encode("utf-8"))
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            with suppress(BrokenPipeError, OSError):
                process.stdin.close()

    def terminate_tree() -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
                check=False,
            )
        else:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        if process.poll() is None:
            process.kill()

    threads = [
        threading.Thread(target=read_stream, args=(process.stdout, buffers[0]), daemon=True),
        threading.Thread(target=read_stream, args=(process.stderr, buffers[1]), daemon=True),
        threading.Thread(target=write_input, daemon=True),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    timed_out = False
    while process.poll() is None:
        if exceeded.is_set() or time.monotonic() >= deadline:
            timed_out = not exceeded.is_set()
            terminate_tree()
            break
        exceeded.wait(0.01)
    process.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=1)
    stdout, stderr = (buffer.decode("utf-8", errors="replace") for buffer in buffers)
    return ProcessResult(process.returncode, stdout, stderr, timed_out, exceeded.is_set())
