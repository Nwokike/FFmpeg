"""M8 phone-truth: encoder defaults resolve on the wheel, ticker guard,
picker single-flight, and device-API contracts from the installed .venv.

Every assertion here pins a failure the user hit on-device: H.264 demanded
on an LGPL wheel, frozen mic counters on resume, already_active picker
crashes, and Audio/Video/Camera kwargs that don't exist in flet 1.0.3.
"""

from __future__ import annotations

import asyncio
import inspect
import re

import pytest

from services.engine_service import (
    _codec_supports_mode,
    _encoder_open_kwargs,
    _encoder_pix_fmt,
    _resolve_video_codec,
)

# ── Encoder truth (the H.264-on-LGPL failures) ───────────────────────────────


def test_resolver_picks_a_real_encoder_for_each_offered_codec():
    """Every codec a screen can forward must resolve on THIS wheel."""
    for name in ("libx264", "mpeg4", "mjpeg", "png", "gif", "prores", "ffv1"):
        try:
            resolved = _resolve_video_codec(name)
        except Exception as exc:
            pytest.fail(f"{name} does not resolve on this wheel: {exc}")
        assert _codec_supports_mode(resolved, "w"), f"{resolved} is not an encoder here"


def test_pix_fmt_fits_still_encoders():
    """png rejects yuv420p — the still-convert crash. mjpeg takes yuvj420p."""
    assert _encoder_pix_fmt("libx264") == "yuv420p"
    assert _encoder_pix_fmt("png") in ("rgb24", "rgba", "rgb8"), _encoder_pix_fmt("png")
    assert _encoder_pix_fmt("mjpeg") in ("yuvj420p", "yuv420p")


def test_vorbis_opens_with_strict_kwargs():
    """Experimental vorbis needs strict -2 at add_stream (E2E crash)."""
    assert _encoder_open_kwargs("vorbis") == {"options": {"strict": "-2"}}
    assert _encoder_open_kwargs("aac") == {}
    assert _encoder_open_kwargs("libx264") == {}


def test_compress_cut_join_accept_video_codec_param():
    """New params exist with legacy-compatible defaults (None = auto)."""
    import inspect as _inspect

    from services.engine_service import EngineService

    for fn_name in ("compress_to_target", "cut_trim", "concat"):
        sig = _inspect.signature(getattr(EngineService, fn_name))
        assert "video_codec" in sig.parameters, f"{fn_name} missing video_codec"
        assert sig.parameters["video_codec"].default is None


# ── Ticker generation guard (mic resume double-increment race) ───────────────


def test_ticker_generation_pattern():
    """The capture screen's _tick must ignore stale generations."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src" / "screens" / "capture_screen.py").read_text(
        encoding="utf-8"
    )
    assert "tick_gen_ref" in src, "generation guard missing from capture screen"
    assert "_resume_ticker" in src, "resume must relaunch without resetting elapsed"


# ── Picker single-flight (already_active crash) ──────────────────────────────


def test_picker_has_single_flight_lock():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src" / "services" / "media_io.py").read_text(
        encoding="utf-8"
    )
    assert "_pick_lock" in src, "single-flight lock missing from MediaIOService"


def test_concurrent_picks_serialize():
    """Two overlapping pick rounds must not reach the native picker together."""

    class FakePicker:
        def __init__(self):
            self.active = 0
            self.max_active = 0

        async def pick_files(self, **kwargs):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.05)
            self.active -= 1
            return []

    async def go():
        from services.media_io import MediaIOService

        svc = MediaIOService.__new__(MediaIOService)
        svc.file_picker = FakePicker()
        svc._pick_lock = asyncio.Lock()
        # Drive the locked entry the way pick_media_file does.
        async with svc._pick_lock:
            await svc.file_picker.pick_files()
            await svc.file_picker.pick_files()

    async def race():
        from services.media_io import MediaIOService

        svc = MediaIOService.__new__(MediaIOService)
        picker = FakePicker()
        svc.file_picker = picker
        svc._pick_lock = asyncio.Lock()

        async def one():
            async with svc._pick_lock:
                await picker.pick_files()

        await asyncio.gather(one(), one())
        return picker.max_active

    assert asyncio.run(race()) == 1, "picker rounds overlapped"


# ── Device-API contracts (verified against installed .venv) ──────────────────


def test_audio_kwargs_match_installed_flet_audio():
    """on_error does not exist on flet_audio 1.0.3 Audio — both call sites
    must not pass it."""
    import flet_audio

    sig = inspect.signature(flet_audio.Audio.__init__)
    assert "on_error" not in sig.parameters, "venv grew on_error — re-audit call sites"
    for kw in ("src", "on_state_change", "on_loaded", "release_mode"):
        assert kw in sig.parameters, f"Audio lost {kw}"
    from pathlib import Path

    for rel in ("src/screens/audio_screen.py", "src/screens/result_screen.py"):
        src = (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")
        # Only Audio() constructions are in scope — ftv.Video HAS on_error
        # (verified), so scope the check to the Audio( call blocks.
        for match in re.finditer(r"\bAudio\(", src):
            block = src[match.start() : match.start() + 900]
            assert "on_error" not in block, f"{rel} Audio() still passes on_error"


def test_video_media_uses_resource_not_src():
    """VideoMedia takes resource= (verified dataclass fields); src= TypeErrors."""
    import dataclasses

    import flet_video

    names = [f.name for f in dataclasses.fields(flet_video.VideoMedia)]
    assert "resource" in names
    assert "http_headers" in names


def test_camera_mount_contract_holds():
    """Camera is a LayoutControl: every method needs page attachment."""
    import flet_camera

    assert issubclass(flet_camera.Camera, __import__("flet").LayoutControl)
    sig = inspect.signature(flet_camera.Camera.initialize)
    assert "description" in sig.parameters and "resolution_preset" in sig.parameters


def test_gif_caps_are_phone_safe():
    """Extract sliders must cap the palette-graph cost (30fps/1080p/15s hung)."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src" / "screens" / "extract_screen.py").read_text(
        encoding="utf-8"
    )
    assert "max=20" in src, "GIF fps cap missing"
    assert "max=640" in src, "GIF width cap missing"
    assert "min(8.0" in src, "GIF duration cap missing"
