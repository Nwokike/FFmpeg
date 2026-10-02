"""Tiered on-device storage path management.

Resolves DATA, CACHE, and TEMP tiers via FLET_APP_STORAGE_* environment variables
set by the Flet mobile launcher, falling back to ~/.ffmpeg/* on desktop dev.

Tier contract:

- CACHE holds regenerable bytes only (thumbnails, probe caches, re-pickable
  uploads). :func:`clear_cache` purges this tier and NOTHING else.
- TEMP holds in-flight media processing and unsaved exports. It is managed by
  age-based :func:`prune_temp_outputs_keep` (with an explicit keep set) plus
  explicit discard actions — never by the Clear-cache button.
- Deletion is symlink-safe throughout: a symlink is unlinked, never followed.
  ``rmtree`` on a link would delete the link target's contents.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import shutil
import tempfile
import time
from contextlib import suppress
from pathlib import Path

from core.constants import STORAGE_CACHE_ENV, STORAGE_DATA_ENV, STORAGE_TEMP_ENV

_log = logging.getLogger(__name__)

# cache_bytes key strength: 64 bits makes accidental collision impractical
# while keeping filenames short on filesystems with 255-byte limits.
_DIGEST_HEX_CHARS = 16
_MAX_SAFE_NAME_CHARS = 80


def _resolve_dir(env_key: str, default_subdir: str) -> Path:
    val = os.environ.get(env_key)
    if val:
        return Path(val)
    fallback = Path.home() / ".ffmpeg" / default_subdir
    _log.warning(
        "Storage env %s is unset; falling back to %s (desktop dev layout)",
        env_key,
        fallback,
    )
    return fallback


def _ensure_dir(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log.error("Storage directory %s is not writable: %s", path, exc)
        raise
    return path


def get_data_dir() -> Path:
    """Persistent user data (history, settings, presets)."""
    return _ensure_dir(_resolve_dir(STORAGE_DATA_ENV, "data"))


def get_cache_dir() -> Path:
    """Regenerable cache (thumbnails, probed metadata cache)."""
    return _ensure_dir(_resolve_dir(STORAGE_CACHE_ENV, "cache"))


def get_temp_dir() -> Path:
    """Scratchpad directory for in-flight media processing & exports."""
    return _ensure_dir(_resolve_dir(STORAGE_TEMP_ENV, "temp"))


def cache_bytes(name: str, data: bytes) -> Path:
    """Store ``data`` in CACHE under a content-addressed name and return it.

    Keyed by a 64-bit content digest plus the sanitized original name:
    identical bytes are written once (atomically — a crash mid-write can
    never leave a truncated file behind), and :func:`clear_cache` may
    reclaim the file. Pass re-obtainable bytes only (re-pickable media,
    re-picked watermark), never the only copy of user data.
    """
    digest = hashlib.sha256(data).hexdigest()[:_DIGEST_HEX_CHARS]
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in Path(name).name)
    safe = (safe or "file")[:_MAX_SAFE_NAME_CHARS]
    dest = get_cache_dir() / f"{digest}_{safe}"
    if dest.exists():
        try:
            if dest.stat().st_size == len(data):
                return dest
        except OSError:
            pass
    fd, tmp_name = tempfile.mkstemp(dir=str(dest.parent), prefix=dest.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        Path(tmp_name).replace(dest)
    except BaseException:
        with suppress(OSError):
            Path(tmp_name).unlink(missing_ok=True)
        raise
    return dest


def _safe_unlink(item: Path) -> int:
    """Delete one top-level tier entry; return bytes actually freed.

    Symlinks are unlinked, never followed — ``is_dir()`` follows links, so
    checking it first would ``rmtree`` the link target's contents.
    """
    try:
        if item.is_symlink():
            item.unlink()
            return 0
        if item.is_dir():
            size = _tree_size(item)
            shutil.rmtree(item)
            return size
        size = item.stat().st_size
        item.unlink()
        return size
    except FileNotFoundError:
        return 0


def _walk_size(top: Path) -> int:
    """Sum regular-file bytes under ``top`` without following symlinks."""
    total = 0
    for root, dirs, files in os.walk(top, followlinks=False):
        # Prune symlinked dirs: os.walk lists them in dirs but must not
        # descend (st_size of the link itself is ~0; the target is foreign).
        dirs[:] = [d for d in dirs if not Path(root, d).is_symlink()]
        for f in files:
            p = Path(root) / f
            try:
                if p.is_symlink():
                    continue
                total += p.stat().st_size
            except OSError as e:
                _log.warning("Failed to stat cache file: %s", e)
    return total


def _distinct_dirs(dirs: list[Path]) -> list[Path]:
    """Dedupe tier dirs by resolved path so overlap can't double-count."""
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        try:
            key = str(d.resolve())
        except OSError:
            key = str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def get_cache_size_bytes() -> int:
    """Calculate bytes occupied by the CACHE tier (TEMP excluded)."""
    total = 0
    for d in _distinct_dirs([_resolve_dir(STORAGE_CACHE_ENV, "cache")]):
        if d.exists():
            total += _walk_size(d)
    return total


