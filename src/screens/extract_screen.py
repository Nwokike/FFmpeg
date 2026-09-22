"""Media extraction screen for audio tracks, video frames, and animated GIFs."""

from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from core.state import Job, state
from core.storage_paths import format_bytes, get_temp_dir
from core.styles import card_container, section_header
from core.theme import ACCENT_CYAN, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


@ft.component
def ExtractScreen() -> ft.Control:
    """Extraction studio: Audio rip, frame grabber, and palette-optimized GIF maker."""
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
    duration_s = info.duration_s if info else 10.0

    mode, set_mode = ft.use_state("audio")  # "audio", "frames", "gif"
    audio_fmt, set_audio_fmt = ft.use_state("mp3")
    audio_kbps, set_audio_kbps = ft.use_state(192)
    frame_count, set_frame_count = ft.use_state(5)
    gif_fps, set_gif_fps = ft.use_state(15)
    gif_width, set_gif_width = ft.use_state(480)
    gif_duration, set_gif_duration = ft.use_state(min(5.0, duration_s))
    is_processing, set_is_processing = ft.use_state(False)

    def _start_extraction(_):
        if not media_path:
            return
        set_is_processing(True)

        stem = Path(media_path).stem
        if mode == "audio":
            out_name = f"{stem}_audio.{audio_fmt}"
            out_path = str(get_temp_dir() / out_name)
            job = Job(
                op="extract_audio",
                input_path=media_path,
                output_path=out_path,
                params={"format_name": audio_fmt, "bitrate_kbps": int(audio_kbps)},
                original_size_bytes=Path(media_path).stat().st_size
                if os.path.exists(media_path)
                else 0,
            )
        elif mode == "frames":
            out_dir = str(get_temp_dir() / f"{stem}_frames")
            job = Job(
                op="extract_frames",
                input_path=media_path,
                output_path=out_dir,
                params={"count": int(frame_count), "format_name": "jpg"},
                original_size_bytes=Path(media_path).stat().st_size
                if os.path.exists(media_path)
                else 0,
            )
        else:  # gif
            out_name = f"{stem}_animated.gif"
            out_path = str(get_temp_dir() / out_name)
            job = Job(
                op="create_gif",
                input_path=media_path,
                output_path=out_path,
                params={
                    "fps": int(gif_fps),
                    "width": int(gif_width),
                    "start_s": 0.0,
                    "duration_s": float(gif_duration),
                },
                original_size_bytes=Path(media_path).stat().st_size
                if os.path.exists(media_path)
                else 0,
            )

        ctrl.start_job(job)

    # Audio formats
    audio_formats = ["mp3", "aac", "flac", "opus", "wav"]

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
                    ft.Text("Extract Media Tracks", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Input file overview
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.FILE_DOWNLOAD_OUTLINED, size=32, color=ACCENT_CYAN),
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
                                    f"Size: {file_size_str} • {duration_s:.1f}s",
                                    size=FONT_SM,
                                    color=muted,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.OutlinedButton(
                            "Change", on_click=lambda _: ctrl.pick_media_for("extract")
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Mode Switcher Chips
            section_header("Extraction Target", "Choose what to extract", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text("Audio Track"),
                        selected=mode == "audio",
                        on_select=lambda _: set_mode("audio"),
                    ),
                    ft.Chip(
                        label=ft.Text("Video Frames"),
                        selected=mode == "frames",
                        on_select=lambda _: set_mode("frames"),
                    ),
                    ft.Chip(
                        label=ft.Text("Animated GIF"),
                        selected=mode == "gif",
                        on_select=lambda _: set_mode("gif"),
                    ),
                ],
                spacing=SPACE_SM,
            ),
            # Conditional settings based on mode
            *(
                [
                    section_header("Audio Format", "Select target sound format", is_dark=is_dark),
                    ft.Row(
                        controls=[
                            ft.Chip(
                                label=ft.Text(fmt.upper()),
                                selected=audio_fmt == fmt,
                                on_select=lambda _, f=fmt: set_audio_fmt(f),
                            )
                            for fmt in audio_formats
                        ],
                        wrap=True,
                        spacing=SPACE_SM,
                    ),
                    section_header("Audio Bitrate", f"{audio_kbps} kbps", is_dark=is_dark),
                    ft.Slider(
                        value=float(audio_kbps),
                        min=96,
                        max=320,
                        divisions=7,
                        on_change=lambda e: set_audio_kbps(int(e.control.value)),
                    ),
                ]
                if mode == "audio"
                else []
            ),
            *(
                [
                    section_header(
                        "Number of Frames", f"{frame_count} frames across duration", is_dark=is_dark
                    ),
                    ft.Slider(
                        value=float(frame_count),
                        min=1,
                        max=20,
                        divisions=19,
                        on_change=lambda e: set_frame_count(int(e.control.value)),
                    ),
                ]
                if mode == "frames"
                else []
            ),
            *(
                [
                    section_header(
                        "GIF Framerate & Resolution",
                        f"{gif_fps} fps • {gif_width}px wide",
                        is_dark=is_dark,
                    ),
                    ft.Slider(
                        value=float(gif_fps),
                        min=10,
                        max=30,
                        divisions=20,
                        on_change=lambda e: set_gif_fps(int(e.control.value)),
                    ),
                    section_header("GIF Width", f"{gif_width}px wide", is_dark=is_dark),
                    ft.Slider(
                        value=float(gif_width),
                        min=160,
                        max=1080,
                        divisions=23,
                        on_change=lambda e: set_gif_width(int(e.control.value)),
                    ),
                    section_header("GIF Duration", f"{gif_duration:.1f} seconds", is_dark=is_dark),
                    ft.Slider(
                        value=float(gif_duration),
                        min=1.0,
                        max=float(min(15.0, duration_s)),
                        divisions=14,
                        on_change=lambda e: set_gif_duration(round(float(e.control.value), 1)),
                    ),
                ]
                if mode == "gif"
                else []
            ),
            # Action button
            ft.FilledButton(
                f"Extract {mode.title()}",
                icon=ft.Icons.DOWNLOAD_ROUNDED,
                height=48,
                disabled=not media_path or is_processing,
                on_click=_start_extraction,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
