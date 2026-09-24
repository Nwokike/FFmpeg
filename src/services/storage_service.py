"""Thread-safe, atomic, debounced JSON storage service."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from core.storage_paths import get_data_dir

logger = logging.getLogger("StorageService")

_DEBOUNCE_SEC = 1.0


class StorageService:
    """Manages persistent key-value configuration and history in storage.json."""

    def __init__(self, data_dir: str | None = None) -> None:
        self._dir = data_dir or str(get_data_dir())
        self._path = str(Path(self._dir) / "storage.json")
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        Path(self._dir).mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Any] = self._read()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value
        self._schedule_flush()

    def remove(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)
        self._schedule_flush()

    def flush(self) -> None:
        """Force synchronous write to disk immediately."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._write(self._cache)

    def _schedule_flush(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            timer = threading.Timer(_DEBOUNCE_SEC, self.flush)
            timer.daemon = True
            self._timer = timer
        timer.start()

    def _read(self) -> dict[str, Any]:
        for path in (self._path, self._path + ".bak"):
            if Path(path).is_file():
                try:
                    with Path(path).open(encoding="utf-8") as f:
                        return json.load(f)
                except (OSError, ValueError) as ex:
                    logger.warning("Failed reading %s: %s", path, ex)
        return {}

    def _write(self, data: dict[str, Any]) -> None:
        tmp_path = self._path + ".tmp"
        bak_path = self._path + ".bak"
        try:
            with Path(tmp_path).open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            if Path(self._path).exists():
                try:
                    if Path(bak_path).exists():
                        Path(bak_path).unlink()
                    Path(self._path).rename(bak_path)
                except OSError as e:
                    logger.warning("Backup rotation skipped: %s", e)

            Path(tmp_path).replace(self._path)
        except OSError:
            logger.exception("Failed writing storage")
            if Path(tmp_path).exists():
                try:
                    Path(tmp_path).unlink()
                except OSError as e:
                    logger.warning("Failed to clean up temp file: %s", e)