def clear_cache() -> int:
    """Purge the CACHE tier only; TEMP (in-flight work) is never touched.

    Returns bytes actually deleted (per-item accounting, not a pre-snapshot).
    """
    freed = 0
    for d in _distinct_dirs([get_cache_dir()]):
        if not d.exists():
            continue
        for item in d.iterdir():
            try:
                freed += _safe_unlink(item)
            except OSError as e:
                _log.warning("Failed to clear cache item %s: %s", item, e)
    return freed


def _validate_max_age(max_age_hours: float) -> float:
    if not isinstance(max_age_hours, (int, float)) or not math.isfinite(max_age_hours):
        raise ValueError(f"max_age_hours must be finite, got {max_age_hours!r}")
    if max_age_hours < 0:
        raise ValueError(f"max_age_hours must be >= 0, got {max_age_hours!r}")
    return float(max_age_hours)


def _keep_paths(keep: set[str]) -> list[Path]:
    paths: list[Path] = []
    for k in keep:
        if not k:
            continue
        try:
            paths.append(Path(k).resolve())
        except OSError:
            continue
    return paths


def _is_protected(item: Path, keep: list[Path]) -> bool:
    """True when ``item`` equals, contains, or is contained by any keep path.

    Exact top-level matching is not enough: a keep file nested inside a job
    subdir must protect the whole subdir, and a keep dir must protect its
    contents.
    """
    try:
        resolved = item.resolve()
    except OSError:
        return False
    for k in keep:
        if resolved == k:
            return True
        try:
            resolved.relative_to(k)
            return True
        except ValueError:
            pass
        try:
            k.relative_to(resolved)
            return True
        except ValueError:
            pass
    return False


def _prune_old_entries(top: Path, keep: list[Path], cutoff: float, freed: int = 0) -> int:
    """Recursively delete files older than ``cutoff``; drop newly-empty dirs."""
    try:
        entries = sorted(top.iterdir())
    except OSError:
        return freed
    for item in entries:
        if _is_protected(item, keep):
            continue
        try:
            if item.is_symlink():
                # Stale links are clutter, but the target is none of ours.
                item.unlink()
                continue
            st = item.stat()
        except OSError:
            continue
        if item.is_dir():
            freed = _prune_old_entries(item, keep, cutoff, freed)
            try:
                # Only remove dirs the prune itself emptied of old files —
                # and only when the dir itself is old, so a fresh file
                # landing in an old dir never vanishes with it.
                if not any(item.iterdir()) and st.st_mtime < cutoff:
                    item.rmdir()
            except OSError as e:
                _log.warning("Failed to prune temp item %s: %s", item, e)
            continue
        if st.st_mtime >= cutoff:
            continue
        try:
            freed += st.st_size
            item.unlink()
        except OSError as e:
            _log.warning("Failed to prune temp item %s: %s", item, e)
    return freed


def prune_temp_outputs(max_age_hours: float = 24.0) -> int:
    """Remove TEMP files older than ``max_age_hours``; return bytes freed.

    Recursive: nested files are aged individually, and only dirs left empty
    by the prune (and themselves old) are removed — a new file inside an old
    dir survives, and an old file inside a fresh dir does not leak.
    """
    cutoff = time.time() - _validate_max_age(max_age_hours) * 3600.0
    temp = get_temp_dir()
    if not temp.exists():
        return 0
    return _prune_old_entries(temp, [], cutoff)


def prune_temp_outputs_keep(keep: set[str], max_age_hours: float = 24.0) -> int:
    """Same as :func:`prune_temp_outputs`, but never removes ``keep`` paths.

    ``keep`` holds absolute path strings for the active job's output and the
    result screen's current file, so a background prune can never delete a
    recording the user has not saved yet. Protection is subtree-aware: a keep
    file inside a job subdir protects the whole subdir, and a keep dir
    protects its contents.
    """
    cutoff = time.time() - _validate_max_age(max_age_hours) * 3600.0
    keep_paths = _keep_paths(keep)
    temp = get_temp_dir()
    if not temp.exists():
        return 0
    return _prune_old_entries(temp, keep_paths, cutoff)


def _tree_size(path: Path) -> int:
    return _walk_size(path)


def format_bytes(size: int | float) -> str:
    """Format bytes into readable string (B … EB)."""
    try:
        n = float(size)
    except (TypeError, ValueError):
        return "0 B"
    if not math.isfinite(n) or n < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if n < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.1f} EB"
