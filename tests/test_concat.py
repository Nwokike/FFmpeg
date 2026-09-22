"""Join/concat: lossless stream-copy path, uniform re-encode path, guards."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from services.engine_service import EngineService


def _make_clip(tmp_path, name: str, w: int = 96, h: int = 64, fps: int = 30, frames: int = 30) -> str:
    import array
    import math

    import av

    path = str(tmp_path / name)
    o = av.open(path, "w")
    vs = o.add_stream("libx264", rate=fps)
    vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p"
    vs.options = {"crf": "30", "preset": "ultrafast"}
    asr = o.add_stream("aac", rate=44100)
    asr.layout = "stereo"

    vt = av.VideoFrame(w, h, "yuv420p")
    for plane in vt.planes:
        plane.update(bytes([110]) * plane.buffer_size)
    for i in range(frames):
        vt.pts = i
        for pkt in vs.encode(vt):
            o.mux(pkt)
    for pkt in vs.encode(None):
        o.mux(pkt)

    n = 0
    audio_frames = int(frames / fps * 43) + 1
    for _ in range(audio_frames):
        af = av.AudioFrame("s16", "stereo", 1024)
        af.sample_rate = 44100
        samples = array.array(
            "h",
            (
                v
                for k in range(1024)
                for v in (
                    int(9000 * math.sin(2 * math.pi * 440 * (n + k) / 44100)),
                )
                * 2
            ),
        )
        n += 1024
        af.planes[0].update(samples.tobytes())
        for pkt in asr.encode(af):
            o.mux(pkt)
    for pkt in asr.encode(None):
        o.mux(pkt)
    o.close()
    return path


def test_concat_requires_two_paths(tmp_path):
    with pytest.raises(ValueError, match="at least two"):
        EngineService.concat([str(tmp_path / "only.mp4")], str(tmp_path / "out.mp4"))


def test_concat_stream_copy_join(tmp_path):
    """Two identical-format clips → lossless join, duration doubles."""
    a = _make_clip(tmp_path, "a.mp4")
    b = _make_clip(tmp_path, "b.mp4")
    out = str(tmp_path / "joined.mp4")

    EngineService.concat([a, b], out, on_progress=lambda p, m: None)

    info = EngineService.probe(out)
    da = EngineService.probe(a).duration_s
    db = EngineService.probe(b).duration_s
    assert abs(info.duration_s - (da + db)) < 0.35, (
        f"expected ~{da + db:.2f}s, got {info.duration_s:.2f}s"
    )
    assert info.video_stream is not None
    assert info.audio_stream is not None


def test_concat_reencode_on_mismatch(tmp_path):
    """Different resolution/fps → uniform re-encode at the FIRST clip's shape."""
    a = _make_clip(tmp_path, "base.mp4", w=96, h=64, fps=30)
    b = _make_clip(tmp_path, "odd.mp4", w=32, h=32, fps=10, frames=10)
    out = str(tmp_path / "reencoded.mp4")

    EngineService.concat([a, b], out, on_progress=lambda p, m: None)

    info = EngineService.probe(out)
    assert (info.video_stream.width, info.video_stream.height) == (96, 64)
    da = EngineService.probe(a).duration_s
    db = EngineService.probe(b).duration_s
    assert abs(info.duration_s - (da + db)) < 0.6


def test_concat_to_mkv(tmp_path):
    a = _make_clip(tmp_path, "x1.mp4")
    b = _make_clip(tmp_path, "x2.mp4")
    out = str(tmp_path / "joined.mkv")
    EngineService.concat([a, b], out, container_format="matroska")
    info = EngineService.probe(out)
    assert info.format_name in ("matroska", "matroska,webm")
    assert info.video_stream is not None


def test_concat_missing_file_raises(tmp_path, synthetic_media):
    out = str(tmp_path / "nope.mp4")
    with pytest.raises(Exception):  # noqa: B017 — probe raises FileNotFoundError/FFmpegError
        EngineService.concat([synthetic_media.path, str(tmp_path / "ghost.mp4"),], out)


def test_concat_cancel_cleans_up(tmp_path):
    a = _make_clip(tmp_path, "c1.mp4")
    b = _make_clip(tmp_path, "c2.mp4")
    out = str(tmp_path / "cancelled.mp4")
    evt = threading.Event()
    evt.set()
    with pytest.raises(InterruptedError):
        EngineService.concat([a, b], out, cancel_event=evt, on_progress=lambda p, m: None)
    assert not Path(out).exists()
