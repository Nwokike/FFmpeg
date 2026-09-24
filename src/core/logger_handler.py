"""In-memory logging ring handler backing the Settings 'Activity Terminal'."""

from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime


class MemoryLogHandler(logging.Handler):
    """Stores the latest 500 log records in memory for on-device diagnostics."""

    _instance: MemoryLogHandler | None = None

    def __init__(self, maxlen: int = 500):
        super().__init__()
        self.records: deque[tuple[str, str, str]] = deque(maxlen=maxlen)
        MemoryLogHandler._instance = self

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # UTC → local conversion is DST-correct; a naive fromtimestamp()
            # is ambiguous during the repeated hour each fall.
            timestamp = (
                datetime.fromtimestamp(record.created, tz=UTC).astimezone().strftime("%H:%M:%S")
            )
            level = record.levelname[:4]
            msg = self.format(record)
            self.records.append((timestamp, level, msg))
        except Exception:
            self.handleError(record)

    @classmethod
    def get_logs(cls) -> list[str]:
        """Return formatted log lines."""
        if not cls._instance:
            return ["No logs recorded yet."]
        return [f"[{t}] {lvl} {m}" for t, lvl, m in cls._instance.records]

    @classmethod
    def clear(cls) -> None:
        if cls._instance:
            cls._instance.records.clear()
