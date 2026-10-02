"""Temp-output cleanup and cache-only clearing."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from core.storage_paths import (
    clear_cache,
    format_bytes,
    get_cache_dir,
    get_temp_dir,
    prune_temp_outputs,
    prune_temp_outputs_keep,
)


def _make_temp_file(name: str, *, age_hours: float) -> Path:
    target = get_temp_dir() / name
    target.write_bytes(b"x" * 10)
    old = time.time() - age_hours * 3600.0
    os.utime(target, (old, old))
    return target


def test_prune_removes_old_temp_files():
    stale = _make_temp_file("prune_stale.mp4", age_hours=48)
    fresh = _make_temp_file("prune_fresh.mp4", age_hours=0.5)

    freed = prune_temp_outputs(max_age_hours=24.0)

    assert not stale.exists(), "48h-old temp output should be reclaimed"
    assert fresh.exists(), "recent temp output must survive"
    assert freed >= 10


def test_prune_keep_protects_active_and_unsaved_outputs():
    stale_active = _make_temp_file("prune_keep_active.mp4", age_hours=72)
    stale_unsaved = _make_temp_file("prune_keep_result.mp4", age_hours=72)
    stale_other = _make_temp_file("prune_keep_other.mp4", age_hours=72)

    freed = prune_temp_outputs_keep(
        {str(stale_active), str(stale_unsaved)},
        max_age_hours=24.0,
    )

    assert stale_active.exists(), "active job output must survive the prune"
    assert stale_unsaved.exists(), "unsaved result output must survive the prune"
    assert not stale_other.exists(), "unprotected stale temp output is reclaimed"
    assert freed >= 10

    for path in (stale_active, stale_unsaved):
        path.unlink(missing_ok=True)


def test_prune_handles_missing_dir_gracefully(monkeypatch):
    import core.storage_paths as sp

    monkeypatch.setattr(sp, "get_temp_dir", lambda: Path("/nonexistent/ffmpeg/temp"))
    assert prune_temp_outputs() == 0
    assert prune_temp_outputs_keep({"x"}) == 0


def _age(path: Path, age_hours: float) -> None:
    old = time.time() - age_hours * 3600.0
    os.utime(path, (old, old))


def test_prune_keep_protects_nested_subtree():
    job_dir = get_temp_dir() / "prune_nested_job"
    job_dir.mkdir(exist_ok=True)
    nested = job_dir / "out.mp4"
    nested.write_bytes(b"x" * 10)
    _age(nested, 72)
    _age(job_dir, 72)
    other = _make_temp_file("prune_nested_other.mp4", age_hours=72)

    freed = prune_temp_outputs_keep({str(nested)}, max_age_hours=24.0)

    assert nested.exists(), "keep file inside a subdir must protect the whole subdir"
    assert not other.exists()
    assert freed >= 10
    other.unlink(missing_ok=True)


def test_prune_ages_nested_files_individually():
    job_dir = get_temp_dir() / "prune_mixed_job"
    job_dir.mkdir(exist_ok=True)
    old_file = job_dir / "old.mp4"
    old_file.write_bytes(b"x" * 10)
    _age(old_file, 72)
    new_file = job_dir / "new.mp4"
    new_file.write_bytes(b"x" * 10)  # fresh mtime

    prune_temp_outputs(max_age_hours=24.0)

    assert not old_file.exists(), "old file inside a fresh dir is still reclaimed"
    assert new_file.exists(), "fresh file inside an old dir survives"
    new_file.unlink(missing_ok=True)
    job_dir.rmdir()


def test_clear_cache_never_touches_temp():
    cached = get_cache_dir() / "prune_cached_thumb.jpg"
    cached.write_bytes(b"x" * 10)
    live = _make_temp_file("prune_live_output.mp4", age_hours=0.1)

    freed = clear_cache()

    assert not cached.exists(), "cache entry must be reclaimed"
    assert live.exists(), "in-flight temp output must survive Clear"
    assert freed >= 10
    live.unlink(missing_ok=True)


def test_clear_cache_unlinks_symlink_without_following(tmp_path):
    import os as _os

    if not hasattr(_os, "symlink"):
        pytest.skip("platform lacks symlink support")
    cache = get_cache_dir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"x" * 10)
    link = cache / "prune_evil_link"
    try:
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(outside)
    except OSError:
        pytest.skip("cannot create symlinks here")

    freed = clear_cache()

    assert outside.exists(), "deleting a symlink must never touch its target"
    assert not link.is_symlink()
    assert freed == 0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_prune_rejects_bad_max_age(bad):
    with pytest.raises(ValueError):
        prune_temp_outputs(max_age_hours=bad)
    with pytest.raises(ValueError):
        prune_temp_outputs_keep(set(), max_age_hours=bad)


def test_format_bytes_edge_inputs():
    assert format_bytes(-5) == "0 B"
    assert format_bytes(float("nan")) == "0 B"
    assert format_bytes(float("inf")) == "0 B"
    assert format_bytes(1024**6 * 3) == "3.0 EB"
