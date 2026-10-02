"""Persistent top banner showing active background job progress across all screens."""

from __future__ import annotations

import math
from pathlib import Path

import flet as ft

from core.constants import op_title
from core.state import Job, use_app_state
from core.theme import ACCENT_RED, PRIMARY
from core.tokens import FONT_SM, FONT_XS, ICON_SM, RADIUS_MD, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller
from state.service_ctx import use_services


def _clamped_pct(progress: float | None) -> int:
    """Share the bar's clamp: text and bar can never disagree (NaN-safe)."""
    try:
        pct = float(progress or 0.0)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(pct):
        return 0
    return int(max(0.0, min(pct, 1.0)) * 100)


@ft.component
def jobs_banner_view(active_job: Job | None, is_dark: bool = True) -> ft.Control:
    """Renders a compact progress bar strip when a job is actively processing in the background.

    Tapping the strip (or the queued count) jumps to the Jobs tab — this is
    the only job UI visible on tool screens, so it must not be a dead end.
    """
    app_state = use_app_state()
    ctrl = use_controller()
    services = use_services()
    if not active_job or not active_job.is_running:
        return ft.Container(height=0, width=0, visible=False)

    queue = getattr(services, "queue", None)
    paused = bool(
        queue is not None
        and getattr(queue, "is_job_paused", None) is not None
        and queue.is_job_paused(active_job.id)
    )
    if queue is None:
        paused = (active_job.status_message or "") == "Paused"

    params = active_job.params or {}
    if active_job.op == "concat":
        paths = params.get("paths") or [active_job.input_path]
        name = f"Join {len(paths)} clips" if len(paths) > 1 else Path(paths[0]).name
    elif active_job.op == "record":
        stream_url = params.get("url") or active_job.input_path or ""
        host = stream_url.split("://", 1)[-1].split("/", 1)[0]
        name = host or "Live stream"
    else:
        name = Path(active_job.input_path).name if active_job.input_path else "Media file"
    pct = _clamped_pct(active_job.progress)
    has_total = not (active_job.op == "record" and params.get("duration_s") is None)
    queued = max(0, len(app_state.jobs) - 1)

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.ProgressRing(width=16, height=16, stroke_width=2, color=PRIMARY),
                                ft.Text(
                                    ("Paused — " if paused else "Processing ")
                                    + f"{op_title(active_job.op)}: {name}",
                                    size=FONT_SM,
                                    weight=ft.FontWeight.W_600,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                    tooltip=f"{op_title(active_job.op)}: {name}",
                                ),
                            ],
                            spacing=SPACE_SM,
                            expand=True,
                            on_click=lambda _: ctrl.select_tab(1),
                        ),
                        *(
                            [
                                ft.TextButton(
                                    f"+{queued} queued",
                                    on_click=lambda _: ctrl.select_tab(1),
                                )
                            ]
                            if queued
                            else []
                        ),
                        ft.Text(
                            "REC" if not has_total else f"{pct}%",
                            size=FONT_XS,
                            weight=ft.FontWeight.BOLD,
                            color=ACCENT_RED if not has_total else PRIMARY,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.PAUSE_ROUNDED
                            if not paused
                            else ft.Icons.PLAY_ARROW_ROUNDED,
                            icon_size=ICON_SM,
                            icon_color=PRIMARY,
                            tooltip="Pause Job" if not paused else "Resume Job",
                            on_click=lambda _: ctrl.toggle_pause_job(active_job.id),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_size=ICON_SM,
                            icon_color=ACCENT_RED,
                            tooltip="Cancel Job",
                            on_click=lambda _: ctrl.cancel_job(active_job.id),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ProgressBar(
                    value=None
                    if not has_total
                    else max(0.0, min(float(active_job.progress or 0.0), 1.0)),
                    color=PRIMARY,
                    bgcolor="#242930" if is_dark else "#E5E7EB",
                ),
            ],
            spacing=4,
            tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=SPACE_MD, vertical=SPACE_SM),
        bgcolor="#1E3E1C" if is_dark else "#E2F4E0",
        border_radius=RADIUS_MD,
        margin=ft.Margin.symmetric(horizontal=SPACE_MD, vertical=4),
        on_click=lambda _: ctrl.select_tab(1),
    )
