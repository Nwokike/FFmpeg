"""FFmpeg — on-device media studio. Main application controller & entrypoint."""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from pathlib import Path

import flet as ft

from app_shell import AppShell
from components.update_dialog import build_update_dialog
from core.constants import APP_NAME
from core.logger_handler import MemoryLogHandler
from core.notify import ERROR, SUCCESS, show_snack
from core.state import Job, state
from core.theme import AppTheme
from services.ad_service import AdService
from services.engine_service import EngineService, set_pause_event
from services.job_queue import JobQueue
from services.media_io import MediaIOService
from services.storage_service import StorageService
from services.update_service import UpdateService
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


def _bootstrap_logging() -> MemoryLogHandler:
    handler = MemoryLogHandler()
    logging.basicConfig(
        level=logging.INFO, force=True, format="%(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger().addHandler(handler)
    return handler


def _crash_hook() -> None:
    def _hook(exc_type, exc, tb):
        logger.critical("Uncaught fatal exception: %s", exc)
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


async def main(page: ft.Page) -> None:
    """Initialize app controller, restore state, and mount reactive component tree."""
    _bootstrap_logging()
    _crash_hook()

    # Global error handler — logs every Flet framework exception and tells the
    # user where to find it (previously log-only: frozen UI with no feedback).
    def _on_global_error(e):
        logger.error("Unhandled Flet error: %s", e)
        show_snack(
            page,
            "Something went wrong — see Settings → Activity Terminal.",
            bgcolor=ERROR,
            duration_ms=5000,
        )

    page.on_error = _on_global_error

    page.title = APP_NAME
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
        except Exception as exc:  # noqa: BLE001 — keep last known state on failure
            logger.debug("Connectivity query failed: %s", exc)
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
        except Exception as exc:  # noqa: BLE001 — desktop/web may not support it
            logger.debug("Wakelock %s failed: %s", on, exc)

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
        except Exception as exc:  # noqa: BLE001 — capture degrades without it
            logger.warning("PermissionHandler unavailable: %s", exc)
            permission_handler = None

    audio_recorder = None
    if _HAS_RECORDER:
        try:
            audio_recorder = AudioRecorder()
            page.services.append(audio_recorder)
        except Exception as exc:  # noqa: BLE001
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
    state.has_accepted_terms = storage.get("terms_accepted") == "true"
    saved_theme = storage.get("theme_mode", "system")
    if saved_theme == "dark":
        page.theme_mode = ft.ThemeMode.DARK
    elif saved_theme == "light":
        page.theme_mode = ft.ThemeMode.LIGHT
    else:
        page.theme_mode = ft.ThemeMode.SYSTEM

    # Restore past jobs history
    saved_history = storage.get("history_jobs", [])
    if isinstance(saved_history, list):
        restored_jobs: list[Job] = []
        for d in saved_history:
            if isinstance(d, dict):
                restored_jobs.append(
                    Job(
                        id=d.get("id", ""),
                        op=d.get("op", "convert"),
                        input_path=d.get("input_path", ""),
                        output_path=d.get("output_path", ""),
                        params=d.get("params", {}),
                        status=d.get("status", "completed"),
                        created_at=d.get("created_at", 0.0),
                        original_size_bytes=d.get("original_size_bytes", 0),
                        output_size_bytes=d.get("output_size_bytes", 0),
                    )
                )
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
    # view-name → route map: screens keep calling ctrl.navigate(name) while
    # ft.Router owns the actual view stack (system back, swipe-back, deep links).
    _VIEW_ROUTES = {
        "dashboard": "/",
        "convert": "/convert",
        "compress": "/compress",
        "cut": "/cut",
        "extract": "/extract",
        "filters": "/filters",
        "audio": "/audio",
        "probe": "/probe",
        "engine_info": "/engine-info",
        "result": "/result",
        "capture": "/capture",
        "streams": "/streams",
        "join": "/join",
    }

    def navigate(view: str) -> None:
        leaving_result = state.active_view == "result" and view == "dashboard"
        state.active_view = view
        route = _VIEW_ROUTES.get(view, "/")
        if page.route == route:
            page.update()
            return
        if leaving_result:
            # Natural ad break: on the way OUT of the result screen rather than
            # between completion and its result (Play placement policy). Cooldown,
            # mobile-only, consent and connectivity gates live in show_interstitial.
            async def _ad_then_nav():
                try:
                    await ads.show_interstitial()
                except Exception:
                    logger.exception("Interstitial on result-exit failed")
                if page.route != route:
                    page.navigate(route)
                else:
                    page.update()

            page.run_task(_ad_then_nav)
        else:
            page.navigate(route)

    def select_tab(tab_idx: int) -> None:
        state.selected_tab = tab_idx
        state.active_view = "dashboard"
        page.update()

    def finish_onboarding() -> None:
        state.has_accepted_terms = True
        storage.set("terms_accepted", "true")
        page.update()

    async def pick_media_for(target_view: str) -> None:
        path = await media_io.pick_media_file()
        if path:
            try:
                # Sync PyAV probe off the UI loop — large files janked the UI here
                info = await asyncio.to_thread(engine.probe, path)
                state.current_media_path = path
                state.current_media_info = info
                navigate(target_view)
            except Exception as exc:
                logger.error("Media probe failed: %s", exc)
                page.show_dialog(
                    ft.AlertDialog(
                        title=ft.Text("Media Error"),
                        content=ft.Text(f"Could not inspect media file: {exc}"),
                        actions=[ft.TextButton("OK", on_click=lambda _: page.pop_dialog())],
                    )
                )

    # ── Serial job queue (one encode at a time; ordering + cancel ownership) ──

    def _on_job_started(job: Job) -> None:
        state.active_job = job
        page.run_task(lambda: page.update())

    def _job_runner(job: Job, cancel_evt: threading.Event) -> None:
        """Execute one job's engine dispatch on the queue worker thread."""
        job.status = "running"
        job.status_message = "Starting..."
        page.run_task(_set_wakelock, True)

        def _on_progress(pct: float, msg: str):
            job.progress = pct
            job.status_message = msg
            page.run_task(lambda: page.update())

        try:
            p = job.params
            if job.op == "convert":
                engine.convert(
                    input_path=job.input_path,
                    output_path=job.output_path,
                    video_codec=p.get("video_codec", "libx264"),
                    audio_codec=p.get("audio_codec", "aac"),
                    crf=p.get("crf", 23),
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

            job.status = "completed"
            job.progress = 1.0
            job.status_message = "Completed"
            job.finished_at = time.time()
            out_p = Path(job.output_path)
            if out_p.exists() and out_p.is_file():
                job.output_size_bytes = out_p.stat().st_size

        except InterruptedError:
            job.status = "cancelled"
            job.status_message = "Cancelled"
            job.finished_at = time.time()
            logger.info("Job %s cancelled", job.id)
        except Exception as exc:
            job.status = "cancelled" if cancel_evt.is_set() else "failed"
            job.error_message = str(exc)
            job.status_message = "Cancelled" if cancel_evt.is_set() else f"Failed: {exc}"
            job.finished_at = time.time()
            logger.error("Job %s execution failed: %s", job.id, exc)
        finally:
            page.run_task(_set_wakelock, False)

    def _on_job_finished(job: Job) -> None:
        state.active_job = None
        state.last_completed_job = job
        state.jobs = [j for j in state.jobs if j.id != job.id]
        state.history.insert(0, job)
        _persist_history()

        # Notify UI and navigate to result if successful (ad break moved to the
        # result→dashboard exit — never between completion and its own result)
        async def _on_done():
            if job.status == "completed":
                navigate("result")
            else:
                page.update()

        page.run_task(_on_done)

    queue = JobQueue(
        runner=_job_runner, on_started=_on_job_started, on_finished=_on_job_finished
    )
    # One Event drives both gates: the worker (before the next job) and the
    # engine's per-packet pause hook inside the running one.
    set_pause_event(queue.pause_event)

    def toggle_pause_job() -> None:
        paused = queue.toggle_pause()
        current = queue.current
        if current is not None:
            current.status_message = "Paused" if paused else "Processing…"
        page.update()

    def start_job(job: Job) -> None:
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

    async def share_result(job: Job) -> None:
        if job.output_path:
            await media_io.share_file(job.output_path)

    async def save_result(job: Job) -> None:
        if job.output_path:
            saved = await media_io.save_media_file(job.output_path)
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
            page.theme_mode = ft.ThemeMode.LIGHT
            state.settings["theme_mode"] = "light"
        elif current == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.SYSTEM
            state.settings["theme_mode"] = "system"
        else:
            page.theme_mode = ft.ThemeMode.DARK
            state.settings["theme_mode"] = "dark"
        storage.set("theme_mode", state.settings["theme_mode"])
        page.update()

    methods = ControllerMethods(
        navigate=navigate,
        select_tab=select_tab,
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

    # Wire lifecycle
    def _on_disconnect() -> None:
        queue.shutdown()
        storage.flush()

    page.on_disconnect = _on_disconnect
    page.on_close = lambda _: (queue.shutdown(), storage.flush())

    # Background tasks
    page.run_task(_refresh_online)
    page.run_task(ads.gather_consent)
    page.run_task(ads.preload_interstitial)

    async def _silent_update_check():
        data = await update_svc.check_for_updates()
        if data:
            state.update_available = True
            state.update_data = data
            page.update()

    page.run_task(_silent_update_check)

    # Mount UI — render_views: ft.Router(manage_views=True) emits the ft.View
    # list that becomes page.views (back-stack, swipe-back, deep-link entry).
    page.render_views(
        lambda: ServiceCtx(
            services,
            lambda: ControllerMethodsCtx(
                methods,
                lambda: AppShell(),
            ),
        )
    )


if __name__ == "__main__":
    assets_dir = str(Path(__file__).resolve().parent / "assets")
    ft.run(main, assets_dir=assets_dir)
