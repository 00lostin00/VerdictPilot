from __future__ import annotations

import shutil
from dataclasses import replace

import pytest

from verdictpilot.models import TestCase as CppTestCase
from verdictpilot.sandbox import DisabledCppRunner, LocalCppRunner


def test_disabled_runner_never_executes() -> None:
    report = DisabledCppRunner().run("int main(){}", [])
    assert report.status == "disabled"


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ is not installed")
def test_local_runner_pass_and_wrong_answer(settings) -> None:
    local_settings = replace(settings, allow_unsafe_local_execution=True)
    runner = LocalCppRunner(local_settings)
    passing = runner.run(
        "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}",
        [CppTestCase(name="sum", input="2 3\n", expected_output="5\n")],
    )
    assert passing.status == "passed"

    wrong = runner.run(
        "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a-b;}",
        [CppTestCase(name="sum", input="2 3\n", expected_output="5\n")],
    )
    assert wrong.status == "wrong_answer"


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ is not installed")
def test_local_runner_reports_compile_error(settings) -> None:
    local_settings = replace(settings, allow_unsafe_local_execution=True)
    report = LocalCppRunner(local_settings).run(
        "int main(){ return missing; }",
        [CppTestCase()],
    )
    assert report.status == "compile_error"
    assert "missing" in report.compile_output
