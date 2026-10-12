from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from verdictpilot.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    base = Settings.from_env(PROJECT_ROOT)
    data_dir = tmp_path / "data"
    return replace(
        base,
        data_dir=data_dir,
        database_path=data_dir / "test.db",
        trace_path=data_dir / "traces.jsonl",
        provider="offline",
        execution_backend="disabled",
        allow_unsafe_local_execution=False,
    )
