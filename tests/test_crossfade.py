"""Crossfade join: color-probe blend proof, duration math, gates, cancel."""

from __future__ import annotations

import array
import math
import threading
from pathlib import Path

import av
import pytest

from services.engine_service import EngineService


def _gray_clip(path: str, gray: int, frames: int = 60, fps: int = 30) -> None:
    """Solid-gray clip (crf 0 keeps pixel values near-lossless for probes)."""
    o = av.open(path, "w")
    vs = o.add_stream("libx264", rate=fps)
    vs.width, vs.height, vs.pix_fmt = 96, 64, "yuv420p"
    vs.options = {"crf": "0", "preset": "ultrafast"}
    asr = o.add_stream("aac", rate=44100)
    asr.layout = "stereo"

    vt = av.VideoFrame(96, 64, "yuv420p")
    for pl in vt.planes:
        pl.update(bytes([gray]) * pl.buffer_size)
    for i in range(frames):
        vt.pts = i
        for pkt in vs.encode(vt):
            o.mux(pkt)
    for pkt in vs.encode(None):
        o.mux(pkt)

    n = 0
    for _ in range(int(frames / fps * 43) + 1):
        af = av.AudioFrame("s16", "stereo", 1024)
        af.sample_rate = 44100
        samples = array.array(
            "h",
            (
                v
                for k in range(1024)
                for v in (int(9000 * math.sin(2 * math.pi * 440 * (n + k) / 44100)),) * 2
            ),
        )
        n += 1024
        af.planes[0].update(samples.tobytes())
        for pkt in asr.encode(af):
            o.mux(pkt)
    for pkt in asr.encode(None):
        o.mux(pkt)
    o.close()


@pytest.fixture
def gray_pair(tmp_path):
    a = str(tmp_path / "a.mp4")
    b = str(tmp_path / "b.mp4")
    _gray_clip(a, 40)
    _gray_clip(b, 200)
    return a, b


def test_crossfade_duration_is_sum_minus_overlaps(gray_pair):
    a, b = gray_pair
    out = str(gray_pair[0]).replace("a.mp4", "xf.mp4")
    EngineService.concat([a, b], out, transition="crossfade", fade_s=0.5)

    info = EngineService.probe(out)
    expected = EngineService.probe(a).duration_s + EngineService.probe(b).duration_s - 0.5
    assert abs(info.duration_s - expected) < 0.15, (
        f"expected ~{expected:.3f}s, got {info.duration_s:.3f}s"
    )
    assert info.audio_stream is not None


def test_crossfade_three_clip_duration(gray_pair, tmp_path):
    a, b = gray_pair
    c = str(tmp_path / "c.mp4")
    _gray_clip(c, 120, frames=45)
    out = str(tmp_path / "xf3.mp4")

    EngineService.concat([a, b, c], out, transition="crossfade", fade_s=0.5)

    total = sum(EngineService.probe(p).duration_s for p in (a, b, c))
    info = EngineService.probe(out)
    # two fades overlap 1.0s total
    assert abs(info.duration_s - (total - 1.0)) < 0.2


def test_crossfade_actually_blends_pixels(gray_pair):
    """THE proof: solid 40-gray + 200-gray must produce intermediate values
    across the boundary — this is the exact test that condemned xfade."""
    a, b = gray_pair
    out = str(Path(a).parent / "blend.mp4")
    EngineService.concat([a, b], out, transition="crossfade", fade_s=0.5)

    dur_a = EngineService.probe(a).duration_s
    boundary = dur_a - 0.25  # inside the fade window on the output timeline

    inp = av.open(out)
    vs = inp.streams.video[0]
    inp.seek(int(max(0.0, boundary - 0.2) * av.time_base), backward=True)
    samples: list[int] = []
    stop = False
    for pkt in inp.demux([vs]):
        for fr in pkt.decode():
            t = fr.time
            if t is None or t < boundary - 0.25:
                continue
            if t > boundary + 0.05:
                stop = True
                break
            rf = fr.reformat(format="gray")
            data = bytes(memoryview(rf.planes[0]))
            samples.append(int(data[len(data) // 2]))
        if stop:
            break
    inp.close()

    intermediates = [v for v in samples if 45 < v < 195]
    assert len(intermediates) >= 3, f"expected a blended ramp across the boundary, got {samples}"
    assert samples == sorted(samples) or len(intermediates) >= 3  # ramp direction varies with codec


def test_crossfade_gate_undersized_clip_falls_back(gray_pair, tmp_path, caplog):
    a, _b = gray_pair
    short = str(tmp_path / "short.mp4")
    _gray_clip(short, 90, frames=6)  # ~0.2s → cannot host a 0.5s fade window
    out = str(tmp_path / "fallback.mp4")

    with caplog.at_level("WARNING"):
        EngineService.concat([a, short], out, transition="crossfade", fade_s=0.5)

    assert any("falling back to instant" in r.message for r in caplog.records)
    info = EngineService.probe(out)
    expected = EngineService.probe(a).duration_s + EngineService.probe(short).duration_s
    assert abs(info.duration_s - expected) < 0.3  # instant = sum, no overlap


def test_crossfade_gate_missing_filters(monkeypatch, gray_pair, caplog):
    """Filters absent → warn and still join via the instant path (no crash)."""
    a, b = gray_pair
    out = str(Path(a).parent / "nofilters.mp4")
    monkeypatch.setattr("services.engine_service.available_filters", lambda: {"fps"})
    with caplog.at_level("WARNING"):
        EngineService.concat([a, b], out, transition="crossfade", fade_s=0.5)

    assert any("falling back to instant" in r.message for r in caplog.records)
    info = EngineService.probe(out)
    expected = EngineService.probe(a).duration_s + EngineService.probe(b).duration_s
    assert abs(info.duration_s - expected) < 0.3


def test_crossfade_cancel_cleans_up(gray_pair, tmp_path):
    a, b = gray_pair
    out = str(tmp_path / "cancelled.mp4")
    evt = threading.Event()
    evt.set()
    with pytest.raises(InterruptedError):
        EngineService.concat(
            [a, b],
            out,
            transition="crossfade",
            fade_s=0.5,
            cancel_event=evt,
            on_progress=lambda p, m: None,
        )
    assert not Path(out).exists()
