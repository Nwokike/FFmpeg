"""Remux track-picker + dossier upgrades: rotation, chapters, disposition, report."""

from __future__ import annotations

import array
import math
import threading
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import av
import pytest

from screens.probe_screen import _fmt_ct, build_media_report
from services.engine_service import EngineService


def _rich_source(tmp_path: Path) -> str:
    """MP4 with rotation + chapters + tagged audio.

    Chaptered MP4s also carry a data stream — this doubles as the regression
    fixture for the probe crash ('DataStream' has no bit_rate).
    """
    src = str(tmp_path / "rich.mp4")
    o = av.open(src, "w")
    vs = o.add_stream("libx264", rate=10)
    vs.width, vs.height, vs.pix_fmt = 64, 64, "yuv420p"
    vs.options = {"preset": "ultrafast", "crf": "40", "keyint": "5"}
    asr = o.add_stream("aac", rate=44100)
    asr.layout = "stereo"
    vs.set_display_rotation(90)
    try:
        from av.stream import Disposition

        asr.disposition = Disposition.default
    except Exception:  # pragma: no cover
        pass
    asr.metadata["language"] = "eng"
    o.set_chapters(
        [
            {
                "id": 1,
                "start": 0,
                "end": 500,
                "time_base": Fraction(1, 1000),
                "metadata": {"title": "Intro"},
            },
            {
                "id": 2,
                "start": 500,
                "end": 1000,
                "time_base": Fraction(1, 1000),
                "metadata": {"title": "Part Two"},
            },
        ]
    )

    vt = av.VideoFrame(64, 64, "yuv420p")
    for plane in vt.planes:
        plane.update(bytes([120]) * plane.buffer_size)
    for i in range(10):
        vt.pts = i
        for pkt in vs.encode(vt):
            o.mux(pkt)
    for pkt in vs.encode(None):
        o.mux(pkt)

    n = 0
    for _ in range(21):
        af = av.AudioFrame("s16", "stereo", 1024)
        af.sample_rate = 44100
        samples = array.array(
            "h",
            (
                v
                for k in range(1024)
                for v in (int(8000 * math.sin(2 * math.pi * 440 * (n + k) / 44100)),) * 2
            ),
        )
        n += 1024
        af.planes[0].update(samples.tobytes())
        for pkt in asr.encode(af):
            o.mux(pkt)
    for pkt in asr.encode(None):
        o.mux(pkt)
    o.close()
    return src


@pytest.fixture
def rich_source(tmp_path: Path) -> SimpleNamespace:
    path = _rich_source(tmp_path)
    return SimpleNamespace(path=path, dir=tmp_path)


# ── Probe upgrades ───────────────────────────────────────────────────────


def test_probe_reads_rotation_chapters_disposition(rich_source):
    # Regression: chaptered MP4s carry a DataStream; probe used to raise
    # AttributeError ('DataStream' object has no attribute 'bit_rate').
    info = EngineService.probe(rich_source.path)

    assert info.video_stream is not None
    assert abs(info.video_stream.rotation or 0) == 90
    assert len(info.chapters) == 2
    assert info.chapters[0].title == "Intro"
    assert info.chapters[1].title == "Part Two"
    assert info.chapters[0].start_s == 0.0
    assert abs(info.chapters[1].start_s - 0.5) < 0.01

    audio = info.audio_stream
    assert audio is not None
    assert audio.language == "eng"
    assert audio.disposition.get("default") is True

    assert "Intro" not in info.raw_dump  # summary lists streams, not chapter titles
    assert any(s.stream_type == "video" for s in info.streams)


def test_probe_plain_synthetic_still_works(synthetic_media):
    info = EngineService.probe(synthetic_media.path)
    assert info.chapters == []
    assert info.video_stream.rotation in (0, None)
    assert info.audio_stream.disposition.get("default") in (None, False, True)


# ── Report builder ───────────────────────────────────────────────────────


def test_build_media_report_contains_essentials(rich_source):
    info = EngineService.probe(rich_source.path)
    report = build_media_report(info)
    assert report.startswith("# rich.mp4")
    assert "## Streams" in report
    assert "`" in report  # codec backticks
    assert "## Chapters" in report
    assert "Intro" in report and "Part Two" in report
    assert "rot 90°" in report or "rot -90°" in report
    assert "lang eng" in report


def test_fmt_ct_formats():
    assert _fmt_ct(0) == "00:00"
    assert _fmt_ct(65) == "01:05"
    assert _fmt_ct(3661) == "1:01:01"


# ── Remux (lossless track picker) ────────────────────────────────────────


def test_remux_drops_audio_track(rich_source):
    out = str(rich_source.dir / "video_only.mkv")
    info_in = EngineService.probe(rich_source.path)
    audio_idx = next(s.index for s in info_in.streams if s.stream_type == "audio")

    EngineService.remux(
        rich_source.path, out, drop_indices=[audio_idx], on_progress=lambda p, m: None
    )

    info_out = EngineService.probe(out)
    assert info_out.video_stream is not None
    assert info_out.audio_stream is None
    assert abs(info_out.duration_s - info_in.duration_s) < 0.5


def test_remux_preserves_language_disposition_and_chapters(rich_source):
    out = str(rich_source.dir / "full.mkv")
    EngineService.remux(rich_source.path, out)

    info_out = EngineService.probe(out)
    assert info_out.audio_stream is not None
    assert info_out.audio_stream.language == "eng"
    assert info_out.audio_stream.disposition.get("default") is True
    titles = [c.title for c in info_out.chapters]
    assert "Intro" in titles and "Part Two" in titles


def test_remux_keeps_video_rotation(rich_source):
    out = str(rich_source.dir / "rot_copy.mkv")
    EngineService.remux(rich_source.path, out)
    info_out = EngineService.probe(out)
    assert abs(info_out.video_stream.rotation or 0) == 90


def test_remux_rejects_dropping_everything(rich_source):
    info = EngineService.probe(rich_source.path)
    all_idx = [s.index for s in info.streams]
    with pytest.raises(ValueError, match="excluded"):
        EngineService.remux(rich_source.path, str(rich_source.dir / "none.mkv"), all_idx)


def test_remux_cancel_cleans_up(rich_source):
    out = str(rich_source.dir / "cancelled.mkv")
    evt = threading.Event()
    evt.set()
    with pytest.raises(InterruptedError):
        EngineService.remux(rich_source.path, out, cancel_event=evt, on_progress=lambda p, m: None)
    assert not Path(out).exists()
