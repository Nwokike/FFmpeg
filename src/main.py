"""FFmpeg — on-device media studio. Main application controller & entrypoint."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import threading
import time
import uuid
from pathlib import Path
from queue import Empty, Full, Queue

import flet as ft

from app_shell import ACTIVE_VIEWS, AppShell
from components.update_dialog import build_update_dialog
from core.constants import APP_NAME, APP_VERSION
from core.engine_probe import probe as engine_probe
from core.logger_handler import MemoryLogHandler
from core.notify import ERROR, SUCCESS, show_snack
from core.state import AppStateCtx, Job, state
from core.storage_paths import format_bytes, prune_temp_outputs_keep
from core.theme import AppTheme
from services.ad_service import AdService
from services.engine_service import (
    EngineCapabilityError,
    EngineService,
    friendly_job_error,
    set_pause_event,
)
from services.job_queue import JobQueue
from services.media_io import MediaIOService
from services.storage_service import StorageService
from services.update_service import UpdateService, close_client
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx
from state.service_ctx import ServiceCtx, Services

try:
    from flet_audio_recorder import AudioRecorder

    _HAS_RECORDER = True
except ImportError:  # pragma: no cover — package is in the dev tree
    _HAS_RECORDER = False

try:
    from flet_permission_handler import PermissionHandler

    _HAS_PERM_HANDLER = True
except ImportError:  # pragma: no cover
    _HAS_PERM_HANDLER = False

logger = logging.getLogger(__name__)

# Bump when the terms text changes — every user is re-prompted on next boot.
TERMS_VERSION = "1"

# The mounted ControllerMethods instance (set once AppShell mounts). Lets
# main-level helpers drive the single-view branch swap even before/around the
# shell (Sherlock pattern: navigate-then-work, controller-owned closures).
_show_view_box: list = [None]


def _select_tab(page: ft.Page, tab_idx: int) -> None:
    """Select a dashboard tab inside the single-view shell."""
    state.selected_tab = tab_idx
    state.active_view = "dashboard"
    # If AppShell's show_view setter is already mounted, drive it directly.
    setter = _show_view_box[0]
    if setter is not None:
        setter("dashboard")
    page.update()


def _bootstrap_logging() -> MemoryLogHandler:
    """Attach terminal + file + memory handlers — never clobber the host's.

    ``basicConfig(force=True)`` used to wipe any handler the Flet runner had
    installed (Sherlock never forces — that is why its logs show). Root runs at
    DEBUG so nothing is hidden; chatty client libraries are hushed instead.
    """
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    ):
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(fmt)
        root.addHandler(stream)

    mem = next((h for h in root.handlers if isinstance(h, MemoryLogHandler)), None)
    if mem is None:
        mem = MemoryLogHandler()
        mem.setFormatter(fmt)
        root.addHandler(mem)

    # File tier: DEBUG survives packaged GUI builds that have no console at all.
    try:
        from core.storage_paths import get_data_dir

        log_path = get_data_dir() / "logs" / "app.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not any(
            isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")) == log_path
            for h in root.handlers
        ):
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)
    except OSError as exc:
        root.warning("File log handler unavailable: %s", exc)

    logging.captureWarnings(True)
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # Root stays DEBUG so our own debugs are visible; the framework's
    # protocol/transport dumps would bury them, so those sit at INFO.
    for calm in ("flet", "flet_transport", "flet_controls", "flet_cli", "asyncio"):
        logging.getLogger(calm).setLevel(logging.INFO)

    return mem


def _crash_hook() -> None:
    """Route every uncaught failure class into the log.

    Only main-thread sync raises were visible before; ``page.run_task``
    coroutines, worker threads, and GC-time unraisables all vanished silently.
    """

    def _hook(exc_type, exc, tb):
        logger.critical("Uncaught fatal exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    def _thread_hook(args):
        logger.error(
            "Thread %r crashed",
            args.thread.name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    def _unraisable_hook(args):
        logger.error(
            "Unraisable exception in %r",
            args.object,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _hook
    threading.excepthook = _thread_hook
    sys.unraisablehook = _unraisable_hook


def _install_loop_handler() -> None:
    """Catch failures inside ``page.run_task`` coroutines (no excepthook covers them)."""

    def _loop_hook(loop, context):
        exc = context.get("exception")
        logger.error(
            "Unhandled exception in task: %s",
            context.get("message", context),
            exc_info=exc if exc is not None else None,
        )

    try:
        asyncio.get_running_loop().set_exception_handler(_loop_hook)
    except RuntimeError:
        logger.debug("No running loop yet — asyncio handler deferred")


# Install at import time: flet run imports this module long before main() runs,
# and packaged GUI builds have no console — visibility cannot wait for main().
_bootstrap_logging()
_crash_hook()


async def main(page: ft.Page) -> None:
    """Initialize app controller, restore state, and mount reactive component tree."""
    _install_loop_handler()
    logger.info(
        "Starting %s v%s — terminal, file and in-app logging active",
        APP_NAME,
        APP_VERSION,
    )

    # Global error handler — logs every Flet framework exception and tells the
    # user where to find it (previously log-only: frozen UI with no feedback).
    # Throttled: each snack triggers a page update, and a page update
    # re-serializes the control that errored — without a cooldown one bad
    # property turns into a self-sustaining error storm (the SafeArea
    # bool→double incident: ~50 errors/second).
    _last_error_snack = 0.0

    def _on_global_error(e):
        nonlocal _last_error_snack
        logger.error("Unhandled Flet error: %s", e)
        now = time.monotonic()
        if now - _last_error_snack < 10.0:
            return
        _last_error_snack = now
        show_snack(
            page,
            "Something went wrong — see Settings → Activity Terminal.",
            bgcolor=ERROR,
            duration_ms=5000,
        )

    page.on_error = _on_global_error

    def _on_brightness_change(_=None):
        # SYSTEM-mode re-theme: platform brightness moved (e.g. OS sunset
        # schedule) — bump the observable so headers/tints refresh at once.
        state.theme_revision += 1
        page.update()

    page.on_platform_brightness_change = _on_brightness_change

    page.title = APP_NAME
    # Deterministic desktop presentation; mobile clients ignore these values.
    page.window.width = 1280
    page.window.height = 800
    page.window.min_width = 960
    page.window.min_height = 640
    page.theme = AppTheme.get_light_theme()
    page.dark_theme = AppTheme.get_dark_theme()
    page.padding = 0

    # Instantiate core services
    storage = StorageService()
    engine = EngineService()
    media_io = MediaIOService(page)
    ads = AdService(page)
    update_svc = UpdateService()

    # Flet 1.0 has no page.launch_url/page.set_clipboard — these services must be
    # registered in page.services before any launch/clipboard call (GC + transport).
    url_launcher = ft.UrlLauncher()
    clipboard = ft.Clipboard()
    if url_launcher not in page.services:
        page.services.append(url_launcher)
    if clipboard not in page.services:
        page.services.append(clipboard)

    # Screen stays awake during encodes; connectivity drives the offline banner
    # (both were dead before: no wakelock at all, is_online hardcoded True).
    wakelock = ft.Wakelock()
    connectivity = ft.Connectivity()
    page.services.append(wakelock)
    page.services.append(connectivity)

    async def _refresh_online() -> None:
        try:
            states = await connectivity.get_connectivity()
            from flet import ConnectivityType

            online = any(s is not ConnectivityType.NONE for s in states)
        except Exception as exc:
            logger.warning("Connectivity query failed: %s", exc)
            return
        if online != state.is_online:
            state.is_online = online
            page.update()

    def _on_connectivity_change(_e) -> None:
        page.run_task(_refresh_online)

    connectivity.on_change = _on_connectivity_change

    async def _set_wakelock(on: bool) -> None:
        try:
            if on:
                await wakelock.enable()
            else:
                await wakelock.disable()
        except Exception as exc:
            logger.warning("Wakelock %s failed: %s", on, exc)

    # PermissionHandler's platform guard allows Android/TV/iOS/Windows/Web but
    # RAISES on Linux/macOS desktops — only register where it can update.
    permission_handler = None
    _perm_platforms = (
        ft.PagePlatform.ANDROID,
        ft.PagePlatform.ANDROID_TV,
        ft.PagePlatform.IOS,
        ft.PagePlatform.WINDOWS,
    )
    if _HAS_PERM_HANDLER and (
        page.web or (page.platform is not None and page.platform in _perm_platforms)
    ):
        try:
            permission_handler = PermissionHandler()
            page.services.append(permission_handler)
        except Exception as exc:
            logger.warning("PermissionHandler unavailable: %s", exc)
            permission_handler = None

    audio_recorder = None
    if _HAS_RECORDER:
        try:
            audio_recorder = AudioRecorder()
            page.services.append(audio_recorder)
        except Exception as exc:
            logger.warning("AudioRecorder unavailable: %s", exc)

    services = Services(
        storage=storage,
        engine=engine,
        media_io=media_io,
        ads=ads,
        update=update_svc,
        url_launcher=url_launcher,
        clipboard=clipboard,
        permission_handler=permission_handler,
        audio_recorder=audio_recorder,
    )

    # Restore persisted state from storage
    state.has_accepted_terms = storage.get("terms_accepted") == TERMS_VERSION
    saved_theme = storage.get("theme_mode", "system")
    if saved_theme == "dark":
        page.theme_mode = ft.ThemeMode.DARK
    elif saved_theme == "light":
        page.theme_mode = ft.ThemeMode.LIGHT
    else:
        page.theme_mode = ft.ThemeMode.SYSTEM
    # Seed the observable so headers boot with the restored mode (and any
    # later toggle propagates through the same whole-value path).
    state.theme_mode = page.theme_mode
    state.set_setting("theme_mode", saved_theme)
    state.set_setting("hardware_accel", bool(storage.get("hardware_accel", True)))

    # Restore past jobs history
    saved_history = storage.get("history_jobs", [])
    if isinstance(saved_history, list):
        restored_jobs: list[Job] = [
            Job(
                # `or` defaults, not .get defaults: an explicit JSON null came
                # back as None and detonated Path(None) in History.
                id=d.get("id") or uuid.uuid4().hex[:8],
                op=d.get("op") or "convert",
                input_path=d.get("input_path") or "",
                output_path=d.get("output_path") or "",
                params=d.get("params") or {},
                status=d.get("status") or "completed",
                created_at=d.get("created_at") or 0.0,
                original_size_bytes=d.get("original_size_bytes") or 0,
                output_size_bytes=d.get("output_size_bytes") or 0,
            )
            for d in saved_history
            if isinstance(d, dict)
        ]
        state.history = restored_jobs

    def _persist_history():
        serializable = [
            {
                "id": j.id,
                "op": j.op,
                "input_path": j.input_path,
                "output_path": j.output_path,
                "params": j.params,
                "status": j.status,
                "created_at": j.created_at,
                "original_size_bytes": j.original_size_bytes,
                "output_size_bytes": j.output_size_bytes,
            }
            for j in state.history[:50]
        ]
        storage.set("history_jobs", serializable)

    # Controller Methods implementation
    # Single-view shell: screens keep calling ctrl.navigate(name); the shell
    # branch swaps in place — no Router, no page.views surgery (Sherlock).

    def _swap_view(view: str) -> None:
        state.active_view = view
        live = _show_view_box[0]
        if live is not None:
            live(view)
            return
        show = methods.show_view
        if show is not None:
            show(view)
        else:
            # Shell not mounted yet (early boot): state flip is enough —
            # the first render reads state.active_view.
            page.update()

    def navigate(view: str) -> None:
        leaving_result = state.active_view == "result" and view == "dashboard"
        if view not in ACTIVE_VIEWS:
            logger.error("Navigation target is not registered: %r", view)
            show_snack(page, f"Unknown screen: {view}", bgcolor=ERROR)
            return
        if state.active_view == view:
            # Same branch: the observable write below would be a no-op for the
            # scheduler, so flush explicitly (tab re-tap, re-entry).
            page.update()
            return
        if leaving_result:
            # Natural ad break: on the way OUT of the result screen rather than
            # between completion and its result (Play placement policy).
            #
            # Native InterstitialAd.show() returns as soon as the ad is
            # requested/displayed — dismissal arrives as a separate close
            # event. Swapping after `await show_interstitial()` therefore
            # swapped the branch UNDER the still-open ad. Every skip path in
            # AdService also fires on_close, so passing the swap as the
            # callback covers both the ad-closed and the no-ad cases.
            def _finish_result_exit() -> None:
                _swap_view(view)

            async def _ad_then_nav():
                try:
                    await ads.show_interstitial(on_close=_finish_result_exit)
                except Exception:
                    logger.exception("Interstitial on result-exit failed")
                    _finish_result_exit()

            page.run_task(_ad_then_nav)
        else:
            _swap_view(view)

    def select_tab(tab_idx: int) -> None:
        _select_tab(page, tab_idx)

    def finish_onboarding() -> None:
        state.has_accepted_terms = True
        storage.set("terms_accepted", TERMS_VERSION)
        # Route components subscribe through AppStateCtx; the observable flip
        # replaces the gate without rebuilding page.views (and without losing
        # the Router's back-stack/deep-link state).

    async def _load_path_into(target_view: str, path: str | None) -> None:
        if path is None:
            logger.info("Media pick cancelled or returned nothing")
            return
        try:
            # Sync PyAV probe off the UI loop — large files janked the UI here
            info = await asyncio.to_thread(engine.probe, path)
            state.current_media_path = path
            state.current_media_info = info
            navigate(target_view)
        except Exception as exc:
            logger.exception("Media probe failed")
            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text("Media Error"),
                    content=ft.Text(f"Could not inspect media file: {exc}"),
                    actions=[ft.TextButton("OK", on_click=lambda _: page.pop_dialog())],
                )
            )

    async def _pick_file_for(target_view: str) -> None:
        await _load_path_into(target_view, await media_io.pick_media_file())

    async def pick_media_for(target_view: str) -> None:
        """Offer Files / Camera / Mic instead of only the system picker.

        Capture used to be a dead-end screen; every tool now starts a source
        choice, and a Camera/Mic take returns to this same tool via
        ``state.pending_media_target`` once it has been probed.

        The picker dialog is capability-filtered so a tool that only handles
        video (e.g. Compress) does not offer Microphone — and Compress/Cut
        camera offers Video, not Photo.  Every tile still works, but the
        dialog only shows sources that produce a usable file for the caller.
        """

        # Home tiles route through here; every tool accepts video, so the
        # superset is: audio, convert, compress, cut, extract, filters, probe.
        # Probe/capture/streams/etc. don't use this dialog — they navigate.
        _TOOL_CAPABILITIES: dict[str, dict[str, bool]] = {
            "audio": {"has_video": False, "has_audio": True},
            "extract": {"has_video": True, "has_audio": True},
            "convert": {"has_video": True, "has_audio": True},
            "compress": {"has_video": True, "has_audio": False},
            "cut": {"has_video": True, "has_audio": False},
            "filters": {"has_video": True, "has_audio": False},
            "probe": {"has_video": True, "has_audio": True},
        }
        caps = _TOOL_CAPABILITIES.get(target_view, {"has_video": True, "has_audio": True})

        def _close_and(action) -> None:
            with contextlib.suppress(Exception):
                page.pop_dialog()
            action()

        def _files(_e=None):
            def go():
                page.run_task(_pick_file_for, target_view)

            _close_and(go)

        def _capture(mode: str):
            def go():
                state.pending_media_target = target_view
                state.pending_capture_mode = mode
                navigate("capture")

            _close_and(go)

        # Build only the source options this tool can actually use.
        # compress/cut/filters → video: Camera in video mode (not photo), no mic.
        # audio → audio only: mic, no camera.
        # everything else → all three.
        actions: list[ft.Control] = [
            ft.FilledButton(
                "Upload",
                icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                on_click=_files,
            )
        ]
        if caps.get("has_video"):
            # Compress/Cut/Filters want a video from the camera, not a still photo.
            cam_mode = "video" if target_view in ("compress", "cut", "filters") else "photo"
            actions.append(
                ft.OutlinedButton(
                    "Camera",
                    icon=ft.Icons.CAMERA_ALT_ROUNDED,
                    on_click=lambda _, m=cam_mode: _capture(m),
                )
            )
        if caps.get("has_audio"):
            actions.append(
                ft.OutlinedButton(
                    "Microphone",
                    icon=ft.Icons.MIC_ROUNDED,
                    on_click=lambda _: _capture("mic"),
                )
            )
        actions.append(ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()))

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Choose a source"),
                content=ft.Text("Where should this input come from?"),
                actions=actions,
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    # ── Serial job queue (one encode at a time; ordering + cancel ownership) ──

    async def _refresh_view() -> None:
        # page.run_task REQUIRES a coroutine function (page.py raises TypeError
        # on lambdas/sync fns) — worker-thread progress updates route through here.
        page.update()

    # Observable objects belong to the Flet event loop.  JobQueue runs on a
    # worker thread, so progress is coalesced here and applied inside a
    # coroutine that owns the page context.
    _progress_events: Queue[tuple[Job | None, float, str]] = Queue(maxsize=1)

    def _schedule_ui(coro, *args) -> None:
        try:
            page.run_task(coro, *args)
        except (RuntimeError, AttributeError) as exc:
            logger.debug("UI task skipped after page teardown: %s", exc)

    def _post_progress(job: Job, pct: float, message: str) -> None:
        item = (job, pct, message)
        try:
            _progress_events.put_nowait(item)
        except Full:
            with contextlib.suppress(Empty):
                _progress_events.get_nowait()
            with contextlib.suppress(Full):
                _progress_events.put_nowait(item)

    async def _drain_progress() -> None:
        while True:
            job, pct, message = await asyncio.to_thread(_progress_events.get)
            if job is None:
                return
            job.progress = pct
            job.status_message = message
            # Replacing the list publishes a fresh AppState change and causes
            # subscribed job/banner/history components to rebuild.
            state.jobs = list(state.jobs)
            page.update()

    def _set_worker_field(job: Job, name: str, value) -> None:
        """Mutate a Job from the worker without notifying Flet off-context."""
        object.__setattr__(job, name, value)

    async def _set_active_job(job: Job) -> None:
        state.active_job = job
        state.jobs = list(state.jobs)
        page.update()

    def _on_job_started(job: Job) -> None:
        _schedule_ui(_set_active_job, job)

    def _job_runner(job: Job, cancel_evt: threading.Event) -> None:
        """Execute one job's engine dispatch on the queue worker thread."""
        _set_worker_field(job, "status", "running")
        _set_worker_field(job, "status_message", "Starting...")
        _schedule_ui(_set_wakelock, True)

        def _on_progress(pct: float, msg: str):
            _post_progress(job, pct, msg)

        try:
            p = job.params
            if job.op == "convert":
                engine.convert(
                    input_path=job.input_path,
                    output_path=job.output_path,
                    video_codec=p.get("video_codec", "libx264"),
                    audio_codec=p.get("audio_codec", "aac"),
                    crf=p.get("crf", 23),
                    fps=p.get("fps"),
                    scale_width=p.get("scale_width"),
                    scale_height=p.get("scale_height"),
                    speed=p.get("speed", 1.0),
                    volume_pct=p.get("volume_pct", 100),
                    rotation=p.get("rotation", 0),
                    crop_aspect=p.get("crop"),
                    eq=p.get("eq"),
                    denoise=p.get("denoise"),
                    sharpen=p.get("sharpen"),
                    watermark=p.get("watermark"),
                    hardware_accel=bool(
                        p.get(
                            "hardware_accel",
                            state.settings.get("hardware_accel", True),
                        )
                    ),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )
            elif job.op == "compress":
                engine.compress_to_target(
                    input_path=job.input_path,
                    output_path=job.output_path,
                    target_size_mb=p.get("target_size_mb", 16.0),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )
            elif job.op == "cut":
                engine.cut_trim(
                    input_path=job.input_path,
                    output_path=job.output_path,
                    start_seconds=p.get("start_seconds", 0.0),
                    end_seconds=p.get("end_seconds", 10.0),
                    stream_copy=p.get("stream_copy", True),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )
            elif job.op == "extract_audio":
                engine.extract_audio(
                    input_path=job.input_path,
                    output_path=job.output_path,
                    format_name=p.get("format_name", "mp3"),
                    bitrate_kbps=p.get("bitrate_kbps", 192),
                    target_lufs=p.get("target_lufs"),
                    channels=p.get("channels"),
                    sample_rate=p.get("sample_rate"),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )
            elif job.op == "extract_frames":
                engine.extract_frames(
                    input_path=job.input_path,
                    output_dir=job.output_path,
                    count=p.get("count", 5),
                    format_name=p.get("format_name", "jpg"),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )
            elif job.op == "extract_subtitles":
                engine.extract_subtitles(
                    input_path=job.input_path,
                    output_path=job.output_path,
                    stream_index=p.get("stream_index", 0),
                    format_name=p.get("format_name", "srt"),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )
            elif job.op == "record":
                engine.record(
                    input_url=p.get("url", job.input_path),
                    output_path=job.output_path,
                    container_format=p.get("format"),
                    duration_s=p.get("duration_s"),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )
            elif job.op == "concat":
                engine.concat(
                    paths=p.get("paths", [job.input_path]),
                    output_path=job.output_path,
                    container_format=p.get("container", "mp4"),
                    transition=p.get("transition", "cut"),
                    fade_s=p.get("fade_s", 0.5),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )
            elif job.op == "remux":
                engine.remux(
                    input_path=job.input_path,
                    output_path=job.output_path,
                    drop_indices=p.get("drop", []),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )
            elif job.op == "create_gif":
                engine.create_gif(
                    input_path=job.input_path,
                    output_path=job.output_path,
                    fps=p.get("fps", 15),
                    width=p.get("width", 480),
                    start_s=p.get("start_s", 0.0),
                    duration_s=p.get("duration_s", 5.0),
                    on_progress=_on_progress,
                    cancel_event=cancel_evt,
                )

            _set_worker_field(job, "status", "completed")
            _set_worker_field(job, "progress", 1.0)
            _set_worker_field(job, "status_message", "Completed")
            _set_worker_field(job, "finished_at", time.time())
            out_p = Path(job.output_path)
            if out_p.exists() and out_p.is_file():
                _set_worker_field(job, "output_size_bytes", out_p.stat().st_size)

        except InterruptedError:
            _set_worker_field(job, "status", "cancelled")
            _set_worker_field(job, "status_message", "Cancelled")
            _set_worker_field(job, "finished_at", time.time())
            logger.info("Job %s cancelled", job.id)
        except Exception as exc:
            cancelled = cancel_evt.is_set()
            message = friendly_job_error(exc)
            _set_worker_field(job, "status", "cancelled" if cancelled else "failed")
            _set_worker_field(job, "error_message", message)
            _set_worker_field(
                job,
                "status_message",
                "Cancelled" if cancelled else f"Failed: {message}",
            )
            _set_worker_field(job, "finished_at", time.time())
            if isinstance(exc, EngineCapabilityError):
                # Expected on the LGPL Android wheel — a real failure, but not a
                # crash, so it belongs in the log as context rather than a traceback.
                logger.warning("Job %s needs a capability this build lacks: %s", job.id, message)
            else:
                logger.exception("Job %s execution failed", job.id)
        finally:
            _schedule_ui(_set_wakelock, False)

    async def _finish_job_ui(job: Job) -> None:
        state.active_job = None
        state.last_completed_job = job
        state.jobs = [j for j in state.jobs if j.id != job.id]
        state.history.insert(0, job)
        _persist_history()

        # Notify UI and navigate to result if successful (ad break moved to the
        # result→dashboard exit — never between completion and its own result)
        if job.status == "completed":
            navigate("result")
        elif job.status == "failed":
            show_snack(
                page,
                f"Job failed: {job.error_message or job.op}",
                bgcolor=ERROR,
                duration_ms=5000,
            )
        page.update()

    def _on_job_finished(job: Job) -> None:
        _schedule_ui(_finish_job_ui, job)

    page.run_task(_drain_progress)

    queue = JobQueue(runner=_job_runner, on_started=_on_job_started, on_finished=_on_job_finished)
    # One Event drives both gates: the worker (before the next job) and the
    # engine's per-packet pause hook inside the running one.
    set_pause_event(queue.pause_event)

    def toggle_pause_job() -> None:
        paused = queue.toggle_pause()
        current = queue.current
        if current is not None:
            current.status_message = "Paused" if paused else "Processing…"
        page.update()

    # Jobs whose submission is the monetizable "big action" (matches the
    # Sherlock/DDGS pattern of an interstitial at a heavy search/content
    # boundary rather than on every button). A failed/no-ad call falls straight
    # through to enqueueing, so ads never gate a job behind a cooldown.
    HIGH_VALUE_JOB_OPS = frozenset({"join", "convert", "compress", "cut", "record"})

    def start_job(job: Job) -> None:
        if job.op in HIGH_VALUE_JOB_OPS:

            def _enqueue() -> None:
                state.jobs.insert(0, job)
                queue.enqueue(job)
                navigate("dashboard")

            async def _action_ad() -> None:
                try:
                    await ads.show_interstitial(on_close=_enqueue)
                except Exception:
                    logger.exception("Interstitial on %s submit failed", job.op)
                    _enqueue()

            page.run_task(_action_ad)
            return
        state.jobs.insert(0, job)
        queue.enqueue(job)
        navigate("dashboard")

    def retry_job(job: Job) -> None:
        # Fresh Job (new id/status) so the original history entry stays intact
        clone = Job(
            op=job.op,
            input_path=job.input_path,
            output_path=job.output_path,
            params=dict(job.params),
            original_size_bytes=job.original_size_bytes,
        )
        start_job(clone)

    def cancel_job(job_id: str) -> None:
        if queue.cancel(job_id):
            current = queue.current
            if current and current.id == job_id:
                current.status_message = "Cancelling..."
                page.update()

    def delete_job(job_id: str) -> None:
        state.history = [j for j in state.history if j.id != job_id]
        _persist_history()
        page.update()

    def restore_job(job: Job) -> None:
        """Undo target for the history swipe-delete SnackBar."""
        state.history.insert(0, job)
        _persist_history()
        page.update()

    def clear_history() -> None:
        state.history = []
        _persist_history()
        page.update()

    async def _run_transfer(title: str, operation) -> object | None:
        """Show honest phase/byte progress around a save/share operation."""
        progress_bar = ft.ProgressBar(value=0)
        progress_text = ft.Text("Preparing…", size=12)
        dialog = ft.AlertDialog(
            modal=False,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[progress_text, progress_bar],
                spacing=12,
                tight=True,
            ),
        )
        page.show_dialog(dialog)

        def on_progress(value: float, message: str) -> None:
            progress_bar.value = value
            progress_text.value = message
            page.update()

        try:
            return await operation(on_progress)
        finally:
            popped = page.pop_dialog()
            # If a different dialog (e.g. a concurrent update prompt) is
            # now on top and we just popped it, put it back — the transfer's
            # finally must not steal someone else's dialog.  Identity
            # (``is``) is the right check — two AlertDialogs are never
            # value-equal twins for this purpose.
            if popped is not None and popped is not dialog:
                with contextlib.suppress(Exception):
                    page.show_dialog(popped)

    async def share_result(job: Job) -> None:
        if job.output_path:
            ok = await _run_transfer(
                "Sharing output",
                lambda on_progress: media_io.share_file(job.output_path, on_progress),
            )
            if not ok:
                show_snack(page, "Couldn't open the share sheet", bgcolor=ERROR)

    async def save_result(job: Job) -> None:
        if job.output_path:
            saved = await _run_transfer(
                "Saving output",
                lambda on_progress: media_io.save_media_file(
                    job.output_path, on_progress=on_progress
                ),
            )
            if saved:
                show_snack(page, f"Saved to {saved}", bgcolor=SUCCESS, duration_ms=4000)
            else:
                show_snack(page, "Couldn't save the file — try again.", bgcolor=ERROR)

    async def check_update() -> None:
        data = await update_svc.check_for_updates()
        if data:
            state.update_available = True
            state.update_data = data
            page.show_dialog(build_update_dialog(page, data, url_launcher))
        else:
            show_snack(page, f"{APP_NAME} is running the latest version.")
        page.update()

    def show_update_dialog() -> None:
        page.show_dialog(build_update_dialog(page, state.update_data, url_launcher))

    def toggle_theme() -> None:
        current = page.theme_mode
        if current == ft.ThemeMode.DARK:
            new_mode = ft.ThemeMode.LIGHT
        elif current == ft.ThemeMode.LIGHT:
            new_mode = ft.ThemeMode.SYSTEM
        else:
            new_mode = ft.ThemeMode.DARK
        page.theme_mode = new_mode
        mode_str = {ft.ThemeMode.DARK: "dark", ft.ThemeMode.LIGHT: "light"}.get(new_mode, "system")
        state.set_setting("theme_mode", mode_str)
        # Whole-value observable writes — the dict-item mutation this replaces
        # never published, which is why headers/tints only finished after a
        # screen change. Both paths (this cycle + Settings picker) must do both.
        state.theme_mode = new_mode
        state.theme_revision += 1
        storage.set("theme_mode", mode_str)
        page.update()

    def _system_back_fallback() -> None:
        """Fallback when called before AppShell's live handler is mounted."""
        if not state.has_accepted_terms:
            return
        if state.active_view != "dashboard":
            navigate("dashboard")
        elif state.selected_tab != 0:
            select_tab(0)

    def handle_system_back() -> None:
        """Map Android/system back onto in-app navigation, never app teardown.

        Single-view shell (Sherlock): page.views stays length 1 for the whole
        session, so Dart's own pop handler has nothing to pop — this callback
        (via ``page.on_view_pop``) just swaps the branch. Nothing is ever
        popped, re-keyed, or restored.
        """
        # ``methods.handle_system_back`` is the shell's live, view-local
        # handler once AppShell mounts. If this *is* that handler it was
        # already replaced, so the identity check gates falling through to
        # the early-boot fallback.
        delegate = methods.handle_system_back
        if delegate is not handle_system_back:
            try:
                delegate()
                return
            except Exception:
                logger.exception("Shell system-back handler failed")
        _system_back_fallback()

    def _on_system_back(_e=None) -> None:
        try:
            # Owner: Android/system back must never tear down the single-view
            # shell — it maps to in-app navigation instead.
            try:
                views_left = len(page.views)
            except Exception:
                views_left = -1
            logger.info("System back pressed (root views=%d) → in-app navigation", views_left)
            handle_system_back()
            try:
                if not page.views:
                    logger.error(
                        "System back removed the ROOT view — single-view shell "
                        "violated (flet behavior change?)"
                    )
            except Exception:
                pass
        except Exception:
            logger.exception("System back handling failed")

    methods = ControllerMethods(
        navigate=navigate,
        select_tab=select_tab,
        handle_system_back=lambda: handle_system_back(),
        pick_media_for=lambda t: page.run_task(pick_media_for, t),
        start_job=start_job,
        cancel_job=cancel_job,
        toggle_pause_job=toggle_pause_job,
        retry_job=retry_job,
        delete_job=delete_job,
        restore_job=restore_job,
        finish_onboarding=finish_onboarding,
        share_result=lambda j: page.run_task(share_result, j),
        save_result=lambda j: page.run_task(save_result, j),
        clear_history=clear_history,
        check_update=lambda: page.run_task(check_update),
        show_update_dialog=show_update_dialog,
        toggle_theme=toggle_theme,
    )

    # Wire lifecycle.  Flet tears down the page connection before invoking
    # on_disconnect, so calling page.run_task() from that synchronous callback
    # can raise before the coroutine is ever scheduled.
    async def _shutdown() -> None:
        _post_progress(None, 0.0, "")
        queue.shutdown()
        storage.flush()
        await close_client()

    async def _on_disconnect(_e) -> None:
        await _shutdown()

    async def _on_close(_e) -> None:
        await _shutdown()

    page.on_disconnect = _on_disconnect
    page.on_close = _on_close

    # Background tasks
    page.run_task(_refresh_online)

    async def _ads_boot():
        # Consent MUST settle before the first ad request — two independent
        # tasks let the preloader request ads before UMP answered (EEA first
        # launch = ads served without a consent decision).
        await ads.gather_consent()
        await ads.preload_interstitial()

    page.run_task(_ads_boot)

    async def _silent_update_check():
        data = await update_svc.check_for_updates()
        if data:
            state.update_available = True
            state.update_data = data
            page.update()

    page.run_task(_silent_update_check)

    async def _load_engine_capabilities():
        """Measure the installed wheel off the UI loop and publish it.

        Screens read state.probe_info to decide which codecs/formats to offer.
        Until this lands they show an empty picker rather than a list of
        encoders this build does not ship.
        """
        try:
            state.probe_info = await asyncio.to_thread(engine_probe)
            page.update()
        except Exception as exc:  # cosmetic: tools fall back to their defaults
            logger.warning("Engine capability probe failed: %s", exc)

    page.run_task(_load_engine_capabilities)

    async def _startup_prune():
        """Reclaim the TEMP tier on boot without deleting work the app still needs.

        Every tool writes its output to TEMP and nothing deleted it — a single
        test session reached 2.2 GB. TEMP is documented as throwaway, so files
        older than 24h are removed; the active job's output and the result
        screen's current file are protected so an in-flight or unsaved take
        survives the prune.
        """
        try:
            keep: set[str] = set()
            if state.active_job and state.active_job.output_path:
                keep.add(state.active_job.output_path)
            if state.last_completed_job and state.last_completed_job.output_path:
                keep.add(state.last_completed_job.output_path)
            freed = await asyncio.to_thread(prune_temp_outputs_keep, keep, 24.0)
            if freed:
                logger.info("Startup prune reclaimed %s of stale temp media", format_bytes(freed))
        except Exception as exc:
            logger.warning("Startup temp prune failed: %s", exc)

    page.run_task(_startup_prune)

    # Mount UI — page.render puts the AppShell tree into the single root
    # view's controls (Sherlock: page.render once, branch via state).
    def _mount_ui() -> None:
        """Render the single-view shell once at session boot."""
        page.render(
            lambda: AppStateCtx(
                state,
                lambda: ServiceCtx(
                    services,
                    lambda: ControllerMethodsCtx(
                        methods,
                        lambda: AppShell(),
                    ),
                ),
            )
        )

    _mount_ui()

    # Back-button ownership (KTV lesson, single-view edition): the root view
    # is declared non-poppable, so Android back can never finish the activity
    # through the Dart stack — every press arrives here as view_pop and maps
    # to in-app navigation (tool → dashboard, tab → Home, Home → swallowed).
    # Verified in installed flet 1.0.1: View(can_pop=False) is honored by
    # _handleSystemPopRoute (returns early, emits view_pop via _markViewAsPopped).
    try:
        if page.views:
            page.views[0].can_pop = False
            page.update()
    except Exception as exc:
        logger.warning("Root view can_pop guard failed: %s", exc)
    page.on_view_pop = _on_system_back


if __name__ == "__main__":
    assets_dir = str(Path(__file__).resolve().parent / "assets")
    ft.run(main, assets_dir=assets_dir)
