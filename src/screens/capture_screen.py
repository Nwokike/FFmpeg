"""Capture screen — in-app photo/video/mic capture feeding the conversion pipeline.

Mobile/web only (flet-camera's platform guard raises on desktop); desktop shows
a pick-a-file fallback instead. Permission flow is just-in-time: rationale on
first capture attempt, DENIED → retry, PERMANENTLY_DENIED/RESTRICTED → App
Settings deep link (6-status handling per flet-permission-handler).
"""

from __future__ import annotations

import asyncio
import logging
import math
import struct
import time
from pathlib import Path

import flet as ft

from components.empty_state import empty_state_view
from core.notify import ERROR, SUCCESS, show_snack
from core.state import state
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
    except Exception:  # noqa: BLE001 — unknown platform → treat as desktop
        return False


@ft.component
def CaptureScreen() -> ft.Control:
    """Photo / Video / Mic capture with just-in-time permissions and an after-capture hand-off."""
    page = ft.context.page
    ctrl = use_controller()
    services = use_services()
    is_dark = is_dark_mode(page)
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
    ticking_ref = ft.use_ref(False)
    elapsed_ref = ft.use_ref(0)
    chunks_ref = ft.use_ref([])
    chunk_bytes_ref = ft.use_ref(0)
    last_level_ts_ref = ft.use_ref(0.0)
    mic_out_ref = ft.use_ref(None)
    mic_codec_ref = ft.use_ref("pcm16")
    mic_preset_ref = ft.use_ref("studio")

    # ── Unmount: stop the ticker (camera is disposed client-side on unmount) ──

    def _cleanup():
        ticking_ref.current = False

    ft.use_effect(lambda: _cleanup, [])

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
        name = "camera" if perm == Permission.CAMERA else "microphone"
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
            if services.permission_handler:
                page.run_task(services.permission_handler.open_app_settings)

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
        except Exception as exc:  # noqa: BLE001 — degrade with a message
            logger.error("Permission flow failed: %s", exc)
            show_snack(page, "Couldn't request permission — check app settings.", bgcolor=ERROR)
            return False

    # ── Camera lifecycle ────────────────────────────────────────────────────

    def _on_camera_state(e) -> None:
        if getattr(e, "has_error", False):
            show_snack(
                page, f"Camera error: {getattr(e, 'error_description', None) or 'unknown'}",
                bgcolor=ERROR,
            )
        set_recording(bool(getattr(e, "is_recording_video", False)))
        set_rec_paused(bool(getattr(e, "is_recording_paused", False)))

    async def _prepare_camera() -> None:
        if camera_ref.current is not None:
            return
        if not _HAS_CAMERA:
            show_snack(page, "Camera support is not installed", bgcolor=ERROR)
            return
        if not await _permission_ok(Permission.CAMERA):
            return
        try:
            camera_ref.current = ftc.Camera(on_state_change=_on_camera_state)
            set_camera_ready(True)
        except Exception as exc:  # noqa: BLE001
            logger.error("Camera creation failed: %s", exc)
            show_snack(page, f"Camera unavailable: {exc}", bgcolor=ERROR)

    async def _init_camera() -> None:
        cam = camera_ref.current
        if cam is None or camera_inited_ref.current:
            return
        try:
            cameras = await cam.get_available_cameras()
            if not cameras:
                show_snack(page, "No camera found on this device", bgcolor=ERROR)
                return
            await cam.initialize(
                cameras[0], ftc.ResolutionPreset.HIGH, enable_audio=True
            )
            camera_inited_ref.current = True
        except Exception as exc:  # noqa: BLE001
            logger.error("Camera init failed: %s", exc)
            show_snack(page, f"Camera failed to start: {exc}", bgcolor=ERROR)

    def _effect_prepare():
        if mode in ("photo", "video") and camera_ref.current is None and not recording:
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
            pass

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
        except Exception as exc:  # noqa: BLE001 — corrupt/unsupported take
            logger.error("Capture probe failed for %s: %s", path, exc)
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
            show_snack(page, "That capture couldn't be read — try again.", bgcolor=ERROR)
            return
        state.current_media_path = path
        state.current_media_info = info
        set_captured_path(path)
        set_captured_info(info)
        show_snack(page, "Capture ready — pick a tool or save it", bgcolor=SUCCESS)

    # ── Photo ───────────────────────────────────────────────────────────────

    async def _take_photo() -> None:
        cam = camera_ref.current
        if cam is None or busy:
            if cam is None:
                page.run_task(_prepare_camera)
            return
        if not camera_inited_ref.current:
            show_snack(page, "Camera is still starting…")
            return
        set_busy(True)
        try:
            data = await cam.take_picture()
            out = get_temp_dir() / f"photo_{int(time.time())}.jpg"
            out.write_bytes(data)
            await _finalize_capture(str(out))
        except Exception as exc:  # noqa: BLE001
            logger.error("Photo capture failed: %s", exc)
            show_snack(page, f"Photo failed: {exc}", bgcolor=ERROR)
        finally:
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
        except Exception as exc:  # noqa: BLE001
            logger.error("Video capture failed: %s", exc)
            show_snack(page, f"Video failed: {exc}", bgcolor=ERROR)
        finally:
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
        if not camera_inited_ref.current:
            show_snack(page, "Camera is still starting…")
            return
        set_busy(True)
        try:
            await cam.prepare_for_video_recording()
            await cam.start_video_recording()
            set_recording(True)
            _start_ticker()
        except Exception as exc:  # noqa: BLE001
            logger.error("Video record start failed: %s", exc)
            show_snack(page, f"Recording failed: {exc}", bgcolor=ERROR)
            set_recording(False)
        finally:
            set_busy(False)

    async def _pause_video() -> None:
        cam = camera_ref.current
        if cam is None:
            return
        try:
            if rec_paused:
                await cam.resume_video_recording()
            else:
                await cam.pause_video_recording()
        except Exception as exc:  # noqa: BLE001
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
                logger.warning("PCM cap reached (%d bytes) — auto-stopping", chunk_bytes_ref.current)
                page.run_task(_finish_mic)

    def _codec_for(mic_codec_name: str):
        return {
            "pcm16": AudioEncoder.PCM16BITS,
            "opus": AudioEncoder.OPUS,
            "aac": AudioEncoder.AACLC,
        }.get(mic_codec_name, AudioEncoder.PCM16BITS)

    async def _finish_mic() -> None:
        rec = services.audio_recorder
        if rec is None:
            return
        _stop_ticker()
        set_busy(True)
        try:
            codec_name = mic_codec_ref.current
            out_path = mic_out_ref.current
            returned = await rec.stop_recording()
            if codec_name == "pcm16":
                rate, ch = _PCM_RATE_CHANNELS[mic_preset_ref.current]
                _write_wav(out_path, b"".join(chunks_ref.current), rate, ch)
                final = out_path
            else:
                final = returned or out_path
            set_level(0.0)
            if final and Path(final).exists():
                await _finalize_capture(final)
            else:
                show_snack(page, "Recording produced no file", bgcolor=ERROR)
        except Exception as exc:  # noqa: BLE001
            logger.error("Mic stop failed: %s", exc)
            show_snack(page, f"Recording failed: {exc}", bgcolor=ERROR)
        finally:
            chunks_ref.current = []
            chunk_bytes_ref.current = 0
            set_recording(False)
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
        codec_name = mic_codec_ref.current
        enc = _codec_for(codec_name)
        try:
            if not await rec.is_supported_encoder(enc):
                show_snack(page, "Codec unavailable — recording WAV instead")
                codec_name = "pcm16"
                enc = _codec_for("pcm16")
        except Exception:  # noqa: BLE001 — capability query failed → try anyway
            pass

        if codec_name == "pcm16":
            rate, ch = _PCM_RATE_CHANNELS[mic_preset_ref.current]
            ext, bit_rate = "wav", 128000
            rec.on_stream = _on_mic_stream
            chunks_ref.current = []
            chunk_bytes_ref.current = 0
        elif codec_name == "opus":
            rate, ch, ext, bit_rate = 48000, 2, "opus", 96000
            rec.on_stream = None  # streaming forces PCM16 — file mode instead
        else:
            rate, ch, ext, bit_rate = 44100, 2, "m4a", 128000
            rec.on_stream = None

        mic_codec_ref.current = codec_name
        mic_preset_ref.current = pcm_preset
        cfg = AudioRecorderConfiguration(
            encoder=enc, channels=ch, sample_rate=rate, bit_rate=bit_rate
        )
        out_path = str(get_temp_dir() / f"rec_{int(time.time())}.{ext}")
        mic_out_ref.current = out_path
        try:
            started = await rec.start_recording(output_path=out_path, configuration=cfg)
        except Exception as exc:  # noqa: BLE001
            logger.error("Mic start failed: %s", exc)
            show_snack(page, f"Recording failed: {exc}", bgcolor=ERROR)
            return
        if not started:
            show_snack(page, "Recorder refused to start", bgcolor=ERROR)
            return
        set_recording(True)
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
            set_rec_paused(not rec_paused)
        except Exception as exc:  # noqa: BLE001
            show_snack(page, f"Pause failed: {exc}", bgcolor=ERROR)

    # ── After-capture actions ───────────────────────────────────────────────

    def _use_in(tool: str) -> None:
        if not captured_path or captured_info is None:
            return
        state.current_media_path = captured_path
        state.current_media_info = captured_info
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
                        value=level if recording else 0.0,
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
                                on_select=lambda _: (set_mic_codec("pcm16"), set_pcm_preset("studio")),
                            ),
                            ft.Chip(
                                label=ft.Text("Voice WAV 16k"),
                                selected=mic_codec == "pcm16" and pcm_preset == "voice",
                                on_select=lambda _: (set_mic_codec("pcm16"), set_pcm_preset("voice")),
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
                        [ft.Text(elapsed_str, size=FONT_MD, weight=ft.FontWeight.BOLD, color=ACCENT_RED)]
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


__all__ = ["CaptureScreen", "next_permission_action", "_write_wav", "_pcm_rms", "_can_capture"]
