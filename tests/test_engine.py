"""Tests for EngineService, EngineProbe, and synthetic transcode."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.engine_probe import probe, synthetic_transcode
from services.engine_service import EngineService


def test_engine_probe():
    p = probe()
    assert p.av_version != ""
    assert p.codec_count > 0
    assert p.filter_count > 0
    assert p.format_count > 0
    assert p.h264_encode is True
    assert p.gif_ok is True


def test_synthetic_transcode_and_probe():
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = synthetic_transcode(tmp_dir)
        assert res["ok"] is True
        assert res["frames"] == 10
        assert res["mp4_bytes"] > 0
        assert res["jpg_bytes"] > 0

        mp4_path = Path(tmp_dir) / "spike_test.mp4"
        info = EngineService.probe(str(mp4_path))
        assert info.duration_s > 0
        assert info.video_stream is not None
        assert info.video_stream.width == 320
        assert info.video_stream.height == 180
        assert len(info.streams) >= 1
