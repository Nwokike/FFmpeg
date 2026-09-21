"""Job completion and export view featuring media playback, metrics, and sharing."""

from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from core.state import state
from core.storage_paths import format_bytes
from core.styles import card_container, status_badge
from core.theme import PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import (
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    RADIUS_LG,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from state.controller_ctx import use_controller

try:
    import flet_video as ftv

    _HAS_VIDEO = True
except ImportError:
    _HAS_VIDEO = False


@ft.component
def ResultScreen() -> ft.Control:
    """Finished job presentation with hardware-accelerated preview player and export actions."""
    page = ft.context.page
    ctrl = use_controller()
    is_dark = is_dark_mode(page)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    job = state.last_completed_job or state.active_job

    if not job or not os.path.exists(job.output_path):
        return ft.ListView(
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            on_click=lambda _: ctrl.navigate("dashboard"),
                        ),
                        ft.Text("Job Results", size=FONT_LG, weight=ft.FontWeight.BOLD),
                    ],
                ),
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=48, color=muted),
                            ft.Text(
                                "No Completed Job Active", size=FONT_MD, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text(
                                "Run any conversion or export to view processed media output.",
                                size=FONT_SM,
                                color=muted,
                            ),
                            ft.FilledButton(
                                "Go to Home", on_click=lambda _: ctrl.navigate("dashboard")
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=SPACE_MD,
                    ),
                    padding=SPACE_LG,
                    is_dark=is_dark,
                ),
            ],
            spacing=SPACE_MD,
            expand=True,
        )

    out_path = job.output_path
    out_name = Path(out_path).name

    orig_size = job.original_size_bytes
    out_size = os.path.getsize(out_path) if os.path.exists(out_path) else job.output_size_bytes

    size_saved_str = ""
    if orig_size > 0 and out_size > 0:
        delta = orig_size - out_size
        pct = (delta / orig_size) * 100
        if delta > 0:
            size_saved_str = f"Reduced by {format_bytes(delta)} ({pct:.1f}% smaller)"
        elif delta < 0:
            size_saved_str = f"Increased by {format_bytes(abs(delta))}"

    # Determine preview player based on extension
    is_video = out_path.lower().endswith((".mp4", ".mkv", ".mov", ".webm", ".avi"))
    is_image = out_path.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))

    preview_control: ft.Control
    if is_video and _HAS_VIDEO:
        preview_control = ft.Container(
            content=ftv.Video(
                playlist=[ftv.VideoMedia(out_path)],
                autoplay=False,
                aspect_ratio=16 / 9,
                filter_quality=ft.FilterQuality.MEDIUM,
            ),
            border_radius=RADIUS_LG,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor="#000000",
        )
    elif is_image:
        preview_control = ft.Container(
            content=ft.Image(
                src=out_path,
                fit=ft.BoxFit.CONTAIN,
                height=240,
            ),
            alignment=ft.Alignment.CENTER,
            padding=SPACE_SM,
        )
    else:
        preview_control = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUDIOTRACK_ROUNDED, size=40, color=PRIMARY),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Audio Export Complete", size=FONT_MD, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text(out_name, size=FONT_SM, color=muted),
                        ],
                        spacing=2,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=SPACE_MD,
            ),
            padding=SPACE_LG,
            bgcolor="#1E3E1C" if is_dark else "#E2F4E0",
            border_radius=RADIUS_LG,
        )

    return ft.ListView(
        controls=[
            # Header
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Processing Complete", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Preview Player Card
            preview_control,
            # Result Stats Card
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(
                                    "Output File",
                                    size=FONT_XS,
                                    color=muted,
                                    weight=ft.FontWeight.W_600,
                                ),
                                status_badge("COMPLETED", text_color=PRIMARY),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(
                            out_name,
                            size=FONT_MD,
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Divider(),
                        ft.Row(
                            controls=[
                                ft.Column(
                                    [
                                        ft.Text("ORIGINAL", size=FONT_XS, color=muted),
                                        ft.Text(
                                            format_bytes(orig_size),
                                            size=FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                    ]
                                ),
                                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=muted),
                                ft.Column(
                                    [
                                        ft.Text("FINAL SIZE", size=FONT_XS, color=PRIMARY),
                                        ft.Text(
                                            format_bytes(out_size),
                                            size=FONT_SM,
                                            weight=ft.FontWeight.BOLD,
                                            color=PRIMARY,
                                        ),
                                    ]
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_AROUND,
                        ),
                        *(
                            [
                                ft.Text(
                                    size_saved_str,
                                    size=FONT_SM,
                                    color=PRIMARY,
                                    text_align=ft.TextAlign.CENTER,
                                    weight=ft.FontWeight.W_500,
                                )
                            ]
                            if size_saved_str
                            else []
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
                padding=SPACE_LG,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Actions Row
            ft.Row(
                controls=[
                    ft.FilledButton(
                        "Save to Device",
                        icon=ft.Icons.DOWNLOAD_ROUNDED,
                        height=48,
                        expand=True,
                        on_click=lambda _: ctrl.save_result(job),
                    ),
                    ft.OutlinedButton(
                        "Share",
                        icon=ft.Icons.SHARE_ROUNDED,
                        height=48,
                        expand=True,
                        on_click=lambda _: ctrl.share_result(job),
                    ),
                ],
                spacing=SPACE_MD,
            ),
            ft.TextButton(
                "Return to Dashboard",
                icon=ft.Icons.HOME_ROUNDED,
                on_click=lambda _: ctrl.navigate("dashboard"),
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
