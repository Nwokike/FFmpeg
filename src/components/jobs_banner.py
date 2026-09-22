"""Persistent top banner showing active background job progress across all screens."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from core.state import Job, state
from core.theme import ACCENT_RED, PRIMARY
from core.tokens import FONT_SM, FONT_XS, ICON_SM, RADIUS_MD, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


def jobs_banner_view(active_job: Job | None, is_dark: bool = True) -> ft.Control:
    """Renders a compact progress bar strip when a job is actively processing in the background."""
    if not active_job or not active_job.is_running:
        return ft.Container(height=0, width=0, visible=False)

    ctrl = use_controller()
    name = Path(active_job.input_path).name if active_job.input_path else "Media file"
    pct = int(active_job.progress * 100)
    is_live = active_job.op == "record"  # live streams have no total — animate
    paused = active_job.status_message == "Paused"
    queued = max(0, len(state.jobs) - 1)

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.ProgressRing(width=16, height=16, stroke_width=2, color=PRIMARY),
                                ft.Text(
                                    (
                                        "Paused — " if paused else "Processing "
                                    )
                                    + f"{active_job.op.title()}: {name}",
                                    size=FONT_SM,
                                    weight=ft.FontWeight.W_600,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                            ],
                            spacing=SPACE_SM,
                            expand=True,
                        ),
                        *(
                            [ft.Text(f"+{queued} queued", size=FONT_XS, color=PRIMARY)]
                            if queued
                            else []
                        ),
                        ft.Text(
                            "REC" if is_live else f"{pct}%",
                            size=FONT_XS,
                            weight=ft.FontWeight.BOLD,
                            color=ACCENT_RED if is_live else PRIMARY,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.PAUSE_ROUNDED
                            if not paused
                            else ft.Icons.PLAY_ARROW_ROUNDED,
                            icon_size=ICON_SM,
                            icon_color=PRIMARY,
                            tooltip="Pause Job" if not paused else "Resume Job",
                            on_click=lambda _: ctrl.toggle_pause_job(),
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
                    value=None if is_live else max(0.0, min(active_job.progress, 1.0)),
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
    )
