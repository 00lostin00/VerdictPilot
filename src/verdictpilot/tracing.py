from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class TraceRecorder:
    _lock = threading.Lock()

    def __init__(self, trace_path: Path, run_id: str | None = None) -> None:
        self.trace_path = trace_path
        self.run_id = run_id or uuid.uuid4().hex

    def emit(self, event: str, **payload: Any) -> None:
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            "event": event,
            "payload": payload,
        }
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock, self.trace_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
