"""Filter pack v2: availability cache, crop math, gated builder, e2e stack."""

from __future__ import annotations

import threading

import av

from services.engine_service import (
    EngineService,
    _build_video_filter_graph,
    _crop_dims,
    available_filters,
)

# ── Availability cache ───────────────────────────────────────────────────


def test_available_filters_cached_and_contains_core_set():
    a = available_filters()
    b = available_filters()
    assert a is b  # cached per process
    # Verified present in this build:
    for name in ("crop", "scale", "unsharp", "overlay", "movie", "nlmeans"):
        assert name in a, f"{name} should be available in this build"


# ── Crop math ────────────────────────────────────────────────────────────


def test_crop_dims_center_crop_square():
    assert _crop_dims(1920, 1080, "1:1") == (1080, 1080)


def test_crop_dims_wide_from_tall():
    cw, ch = _crop_dims(720, 1280, "16:9")
    assert cw == 720
    assert ch < 1280
    assert cw % 2 == 0 and ch % 2 == 0


def test_crop_dims_never_upscales():
    assert _crop_dims(320, 240, "16:9") == (320, 180) or _crop_dims(320, 240, "16:9")[0] <= 320


def test_crop_dims_bad_aspect_passthrough():
    assert _crop_dims(640, 480, "original") == (640, 480)
    assert _crop_dims(640, 480, "bogus") == (640, 480)
    assert _crop_dims(640, 480, "1:0") == (640, 480)


# ── Gated builder ────────────────────────────────────────────────────────


def _first_frame(path: str) -> av.VideoFrame:
    with av.open(path) as inp:
        for pkt in inp.demux([inp.streams.video[0]]):
            frames = pkt.decode()
            if frames:
                return frames[0]
    raise AssertionError("no frames")


def test_builder_returns_none_when_all_gated_off(synthetic_media):
    """eq is compiled OUT of this build — an EQ-only request must no-op safely."""
    frame = _first_frame(synthetic_media.path)
    graph = _build_video_filter_graph(
        frame,
        rotation=0,
        speed=1.0,
        eq={"brightness": 0.2, "contrast": 1.1, "saturation": 1.2},
    )
    if "eq" not in available_filters():
        assert graph is None, "no available filter → plain reformat path"


def test_builder_builds_for_rotation(synthetic_media):
    frame = _first_frame(synthetic_media.path)
    graph = _build_video_filter_graph(frame, rotation=90, speed=1.0)
    assert graph is not None


# ── End-to-end: crop + sharpen + denoise + watermark in one job ──────────


def _make_logo(tmp_path) -> str:
    logo = tmp_path / "logo.png"
    logo_frame = av.VideoFrame(16, 16, "rgb24")
    for plane in logo_frame.planes:
        plane.update(bytes([200, 30, 30]) * (16 * 16))
    logo_frame.save(str(logo))
    return str(logo)


def test_convert_stack_crop_sharpen_denoise_watermark(synthetic_media, tmp_path):
    out = str(synthetic_media.dir / "stacked.mp4")
    EngineService.convert(
        synthetic_media.path,
        out,
        crop_aspect="1:1",
        sharpen=50,
        denoise="low",
        watermark={
            "path": _make_logo(tmp_path),
            "position": "br",
            "width_pct": 25,
        },
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )

    info = EngineService.probe(out)
    v = info.video_stream
    assert v is not None
    # Source is 96x64 → 1:1 center crop must be square
    assert abs(v.width - v.height) <= 2, f"expected square crop, got {v.width}x{v.height}"
    assert info.duration_s > 1.0


def test_convert_with_missing_filter_degrades(synthetic_media):
    """eq-only request on this eq-less build → output still produced."""
    out = str(synthetic_media.dir / "eq_only.mp4")
    EngineService.convert(
        synthetic_media.path,
        out,
        eq={"brightness": 0.3, "contrast": 1.2, "saturation": 0.5},
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    info = EngineService.probe(out)
    assert info.video_stream is not None
    assert (info.video_stream.width, info.video_stream.height) == (96, 64)


def test_watermark_missing_file_is_ignored(synthetic_media, tmp_path):
    out = str(synthetic_media.dir / "wm_missing.mp4")
    EngineService.convert(
        synthetic_media.path,
        out,
        watermark={"path": str(tmp_path / "nope.png"), "position": "br"},
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    assert EngineService.probe(out).video_stream is not None
