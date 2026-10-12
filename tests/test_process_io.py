import sys

from verdictpilot.process_io import bounded_process


def test_output_is_bounded_before_process_exit():
    result = bounded_process(
        [
            sys.executable,
            "-c",
            "import sys;\nwhile True: sys.stdout.write('x'*4096);sys.stdout.flush()",
        ],
        "",
        timeout=2,
        output_limit=1024,
    )
    assert result.output_limited and not result.timed_out
    assert len(result.stdout.encode()) <= 1024


def test_process_timeout_and_input_roundtrip():
    echo = bounded_process(
        [sys.executable, "-c", "import sys;print(sys.stdin.read(),end='')"],
        "hello\n",
        timeout=2,
        output_limit=1024,
    )
    assert echo.returncode == 0 and echo.stdout.replace("\r\n", "\n") == "hello\n"
    assert not echo.timed_out and not echo.output_limited
    slow = bounded_process(
        [sys.executable, "-c", "import time;time.sleep(30)"],
        "",
        timeout=0.1,
        output_limit=1024,
    )
    assert slow.timed_out and not slow.output_limited
