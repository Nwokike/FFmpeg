"""Subtitle extraction: time formatting, hand writers, e2e from a text container.

Fixture strategy: subtitle ENCODERS are unusable on this PyAV build
(avcodec_open2 fails for srt/subrip/webvtt/mov_text; ass encode → EPERM), but
`.srt`/`.vtt` files are plain-text CONTAINERS the demuxer+decoder accept — so
the real decode path (demux → decode2 → SubtitleSet) is exercised end-to-end
against hand-written inputs. Timing was locked empirically: pts in µs,
end_display_time = duration in ms.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from services.engine_service import (
    EngineService,
    SubCue,
    _fmt_ass_time,
    _fmt_srt_time,
    _fmt_vtt_time,
    _write_ass,
    _write_srt,
    _write_vtt,
)

SAMPLE_SRT = """1
00:00:02,000 --> 00:00:03,500
Hello there

2
00:00:05,000 --> 00:00:06,500
Second line
with wrap
"""


@pytest.fixture
def srt_input(tmp_path: Path) -> str:
    p = tmp_path / "sample.srt"
    p.write_text(SAMPLE_SRT, encoding="utf-8")
    return str(p)


# ── Time formatting ──────────────────────────────────────────────────────


def test_srt_time_format():
    assert _fmt_srt_time(2.0) == "00:00:02,000"
    assert _fmt_srt_time(3.5) == "00:00:03,500"
    assert _fmt_srt_time(3661.25) == "01:01:01,250"
    assert _fmt_srt_time(-1.0) == "00:00:00,000"


def test_vtt_time_format():
    assert _fmt_vtt_time(2.0) == "00:00:02.000"
    assert _fmt_vtt_time(3661.25) == "01:01:01.250"


def test_ass_time_format():
    assert _fmt_ass_time(2.0) == "0:00:02.00"
    assert _fmt_ass_time(3.5) == "0:00:03.50"
    assert _fmt_ass_time(3661.25) == "1:01:01.25"


# ── Writers ──────────────────────────────────────────────────────────────

CUES = [
    SubCue(2.0, 3.5, "Hello there"),
    SubCue(5.0, 6.5, "Second line\nwith wrap"),
]


def test_write_srt(tmp_path: Path):
    out = tmp_path / "o.srt"
    _write_srt(str(out), CUES)
    text = out.read_text(encoding="utf-8")
    assert "1\n00:00:02,000 --> 00:00:03,500\nHello there\n" in text
    assert "2\n00:00:05,000 --> 00:00:06,500\nSecond line\nwith wrap\n" in text


def test_write_vtt(tmp_path: Path):
    out = tmp_path / "o.vtt"
    _write_vtt(str(out), CUES)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT\n\n")
    assert "00:00:02.000 --> 00:00:03.500\nHello there" in text


def test_write_ass(tmp_path: Path):
    out = tmp_path / "o.ass"
    _write_ass(str(out), CUES)
    text = out.read_text(encoding="utf-8")
    assert "[Events]" in text
    assert "Dialogue: 0,0:00:02.00,0:00:03.50,Default,,0,0,0,,Hello there" in text
    # newline → ASS \N
    assert "Second line\\Nwith wrap" in text


# ── End-to-end extraction (real demux + decode2 path) ────────────────────


def test_extract_srt_to_srt(srt_input, tmp_path: Path):
    out = str(tmp_path / "out.srt")
    result = EngineService.extract_subtitles(srt_input, out, format_name="srt")
    assert result == out
    text = Path(out).read_text(encoding="utf-8")
    assert "Hello there" in text
    assert "00:00:02,000 --> 00:00:03,500" in text
    assert "Second line\nwith wrap" in text


def test_extract_srt_to_vtt(srt_input, tmp_path: Path):
    out = str(tmp_path / "out.vtt")
    EngineService.extract_subtitles(srt_input, out, format_name="webvtt")
    text = Path(out).read_text(encoding="utf-8")
    assert text.startswith("WEBVTT")
    assert "Hello there" in text


def test_extract_srt_to_ass(srt_input, tmp_path: Path):
    out = str(tmp_path / "out.ass")
    EngineService.extract_subtitles(srt_input, out, format_name="ass")
    text = Path(out).read_text(encoding="utf-8")
    assert "[Script Info]" in text
    assert "Dialogue: 0,0:00:02.00,0:00:03.50" in text
    assert "Hello there" in text


def test_extract_out_of_range_index_falls_back(srt_input, tmp_path: Path):
    out = str(tmp_path / "fb.srt")
    EngineService.extract_subtitles(srt_input, out, stream_index=99, format_name="srt")
    assert "Hello there" in Path(out).read_text(encoding="utf-8")


def test_extract_no_subtitle_streams_errors(synthetic_media, tmp_path: Path):
    out = str(tmp_path / "none.srt")
    with pytest.raises(ValueError, match="no subtitle streams"):
        EngineService.extract_subtitles(synthetic_media.path, out)


def test_extract_unknown_format_errors(srt_input, tmp_path: Path):
    with pytest.raises(ValueError, match="Unsupported subtitle format"):
        EngineService.extract_subtitles(srt_input, str(tmp_path / "x.abc"), format_name="abc")


def test_extract_cancel_leaves_no_file(srt_input, tmp_path: Path):
    out = str(tmp_path / "cancelled.srt")
    evt = threading.Event()
    evt.set()  # cancelled before the first packet
    with pytest.raises(InterruptedError):
        EngineService.extract_subtitles(
            srt_input, out, cancel_event=evt, on_progress=lambda p, m: None
        )
    assert not Path(out).exists()


def test_extract_reports_cue_count(srt_input, tmp_path: Path):
    events: list[str] = []
    EngineService.extract_subtitles(
        srt_input, str(tmp_path / "c.srt"), on_progress=lambda p, m: events.append(m)
    )
    assert any("Wrote 2 cues" in m for m in events)
