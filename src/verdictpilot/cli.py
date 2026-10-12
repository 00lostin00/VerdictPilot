from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .coach import VerdictPilotCoach
from .config import Settings
from .models import AnalyzeRequest
from .services import AppServices


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verdictpilot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap", help="Index Markdown notes into SQLite.")

    analyze = subparsers.add_parser("analyze", help="Analyze a JSON request file.")
    analyze.add_argument("--input", required=True, type=Path)
    analyze.add_argument("--provider", choices=("offline", "openai"))

    serve = subparsers.add_parser("serve", help="Run the FastAPI service.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)
    serve.add_argument(
        "--trusted-local",
        action="store_true",
        help="Enable host C++ execution for your own code on a loopback-only learning server.",
    )

    subparsers.add_parser("eval", help="Run the deterministic offline evaluation set.")
    return parser


async def _analyze(path: Path, provider: str | None) -> None:
    settings = Settings.from_env()
    services = AppServices.create(settings)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if provider:
        payload["provider"] = provider
    request = AnalyzeRequest.model_validate(payload)
    response = await VerdictPilotCoach(services).analyze(request)
    print(response.answer_markdown)
    print(f"\nrun_id={response.run_id}")


def main() -> None:
    # Keep Chinese diagnostics readable in redirected Windows terminals.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = _build_parser()
    arguments = parser.parse_args()
    if arguments.command == "bootstrap":
        settings = Settings.from_env()
        services = AppServices.create(settings)
        count = services.knowledge.bootstrap(settings.knowledge_dir)
        print(f"Indexed {count} knowledge documents into {settings.database_path}")
    elif arguments.command == "analyze":
        asyncio.run(_analyze(arguments.input, arguments.provider))
    elif arguments.command == "serve":
        import uvicorn

        if arguments.trusted_local:
            if arguments.host not in {"127.0.0.1", "localhost", "::1"}:
                parser.error("--trusted-local requires a loopback host")
            os.environ["VERDICTPILOT_EXECUTION_BACKEND"] = "local"
            os.environ["VERDICTPILOT_ALLOW_UNSAFE_LOCAL_EXECUTION"] = "true"

        uvicorn.run("verdictpilot.api:app", host=arguments.host, port=arguments.port, reload=False)
    elif arguments.command == "eval":
        from .evals import run_offline_evals

        result = run_offline_evals(Settings.from_env())
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
