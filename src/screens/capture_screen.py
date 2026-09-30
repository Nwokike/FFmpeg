"""Capture screen — in-app photo/video/mic capture feeding the conversion pipeline.

Mobile/web only (flet-camera's platform guard raises on desktop); desktop shows
a pick-a-file fallback instead. Permission flow is just-in-time: rationale on
first capture attempt, DENIED → retry, PERMANENTLY_DENIED/RESTRICTED → App
Settings deep link (6-status handling per flet-permission-handler).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import struct
import time
from pathlib import Path

import flet as ft

from components.empty_state import empty_state_view
from core.notify import ERROR, SUCCESS, show_snack
from core.state import use_app_state
from core.storage_paths import format_bytes, get_temp_dir
from core.styles import card_container, section_header
from core.theme import ACCENT_RED, PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import (
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    RADIUS_LG,
    SPACE_MD,
    SPACE_SM,
)
from state.controller_ctx import use_controller
from state.service_ctx import use_services

try:
    import flet_camera as ftc

    _HAS_CAMERA = True
except ImportError:  # pragma: no cover — package is in the dev tree
    _HAS_CAMERA = False

try:
    from flet_permission_handler import Permission, PermissionStatus
except ImportError:  # pragma: no cover
    Permission = None
    PermissionStatus = None

try:
    from flet_audio_recorder import AudioEncoder, AudioRecorderConfiguration
except ImportError:  # pragma: no cover
    AudioEncoder = None
    AudioRecorderConfiguration = None

logger = logging.getLogger(__name__)

# Streaming meter mode forces PCM16BITS (flet-audio-recorder constraint) — these
# are the raw-PCM recording presets we WAV-wrap ourselves on stop.
_PCM_RATE_CHANNELS = {"studio": (44100, 2), "voice": (16000, 1)}
_MAX_PCM_BYTES = 200 * 1024 * 1024  # streaming safety cap (~9 min studio WAV)
_MAX_RECORD_SEC = 1200  # hard stop for runaway recordings


def _status_value(status) -> str:
    """Normalize PermissionStatus (enum member or plain str) to its raw value."""
    return str(getattr(status, "value", status) or "").lower()


def next_permission_action(status, just_requested: bool = False) -> str:
    """Map a permission status to the next UI action.

    Returns one of: ``ok`` | ``ask`` | ``explain`` | ``settings``.
    ``explain`` = a just-made request was denied → show rationale with retry;
    ``settings`` = only the OS Settings page can help (permanent/restricted).
    """
    val = _status_value(status)
    if val in ("granted", "limited", "provisional"):
        return "ok"
    if val in ("permanentlydenied", "restricted"):
        return "settings"
    if val in ("denied",):
        return "explain" if just_requested else "ask"
    # None/unknown → ask
    return "explain" if just_requested else "ask"


def _write_wav(path: str, data: bytes, sample_rate: int, channels: int) -> None:
    """Wrap raw PCM16 chunks in a RIFF/WAV header (streaming mode has no muxer)."""
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(data))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, 16)
        + b"data"
        + struct.pack("<I", len(data))
    )
    Path(path).write_bytes(header + data)


def _pcm_rms(chunk: bytes) -> float:
    """Normalized RMS (0..1) of a PCM16 little-endian chunk."""
    usable = len(chunk) - (len(chunk) % 2)
    if usable <= 0:
        return 0.0
    samples = struct.unpack(f"<{usable // 2}h", chunk[:usable])
    acc = 0
    for s in samples:
        acc += s * s
    return min(1.0, math.sqrt(acc / (usable // 2)) / 32768.0 * 3.0)


def _can_capture(page: ft.Page) -> bool:
    """Camera requires web/mobile (desktop raises in flet-camera's guard)."""
    try:
        return bool(page.web or (page.platform and page.platform.is_mobile()))
    except Exception as exc:
        logger.warning("Capture capability check failed: %s", exc)
        return False


def _is_mounted(ctrl) -> bool:
    """True once Flet has attached the control to the page.

    Control has no ``_page`` attribute in Flet 1.0.1 — ``getattr(ctrl, "_page")``
    is always None, which made every guard silently false (camera never starts,
    teardown never runs). The ``page`` property walks the parent chain and is
    the canonical probe: it raises RuntimeError while unmounted.
    """
    if ctrl is None:
        return False
    try:
        _ = ctrl.page  # property walk is the probe; raises until attached
        return True
    except (RuntimeError, AttributeError):
        return False


@ft.component
def CaptureScreen() -> ft.Control:
    """Photo / Video / Mic capture with just-in-time permissions and an after-capture hand-off."""
    page = ft.context.page
    ctrl = use_controller()
    services = use_services()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    mode, set_mode = ft.use_state("photo")  # "photo" | "video" | "mic"
    camera_ready, set_camera_ready = ft.use_state(False)
    recording, set_recording = ft.use_state(False)
    rec_paused, set_rec_paused = ft.use_state(False)
    elapsed, set_elapsed = ft.use_state(0)
    level, set_level = ft.use_state(0.0)
    pcm_preset, set_pcm_preset = ft.use_state("studio")  # "studio" | "voice"
    mic_codec, set_mic_codec = ft.use_state("pcm16")  # "pcm16" | "opus" | "aac"
    captured_path, set_captured_path = ft.use_state(None)
    captured_info, set_captured_info = ft.use_state(None)
    busy, set_busy = ft.use_state(False)

    camera_ref = ft.use_ref(None)
    camera_inited_ref = ft.use_ref(False)
    camera_audio_mode_ref = ft.use_ref(None)
    taking_ref = ft.use_ref(False)
    recording_ref = ft.use_ref(
        False
    )  # queryable from unmount cleanup (effect captures first render)
    ticking_ref = ft.use_ref(False)
    elapsed_ref = ft.use_ref(0)
    chunks_ref = ft.use_ref([])
    chunk_bytes_ref = ft.use_ref(0)
    last_level_ts_ref = ft.use_ref(0.0)
    mic_out_ref = ft.use_ref(None)
    mic_codec_ref = ft.use_ref("pcm16")
    mic_preset_ref = ft.use_ref("studio")

    # ── Unmount: stop ticker + release mic/camera — the effect body captured
    # the FIRST render, so live state must be read from refs, never closures.

    def _cleanup():
        ticking_ref.current = False
        taking_ref.current = False
        cam = camera_ref.current
        rec = services.audio_recorder

        async def _teardown():
            # Mid-take navigate-away is a DISCARD, not a silent save.
            if rec is not None:
                try:
                    if await rec.is_recording():
                        await rec.cancel_recording()
                except Exception as exc:
                    logger.debug("Recorder cancel on unmount failed: %s", exc)
                rec.on_stream = None
                set_rec_paused(False)
            if cam is not None and _is_mounted(cam):
                if recording_ref.current:
                    try:
                        await cam.stop_video_recording()
                    except Exception as exc:
                        logger.debug("Stop video on unmount failed: %s", exc)
                try:
                    await cam.pause_preview()
                except Exception as exc:
                    logger.debug("Pause preview on unmount failed: %s", exc)
            camera_inited_ref.current = False
            camera_audio_mode_ref.current = None
            camera_ref.current = None

        page.run_task(_teardown)

    ft.use_effect(lambda: _cleanup, [])

    def _apply_requested_mode():
        """Apply the pending_capture_mode a tool requested before routing here.

        Registered before the platform early-return so hook order is identical
        on every render path, and keyed on the observable field so a second
        tool request re-applies the mode (the value clears once consumed).
        """
        requested = app_state.pending_capture_mode
        if requested in ("photo", "video", "mic") and requested != mode:
            set_mode(requested)
        return None

    ft.use_effect(_apply_requested_mode, [app_state.pending_capture_mode])

    # ── Desktop / unsupported platform fallback ────────────────────────────

    if not _can_capture(page):
        return ft.ListView(
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            on_click=lambda _: ctrl.navigate("dashboard"),
                        ),
                        ft.Text("Capture", size=FONT_LG, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=SPACE_SM,
                ),
                empty_state_view(
                    icon=ft.Icons.CAMERA_ALT_ROUNDED,
                    title="Capture is mobile-only",
                    subtitle="Camera and microphone capture run on Android, iOS and the web app. On desktop, pick a media file instead.",
                    action=ft.FilledButton(
                        "Pick a File Instead",
                        on_click=lambda _: ctrl.pick_media_for("convert"),
                    ),
                    is_dark=is_dark,
                ),
            ],
            spacing=SPACE_MD,
            expand=True,
        )

    # ── Permission flow ─────────────────────────────────────────────────────

    def _perm_rationale(perm, settings_only: bool) -> None:
        # Only camera/mic are requested today; anything else gets a neutral
        # label instead of being misnamed as one of the two.
        name = (
            "camera"
            if perm == Permission.CAMERA
            else "microphone"
            if perm == Permission.MICROPHONE
            else "this"
        )
        if settings_only:
            body = (
                f"{name.title()} access is blocked for this app. Enable it in "
                "Android/iOS Settings to use capture."
            )
        else:
            body = (
                f"FFmpeg needs {name} access to capture media on this device. "
                "Everything is processed on-device."
            )

        def _open_settings(_):
            page.pop_dialog()
            if not services.permission_handler:
                return

            async def _open():
                try:
                    # open_app_settings returns False when the OS refuses —
                    # tell the user instead of leaving a dead tap.
                    opened = await services.permission_handler.open_app_settings()
                    if not opened:
                        show_snack(
                            page,
                            f"Couldn't open Settings — enable {name} there manually",
                            bgcolor=ERROR,
                        )
                except Exception as exc:
                    logger.warning("open_app_settings failed: %s", exc)
                    show_snack(page, "Couldn't open Settings", bgcolor=ERROR)

            page.run_task(_open)

        def _retry(_):
            page.pop_dialog()
            if mode in ("photo", "video"):
                page.run_task(_prepare_camera)
            else:
                page.run_task(_toggle_mic)

        actions = []
        if not settings_only:
            actions.append(ft.FilledButton("Try Again", on_click=_retry))
        actions.append(ft.TextButton("Open Settings", on_click=_open_settings))
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"{name.title()} access needed"),
                content=ft.Text(body),
                actions=actions,
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    async def _permission_ok(perm) -> bool:
        ph = services.permission_handler
        if ph is None or Permission is None:
            show_snack(page, "Permissions are unavailable on this platform", bgcolor=ERROR)
            return False
        try:
            status = await ph.get_status(perm)
            action = next_permission_action(status, just_requested=False)
            if action == "ask":
                status = await ph.request(perm)
                action = next_permission_action(status, just_requested=True)
            if action == "ok":
                return True
            _perm_rationale(perm, settings_only=(action == "settings"))
            return False
        except Exception:
            logger.exception("Permission flow failed")
            show_snack(page, "Couldn't request permission — check app settings.", bgcolor=ERROR)
            return False

    # ── Camera lifecycle ────────────────────────────────────────────────────

    def _on_camera_state(e) -> None:
        if getattr(e, "has_error", False):
            show_snack(
                page,
                f"Camera error: {getattr(e, 'error_description', None) or 'unknown'}",
                bgcolor=ERROR,
            )
        is_recording = bool(getattr(e, "is_recording_video", False))
        set_recording(is_recording)
        recording_ref.current = is_recording
        set_rec_paused(bool(getattr(e, "is_recording_paused", False)))
        # The native state event is the truth for "camera is live" — the local
        # flag used to go stale when init completed on a different render pass.
        if getattr(e, "is_initialized", False):
            camera_inited_ref.current = True

    async def _prepare_camera() -> None:
        if camera_ref.current is not None:
            # Retry after a permission denial: the control exists, so re-arm
            # the init effect instead of stranding camera_ready=False.
            if not camera_ready:
                set_camera_ready(True)
            return
        if not _HAS_CAMERA:
            show_snack(page, "Camera support is not installed", bgcolor=ERROR)
            return
        if not await _permission_ok(Permission.CAMERA):
            return
        if mode == "video" and not await _permission_ok(Permission.MICROPHONE):
            return
        try:
            camera_ref.current = ftc.Camera(on_state_change=_on_camera_state)
            set_camera_ready(True)
        except Exception as exc:
            logger.exception("Camera creation failed")
            show_snack(page, f"Camera unavailable: {exc}", bgcolor=ERROR)

    async def _wait_for_mount(cam, timeout_s: float = 6.0) -> bool:
        """Wait until a freshly created Camera control is attached to the page.

        ``_is_mounted`` probes the canonical ``Control.page`` property, which
        raises RuntimeError until the control is in the page tree.
        """
        deadline = time.monotonic() + timeout_s
        while not _is_mounted(cam):
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.05)
        return True

    async def _init_camera() -> None:
        cam = camera_ref.current
        if cam is None or camera_inited_ref.current:
            return
        if not await _wait_for_mount(cam):
            logger.error("Camera control never mounted — init aborted")
            show_snack(page, "Camera failed to start: control was not mounted", bgcolor=ERROR)
            return
        try:
            cameras = await cam.get_available_cameras()
            if not cameras:
                show_snack(page, "No camera found on this device", bgcolor=ERROR)
                return
            # Prefer the back lens — cameras[0] is often the selfie.
            target = next(
                (
                    c
                    for c in cameras
                    if getattr(c, "lens_direction", None) == ftc.CameraLensDirection.BACK
                ),
                cameras[0],
            )
            # Video is the ONLY consumer of the mic; asking for audio in photo
            # mode risks silent video / OEM throws when MIC is denied.
            enable_audio = mode == "video"
            last_err: Exception | None = None
            for preset in (ftc.ResolutionPreset.HIGH, ftc.ResolutionPreset.MEDIUM):
                try:
                    await cam.initialize(target, preset, enable_audio=enable_audio)
                    camera_inited_ref.current = True
                    camera_audio_mode_ref.current = enable_audio
                    return
                except Exception as exc:
                    last_err = exc
                    logger.warning("Camera init failed at %s: %s", preset, exc)
            show_snack(page, f"Camera failed to start: {last_err}", bgcolor=ERROR)
        except Exception as exc:
            logger.exception("Camera init failed")
            show_snack(page, f"Camera failed to start: {exc}", bgcolor=ERROR)

    async def _reconfigure_camera() -> None:
        """Recreate the controller when photo/video changes its audio contract."""
        cam = camera_ref.current
        if cam is None:
            return
        try:
            await cam.pause_preview()
        except Exception as exc:
            logger.debug("Camera preview pause during mode switch failed: %s", exc)
        camera_ref.current = None
        camera_inited_ref.current = False
        camera_audio_mode_ref.current = None
        set_camera_ready(False)
        await _prepare_camera()

    def _effect_prepare():
        desired_audio = mode == "video"
        if mode == "mic":
            # Leaving camera modes releases the native controller — reusing the
            # stale ref after the Camera control left the tree produced the
            # "Control must be added to the page first" error on return.
            if camera_ref.current is not None:
                _cleanup()
            return None
        if not recording:
            if (
                camera_ref.current is not None
                and camera_inited_ref.current
                and camera_audio_mode_ref.current != desired_audio
            ):
                page.run_task(_reconfigure_camera)
            elif camera_ref.current is None:
                page.run_task(_prepare_camera)
        return None

    ft.use_effect(_effect_prepare, [mode])

    def _effect_init():
        if camera_ready:
            page.run_task(_init_camera)

    ft.use_effect(_effect_init, [camera_ready])

    # ── Shared ticker (video record + mic record) ───────────────────────────

    async def _tick() -> None:
        # Loop is gated on ticking_ref so it exits even if task-cancelling is
        # unavailable on this platform's Flet runtime.
        try:
            while ticking_ref.current:
                await asyncio.sleep(1)
                elapsed_ref.current += 1
                set_elapsed(elapsed_ref.current)
                if elapsed_ref.current >= _MAX_RECORD_SEC:
                    show_snack(page, "Maximum capture length reached", bgcolor=ERROR)
                    if mode == "video":
                        await _finish_video()
                    else:
                        await _finish_mic()
                    break
        except asyncio.CancelledError:
            logger.debug("Capture ticker cancelled")

    def _start_ticker() -> None:
        elapsed_ref.current = 0
        set_elapsed(0)
        ticking_ref.current = True
        page.run_task(_tick)

    def _stop_ticker() -> None:
        ticking_ref.current = False

    # ── Capture finalize (shared by photo/video/mic) ────────────────────────

    async def _finalize_capture(path: str) -> None:
        """Probe the take, stage it as current media, show the after-capture card."""
        from services.engine_service import EngineService

        try:
            info = await asyncio.to_thread(EngineService.probe, path)
        except Exception:
            logger.exception("Capture probe failed for %s", path)
            with contextlib.suppress(OSError):
                Path(path).unlink(missing_ok=True)  # noqa: ASYNC240 — trivial stat/exists check
            show_snack(page, "That capture couldn't be read — try again.", bgcolor=ERROR)
            return
        app_state.current_media_path = path
        app_state.current_media_info = info
        set_captured_path(path)
        set_captured_info(info)
        # If a tool sent us here, return the take to that tool rather than
        # dead-ending on the after-capture card.
        target = app_state.pending_media_target
        if target:
            app_state.pending_media_target = None
            app_state.pending_capture_mode = None
            show_snack(page, "Capture loaded", bgcolor=SUCCESS)
            ctrl.navigate(target)
            return
        show_snack(page, "Capture ready — pick a tool or save it", bgcolor=SUCCESS)

    # ── Photo ───────────────────────────────────────────────────────────────

    async def _take_photo() -> None:
        cam = camera_ref.current
        if cam is None or busy:
            if cam is None:
                page.run_task(_prepare_camera)
            return
        if not camera_inited_ref.current or not _is_mounted(cam):
            show_snack(page, "Camera is still starting…")
            return
        if taking_ref.current:  # native shutter busy — ignore double taps
            return
        taking_ref.current = True
        set_busy(True)
        try:
            data = await cam.take_picture()
            out = get_temp_dir() / f"photo_{int(time.time())}.jpg"
            out.write_bytes(data)
            await _finalize_capture(str(out))
        except Exception as exc:
            logger.exception("Photo capture failed")
            show_snack(page, f"Photo failed: {exc}", bgcolor=ERROR)
        finally:
            taking_ref.current = False
            set_busy(False)

    # ── Video ───────────────────────────────────────────────────────────────

    async def _finish_video() -> None:
        cam = camera_ref.current
        if cam is None:
            return
        _stop_ticker()
        set_busy(True)
        try:
            data = await cam.stop_video_recording()
            ext = ftc.detect_video_extension(data) if _HAS_CAMERA else "mp4"
            if ext == "bin":
                ext = "mp4"  # container sniff failed — probe validates below
            out = get_temp_dir() / f"video_{int(time.time())}.{ext}"
            out.write_bytes(data)
            await _finalize_capture(str(out))
        except Exception as exc:
            logger.exception("Video capture failed")
            show_snack(page, f"Video failed: {exc}", bgcolor=ERROR)
        finally:
            recording_ref.current = False
            set_recording(False)
            set_busy(False)

    async def _toggle_video() -> None:
        cam = camera_ref.current
        if cam is None:
            page.run_task(_prepare_camera)
            return
        if recording:
            await _finish_video()
            return
        if not camera_inited_ref.current or not _is_mounted(cam):
            show_snack(page, "Camera is still starting…")
            return
        # Video mode initializes the camera WITH audio — gate on the mic grant
        # or the start silently fails (or throws) on OEM builds.
        if not await _permission_ok(Permission.MICROPHONE):
            return
        set_busy(True)
        try:
            await cam.prepare_for_video_recording()
            await cam.start_video_recording()
            set_recording(True)
            recording_ref.current = True
            _start_ticker()
        except Exception as exc:
            logger.exception("Video record start failed")
            show_snack(page, f"Recording failed: {exc}", bgcolor=ERROR)
            set_recording(False)
            recording_ref.current = False
        finally:
            set_busy(False)

    async def _pause_video() -> None:
        cam = camera_ref.current
        if cam is None or not _is_mounted(cam):
            return
        try:
            if rec_paused:
                await cam.resume_video_recording()
            else:
                await cam.pause_video_recording()
        except Exception as exc:
            logger.warning("Pause toggle failed: %s", exc)
            show_snack(page, f"Pause failed: {exc}", bgcolor=ERROR)

    # ── Mic ─────────────────────────────────────────────────────────────────

    def _on_mic_stream(e) -> None:
        chunk = getattr(e, "chunk", b"") or b""
        chunks_ref.current.append(chunk)
        chunk_bytes_ref.current += len(chunk)
        now = time.monotonic()
        if now - last_level_ts_ref.current >= 0.1:
            last_level_ts_ref.current = now
            set_level(_pcm_rms(chunk))
            if chunk_bytes_ref.current >= _MAX_PCM_BYTES:
                logger.warning(
                    "PCM cap reached (%d bytes) — auto-stopping", chunk_bytes_ref.current
                )
                page.run_task(_finish_mic)

    def _codec_for(mic_codec_name: str):
        return {
            "pcm16": AudioEncoder.WAV,
            "opus": AudioEncoder.OPUS,
            "aac": AudioEncoder.AACLC,
        }.get(mic_codec_name, AudioEncoder.WAV)

    async def _finish_mic() -> None:
        rec = services.audio_recorder
        if rec is None:
            return
        _stop_ticker()
        set_busy(True)
        try:
            out_path = mic_out_ref.current
            returned = await rec.stop_recording()
            final = returned or out_path
            set_level(0.0)
            if final and Path(final).exists() and Path(final).stat().st_size > 100:  # noqa: ASYNC240
                await _finalize_capture(final)
            else:
                show_snack(page, "No audio recorded — hold and speak into the mic", bgcolor=ERROR)
        except Exception as exc:
            logger.exception("Mic stop failed")
            show_snack(page, f"Recording failed: {exc}", bgcolor=ERROR)
        finally:
            rec.on_stream = None
            chunks_ref.current = []
            chunk_bytes_ref.current = 0
            set_recording(False)
            set_rec_paused(False)
            set_busy(False)

    async def _toggle_mic() -> None:
        rec = services.audio_recorder
        if rec is None or AudioRecorderConfiguration is None:
            show_snack(page, "Recorder is unavailable on this platform", bgcolor=ERROR)
            return
        if recording:
            await _finish_mic()
            return
        if not await _permission_ok(Permission.MICROPHONE):
            return
        try:
            # Revoked mid-session surfaces as a generic start refusal without
            # this just-in-time check.
            if not await rec.has_permission():
                show_snack(
                    page,
                    "Microphone access is off — enable it in Settings",
                    bgcolor=ERROR,
                )
                return
        except Exception as exc:
            logger.warning("Recorder has_permission check failed: %s", exc)
        # The chip value is the current render state; the ref is only a
        # snapshot for asynchronous teardown.  Reading the ref here made Opus
        # and AAC selections silently fall back to the initial PCM16 take.
        codec_name = mic_codec
        mic_codec_ref.current = codec_name
        enc = _codec_for(codec_name)
        try:
            if not await rec.is_supported_encoder(enc):
                show_snack(page, "Codec unavailable — recording WAV instead")
                codec_name = "pcm16"
                enc = _codec_for("pcm16")
        except Exception as exc:
            logger.warning("Encoder probe failed, recording WAV instead: %s", exc)

        if codec_name == "pcm16":
            rate, ch = _PCM_RATE_CHANNELS[mic_preset_ref.current]
            ext, bit_rate = "wav", 128000
        elif codec_name == "opus":
            rate, ch, ext, bit_rate = 48000, 2, "opus", 96000
        else:
            rate, ch, ext, bit_rate = 44100, 2, "m4a", 128000

        # Direct file mode: native plugin writes the complete audio file
        # directly without streaming interference.
        rec.on_stream = None
        chunks_ref.current = []
        chunk_bytes_ref.current = 0

        mic_codec_ref.current = codec_name
        mic_preset_ref.current = pcm_preset
        cfg = AudioRecorderConfiguration(
            encoder=enc, channels=ch, sample_rate=rate, bit_rate=bit_rate
        )
        # The recorder's Dart side resolves output_path against its own app-local
        # recordings directory. Feeding it our absolute sandbox path produced
        # `<assets>/data/user/0/.../cache/rec_….wav` and an ENOENT crash. Give it
        # a bare filename and use whatever path it returns in _finish_mic.
        recording_name = f"rec_{int(time.time())}.{ext}"
        out_path = str(get_temp_dir() / recording_name)
        mic_out_ref.current = out_path
        try:
            started = await rec.start_recording(output_path=recording_name, configuration=cfg)
        except Exception as exc:
            logger.exception("Mic start failed")
            rec.on_stream = None  # don't stream into chunks nobody will write
            chunks_ref.current = []
            chunk_bytes_ref.current = 0
            show_snack(page, f"Recording failed: {exc}", bgcolor=ERROR)
            return
        if not started:
            rec.on_stream = None
            chunks_ref.current = []
            chunk_bytes_ref.current = 0
            show_snack(page, "Recorder refused to start", bgcolor=ERROR)
            return
        try:
            # start_recording can report success while the native side refused
            # (mic held by a call, OEM policy).
            if not await rec.is_recording():
                rec.on_stream = None
                chunks_ref.current = []
                chunk_bytes_ref.current = 0
                show_snack(page, "Recorder didn't start — mic may be in use", bgcolor=ERROR)
                return
        except Exception as exc:
            logger.warning("is_recording check failed: %s", exc)
        set_recording(True)
        set_rec_paused(False)
        _start_ticker()

    async def _pause_mic() -> None:
        rec = services.audio_recorder
        if rec is None:
            return
        try:
            if rec_paused:
                await rec.resume_recording()
            else:
                await rec.pause_recording()
            paused_now = bool(await rec.is_paused())
            set_rec_paused(paused_now)
            # The 1s ticker keeps going while the button says Resume — gate it
            # on the recorder's actual paused state so the MM:SS freezes too.
            ticking_ref.current = not paused_now
        except Exception as exc:
            logger.warning("Pause toggle failed: %s", exc)
            show_snack(page, f"Pause failed: {exc}", bgcolor=ERROR)

    # ── After-capture actions ───────────────────────────────────────────────

    def _use_in(tool: str) -> None:
        if not captured_path or captured_info is None:
            return
        app_state.current_media_path = captured_path
        app_state.current_media_info = captured_info
        ctrl.navigate(tool)

    async def _save_capture() -> None:
        if not captured_path:
            return
        saved = await services.media_io.save_media_file(captured_path)
        if saved:
            show_snack(page, f"Saved to {saved}", bgcolor=SUCCESS, duration_ms=4000)
        else:
            show_snack(page, "Couldn't save the capture", bgcolor=ERROR)

    def _retake() -> None:
        set_captured_path(None)
        set_captured_info(None)
        set_elapsed(0)
        elapsed_ref.current = 0

    def _set_mode(m: str) -> None:
        if recording or busy:
            return
        set_mode(m)

    # ── Render ──────────────────────────────────────────────────────────────

    elapsed_str = f"{elapsed // 60:02d}:{elapsed % 60:02d}"

    if captured_path and captured_info is not None:
        preview: ft.Control = card_container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=PRIMARY, size=28),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        Path(captured_path).name,
                                        size=FONT_MD,
                                        weight=ft.FontWeight.W_600,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        f"{format_bytes(Path(captured_path).stat().st_size)} • captured",
                                        size=FONT_SM,
                                        color=muted,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=SPACE_SM,
                    ),
                    ft.Divider(height=1),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton("Convert", on_click=lambda _: _use_in("convert")),
                            ft.OutlinedButton("Compress", on_click=lambda _: _use_in("compress")),
                            ft.OutlinedButton("Cut", on_click=lambda _: _use_in("cut")),
                        ],
                        spacing=SPACE_SM,
                    ),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton("Audio", on_click=lambda _: _use_in("audio")),
                            ft.OutlinedButton(
                                "Save to Device",
                                icon=ft.Icons.DOWNLOAD_ROUNDED,
                                on_click=lambda _: page.run_task(_save_capture),
                            ),
                            ft.TextButton("Retake", on_click=_retake),
                        ],
                        spacing=SPACE_SM,
                    ),
                ],
                spacing=SPACE_MD,
            ),
            padding=SPACE_MD,
            border_radius=RADIUS_LG,
            is_dark=is_dark,
        )
    elif mode in ("photo", "video"):
        active_camera = camera_ref.current if (camera_ready and camera_ref.current) else None
        inner: ft.Control = (
            active_camera
            if active_camera is not None
            else ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.CAMERA_ALT_ROUNDED, size=56, color=muted),
                        ft.Text(
                            "Starting camera…"
                            if camera_ready
                            else "Preparing camera — access is requested on first use",
                            size=FONT_SM,
                            color=muted,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=SPACE_SM,
                    expand=True,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        )
        preview = ft.Container(
            content=inner,
            height=300,
            border_radius=RADIUS_LG,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor="#000000",
        )
    else:  # mic mode, no capture yet
        preview = card_container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.MIC_ROUNDED,
                                size=32,
                                color=ACCENT_RED if recording else PRIMARY,
                            ),
                            ft.Text(
                                f"Recording {elapsed_str}" if recording else "Microphone ready",
                                size=FONT_MD,
                                weight=ft.FontWeight.W_600,
                            ),
                        ],
                        spacing=SPACE_SM,
                    ),
                    ft.ProgressBar(
                        value=float(level or 0.0) if recording else 0.0,
                        height=8,
                        color=ACCENT_RED if level > 0.7 else PRIMARY,
                    ),
                    ft.Text(
                        "Live level meter needs WAV mode — Opus/AAC record without it.",
                        size=FONT_XS,
                        color=muted,
                    ),
                ],
                spacing=SPACE_SM,
            ),
            padding=SPACE_MD,
            border_radius=RADIUS_LG,
            is_dark=is_dark,
        )

    # Mode chips
    mode_row = ft.Row(
        controls=[
            ft.Chip(
                label=ft.Text("Photo"),
                selected=mode == "photo",
                on_select=lambda _: _set_mode("photo"),
            ),
            ft.Chip(
                label=ft.Text("Video"),
                selected=mode == "video",
                on_select=lambda _: _set_mode("video"),
            ),
            ft.Chip(
                label=ft.Text("Mic"),
                selected=mode == "mic",
                on_select=lambda _: _set_mode("mic"),
            ),
        ],
        spacing=SPACE_SM,
    )

    # Capture controls
    controls: list[ft.Control] = []
    if not captured_path:
        if mode == "photo":
            controls.append(
                ft.FilledButton(
                    "Take Photo" if not busy else "Capturing…",
                    icon=ft.Icons.PHOTO_CAMERA_ROUNDED,
                    height=48,
                    expand=True,
                    disabled=busy or recording,
                    on_click=lambda _: page.run_task(_take_photo),
                )
            )
        elif mode == "video":
            if recording:
                controls.append(
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Stop",
                                icon=ft.Icons.STOP_ROUNDED,
                                bgcolor=ACCENT_RED,
                                height=48,
                                expand=True,
                                disabled=busy,
                                on_click=lambda _: page.run_task(_finish_video),
                            ),
                            ft.OutlinedButton(
                                "Pause" if not rec_paused else "Resume",
                                icon=ft.Icons.PAUSE_ROUNDED
                                if not rec_paused
                                else ft.Icons.PLAY_ARROW_ROUNDED,
                                height=48,
                                disabled=busy,
                                on_click=lambda _: page.run_task(_pause_video),
                            ),
                        ],
                        spacing=SPACE_SM,
                        expand=True,
                    )
                )
            else:
                controls.append(
                    ft.FilledButton(
                        "Record Video",
                        icon=ft.Icons.VIDEOCAM_ROUNDED,
                        height=48,
                        expand=True,
                        disabled=busy,
                        on_click=lambda _: page.run_task(_toggle_video),
                    )
                )
        else:  # mic
            if recording:
                controls.append(
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Stop Recording",
                                icon=ft.Icons.STOP_ROUNDED,
                                bgcolor=ACCENT_RED,
                                height=48,
                                expand=True,
                                disabled=busy,
                                on_click=lambda _: page.run_task(_finish_mic),
                            ),
                            ft.OutlinedButton(
                                "Pause" if not rec_paused else "Resume",
                                icon=ft.Icons.PAUSE_ROUNDED
                                if not rec_paused
                                else ft.Icons.PLAY_ARROW_ROUNDED,
                                height=48,
                                disabled=busy,
                                on_click=lambda _: page.run_task(_pause_mic),
                            ),
                        ],
                        spacing=SPACE_SM,
                        expand=True,
                    )
                )
            else:
                # Preset row (WAV quality) + codec row
                controls.append(
                    ft.Row(
                        controls=[
                            ft.Chip(
                                label=ft.Text("Studio WAV 44.1k"),
                                selected=mic_codec == "pcm16" and pcm_preset == "studio",
                                on_select=lambda _: (
                                    set_mic_codec("pcm16"),
                                    set_pcm_preset("studio"),
                                ),
                            ),
                            ft.Chip(
                                label=ft.Text("Voice WAV 16k"),
                                selected=mic_codec == "pcm16" and pcm_preset == "voice",
                                on_select=lambda _: (
                                    set_mic_codec("pcm16"),
                                    set_pcm_preset("voice"),
                                ),
                            ),
                            ft.Chip(
                                label=ft.Text("Opus"),
                                selected=mic_codec == "opus",
                                on_select=lambda _: set_mic_codec("opus"),
                            ),
                            ft.Chip(
                                label=ft.Text("AAC"),
                                selected=mic_codec == "aac",
                                on_select=lambda _: set_mic_codec("aac"),
                            ),
                        ],
                        wrap=True,
                        spacing=SPACE_SM,
                    )
                )
                controls.append(
                    ft.FilledButton(
                        "Start Recording",
                        icon=ft.Icons.MIC_ROUNDED,
                        height=48,
                        expand=True,
                        disabled=busy,
                        on_click=lambda _: page.run_task(_toggle_mic),
                    )
                )

    return ft.ListView(
        controls=[
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Capture", size=FONT_LG, weight=ft.FontWeight.BOLD),
                    *(
                        [
                            ft.Text(
                                elapsed_str,
                                size=FONT_MD,
                                weight=ft.FontWeight.BOLD,
                                color=ACCENT_RED,
                            )
                        ]
                        if recording
                        else []
                    ),
                ],
                spacing=SPACE_SM,
            ),
            section_header("Capture Mode", "On-device, straight into the tools", is_dark=is_dark),
            mode_row,
            preview,
            *controls,
        ],
        spacing=SPACE_MD,
        expand=True,
    )


__all__ = ["CaptureScreen", "_can_capture", "_pcm_rms", "_write_wav", "next_permission_action"]
