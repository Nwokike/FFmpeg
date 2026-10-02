"""In-memory logging ring handler backing the Settings 'Activity Terminal'."""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import UTC, datetime


class MemoryLogHandler(logging.Handler):
    """Stores the latest 500 log records in memory for on-device diagnostics."""

    _instance: MemoryLogHandler | None = None

    def __init__(self, maxlen: int = 500):
        super().__init__()
        # Message-only formatter: the timestamp/level prefix is added once in
        # get_logs(). Formatting the full record here too would print every
        # line's time and level twice.
        super().setFormatter(logging.Formatter("%(name)s: %(message)s"))
        self._lock = threading.Lock()
        self.records: deque[tuple[str, str, str]] = deque(maxlen=maxlen)
        MemoryLogHandler._instance = self

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # UTC → local conversion is DST-correct; a naive fromtimestamp()
            # is ambiguous during the repeated hour each fall.
            timestamp = (
                datetime.fromtimestamp(record.created, tz=UTC).astimezone().strftime("%H:%M:%S")
            )
            level = record.levelname
            msg = self.format(record)
            with self._lock:
                self.records.append((timestamp, level, msg))
        except Exception:
            self.handleError(record)

    @classmethod
    def get_logs(cls, limit: int = 100) -> list[str]:
        """Return up to ``limit`` formatted log lines (newest last)."""
        if not cls._instance:
            return ["No logs recorded yet."]
        with cls._instance._lock:
            records = list(cls._instance.records)[-limit:]
        return [f"[{t}] {lvl} {m}" for t, lvl, m in records]

    @classmethod
    def clear(cls) -> None:
        if cls._instance:
            with cls._instance._lock:
                cls._instance.records.clear()
