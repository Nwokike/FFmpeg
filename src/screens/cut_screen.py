"""Media trim and cut screen with stream-copy and re-encode modes."""

from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from core.state import Job, state
from core.storage_paths import format_bytes, get_temp_dir
from core.styles import card_container, section_header
from core.theme import ACCENT_AMBER, PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, FONT_XS, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


def _format_time_s(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 10)
    return f"{m:02d}:{s:02d}.{ms}"


@ft.component
def CutScreen() -> ft.Control:
    """Segment trimmer view supporting lossless copy and frame-accurate cutting."""
    page = ft.context.page
    ctrl = use_controller()
    is_dark = is_dark_mode(page)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    media_path = state.current_media_path
    info = state.current_media_info
    file_name = Path(media_path).name if media_path else "No file selected"
    file_size_str = (
        format_bytes(Path(media_path).stat().st_size)
        if media_path and os.path.exists(media_path)
        else "0 B"
    )
    total_dur = max(1.0, info.duration_s if info else 60.0)

    start_s, set_start_s = ft.use_state(0.0)
    end_s, set_end_s = ft.use_state(total_dur)
    stream_copy, set_stream_copy = ft.use_state(True)
    is_processing, set_is_processing = ft.use_state(False)

    cut_duration = max(0.0, end_s - start_s)

    def _set_trim_range(lo: float, hi: float) -> None:
        """RangeSlider handler: keep an ordered, non-empty trim window."""
        a = max(0.0, min(lo, hi))
        b = min(float(total_dur), max(lo, hi))
        if b - a < 0.05:
            return
        set_start_s(a)
        set_end_s(b)

    def _start_cut(_):
        if not media_path or cut_duration <= 0.05:
            return
        set_is_processing(True)

        ext = Path(media_path).suffix or ".mp4"
        out_name = f"{Path(media_path).stem}_trimmed{ext}"
        out_path = str(get_temp_dir() / out_name)

        job = Job(
            op="cut",
            input_path=media_path,
            output_path=out_path,
            params={
                "start_seconds": float(start_s),
                "end_seconds": float(end_s),
                "stream_copy": bool(stream_copy),
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
                    ft.Text("Trim & Cut Segment", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Input file overview
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CONTENT_CUT_ROUNDED, size=32, color=ACCENT_AMBER),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    file_name,
                                    size=FONT_MD,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    f"Total Duration: {_format_time_s(total_dur)} • {file_size_str}",
                                    size=FONT_SM,
                                    color=muted,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.OutlinedButton("Change", on_click=lambda _: ctrl.pick_media_for("cut")),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Trim boundaries display
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "START TIME",
                                    size=FONT_XS,
                                    color=muted,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    _format_time_s(start_s), size=FONT_LG, weight=ft.FontWeight.BOLD
                                ),
                            ],
                            spacing=2,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "CLIP LENGTH",
                                    size=FONT_XS,
                                    color=PRIMARY,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    _format_time_s(cut_duration),
                                    size=FONT_LG,
                                    weight=ft.FontWeight.BOLD,
                                    color=PRIMARY,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=2,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "END TIME",
                                    size=FONT_XS,
                                    color=muted,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    _format_time_s(end_s), size=FONT_LG, weight=ft.FontWeight.BOLD
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            spacing=2,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                is_dark=is_dark,
            ),
            # Trim range — one RangeSlider keeps start <= end by construction
            # (the old interlinked Slider pair misbehaved on sub-second clips)
            section_header(
                "Trim Range",
                f"{_format_time_s(start_s)} → {_format_time_s(end_s)}",
                is_dark=is_dark,
            ),
            ft.RangeSlider(
                min=0.0,
                max=float(max(total_dur, 0.5)),
                start_value=float(start_s),
                end_value=float(end_s),
                divisions=100,
                on_change=lambda e: _set_trim_range(
                    round(float(e.control.start_value), 2),
                    round(float(e.control.end_value), 2),
                ),
            ),
            # Mode toggle
            section_header("Processing Mode", "Cutting method", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text("Stream Copy (Instant Lossless)"),
                        selected=stream_copy,
                        on_select=lambda _: set_stream_copy(True),
                    ),
                    ft.Chip(
                        label=ft.Text("Re-encode (Frame-Accurate)"),
                        selected=not stream_copy,
                        on_select=lambda _: set_stream_copy(False),
                    ),
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Action button
            ft.FilledButton(
                f"Cut Segment ({_format_time_s(cut_duration)})",
                icon=ft.Icons.CONTENT_CUT_ROUNDED,
                height=48,
                disabled=not media_path or is_processing or cut_duration <= 0.05,
                on_click=_start_cut,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
