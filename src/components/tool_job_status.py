"""Shared live-job row for tool screens — pipeline status while a job runs."""

from __future__ import annotations

import flet as ft

from components.job_card import clamped_progress
from core.constants import op_title
from core.state import Job
from core.tokens import FONT_SM, FONT_XS, SPACE_MD, SPACE_SM
from state.controller_ctx import ControllerMethods


def tool_job_row(job: Job, ctrl: ControllerMethods, *, is_dark: bool = True) -> ft.Control:
    """One live row: op label, determinate bar + clamped %, cancel button.

    Rendered when ``app_state.active_job`` is running. The label names the
    running op, so on the owning screen it reads as "its job" and everywhere
    else as honest pipeline state (never "your convert is at 40%" when the
    running job is a join).
    """
    from core.theme import PRIMARY

    pct = clamped_progress(job.progress)
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.ProgressRing(width=14, height=14, stroke_width=2, color=PRIMARY),
                        ft.Text(
                            f"{op_title(job.op)} running — {int(pct * 100)}%",
                            size=FONT_SM,
                            weight=ft.FontWeight.W_600,
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.STOP_CIRCLE_OUTLINED,
                            icon_color="#EF4444",
                            tooltip="Cancel Job",
                            on_click=lambda _: ctrl.cancel_job(job.id),
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
                ft.ProgressBar(value=pct, color=PRIMARY),
                ft.Text(
                    "A job is already running — Start unlocks when it finishes.",
                    size=FONT_XS,
                    color="#8A92A0" if is_dark else "#6B7280",
                ),
            ],
            spacing=SPACE_SM,
            tight=True,
        ),
        padding=SPACE_MD,
        border_radius=12,
        bgcolor="#1A1D22" if is_dark else "#F3F4F6",
    )


__all__ = ["tool_job_row"]
