"""Tests for EngineService, EngineProbe, and synthetic transcode."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import av

from core.engine_probe import probe, synthetic_transcode
from services.engine_service import EngineService, _decode_packet


def test_engine_probe():
    p = probe()
    assert p.av_version != ""
    assert p.codec_count > 0
    assert p.filter_count > 0
    assert p.format_count > 0
    assert p.bitstream_filters
    assert p.library_versions
    assert p.encoder_options
    assert p.h264_encode is True
    assert p.gif_ok is True


def test_decode_packet_skips_invalid_data(caplog):
    class BadPacket:
        stream = type("Stream", (), {"index": 3})()
        pts = 123
        dts = 120

        def decode(self):
            raise av.error.InvalidDataError(1, "corrupt packet")

    with caplog.at_level(logging.WARNING, logger="EngineService"):
        assert list(_decode_packet(BadPacket())) == []

    assert "Skipping corrupt media packet" in caplog.text


def test_compress_to_target_uses_supported_stream_properties(synthetic_media):
    output = str(synthetic_media.dir / "compressed.mp4")
    EngineService.compress_to_target(
        synthetic_media.path,
        output,
        target_size_mb=1.0,
        on_progress=lambda _pct, _message: None,
    )
    info = EngineService.probe(output)
    assert info.video_stream is not None
    assert info.video_stream.width == 96
    assert info.video_stream.height == 64


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
