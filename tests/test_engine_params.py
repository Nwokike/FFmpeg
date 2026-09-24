"""Engine parameter handling: filters, mastering params, m4a, cancel cleanup.

These are the M1 regression tests for the "UI collects params the engine
dropped" class of bug, plus the PyAV 18 quirks found while fixing it.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from services.engine_service import (
    EngineService,
    _atempo_factors,
    _av_rational,
    _hardware_decode,
    _supported_encoder_options,
)


def test_av_rational_conversion_for_packet_rescale():
    from fractions import Fraction

    import av

    converted = _av_rational(Fraction(1, 90_000))
    assert isinstance(converted, av.AVRational)
    assert converted.numerator == 1
    assert converted.denominator == 90_000


def test_encoder_options_are_validated_against_installed_codec():
    options = _supported_encoder_options(
        "libx264", {"crf": "23", "preset": "fast", "definitely_not_an_option": "x"}
    )
    assert options == {"crf": "23", "preset": "fast"}


def test_hardware_decode_is_opt_in_and_safe():
    assert _hardware_decode(False) is None
    # On a host with a listed device this returns an HWAccel; without one it
    # must still degrade to software rather than raising.
    assert _hardware_decode(True) is None or hasattr(_hardware_decode(True), "device_id")


# ── atempo chain math ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("speed", "expected"),
    [
        (1.0, []),
        (2.0, [2.0]),
        (0.75, [0.75]),
        (1.5, [1.5]),
        (4.0, [2.0, 2.0]),
        (0.25, [0.5, 0.5]),
    ],
)
def test_atempo_factors(speed, expected):
    assert _atempo_factors(speed) == expected


# ── convert: speed / rotation actually transform output ─────────────────


def test_convert_speed_and_rotation(synthetic_media):
    src = synthetic_media.path
    out = str(synthetic_media.dir / "speed_rot.mp4")
    src_dur = EngineService.probe(src).duration_s

    EngineService.convert(
        src,
        out,
        speed=1.5,
        rotation=90,
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )

    info = EngineService.probe(out)
    v = info.video_stream
    # 96x64 rotated 90° → 64x96; duration shrinks by the speed factor
    assert (v.width, v.height) == (64, 96)
    assert abs(info.duration_s - src_dur / 1.5) < 0.4


def test_convert_baseline_unchanged(synthetic_media):
    src = synthetic_media.path
    out = str(synthetic_media.dir / "baseline.mp4")
    src_dur = EngineService.probe(src).duration_s

    EngineService.convert(src, out, on_progress=lambda p, m: None, cancel_event=threading.Event())

    info = EngineService.probe(out)
    assert abs(info.duration_s - src_dur) < 0.4
    assert (info.video_stream.width, info.video_stream.height) == (96, 64)


# ── extract_audio: mastering params + m4a mapping ───────────────────────


def test_extract_audio_honors_channels_and_rate(synthetic_media):
    out = str(synthetic_media.dir / "mono_22k.flac")
    EngineService.extract_audio(
        synthetic_media.path,
        out,
        format_name="flac",
        channels=1,
        sample_rate=22050,
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    a = EngineService.probe(out).audio_stream
    assert a.channels == 1
    assert a.sample_rate == 22050


def test_m4a_maps_to_aac_not_mp3(synthetic_media):
    out = str(synthetic_media.dir / "mastered.m4a")
    EngineService.extract_audio(
        synthetic_media.path,
        out,
        format_name="m4a",
        bitrate_kbps=192,
        target_lufs=-16.0,
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    a = EngineService.probe(out).audio_stream
    assert a.codec_name == "aac", "m4a container must carry AAC, not an mp3 payload"


def test_loudnorm_measurement_returns_stats(synthetic_media):
    stats = EngineService._measure_loudnorm(synthetic_media.path, -16.0)
    assert isinstance(stats, dict)
    if stats:  # measured successfully (not the dynamic-mode fallback)
        assert "input_i" in stats


# ── cancel leaves no partial output ─────────────────────────────────────


def test_cancel_mid_cut_removes_partial(synthetic_media):
    out = str(synthetic_media.dir / "cancelled_cut.mp4")
    evt = threading.Event()

    def progress(pct, msg):
        evt.set()  # cancel at the first progress tick

    with pytest.raises(InterruptedError):
        EngineService.cut_trim(
            synthetic_media.path,
            out,
            0.0,
            1.5,
            stream_copy=False,
            on_progress=progress,
            cancel_event=evt,
        )
    assert not Path(out).exists(), "cancelled cut must clean up its partial file"


def test_cancel_mid_extract_audio_removes_partial(synthetic_media):
    out = str(synthetic_media.dir / "cancelled.mp3")
    evt = threading.Event()

    def progress(pct, msg):
        evt.set()

    with pytest.raises(InterruptedError):
        EngineService.extract_audio(
            synthetic_media.path,
            out,
            on_progress=progress,
            cancel_event=evt,
        )
    assert not Path(out).exists()


# ── frames: single-pass output + format passthrough ─────────────────────


def test_extract_frames_single_pass(synthetic_media):
    out_dir = str(synthetic_media.dir / "frames_out")
    paths = EngineService.extract_frames(
        synthetic_media.path,
        out_dir,
        count=4,
        format_name="jpg",
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    assert len(paths) == 4
    assert all(p.endswith(".jpg") for p in paths)
    assert len(list(Path(out_dir).glob("*.jpg"))) == 4


def test_create_gif_palette_output(synthetic_media):
    out = str(synthetic_media.dir / "anim.gif")
    EngineService.create_gif(
        synthetic_media.path,
        out,
        fps=10,
        width=48,
        start_s=0.0,
        duration_s=1.0,
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    assert Path(out).exists() and Path(out).stat().st_size > 0
