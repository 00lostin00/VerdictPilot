"""Exercise the learning loop in an isolated, temporary local server and browser profile."""

from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from playwright.sync_api import expect, sync_playwright

from verdictpilot.api import create_app
from verdictpilot.catalog import LearningCatalog
from verdictpilot.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default="chrome", help="Installed browser channel or chromium")
    parser.add_argument("--output", type=Path, default=Path("tmp/browser"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="verdictpilot-e2e-") as temp:
        base = Settings.from_env()
        settings = replace(
            base,
            data_dir=Path(temp),
            database_path=Path(temp) / "test.db",
            trace_path=Path(temp) / "trace.jsonl",
            provider="offline",
            execution_backend="local",
            allow_unsafe_local_execution=True,
        )
        server = uvicorn.Server(
            uvicorn.Config(create_app(settings), host="127.0.0.1", port=0, log_level="error")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        assert server.started, "Test server did not start"
        url = f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
        errors = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, channel=args.channel)
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000}, locale="zh-CN"
                )
                context.tracing.start(screenshots=True, snapshots=True)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url)
                expect(page.get_by_role("heading", name="你好，学习者。")).to_be_visible()
                page.screenshot(path=str(args.output / "dashboard.png"), full_page=True)
                page.get_by_role("link", name="学习路线", exact=True).click()
                expect(page.get_by_role("heading", name="一步步，构建完整的能力。")).to_be_visible()
                page.locator('a[href="#lesson/complexity"]').click()
                expect(page.locator("#quiz-form")).to_be_visible()
                lesson = LearningCatalog(base.project_root / "content").lesson("complexity")
                for index, q in enumerate(lesson["quiz"]):
                    page.locator(f'input[name="q{index}"][value="{q["answer"]}"]').check()
                page.locator("#quiz-form button").click()
                expect(page.locator("#quiz-feedback")).to_contain_text("100 分")
                page.locator("#lesson-note").fill("估计总操作次数，同时考虑所有测试组规模。")
                page.get_by_role("button", name="保存笔记", exact=True).click()
                expect(page.locator("#note-status")).to_contain_text("已保存")
                page.reload()
                expect(page.locator("#lesson-note")).to_have_value(
                    "估计总操作次数，同时考虑所有测试组规模。"
                )
                page.goto(url + "/#problems")
                expect(page.locator(".problem-card")).to_have_count(12)
                page.locator("#problem-search").fill("二分")
                expect(page.locator(".problem-card")).to_have_count(2)
                page.goto(url + "/#lab/sum")
                expect(page.locator("#code-editor")).to_be_visible()
                page.locator("#submit-code").click()
                expect(page.locator("#editor-results")).to_contain_text("答案错误", timeout=30000)
                page.screenshot(path=str(args.output / "training.png"), full_page=True)
                page.get_by_role("button", name="写入错题本", exact=True).click()
                page.locator("#mistake-form textarea").fill(
                    "加法题误写成减法，先手算样例并核对运算符。"
                )
                page.get_by_role("button", name="保存并安排复习", exact=True).click()
                expect(page.locator("#mistake-dialog")).not_to_be_visible()
                page.goto(url + "/#reviews")
                expect(page.locator(".review-card")).to_have_count(1)
                page.get_by_role("button", name="可以复述", exact=True).click()
                expect(page.locator(".review-card")).to_contain_text("已复习 1 次")
                page.goto(url + "/#lab/sum")
                expect(page.locator("#code-editor")).to_be_visible()
                source = LearningCatalog(base.project_root / "content").problems["sum"][
                    "reference_solution"
                ]
                page.locator("#code-editor").fill(source)
                page.locator("#submit-code").click()
                expect(page.locator("#editor-results")).to_contain_text(
                    "5 / 5 用例通过", timeout=30000
                )
                page.goto(url + "/#diagnose")
                expect(page.locator("#diagnose-form")).to_be_visible()
                page.locator('#diagnose-form button[type="submit"]').click()
                expect(page.locator("#diagnosis-result")).to_contain_text("检索依据", timeout=15000)
                page.get_by_role("link", name="查看调用轨迹 ↗", exact=True).click()
                expect(page.locator(".timeline")).to_contain_text("工作流开始")
                expect(page.locator(".timeline")).to_contain_text("回答生成完成")
                page.goto(url + "/#knowledge")
                page.locator("#knowledge-search-form input").fill("BFS 最短路")
                page.get_by_role("button", name="搜索资料", exact=True).click()
                expect(page.locator("#knowledge-content")).to_contain_text("图论")
                page.keyboard.press("Control+k")
                expect(page.locator("#search-dialog")).to_be_visible()
                page.locator("#global-search").fill("BFS")
                expect(page.locator(".search-result")).to_have_count(2)
                page.keyboard.press("Escape")
                page.goto(url + "/#projects")
                expect(page.get_by_role("heading", name="做出能被复现的作品。")).to_be_visible()
                page.locator('a[href="#projects/retrieval-engine"]').click()
                expect(page.locator("#project-evidence-form")).to_be_visible()
                page.locator('#project-evidence-form textarea[name="summary"]').fill(
                    "完成三十篇算法资料整理和六十条固定查询，保留独立测试划分。"
                )
                page.locator('#project-evidence-form input[name="command"]').fill(
                    "python validate_queries.py"
                )
                page.locator('#project-evidence-form input[name="artifact"]').fill(
                    "reports/dataset-v1.json"
                )
                page.locator('input[name="metric_documents"]').fill("30")
                page.locator('input[name="metric_queries"]').fill("60")
                page.get_by_role("button", name="保存里程碑证据", exact=True).click()
                expect(page.locator(".exercise-box").first).to_contain_text("已记录证据")
                page.goto(url + "/#settings")
                page.locator('input[name="display_name"]').fill("验收学习者")
                page.locator("#profile-form button").click()
                expect(page.locator("#side-name")).to_contain_text("验收学习者")
                with page.expect_download() as download:
                    page.get_by_role("button", name="导出我的学习证据 ↗", exact=True).click()
                download.value.save_as(str(args.output / "evidence.json"))
                exported = json.loads((args.output / "evidence.json").read_text(encoding="utf-8"))
                assert len(exported["runs"]) == 3 and len(exported["reviews"]) == 1
                assert len(exported["project_evidence"]) == 1
                mobile = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    is_mobile=True,
                    has_touch=True,
                    locale="zh-CN",
                )
                mobile_page = mobile.new_page()
                mobile_page.on("pageerror", lambda error: errors.append(str(error)))
                mobile_page.goto(url)
                expect(mobile_page.get_by_role("heading", name="你好，学习者。")).to_be_visible()
                assert mobile_page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    "Mobile dashboard overflows"
                )
                mobile_page.screenshot(path=str(args.output / "mobile.png"), full_page=True)
                mobile_page.get_by_role("button", name="展开导航").click()
                mobile_page.get_by_role("link", name="题目训练", exact=True).click()
                expect(mobile_page.locator(".problem-card")).to_have_count(12)
                mobile_page.goto(url + "/#lab/sum")
                expect(mobile_page.locator("#code-editor")).to_be_visible()
                assert mobile_page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    "Mobile lab overflows"
                )
                context.tracing.stop(path=str(args.output / "trace.zip"))
                browser.close()
                assert not errors, errors
                print(
                    "Browser flow passed: learning, quizzes, notes, drafts, WA, review, repair, "
                    "diagnosis, trace, search, profile, export, mobile. No JavaScript errors."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=15)


if __name__ == "__main__":
    main()
