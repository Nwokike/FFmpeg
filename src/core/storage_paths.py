"""Tiered on-device storage path management.

Resolves DATA, CACHE, and TEMP tiers via FLET_APP_STORAGE_* environment variables
set by the Flet mobile launcher, falling back to ~/.ffmpeg/* on desktop dev.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path

from core.constants import STORAGE_CACHE_ENV, STORAGE_DATA_ENV, STORAGE_TEMP_ENV


def _resolve_dir(env_key: str, default_subdir: str) -> Path:
    val = os.environ.get(env_key)
    path = Path(val) if val else Path.home() / ".ffmpeg" / default_subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    """Persistent user data (history, settings, presets)."""
    return _resolve_dir(STORAGE_DATA_ENV, "data")


def get_cache_dir() -> Path:
    """Regenerable cache (thumbnails, probed metadata cache)."""
    return _resolve_dir(STORAGE_CACHE_ENV, "cache")


def get_temp_dir() -> Path:
    """Scratchpad directory for in-flight media processing & exports."""
    return _resolve_dir(STORAGE_TEMP_ENV, "temp")


def cache_bytes(name: str, data: bytes) -> Path:
    """Store ``data`` in CACHE under a content-addressed name and return it.

    Keyed by an 8-hex content digest plus the sanitized original name:
    identical bytes are written once, and clear_cache() may reclaim the
    file — it is a re-obtainable copy (re-pickable media, re-picked
    watermark), never the only copy of user data.
    """
    digest = hashlib.sha256(data).hexdigest()[:8]
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in Path(name).name)
    dest = get_cache_dir() / f"{digest}_{safe or 'file'}"
    if not dest.exists():
        dest.write_bytes(data)
    return dest


def get_cache_size_bytes() -> int:
    """Calculate total bytes occupied by cache and temp directories."""
    total = 0
    for d in (get_cache_dir(), get_temp_dir()):
        if d.exists():
            for root, _, files in os.walk(d):
                for f in files:
                    try:
                        total += (Path(root) / f).stat().st_size
                    except OSError as e:
                        logging.getLogger(__name__).warning("Failed to stat cache file: %s", e)
    return total


def clear_cache() -> int:
    """Purge all files in the cache and temp directories. Returns bytes freed."""
    freed = get_cache_size_bytes()
    for d in (get_cache_dir(), get_temp_dir()):
        if d.exists():
            for item in d.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except OSError as e:
                    logging.getLogger(__name__).warning(
                        "Failed to clear cache item %s: %s", item, e
                    )
    return freed


def format_bytes(size: int | float) -> str:
    """Format bytes into readable string (KB, MB, GB)."""
    n = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.1f} PB"
