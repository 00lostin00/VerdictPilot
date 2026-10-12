from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ExecutionReport,
    NewMistake,
    RetrievedDocument,
    TestCase,
)
from .services import AppServices
from .tracing import TraceRecorder


class OpenAIConfigurationError(RuntimeError):
    pass


@dataclass(slots=True)
class _RunArtifacts:
    retrieved: list[RetrievedDocument] = field(default_factory=list)
    execution: ExecutionReport | None = None


class OpenAICoach:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        if not os.getenv("OPENAI_API_KEY"):
            raise OpenAIConfigurationError(
                "OPENAI_API_KEY is not set. Use provider=offline or configure a key locally."
            )

        # Lazy import keeps the complete offline path usable without contacting an API.
        from agents import Agent, Runner, function_tool

        trace = TraceRecorder(self.services.settings.trace_path)
        artifacts = _RunArtifacts()

        @function_tool
        def retrieve_algorithm_knowledge(query: str, limit: int = 4) -> str:
            """Search local algorithm notes. Use this before proposing a diagnosis."""

            artifacts.retrieved = self.services.knowledge.search(query, limit=limit)
            trace.emit(
                "tool.knowledge_search.completed",
                query=query,
                results=[document.doc_id for document in artifacts.retrieved],
            )
            return json.dumps(
                [document.model_dump() for document in artifacts.retrieved],
                ensure_ascii=False,
            )

        @function_tool
        def run_cpp_tests(source_code: str, test_cases_json: str) -> str:
            """Compile C++20 and run explicit tests in the configured execution backend."""

            raw_cases = json.loads(test_cases_json)
            cases = [TestCase.model_validate(case) for case in raw_cases]
            artifacts.execution = self.services.runner.run(source_code, cases)
            trace.emit(
                "tool.cpp_runner.completed",
                backend=artifacts.execution.backend,
                status=artifacts.execution.status,
            )
            return artifacts.execution.model_dump_json()

        @function_tool
        def recall_mistakes(session_id: str, topic: str = "") -> str:
            """Recall a learner's confirmed prior mistakes for the current topic."""

            mistakes = self.services.memory.search(session_id, topic, limit=5)
            trace.emit("tool.memory_recall.completed", count=len(mistakes))
            return json.dumps(
                [mistake.model_dump(mode="json") for mistake in mistakes],
                ensure_ascii=False,
            )

        @function_tool
        def save_confirmed_mistake(
            session_id: str,
            problem_title: str,
            category: str,
            symptom: str,
            lesson: str,
        ) -> str:
            """Save only a mistake confirmed by execution evidence or an explicit user statement."""

            record = self.services.memory.add(
                NewMistake(
                    session_id=session_id,
                    problem_title=problem_title,
                    category=category,
                    symptom=symptom,
                    lesson=lesson,
                )
            )
            trace.emit("tool.memory_save.completed", mistake_id=record.id)
            return record.model_dump_json()

        instructions = """
You are VerdictPilot, an algorithm-contest coaching agent.

Goal: diagnose a problem or solution with evidence, then give the smallest useful next step.

Workflow rules:
- Search the local knowledge base before making an algorithm claim.
- If source code and test cases are present, call run_cpp_tests before declaring correctness.
- Treat disabled execution as unknown, never as a pass.
- Cite retrieved note sources in the final answer.
- In hint mode, provide progressive hints and do not reveal a full solution immediately.
- Save a mistake only when a tool result or the user explicitly confirms it.
- Never claim an online judge submission passed; this app does not submit to OJ systems.
- Return concise Markdown with: diagnosis, evidence, execution result, and next steps.
""".strip()
        agent = Agent(
            name="VerdictPilot",
            instructions=instructions,
            model=self.services.settings.openai_model,
            tools=[
                retrieve_algorithm_knowledge,
                run_cpp_tests,
                recall_mistakes,
                save_confirmed_mistake,
            ],
        )
        trace.emit("workflow.started", provider="openai", model=self.services.settings.openai_model)
        result = await Runner.run(agent, request.model_dump_json())
        answer = str(result.final_output)
        trace.emit("workflow.completed", answer_chars=len(answer))
        return AnalyzeResponse(
            run_id=trace.run_id,
            provider="openai",
            answer_markdown=answer,
            retrieved=artifacts.retrieved,
            execution=artifacts.execution,
            trace_path=str(self.services.settings.trace_path),
        )
