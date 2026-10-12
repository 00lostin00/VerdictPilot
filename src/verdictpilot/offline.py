from __future__ import annotations

from .models import AnalyzeRequest, AnalyzeResponse, ExecutionReport
from .services import AppServices
from .tracing import TraceRecorder


class OfflineCoach:
    """Deterministic workflow used for learning, demos, and repeatable tests."""

    def __init__(self, services: AppServices) -> None:
        self.services = services

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        trace = TraceRecorder(self.services.settings.trace_path)
        trace.emit("workflow.started", provider="offline", mode=request.mode)

        query = f"{request.title}\n{request.statement}"
        retrieved = self.services.knowledge.search(query, limit=4)
        trace.emit(
            "tool.knowledge_search.completed",
            query=query[:500],
            results=[document.doc_id for document in retrieved],
        )

        remembered = self.services.memory.search(request.session_id, request.title, limit=3)
        trace.emit("tool.memory_recall.completed", count=len(remembered))

        execution: ExecutionReport | None = None
        if request.code:
            execution = self.services.runner.run(request.code, request.test_cases)
            trace.emit(
                "tool.cpp_runner.completed",
                backend=execution.backend,
                status=execution.status,
                case_count=len(execution.cases),
            )

        answer = self._render_answer(request, retrieved, remembered, execution)
        trace.emit("workflow.completed", answer_chars=len(answer))
        return AnalyzeResponse(
            run_id=trace.run_id,
            provider="offline",
            answer_markdown=answer,
            retrieved=retrieved,
            execution=execution,
            trace_path=str(self.services.settings.trace_path),
        )

    @staticmethod
    def _render_answer(request, retrieved, remembered, execution) -> str:
        lines = ["## 诊断概览"]
        if execution is None:
            lines.append("当前未提供代码，先根据题面检索相关算法知识。")
        elif execution.status == "disabled":
            lines.append("已完成知识检索；代码执行处于安全关闭状态。")
        elif execution.status == "passed":
            lines.append("代码通过了已提供测试，但仍应补充边界用例与复杂度检查。")
        elif execution.status == "compile_error":
            lines.append("编译失败。先处理编译器输出，再讨论算法正确性。")
        elif execution.status == "wrong_answer":
            lines.append("代码可以运行，但至少一个样例输出不一致，优先检查状态定义和边界。")
        elif execution.status == "time_limit":
            lines.append("执行超时，优先核对复杂度、循环终止条件和重复状态。")
        elif execution.status == "output_limit":
            lines.append("程序输出超过上限，检查调试输出或未终止的输出循环。")
        else:
            lines.append("程序发生运行时错误，优先检查数组边界、空容器和非法运算。")

        lines.extend(["", "## 检索依据"])
        if retrieved:
            for index, document in enumerate(retrieved, start=1):
                lines.append(
                    f"{index}. **{document.title}** - {document.snippet} `[{document.source}]`"
                )
        else:
            lines.append("没有命中本地知识库；可先补充对应算法笔记。")

        if execution and execution.status != "disabled":
            lines.extend(["", "## 执行反馈"])
            if execution.compile_output:
                lines.append(f"```text\n{execution.compile_output}\n```")
            for case in execution.cases:
                lines.append(f"- `{case.name}`: **{case.status}**, {case.elapsed_ms:.2f} ms")
                if case.status == "wrong_answer":
                    lines.append(
                        f"  - expected: `{(case.expected_output or '').strip()}`; "
                        f"actual: `{case.stdout.strip()}`"
                    )

        lines.extend(["", "## 下一步"])
        if request.mode == "hint":
            lines.append("1. 先写出状态、转移或图节点含义，不直接跳到完整代码。")
            lines.append("2. 手算最小用例、空边界与最大规模，再决定数据结构。")
        else:
            lines.append("1. 用命中的知识条目核对算法不变量与复杂度。")
            lines.append("2. 为最小规模、重复值、极值和无解情况各补一个测试。")
            lines.append("3. 修复后重新运行全部样例，并把确认过的错误写入错题记忆。")
        if remembered:
            lines.append(f"4. 本会话已有 {len(remembered)} 条相关错题记录，建议优先复查重复错误。")
        return "\n".join(lines)
