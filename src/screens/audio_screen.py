"""Audio Studio screen for loudness normalization, resampling, and channel mixing."""

from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from core.state import Job, state
from core.storage_paths import format_bytes, get_temp_dir
from core.styles import card_container, section_header
from core.theme import PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


@ft.component
def AudioScreen() -> ft.Control:
    """Audio post-production studio: EBU R128 loudness target presets and acoustic routing."""
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

    lufs_target, set_lufs_target = ft.use_state(-16.0)  # Default: Podcast (-16 LUFS)
    channel_layout, set_channel_layout = ft.use_state("stereo")
    sample_rate, set_sample_rate = ft.use_state(48000)
    audio_format, set_audio_format = ft.use_state("m4a")
    is_processing, set_is_processing = ft.use_state(False)

    lufs_presets = [
        ("youtube", "YouTube / Music (-14 LUFS)", -14.0),
        ("podcast", "Podcast / Vocal (-16 LUFS)", -16.0),
        ("broadcast", "Broadcast EBU R128 (-23 LUFS)", -23.0),
    ]

    rates = [48000, 44100, 32000]

    def _start_audio_studio(_):
        if not media_path:
            return
        set_is_processing(True)

        stem = Path(media_path).stem
        out_name = f"{stem}_mastered.{audio_format}"
        out_path = str(get_temp_dir() / out_name)

        job = Job(
            op="extract_audio",
            input_path=media_path,
            output_path=out_path,
            params={
                "format_name": audio_format,
                "bitrate_kbps": 256,
                "target_lufs": float(lufs_target),
                "channels": 2 if channel_layout == "stereo" else 1,
                "sample_rate": int(sample_rate),
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
                    ft.Text("Audio Studio & Mastering", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Input file overview
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.GRAPHIC_EQ_ROUNDED, size=32, color=PRIMARY),
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
                            "Change", on_click=lambda _: ctrl.pick_media_for("audio")
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Loudness Normalization Presets
            section_header(
                "Loudness Normalization",
                "Standard EBU R128 target integrated loudness",
                is_dark=is_dark,
            ),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(label),
                        selected=abs(lufs_target - val) < 0.1,
                        on_select=lambda _, v=val: set_lufs_target(v),
                    )
                    for _, label, val in lufs_presets
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Channel Routing
            section_header("Channel Routing", "Acoustic layout", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text("Stereo (2 Channels)"),
                        selected=channel_layout == "stereo",
                        on_select=lambda _: set_channel_layout("stereo"),
                    ),
                    ft.Chip(
                        label=ft.Text("Mono (1 Channel)"),
                        selected=channel_layout == "mono",
                        on_select=lambda _: set_channel_layout("mono"),
                    ),
                ],
                spacing=SPACE_SM,
            ),
            # Sample Rate
            section_header("Sample Rate", "Digital frequency", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(f"{r // 1000} kHz"),
                        selected=sample_rate == r,
                        on_select=lambda _, rate=r: set_sample_rate(rate),
                    )
                    for r in rates
                ],
                spacing=SPACE_SM,
            ),
            # Output Format
            section_header("Output Format", "Container / codec target", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(fmt.upper() if fmt != "m4a" else "M4A (AAC)"),
                        selected=audio_format == fmt,
                        on_select=lambda _, f=fmt: set_audio_format(f),
                    )
                    for fmt in ["m4a", "mp3", "aac", "flac", "opus", "wav"]
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Action button
            ft.FilledButton(
                "Process & Master Audio",
                icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                height=48,
                disabled=not media_path or is_processing,
                on_click=_start_audio_studio,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
