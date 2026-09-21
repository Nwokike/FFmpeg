"""Media Dossier inspection screen displaying stream, container, and codec specs."""

from __future__ import annotations

import os

import flet as ft

from core.state import state
from core.storage_paths import format_bytes
from core.styles import card_container, section_header, status_badge
from core.theme import ACCENT_BLUE, PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import (
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    RADIUS_LG,
    RADIUS_MD,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from state.controller_ctx import use_controller


@ft.component
def ProbeScreen() -> ft.Control:
    """Detailed media intelligence dossier showing streams, codecs, and metadata."""
    page = ft.context.page
    ctrl = use_controller()
    is_dark = is_dark_mode(page)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    info = state.current_media_info
    media_path = state.current_media_path

    if not info or not media_path or not os.path.exists(media_path):
        return ft.ListView(
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            on_click=lambda _: ctrl.navigate("dashboard"),
                        ),
                        ft.Text("Media Dossier", size=FONT_LG, weight=ft.FontWeight.BOLD),
                    ],
                ),
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.ANALYTICS_OUTLINED, size=48, color=muted),
                            ft.Text(
                                "No Media File Selected", size=FONT_MD, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text(
                                "Select any video or audio file to inspect its internal streams.",
                                size=FONT_SM,
                                color=muted,
                            ),
                            ft.FilledButton(
                                "Select Media",
                                icon=ft.Icons.FILE_OPEN_ROUNDED,
                                on_click=lambda _: ctrl.pick_media_for("probe"),
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

    file_size_str = format_bytes(info.file_size_bytes)
    dur_str = (
        f"{int(info.duration_s // 60)}m {int(info.duration_s % 60)}s"
        if info.duration_s > 0
        else "Unknown"
    )

    stream_cards: list[ft.Control] = []
    for s in info.streams:
        props: list[ft.Control] = []
        if s.stream_type == "video":
            icon = ft.Icons.VIDEOCAM_OUTLINED
            color = PRIMARY
            props = [
                ft.Text(f"Resolution: {s.width}x{s.height}", size=FONT_SM),
                ft.Text(
                    f"Framerate: {s.fps:.1f} fps" if s.fps else "Framerate: Variable", size=FONT_SM
                ),
                ft.Text(f"Pixel Format: {s.pix_fmt}", size=FONT_SM),
            ]
        elif s.stream_type == "audio":
            icon = ft.Icons.AUDIOTRACK_OUTLINED
            color = ACCENT_BLUE
            props = [
                ft.Text(f"Sample Rate: {s.sample_rate} Hz", size=FONT_SM),
                ft.Text(f"Channels: {s.channels} ({s.channel_layout})", size=FONT_SM),
            ]
        else:
            icon = ft.Icons.SUBTITLES_OUTLINED
            color = muted
            props = [
                ft.Text(f"Language: {s.language or 'Undetermined'}", size=FONT_SM),
            ]

        stream_cards.append(
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=24, color=color),
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            f"Stream #{s.index}: {s.stream_type.upper()}",
                                            size=FONT_SM,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        status_badge(
                                            s.codec_name.upper(),
                                            text_color=color,
                                            bg_color=f"{color}22",
                                        ),
                                    ],
                                    spacing=SPACE_SM,
                                ),
                                *props,
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    spacing=SPACE_MD,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            )
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
                    ft.Text("Media Dossier", size=FONT_LG, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.OutlinedButton("Change", on_click=lambda _: ctrl.pick_media_for("probe")),
                ],
                spacing=SPACE_SM,
            ),
            # General Specs Card
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(
                                    info.file_name,
                                    size=FONT_MD,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                                status_badge(info.format_name.upper(), text_color=PRIMARY),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Row(
                            controls=[
                                ft.Column(
                                    [
                                        ft.Text("SIZE", size=FONT_XS, color=muted),
                                        ft.Text(
                                            file_size_str, size=FONT_SM, weight=ft.FontWeight.W_600
                                        ),
                                    ]
                                ),
                                ft.Column(
                                    [
                                        ft.Text("DURATION", size=FONT_XS, color=muted),
                                        ft.Text(dur_str, size=FONT_SM, weight=ft.FontWeight.W_600),
                                    ]
                                ),
                                ft.Column(
                                    [
                                        ft.Text("BITRATE", size=FONT_XS, color=muted),
                                        ft.Text(
                                            f"{info.bitrate // 1000} kbps",
                                            size=FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                    ]
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=SPACE_MD,
                ),
                padding=SPACE_LG,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Stream specifications
            section_header(
                f"Streams ({len(info.streams)})", "Track-by-track breakdown", is_dark=is_dark
            ),
            ft.Column(controls=stream_cards, spacing=SPACE_SM),
            # Raw FFmpeg Overview
            section_header("Raw Diagnostics", "Direct container summary", is_dark=is_dark),
            card_container(
                content=ft.Text(
                    info.raw_dump, size=FONT_XS, font_family="monospace", selectable=True
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
            # Quick conversion action
            ft.FilledButton(
                "Convert This File",
                icon=ft.Icons.TRANSFORM_ROUNDED,
                height=48,
                on_click=lambda _: ctrl.navigate("convert"),
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
