"""FFmpeg — on-device media studio. Main application controller & entrypoint."""

from __future__ import annotations

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
from core.state import Job, state
from core.theme import AppTheme
from services.ad_service import AdService
from services.engine_service import EngineService
from services.media_io import MediaIOService
from services.storage_service import StorageService
from services.update_service import UpdateService
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx
from state.service_ctx import ServiceCtx, Services

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

    services = Services(
        storage=storage,
        engine=engine,
        media_io=media_io,
        ads=ads,
        update=update_svc,
    )

    # Active cancel event tracker per job
    active_cancel_events: dict[str, threading.Event] = {}

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
    def navigate(view: str) -> None:
        state.active_view = view
        page.update()

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
                info = engine.probe(path)
                state.current_media_path = path
                state.current_media_info = info
                state.active_view = target_view
                page.update()
            except Exception as exc:
                logger.error("Media probe failed: %s", exc)
                page.show_dialog(
                    ft.AlertDialog(
                        title=ft.Text("Media Error"),
                        content=ft.Text(f"Could not inspect media file: {exc}"),
                        actions=[ft.TextButton("OK", on_click=lambda _: page.pop_dialog())],
                    )
                )

    def start_job(job: Job) -> None:
        state.jobs.insert(0, job)
        state.active_job = job
        state.active_view = "dashboard"
        page.update()

        cancel_evt = threading.Event()
        active_cancel_events[job.id] = cancel_evt

        def _worker():
            job.status = "running"
            job.status_message = "Starting..."

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
                        on_progress=_on_progress,
                        cancel_event=cancel_evt,
                    )
                elif job.op == "extract_frames":
                    engine.extract_frames(
                        input_path=job.input_path,
                        output_dir=job.output_path,
                        count=p.get("count", 5),
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

            except Exception as exc:
                job.status = "cancelled" if cancel_evt.is_set() else "failed"
                job.error_message = str(exc)
                job.status_message = "Cancelled" if cancel_evt.is_set() else f"Failed: {exc}"
                logger.error("Job %s execution failed: %s", job.id, exc)

            finally:
                active_cancel_events.pop(job.id, None)
                state.active_job = None
                state.last_completed_job = job
                state.history.insert(0, job)
                _persist_history()

                # Notify UI and navigate to result if successful
                async def _on_done():
                    if job.status == "completed":
                        await ads.show_interstitial()
                        state.active_view = "result"
                    page.update()

                page.run_task(_on_done)

        page.run_thread(_worker)

    def cancel_job(job_id: str) -> None:
        evt = active_cancel_events.get(job_id)
        if evt:
            evt.set()
        if state.active_job and state.active_job.id == job_id:
            state.active_job.status_message = "Cancelling..."
            page.update()

    def delete_job(job_id: str) -> None:
        state.history = [j for j in state.history if j.id != job_id]
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
                page.show_dialog(
                    ft.AlertDialog(
                        title=ft.Text("Saved Successfully"),
                        content=ft.Text(f"File saved to:\n{saved}"),
                        actions=[ft.TextButton("OK", on_click=lambda _: page.pop_dialog())],
                    )
                )

    async def check_update() -> None:
        data = await update_svc.check_for_updates()
        if data:
            state.update_available = True
            state.update_data = data
            page.show_dialog(build_update_dialog(page, data))
        else:
            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text("Up to Date"),
                    content=ft.Text(f"{APP_NAME} is running the latest version."),
                    actions=[ft.TextButton("OK", on_click=lambda _: page.pop_dialog())],
                )
            )
        page.update()

    def show_update_dialog() -> None:
        page.show_dialog(build_update_dialog(page, state.update_data))

    methods = ControllerMethods(
        navigate=navigate,
        select_tab=select_tab,
        pick_media_for=lambda t: page.run_task(pick_media_for, t),
        start_job=start_job,
        cancel_job=cancel_job,
        delete_job=delete_job,
        retry_job=start_job,
        finish_onboarding=finish_onboarding,
        share_result=lambda j: page.run_task(share_result, j),
        save_result=lambda j: page.run_task(save_result, j),
        clear_history=clear_history,
        check_update=lambda: page.run_task(check_update),
        show_update_dialog=show_update_dialog,
    )

    # Wire lifecycle
    page.on_view_pop = lambda _: navigate("dashboard")
    page.on_disconnect = lambda _: storage.flush()

    # Background tasks
    page.run_task(ads.gather_consent)
    page.run_task(ads.preload_interstitial)

    async def _silent_update_check():
        data = await update_svc.check_for_updates()
        if data:
            state.update_available = True
            state.update_data = data
            page.update()

    page.run_task(_silent_update_check)

    # Mount UI
    page.render(
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
