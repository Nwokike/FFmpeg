"""Stream recording: local-container seam, duration cap, Stop-keeps semantics."""

from __future__ import annotations

import threading
from pathlib import Path

import av
import pytest

from services.engine_service import EngineService


def _open_source(synthetic_media):
    return av.open(synthetic_media.path, "r")


def test_record_from_copies_streams(synthetic_media):
    out = str(synthetic_media.dir / "recorded.mp4")
    inp = _open_source(synthetic_media)
    try:
        EngineService._record_from(inp, out)
    finally:
        inp.close()

    info = EngineService.probe(out)
    assert info.video_stream is not None
    assert info.audio_stream is not None
    assert abs(info.duration_s - EngineService.probe(synthetic_media.path).duration_s) < 0.5


def test_record_from_starts_timeline_at_zero(synthetic_media):
    """Recorded output must not inherit a large starting timestamp."""
    out = str(synthetic_media.dir / "recorded_zero.mp4")
    inp = _open_source(synthetic_media)
    try:
        EngineService._record_from(inp, out)
    finally:
        inp.close()
    # container duration sanity (a broken pts base would blow this up or zero it)
    dur = EngineService.probe(out).duration_s
    assert 1.0 < dur < 5.0


def test_record_duration_cap_stops_early(synthetic_media):
    """Cap check fires before the first mux → clean stop, no exception.

    A negative cap makes the branch deterministic (a positive cap races the
    very fast local remux, which can copy the whole file in <300ms).
    """
    out = str(synthetic_media.dir / "capped.ts")
    events: list[str] = []

    def progress(pct, msg):
        events.append(msg)

    inp = _open_source(synthetic_media)
    try:
        result = EngineService._record_from(
            inp, out, "mpegts", duration_s=-1.0, on_progress=progress
        )
    finally:
        inp.close()

    assert result == out
    assert Path(out).exists()
    assert any(m.startswith("Recorded") for m in events)


def test_record_full_copy_to_mpegts(synthetic_media):
    """MP4 source → TS target exercises the h264_mp4toannexb BSF path."""
    out = str(synthetic_media.dir / "full_copy.ts")
    inp = _open_source(synthetic_media)
    try:
        EngineService._record_from(inp, out, "mpegts")
    finally:
        inp.close()

    info = EngineService.probe(out)
    assert info.video_stream is not None
    assert info.audio_stream is not None
    assert abs(info.duration_s - EngineService.probe(synthetic_media.path).duration_s) < 0.5


def test_record_cancel_keeps_output(synthetic_media):
    """Stop = keep: cancellation returns normally and the file survives."""
    out = str(synthetic_media.dir / "stopped.mp4")
    evt = threading.Event()

    def progress(pct, msg):
        evt.set()  # user presses Stop at first progress tick

    inp = _open_source(synthetic_media)
    try:
        result = EngineService._record_from(inp, out, None, None, progress, evt)
    finally:
        inp.close()

    assert result == out
    assert Path(out).exists() and Path(out).stat().st_size > 0
    assert EngineService.probe(out).duration_s > 0


def test_record_rejects_non_urls(synthetic_media):
    with pytest.raises(ValueError, match="stream URL"):
        EngineService.record("not-a-url", str(synthetic_media.dir / "x.mp4"))


def test_record_unknown_protocol_is_friendly():
    with pytest.raises(ValueError, match=r"protocol|Couldn't|read"):
        EngineService.record(
            "gopher://example.com/feed",
            "unused_out.mp4",
        )
