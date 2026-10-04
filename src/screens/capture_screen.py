"""Capture screen — in-app photo/video/mic capture feeding the conversion pipeline.

Mobile/web only (flet-camera's platform guard raises on desktop); desktop shows
a pick-a-file fallback instead. Permission flow is just-in-time: rationale on
first capture attempt, DENIED → retry, PERMANENTLY_DENIED → App Settings deep
link, RESTRICTED → "unavailable on this device" (the OS forbids changes, so no
Settings trip can help).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path

import flet as ft

from components.empty_state import empty_state_view
from core.constants import kind_allowed, kind_refusal
from core.notify import ERROR, SUCCESS, show_snack
from core.permissions import next_permission_action  # re-exported: tests import it from here
from core.state import use_app_state
from core.storage_paths import format_bytes, get_temp_dir, unique_temp_name
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

# Direct file mode: the native plugin writes the complete audio file itself
# (WAV/Opus/AAC per chip). No PCM streaming is wired — on_stream stays None
# and there is no live level meter (a streaming meter would need PCM16BITS +
# an on_stream handler; that is M5 work, not this screen).
_PCM_RATE_CHANNELS = {"studio": (44100, 2), "voice": (16000, 1)}
_MAX_RECORD_SEC = 1200  # hard stop for runaway recordings


def _status_value(status) -> str:
    """Normalize PermissionStatus (enum member or plain str) to its raw value."""
    return str(getattr(status, "value", status) or "").lower()


def _can_capture(page: ft.Page) -> bool:
    """Camera requires web/mobile (desktop raises in flet-camera's guard)."""
    try:
        return bool(page.web or (page.platform and page.platform.is_mobile()))
    except Exception as exc:
        logger.warning("Capture capability check failed: %s", exc)
        return False


def _is_mounted(ctrl) -> bool:
    """True once Flet has attached the control to the page.

    Control has no ``_page`` attribute — ``getattr(ctrl, "_page")`` is always
    None, which made every guard silently false (camera never starts,
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
    pcm_preset, set_pcm_preset = ft.use_state("studio")  # "studio" | "voice"
    mic_codec, set_mic_codec = ft.use_state("pcm16")  # "pcm16" | "opus" | "aac" | "flac"
    # Recorder DSP (best-effort: OEMs may ignore — never gated, never promised).
    dsp_noise, set_dsp_noise = ft.use_state(False)
    dsp_echo, set_dsp_echo = ft.use_state(False)
    dsp_gain, set_dsp_gain = ft.use_state(False)
    mic_device, set_mic_device = ft.use_state(None)  # InputDevice id or None = default
    mic_devices, set_mic_devices = ft.use_state([])
    # Camera extras (all runtime-probed, hidden when unsupported).
    torch_on, set_torch_on = ft.use_state(False)
    front_lens, set_front_lens = ft.use_state(False)
    zoom_level, set_zoom_level = ft.use_state(1.0)
    zoom_range, set_zoom_range = ft.use_state(None)  # (min, max) or None = unsupported
    cam_quality, set_cam_quality = ft.use_state("HIGH")  # HIGH | MEDIUM | LOW
    preview_aspect, set_preview_aspect = ft.use_state(None)
    lock_orientation, set_lock_orientation = ft.use_state(False)
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

        Keyed on the observable field so a second tool request re-applies the
        mode (the value clears once consumed).
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

    def _perm_rationale(perm, action: str) -> None:
        # Only camera/mic are requested today; anything else gets a neutral
        # label instead of being misnamed as one of the two.
        name = (
            "camera"
            if perm == Permission.CAMERA
            else "microphone"
            if perm == Permission.MICROPHONE
            else "this"
        )
        if action == "unavailable":
            body = (
                f"{name.title()} access is restricted on this device (parental "
                "controls or device policy). The OS forbids changes — contact "
                "the device administrator."
            )
        elif action == "settings":
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
        if action not in ("settings", "unavailable"):
            actions.append(ft.FilledButton("Try Again", on_click=_retry))
        if action == "settings":
            actions.append(ft.TextButton("Open Settings", on_click=_open_settings))
        else:
            actions.append(ft.TextButton("Close", on_click=lambda _: page.pop_dialog()))
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"{name.title()} access needed"),
                content=ft.Text(body),
                actions=actions,
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    async def _permission_ok(perm, *, mic_fallback: bool = False) -> bool:
        ph = services.permission_handler
        if ph is None or Permission is None:
            # Linux/macOS have no handler: the mic path falls back to the
            # recorder's own check instead of hard-blocking (Windows/Web keep
            # the handler path above).
            if mic_fallback:
                rec = services.audio_recorder
                if rec is None:
                    return False
                try:
                    return bool(await rec.has_permission())
                except Exception:
                    logger.exception("Recorder permission fallback failed")
                    return False
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
            _perm_rationale(perm, action)
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
        # Native busy flags are the truth for the shutter — the manual
        # taking_ref used to lag the hardware.
        if getattr(e, "is_taking_picture", False):
            taking_ref.current = True
        elif not is_recording:
            taking_ref.current = False
        # Flash state reflects the hardware (OEMs can override our request).
        flash_mode = getattr(e, "flash_mode", None)
        if flash_mode is not None:
            with contextlib.suppress(Exception):
                set_torch_on(str(getattr(flash_mode, "value", flash_mode)).lower() == "torch")
        # Size the preview from the hardware, not the fixed 300px box.
        preview_size = getattr(e, "preview_size", None)
        if preview_size is not None:
            try:
                w, h = float(preview_size.width), float(preview_size.height)
                if w > 0 and h > 0:
                    set_preview_aspect(w / h)
            except Exception:
                pass
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
            # Lens flip without destroy: set_description on the enumerated
            # sibling beats the full reconfigure path (kept as fallback).
            want_front = front_lens
            target = next(
                (
                    c
                    for c in cameras
                    if (
                        getattr(c, "lens_direction", None)
                        == (
                            ftc.CameraLensDirection.FRONT
                            if want_front
                            else ftc.CameraLensDirection.BACK
                        )
                    )
                ),
                next(
                    (
                        c
                        for c in cameras
                        if getattr(c, "lens_direction", None) == ftc.CameraLensDirection.BACK
                    ),
                    cameras[0],
                ),
            )
            # Video is the ONLY consumer of the mic; asking for audio in photo
            # mode risks silent video / OEM throws when MIC is denied.
            enable_audio = mode == "video"
            last_err: Exception | None = None
            presets = {
                "HIGH": (ftc.ResolutionPreset.HIGH, ftc.ResolutionPreset.MEDIUM),
                "MEDIUM": (ftc.ResolutionPreset.MEDIUM, ftc.ResolutionPreset.LOW),
                "LOW": (ftc.ResolutionPreset.LOW,),
            }.get(cam_quality, (ftc.ResolutionPreset.HIGH, ftc.ResolutionPreset.MEDIUM))
            init_kwargs: dict = {}
            if mode == "video":
                # Conservative caps: huge bitrates therm-throttle phones.
                init_kwargs = {"fps": 30, "video_bitrate": 8_000_000, "audio_bitrate": 128_000}
            for preset in presets:
                try:
                    await cam.initialize(target, preset, enable_audio=enable_audio, **init_kwargs)
                    camera_inited_ref.current = True
                    camera_audio_mode_ref.current = enable_audio
                    # Zoom range is hardware truth — clamp every later set to it.
                    try:
                        lo = await cam.get_min_zoom_level()
                        hi = await cam.get_max_zoom_level()
                        if hi is not None and hi > (lo or 1.0):
                            set_zoom_range((float(lo or 1.0), float(hi)))
                    except Exception:
                        pass
                    if lock_orientation and mode == "video":
                        try:
                            await cam.lock_capture_orientation()
                        except Exception as exc:
                            logger.debug("Orientation lock unsupported: %s", exc)
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
        if not _is_mounted(cam):
            logger.warning("Camera preview pause skipped: control not mounted")
            camera_ref.current = None
            camera_inited_ref.current = False
            camera_audio_mode_ref.current = None
            set_camera_ready(False)
            return
        try:
            await cam.pause_preview()
        except Exception as exc:
            logger.warning("Camera preview pause during mode switch failed: %s", exc)
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
        # Loop is gated on ticking_ref (cleared by _stop_ticker and unmount
        # cleanup), so it always has an exit — no reliance on task cancellation.
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

    def _kind_gate(target: str, kind: str) -> bool:
        """A take never enters a tool that cannot process its kind."""
        if kind_allowed(target, kind):
            return True
        show_snack(page, kind_refusal(target, kind), bgcolor=ERROR)
        return False

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
        # dead-ending on the after-capture card — but only if the tool can
        # process this kind; a refused take stays on the card for a valid tool.
        target = app_state.pending_media_target
        if target:
            app_state.pending_media_target = None
            app_state.pending_capture_mode = None
            if not _kind_gate(target, info.kind):
                return
            show_snack(page, "Capture loaded", bgcolor=SUCCESS)
            ctrl.navigate(target)
            return
        show_snack(page, "Capture ready — pick a tool or save it", bgcolor=SUCCESS)

    # ── Camera extras (all runtime-probed) ────────────────────────────────

    async def _toggle_torch() -> None:
        cam = camera_ref.current
        if cam is None or not _is_mounted(cam):
            return
        try:
            await cam.set_flash_mode(ftc.FlashMode.TORCH if not torch_on else ftc.FlashMode.OFF)
            set_torch_on(not torch_on)
        except Exception as exc:
            logger.warning("Torch toggle failed (unsupported?): %s", exc)

    async def _flip_lens() -> None:
        cam = camera_ref.current
        if cam is None:
            return
        try:
            cameras = await cam.get_available_cameras()
        except Exception as exc:
            logger.warning("Lens list failed: %s", exc)
            return
        want = ftc.CameraLensDirection.FRONT if not front_lens else ftc.CameraLensDirection.BACK
        target = next((c for c in cameras if getattr(c, "lens_direction", None) == want), None)
        if target is None:
            show_snack(page, "No second lens on this device", bgcolor=ERROR)
            return
        # Hot-switch without destroy; fall back to full reconfigure.
        try:
            await cam.set_description(target)
            set_front_lens(not front_lens)
        except Exception as exc:
            logger.warning("Hot lens switch failed, reconfiguring: %s", exc)
            set_front_lens(not front_lens)
            camera_inited_ref.current = False
            camera_audio_mode_ref.current = None
            set_camera_ready(False)
            await _prepare_camera()

    async def _apply_zoom(value: float) -> None:
        cam = camera_ref.current
        if cam is None or not _is_mounted(cam) or zoom_range is None:
            return
        lo, hi = zoom_range
        clamped = max(lo, min(float(value), hi))
        set_zoom_level(clamped)
        try:
            await cam.set_zoom_level(clamped)
        except Exception as exc:
            logger.warning("Zoom set failed: %s", exc)

    async def _resume_preview_safe() -> None:
        cam = camera_ref.current
        if cam is None or not _is_mounted(cam):
            return
        try:
            await cam.resume_preview()
        except Exception as exc:
            logger.debug("Preview resume skipped: %s", exc)

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
            # Second-resolution timestamps collided on burst taps (same path
            # overwrote the previous shot) — unique names per take.
            out = get_temp_dir() / unique_temp_name("photo", ".jpg")
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
        if not camera_inited_ref.current or not _is_mounted(cam):
            logger.warning("Video stop skipped: camera not mounted")
            show_snack(page, "Camera is still starting…")
            return
        _stop_ticker()
        set_busy(True)
        try:
            data = await cam.stop_video_recording()
            ext = ftc.detect_video_extension(data) if _HAS_CAMERA else "mp4"
            if ext == "bin":
                ext = "mp4"  # container sniff failed — probe validates below
            out = get_temp_dir() / unique_temp_name("video", f".{ext}")
            out.write_bytes(data)
            await _finalize_capture(str(out))
        except Exception as exc:
            logger.exception("Video capture failed")
            show_snack(page, f"Video failed: {exc}", bgcolor=ERROR)
        finally:
            recording_ref.current = False
            set_recording(False)
            set_busy(False)
            if lock_orientation:
                try:
                    await cam.unlock_capture_orientation()
                except Exception as exc:
                    logger.debug("Orientation unlock skipped: %s", exc)

    async def _toggle_video() -> None:
        cam = camera_ref.current
        if cam is None:
            page.run_task(_prepare_camera)
            return
        if recording:
            await _finish_video()
            return
        if not camera_inited_ref.current or not _is_mounted(cam):
            logger.warning("Video record blocked: camera not mounted")
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
            logger.warning("Video pause skipped: camera not mounted")
            return
        try:
            if rec_paused:
                await cam.resume_video_recording()
            else:
                await cam.pause_video_recording()
        except Exception as exc:
            logger.warning("Pause toggle failed: %s", exc)
            show_snack(page, f"Pause failed: {exc}", bgcolor=ERROR)

    async def _reconfigure_for_quality() -> None:
        """Quality chips re-init the controller at the new preset."""
        camera_inited_ref.current = False
        camera_audio_mode_ref.current = None
        cam = camera_ref.current
        if cam is not None and _is_mounted(cam):
            try:
                await cam.pause_preview()
            except Exception as exc:
                logger.debug("Preview pause for quality switch skipped: %s", exc)
        await _init_camera()

    # ── Mic (direct file mode: the native plugin writes the file) ─────────

    def _codec_for(mic_codec_name: str):
        return {
            "pcm16": AudioEncoder.WAV,
            "opus": AudioEncoder.OPUS,
            "aac": AudioEncoder.AACLC,
            "flac": AudioEncoder.FLAC,
        }.get(mic_codec_name, AudioEncoder.WAV)

    async def _load_mic_devices() -> None:
        rec = services.audio_recorder
        if rec is None:
            return
        try:
            devices = await rec.get_input_devices()
        except Exception as exc:
            logger.debug("Mic device list unavailable: %s", exc)
            return
        try:
            set_mic_devices([(str(d.id), str(getattr(d, "label", d.id) or d.id)) for d in devices])
        except Exception as exc:
            logger.debug("Mic device parse failed: %s", exc)

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
            if final and Path(final).exists() and Path(final).stat().st_size > 100:  # noqa: ASYNC240
                await _finalize_capture(final)
            else:
                show_snack(page, "No audio recorded — hold and speak into the mic", bgcolor=ERROR)
        except Exception as exc:
            logger.exception("Mic stop failed")
            show_snack(page, f"Recording failed: {exc}", bgcolor=ERROR)
        finally:
            rec.on_stream = None
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
        if not await _permission_ok(Permission.MICROPHONE, mic_fallback=True):
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
        elif codec_name == "flac":
            rate, ch, ext, bit_rate = 44100, 2, "flac", 0
        else:
            rate, ch, ext, bit_rate = 44100, 2, "m4a", 128000

        # Direct file mode: the native plugin writes the complete audio file
        # itself. on_stream stays None — nothing streams anywhere.
        rec.on_stream = None

        mic_codec_ref.current = codec_name
        mic_preset_ref.current = pcm_preset
        cfg_kwargs: dict = {
            "encoder": enc,
            "channels": ch,
            "sample_rate": rate,
            "bit_rate": bit_rate,
            # DSP is best-effort (OEMs may ignore) — passed, never gated.
            "suppress_noise": bool(dsp_noise),
            "cancel_echo": bool(dsp_echo),
            "auto_gain": bool(dsp_gain),
        }
        if mic_device:
            cfg_kwargs["device"] = mic_device
        # Voice preset favors speech recognition tuning where the platform
        # offers distinct audio sources; studio keeps the default path.
        try:
            from flet_audio_recorder import AndroidRecorderConfiguration  # type: ignore
            from flet_audio_recorder.types import AndroidAudioSource  # type: ignore

            if mic_preset_ref.current == "voice":
                cfg_kwargs["android_configuration"] = AndroidRecorderConfiguration(
                    audio_source=AndroidAudioSource.VOICE_RECOGNITION
                )
        except Exception:
            pass
        try:
            from flet_audio_recorder import IosRecorderConfiguration  # type: ignore
            from flet_audio_recorder.types import IosAudioCategoryOption  # type: ignore

            cfg_kwargs["ios_configuration"] = IosRecorderConfiguration(
                options=[
                    IosAudioCategoryOption.ALLOW_BLUETOOTH,
                    IosAudioCategoryOption.DEFAULT_TO_SPEAKER,
                ]
            )
        except Exception:
            pass
        try:
            cfg = AudioRecorderConfiguration(**cfg_kwargs)
        except TypeError:
            # Older plugin builds may not accept newer kwargs — retry bare.
            cfg = AudioRecorderConfiguration(
                encoder=enc, channels=ch, sample_rate=rate, bit_rate=bit_rate
            )
        # The recorder's Dart side resolves output_path against its own app-local
        # recordings directory. Feeding it our absolute sandbox path produced
        # `<assets>/data/user/0/.../cache/rec_….wav` and an ENOENT crash. Give it
        # a bare filename and use whatever path it returns in _finish_mic.
        # Unique per take: two recordings in one second shared one Dart-side
        # path and the second overwrote the first.
        recording_name = unique_temp_name("rec", f".{ext}")
        out_path = str(get_temp_dir() / recording_name)
        mic_out_ref.current = out_path
        try:
            started = await rec.start_recording(output_path=recording_name, configuration=cfg)
        except Exception as exc:
            logger.exception("Mic start failed")
            rec.on_stream = None
            show_snack(page, f"Recording failed: {exc}", bgcolor=ERROR)
            return
        if not started:
            rec.on_stream = None
            show_snack(page, "Recorder refused to start", bgcolor=ERROR)
            return
        try:
            # start_recording can report success while the native side refused
            # (mic held by a call, OEM policy).
            if not await rec.is_recording():
                rec.on_stream = None
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
        if not _kind_gate(tool, captured_info.kind):
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
        page.run_task(_resume_preview_safe)

    def _set_mode(m: str) -> None:
        if recording or busy:
            return
        set_mode(m)
        if m == "mic":
            page.run_task(_load_mic_devices)

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
            height=300 if preview_aspect is None else None,
            aspect_ratio=preview_aspect,
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
                    ft.Text(
                        f"Recording {elapsed_str} — tap Stop to keep the take"
                        if recording
                        else "Tap Record, speak, then Stop — the file lands below.",
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
    # Photo/Video buttons stay disabled until the camera is both created AND
    # initialized — tapping mid-mount used to crash with "Control must be
    # added to the page first" on the phone (19:02:14 device log).
    cam_live = camera_ready and camera_inited_ref.current
    controls: list[ft.Control] = []
    if not captured_path:
        if mode in ("photo", "video"):
            # Camera extras — every control hides when the hardware says no.
            extras: list[ft.Control] = [
                ft.IconButton(
                    icon=ft.Icons.FLASHLIGHT_ON_ROUNDED
                    if not torch_on
                    else ft.Icons.FLASHLIGHT_OFF_ROUNDED,
                    tooltip="Torch on" if not torch_on else "Torch off",
                    on_click=lambda _: page.run_task(_toggle_torch),
                ),
                ft.IconButton(
                    icon=ft.Icons.CAMERASWITCH_ROUNDED,
                    tooltip="Front/back lens",
                    on_click=lambda _: page.run_task(_flip_lens),
                ),
            ]
            if zoom_range is not None:
                lo, hi = zoom_range
                extras.append(
                    ft.Slider(
                        value=float(min(max(zoom_level, lo), hi)),
                        min=float(lo),
                        max=float(hi),
                        expand=True,
                        tooltip="Zoom",
                        on_change=lambda e: page.run_task(_apply_zoom, float(e.control.value)),
                    )
                )
            controls.append(ft.Row(controls=extras, spacing=SPACE_SM))
            controls.append(
                ft.Row(
                    controls=[
                        *[
                            ft.Chip(
                                label=ft.Text(label),
                                selected=cam_quality == key,
                                on_click=lambda _, k=key: (
                                    set_cam_quality(k),
                                    page.run_task(_reconfigure_for_quality),
                                ),
                            )
                            for key, label in (
                                ("HIGH", "HD"),
                                ("MEDIUM", "SD"),
                                ("LOW", "Low"),
                            )
                        ],
                        ft.Chip(
                            label=ft.Text("Lock rotation" if not lock_orientation else "Locked"),
                            selected=lock_orientation,
                            on_click=lambda _: set_lock_orientation(not lock_orientation),
                            tooltip="Lock capture orientation during video",
                        ),
                    ],
                    wrap=True,
                    spacing=SPACE_SM,
                )
            )
        if mode == "photo":
            controls.append(
                ft.FilledButton(
                    "Take Photo" if not busy else "Capturing…",
                    icon=ft.Icons.PHOTO_CAMERA_ROUNDED,
                    height=48,
                    expand=True,
                    disabled=busy or recording or not cam_live,
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
                        disabled=busy or not cam_live,
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
                            ft.Chip(
                                label=ft.Text("FLAC"),
                                selected=mic_codec == "flac",
                                on_select=lambda _: set_mic_codec("flac"),
                            ),
                        ],
                        wrap=True,
                        spacing=SPACE_SM,
                    )
                )
                # DSP is best-effort (OEMs may ignore) — chips, never gates.
                controls.append(
                    ft.Row(
                        controls=[
                            ft.Chip(
                                label=ft.Text("Denoise"),
                                selected=dsp_noise,
                                on_select=lambda _: set_dsp_noise(not dsp_noise),
                                tooltip="Suppress background noise (device-dependent)",
                            ),
                            ft.Chip(
                                label=ft.Text("No echo"),
                                selected=dsp_echo,
                                on_select=lambda _: set_dsp_echo(not dsp_echo),
                                tooltip="Cancel echo (device-dependent)",
                            ),
                            ft.Chip(
                                label=ft.Text("Auto gain"),
                                selected=dsp_gain,
                                on_select=lambda _: set_dsp_gain(not dsp_gain),
                                tooltip="Auto level (device-dependent)",
                            ),
                        ],
                        wrap=True,
                        spacing=SPACE_SM,
                    )
                )
                # Input devices (multi-mic phones; default when empty).
                if mic_devices:
                    controls.append(
                        ft.Row(
                            controls=[
                                ft.Chip(
                                    label=ft.Text("Default mic"),
                                    selected=mic_device is None,
                                    on_select=lambda _: set_mic_device(None),
                                ),
                                *[
                                    ft.Chip(
                                        label=ft.Text(label),
                                        selected=mic_device == dev_id,
                                        on_select=lambda _, d=dev_id: set_mic_device(d),
                                    )
                                    for dev_id, label in mic_devices
                                ],
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


__all__ = ["CaptureScreen", "_can_capture", "next_permission_action"]
