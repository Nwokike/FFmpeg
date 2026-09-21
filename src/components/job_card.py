"""Job item card for queue, in-progress tasks, and history lists."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from core.state import Job
from core.storage_paths import format_bytes
from core.styles import card_container, status_badge
from core.theme import ACCENT_AMBER, ACCENT_RED, PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT
from core.tokens import FONT_MD, FONT_SM, FONT_XS, ICON_MD, RADIUS_MD, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


def job_card_view(job: Job, is_dark: bool = True) -> ft.Control:
    """Card displaying a media job with real-time progress bar or result metadata."""
    ctrl = use_controller()
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    # Status color resolution
    if job.status == "completed":
        status_color = PRIMARY
        bg_status = "#1E3E1C" if is_dark else "#E2F4E0"
    elif job.status == "running":
        status_color = ACCENT_AMBER
        bg_status = "#3D2E0B" if is_dark else "#FEF3C7"
    elif job.status == "failed":
        status_color = ACCENT_RED
        bg_status = "#3E1C1C" if is_dark else "#FEE2E2"
    else:
        status_color = muted
        bg_status = "#242930" if is_dark else "#E5E7EB"

    op_labels = {
        "convert": "Convert",
        "compress": "Compress",
        "cut": "Trim",
        "extract_audio": "Extract Audio",
        "extract_frames": "Extract Frames",
        "create_gif": "Make GIF",
        "filters": "Filter Stack",
        "audio_studio": "Audio Studio",
    }
    op_title = op_labels.get(job.op, job.op.title())

    in_name = Path(job.input_path).name if job.input_path else "Unknown"
    out_name = Path(job.output_path).name if job.output_path else ""

    # Action buttons
    action_btns: list[ft.Control] = []
    if job.is_running:
        action_btns.append(
            ft.IconButton(
                icon=ft.Icons.STOP_CIRCLE_OUTLINED,
                icon_color=ACCENT_RED,
                icon_size=ICON_MD,
                tooltip="Cancel Job",
                on_click=lambda _: ctrl.cancel_job(job.id),
            )
        )
    elif job.status == "completed":
        action_btns.extend(
            [
                ft.IconButton(
                    icon=ft.Icons.SHARE_OUTLINED,
                    icon_size=ICON_MD,
                    tooltip="Share",
                    on_click=lambda _: ctrl.share_result(job),
                ),
                ft.IconButton(
                    icon=ft.Icons.DOWNLOAD_OUTLINED,
                    icon_size=ICON_MD,
                    tooltip="Save to Device",
                    on_click=lambda _: ctrl.save_result(job),
                ),
            ]
        )

    content_rows = [
        ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.MOVIE_OUTLINED
                            if "audio" not in job.op
                            else ft.Icons.AUDIOTRACK_OUTLINED,
                            size=ICON_MD,
                            color=PRIMARY,
                        ),
                        ft.Text(op_title, size=FONT_MD, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=SPACE_SM,
                    tight=True,
                ),
                ft.Row(
                    controls=[
                        status_badge(
                            job.status.upper(), text_color=status_color, bg_color=bg_status
                        ),
                        *action_btns,
                    ],
                    spacing=SPACE_SM,
                    tight=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        ft.Text(
            f"Input: {in_name}",
            size=FONT_SM,
            color=muted,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    ]

    if job.is_running:
        content_rows.extend(
            [
                ft.ProgressBar(
                    value=max(0.0, min(job.progress, 1.0)), color=PRIMARY, bgcolor=bg_status
                ),
                ft.Row(
                    controls=[
                        ft.Text(job.status_message, size=FONT_XS, color=muted),
                        ft.Text(
                            f"{int(job.progress * 100)}%", size=FONT_XS, weight=ft.FontWeight.W_600
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ]
        )
    elif job.status == "completed":
        size_info = ""
        if job.original_size_bytes > 0 and job.output_size_bytes > 0:
            size_info = (
                f"{format_bytes(job.original_size_bytes)} → {format_bytes(job.output_size_bytes)}"
            )
        content_rows.append(
            ft.Row(
                controls=[
                    ft.Text(
                        f"Output: {out_name}",
                        size=FONT_SM,
                        weight=ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    *(
                        [
                            ft.Text(
                                size_info, size=FONT_XS, color=PRIMARY, weight=ft.FontWeight.W_600
                            )
                        ]
                        if size_info
                        else []
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )
    elif job.status == "failed" and job.error_message:
        content_rows.append(
            ft.Text(
                f"Error: {job.error_message}",
                size=FONT_XS,
                color=ACCENT_RED,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )

    def _card_clicked(_):
        if job.status == "completed":
            from core.state import state

            state.last_completed_job = job
            ctrl.navigate("result")

    return card_container(
        content=ft.Column(controls=content_rows, spacing=SPACE_SM),
        padding=SPACE_MD,
        border_radius=RADIUS_MD,
        on_click=_card_clicked if job.status == "completed" else None,
        is_dark=is_dark,
    )
