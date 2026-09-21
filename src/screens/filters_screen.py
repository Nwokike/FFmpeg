"""Video and audio filter stack screen (speed, volume, rotate, flip)."""

from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from core.state import Job, state
from core.storage_paths import format_bytes, get_temp_dir
from core.styles import card_container, section_header
from core.theme import ACCENT_PURPLE, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


@ft.component
def FiltersScreen() -> ft.Control:
    """Filter adjustments: Speed/tempo multiplier, audio gain, and spatial rotation."""
    page = ft.context.page
    ctrl = use_controller()
    is_dark = is_dark_mode(page)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    media_path = state.current_media_path
    file_name = Path(media_path).name if media_path else "No file selected"
    file_size_str = (
        format_bytes(Path(media_path).stat().st_size)
        if media_path and os.path.exists(media_path)
        else "0 B"
    )

    speed_val, set_speed_val = ft.use_state(1.0)
    volume_pct, set_volume_pct = ft.use_state(100)
    rotation_deg, set_rotation_deg = ft.use_state(0)
    is_processing, set_is_processing = ft.use_state(False)

    speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    rotations = [(0, "Normal"), (90, "90° CW"), (180, "180°"), (270, "270° CW")]

    def _start_filters(_):
        if not media_path:
            return
        set_is_processing(True)

        stem = Path(media_path).stem
        ext = Path(media_path).suffix or ".mp4"
        out_name = f"{stem}_filtered{ext}"
        out_path = str(get_temp_dir() / out_name)

        job = Job(
            op="convert",
            input_path=media_path,
            output_path=out_path,
            params={
                "speed": float(speed_val),
                "volume_pct": int(volume_pct),
                "rotation": int(rotation_deg),
            },
            original_size_bytes=Path(media_path).stat().st_size
            if os.path.exists(media_path)
            else 0,
        )
        ctrl.start_job(job)

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
                    ft.Text("Media Filter Stack", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Input file card
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TUNE_ROUNDED, size=32, color=ACCENT_PURPLE),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    file_name,
                                    size=FONT_MD,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(f"Size: {file_size_str}", size=FONT_SM, color=muted),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.OutlinedButton(
                            "Change", on_click=lambda _: ctrl.pick_media_for("filters")
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Speed / Tempo
            section_header("Playback Speed", f"{speed_val}x playback multiplier", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(f"{s}x"),
                        selected=abs(speed_val - s) < 0.05,
                        on_select=lambda _, sp=s: set_speed_val(sp),
                    )
                    for s in speeds
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Volume Boost
            section_header(
                "Audio Volume Boost", f"{volume_pct}% (100% is normal volume)", is_dark=is_dark
            ),
            ft.Slider(
                value=float(volume_pct),
                min=0,
                max=250,
                divisions=25,
                on_change=lambda e: set_volume_pct(int(e.control.value)),
            ),
            # Orientation / Rotate
            section_header("Video Rotation", "Rotate video frame", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(lbl),
                        selected=rotation_deg == deg,
                        on_select=lambda _, d=deg: set_rotation_deg(d),
                    )
                    for deg, lbl in rotations
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Action button
            ft.FilledButton(
                "Apply Filters & Render",
                icon=ft.Icons.AUTO_FIX_HIGH_ROUNDED,
                height=48,
                disabled=not media_path or is_processing,
                on_click=_start_filters,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
