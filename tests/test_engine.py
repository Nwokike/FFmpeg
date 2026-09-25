"""Tests for EngineService, EngineProbe, and synthetic transcode."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import av
import pytest

from core.engine_probe import can_encode, can_encode_format, probe, synthetic_transcode
from services.engine_service import (
    EngineCapabilityError,
    EngineService,
    _decode_packet,
    _resolve_audio_codec,
    _resolve_video_codec,
    friendly_job_error,
)


def test_engine_probe():
    p = probe()
    assert p.av_version != ""
    assert p.codec_count > 0
    assert p.filter_count > 0
    assert p.format_count > 0
    assert p.bitstream_filters
    assert p.library_versions
    assert p.encoder_options

    # Measured, not asserted from the dev machine: every pick the probe reports
    # must be a real mode='w' encoder. The old `assert h264_encode is True`
    # encoded the Windows wheel's capabilities and would fail on Android, whose
    # LGPL build ships no H.264 encoder.
    for name in p.video_encoder_picks + p.audio_encoder_picks:
        av.codec.Codec(name, mode="w")
    assert isinstance(p.gif_ok, bool)


def test_probe_reports_lgpl_encoders_needed_by_mobile():
    """The FFmpeg-own encoders must be discoverable, or Android ships NONE."""
    p = probe()
    assert "mpeg4" in p.video_encoder_picks
    assert "aac" in p.audio_encoder_picks
    assert "pcm_s16le" in p.audio_encoder_picks
    assert can_encode("mpeg4") is True
    assert can_encode_format("aac") is True
    assert can_encode_format("wav") is True


def test_resolve_codec_substitutes_available_alias():
    # libx264 and h264 name the same encoder under different builds.
    resolved = _resolve_video_codec("libx264")
    av.codec.Codec(resolved, mode="w")


def test_resolve_codec_raises_friendly_error_instead_of_unknown_codec():
    with pytest.raises(EngineCapabilityError) as exc:
        _resolve_video_codec("definitely-not-a-codec")
    message = str(exc.value)
    assert "not available" in message
    assert "UnknownCodec" not in message


def test_audio_format_resolver_refuses_unencodable_format():
    with pytest.raises(EngineCapabilityError):
        _resolve_audio_codec("mp3xyz")


def test_friendly_job_error_names_missing_capability():
    unknown = getattr(av.codec, "UnknownCodecError", None)
    if unknown is not None:
        message = friendly_job_error(unknown("h264", "No encoder"))
        assert "UnknownCodec" not in message
        assert "device" in message or "encode" in message

    # A capability error passes through unchanged — it is already user-facing.
    cap = EngineCapabilityError("VP9 encoding is not available.")
    assert friendly_job_error(cap) == "VP9 encoding is not available."


def test_android_lgpl_wheel_never_returns_an_unverified_encoder(monkeypatch):
    """The phone failure in one test: no libx264 ⇒ no blind `h264` fallback."""
    from services import engine_service as es

    lgpl_only = {"mpeg4", "mjpeg", "png", "gif", "prores", "ffv1", "aac", "pcm_s16le"}

    def mobile_supports(name: str, mode: str) -> bool:
        return mode == "w" and name in lgpl_only

    monkeypatch.setattr(es, "_codec_supports_mode", mobile_supports)

    # An encoder this build really has resolves fine…
    assert es._resolve_video_codec("mpeg4") == "mpeg4"

    # …and one it does not raises a capability error rather than handing
    # add_stream() a name FFmpeg cannot open.
    with pytest.raises(EngineCapabilityError) as exc:
        es._resolve_video_codec("libx264")
    assert "H.264" in str(exc.value)

    # _pick_video_encoder must never hand back an unverified name either.
    with pytest.raises(EngineCapabilityError):
        es._pick_video_encoder()


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
