"""Bounded temp-output cleanup — the 2.2 GB phone-cache regression."""

from __future__ import annotations

import os
import time
from pathlib import Path

from core.storage_paths import (
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
