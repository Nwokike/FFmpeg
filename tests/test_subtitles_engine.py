"""Subtitle engine: muxing, cue reading/shifting, burn-in gating.

The lean Android wheel ships drawtext (freetype); the stock desktop PyAV wheel
does not — the burn-in path must therefore refuse loudly rather than build an
unknown filter, and the test suite pins both sides of that gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import av
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.engine_service import (  # noqa: E402
    EngineCapabilityError,
    EngineService,
    available_filters,
    burn_subtitles,
    mux_subtitles,
    read_cues,
)
from services.engine_service.ops_subtitles import _escaped  # noqa: E402

SRT = (
    "1\n00:00:00,500 --> 00:00:02,000\nHello: it's 100% done, really\n\n"
    "2\n00:00:03,000 --> 00:00:05,000\nSecond\nline\n"
)


@pytest.fixture
def srt(tmp_path):
    path = tmp_path / "en.srt"
    path.write_text(SRT)
    return path


def test_drawtext_text_is_escaped_and_flattened():
    assert _escaped("a:b") == r"a\:b"
    assert _escaped("it's") == r"it\'s"
    assert _escaped("50%") == r"50\%"
    assert _escaped("a,b") == r"a\,b"
    assert _escaped("line one\nline two") == "line one line two"


def test_sidecar_mux_into_matroska(srt, tmp_path):
    other = tmp_path / "fr.srt"
    other.write_text(SRT)
    out = tmp_path / "subs.mkv"
    mux_subtitles(str(srt), str(other), str(out), language="fra")
    with av.open(str(out)) as c:
        subs = c.streams.subtitles
        assert len(subs) == 2
        assert subs[-1].metadata.get("language") == "fra"


def test_sidecar_mux_refuses_mp4(srt, tmp_path):
    with pytest.raises(ValueError, match="mov_text"):
        mux_subtitles(str(srt), str(srt), str(tmp_path / "subs.mp4"))


def test_read_cues_and_shift(srt, tmp_path):
    cues = read_cues(str(srt))
    assert len(cues) == 2 and "Hello" in cues[0].text
    out = tmp_path / "shifted.srt"
    EngineService.extract_subtitles(str(srt), str(out), shift_s=-0.25)
    shifted = read_cues(str(out))
    assert shifted[0].start_s == pytest.approx(cues[0].start_s - 0.25, abs=0.05)


def test_burn_in_is_capability_gated(srt, tmp_path):
    if "drawtext" in available_filters():
        pytest.skip("this wheel has drawtext — the gate does not apply")
    with pytest.raises(EngineCapabilityError, match="drawtext"):
        burn_subtitles(str(srt), str(tmp_path / "burned.mp4"), sidecar_path=str(srt))
