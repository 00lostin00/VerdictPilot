from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    data_dir: Path
    knowledge_dir: Path
    database_path: Path
    trace_path: Path
    provider: str
    openai_model: str
    execution_backend: str
    docker_image: str
    allow_unsafe_local_execution: bool
    compile_timeout_seconds: float
    run_timeout_seconds: float
    max_output_bytes: int

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> Settings:
        root = (
            project_root
            or Path(
                os.getenv("VERDICTPILOT_PROJECT_ROOT", str(Path(__file__).resolve().parents[2]))
            )
        ).resolve()
        data_dir = Path(os.getenv("VERDICTPILOT_DATA_DIR", str(root / "data"))).resolve()
        return cls(
            project_root=root,
            data_dir=data_dir,
            knowledge_dir=root / "knowledge",
            database_path=data_dir / "verdictpilot.db",
            trace_path=data_dir / "traces.jsonl",
            provider=os.getenv("VERDICTPILOT_PROVIDER", "offline").strip().lower(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.5").strip(),
            execution_backend=os.getenv("VERDICTPILOT_EXECUTION_BACKEND", "disabled")
            .strip()
            .lower(),
            docker_image=os.getenv(
                "VERDICTPILOT_DOCKER_IMAGE", "verdictpilot-sandbox:latest"
            ).strip(),
            allow_unsafe_local_execution=_env_bool("VERDICTPILOT_ALLOW_UNSAFE_LOCAL_EXECUTION"),
            compile_timeout_seconds=float(os.getenv("VERDICTPILOT_COMPILE_TIMEOUT_SECONDS", "15")),
            run_timeout_seconds=float(os.getenv("VERDICTPILOT_RUN_TIMEOUT_SECONDS", "2")),
            max_output_bytes=int(os.getenv("VERDICTPILOT_MAX_OUTPUT_BYTES", "65536")),
        )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
