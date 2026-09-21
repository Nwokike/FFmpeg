"""Home dashboard screen featuring quick actions grid and recent tasks."""

from __future__ import annotations

import flet as ft

from components.banner_ad import BannerAdView
from components.empty_state import empty_state_view
from components.job_card import job_card_view
from core.state import state
from core.styles import card_container, section_header, status_badge
from core.theme import (
    ACCENT_AMBER,
    ACCENT_BLUE,
    ACCENT_CYAN,
    ACCENT_PURPLE,
    PRIMARY,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
    is_dark_mode,
)
from core.tokens import (
    FONT_2XL,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    ICON_LG,
    RADIUS_LG,
    RADIUS_MD,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from state.controller_ctx import use_controller


@ft.component
def HomeScreen() -> ft.Control:
    """Dashboard presenting media tools, recent jobs, and engine status."""
    page = ft.context.page
    ctrl = use_controller()
    is_dark = is_dark_mode(page)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    tools = [
        (
            "convert",
            "Convert",
            "Transcode containers & codecs",
            ft.Icons.TRANSFORM_ROUNDED,
            PRIMARY,
        ),
        (
            "compress",
            "Compress",
            "Shrink for WhatsApp & Email",
            ft.Icons.COMPRESS_ROUNDED,
            ACCENT_BLUE,
        ),
        (
            "cut",
            "Cut & Trim",
            "Lossless or frame-accurate cut",
            ft.Icons.CONTENT_CUT_ROUNDED,
            ACCENT_AMBER,
        ),
        (
            "extract",
            "Extract",
            "Audio, frames, animated GIFs",
            ft.Icons.FILE_DOWNLOAD_OUTLINED,
            ACCENT_CYAN,
        ),
        ("filters", "Filters", "Speed, volume, crop, rotate", ft.Icons.TUNE_ROUNDED, ACCENT_PURPLE),
        (
            "audio",
            "Audio Studio",
            "Loudness EBU R128 & resample",
            ft.Icons.GRAPHIC_EQ_ROUNDED,
            PRIMARY,
        ),
        (
            "probe",
            "Media Dossier",
            "Inspect streams & bitrates",
            ft.Icons.ANALYTICS_OUTLINED,
            ACCENT_BLUE,
        ),
        (
            "engine_info",
            "Engine Info",
            "FFmpeg 8 capability status",
            ft.Icons.INFO_OUTLINE_ROUNDED,
            muted,
        ),
    ]

    def _build_tool_tile(
        key: str, name: str, desc: str, icon: ft.IconData, color: str
    ) -> ft.Control:
        return card_container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, size=ICON_LG, color=color),
                        padding=SPACE_SM,
                        border_radius=RADIUS_MD,
                        bgcolor=f"{color}22",
                    ),
                    ft.Text(name, size=FONT_MD, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        desc,
                        size=FONT_XS,
                        color=muted,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=SPACE_SM,
                tight=True,
            ),
            padding=SPACE_MD,
            border_radius=RADIUS_LG,
            on_click=lambda _, k=key: (
                ctrl.pick_media_for(k)
                if k in ("convert", "compress", "cut", "extract", "filters", "audio", "probe")
                else ctrl.navigate(k)
            ),
            is_dark=is_dark,
        )

    # Tool grid responsive row
    tool_controls = [
        ft.Container(
            content=_build_tool_tile(k, n, d, ic, col),
            col={"sm": 6, "md": 4, "lg": 3},
        )
        for k, n, d, ic, col in tools
    ]

    # Recent items list
    recent_items = state.history[:3] if state.history else []
    recent_controls = (
        [job_card_view(j, is_dark=is_dark) for j in recent_items]
        if recent_items
        else [
            empty_state_view(
                icon=ft.Icons.AUTO_AWESOME_MOTION_OUTLINED,
                title="No Recent Conversions",
                subtitle="Select any tool above to process your first media file.",
                is_dark=is_dark,
            )
        ]
    )

    return ft.ListView(
        controls=[
            # Hero Header
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "FFmpeg Media Studio", size=FONT_2XL, weight=ft.FontWeight.BOLD
                                ),
                                ft.Text(
                                    "On-device processing • 100% private • PyAV & FFmpeg 8",
                                    size=FONT_SM,
                                    color=muted,
                                ),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        status_badge(
                            "ENGINE READY",
                            text_color=PRIMARY,
                            bg_color="#1E3E1C" if is_dark else "#E2F4E0",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_LG,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Tools Section
            section_header("Studio Tools", "Select an operation to pick a file", is_dark=is_dark),
            ft.ResponsiveRow(controls=tool_controls, spacing=SPACE_MD, run_spacing=SPACE_MD),
            # Recent Activity
            section_header(
                "Recent Jobs",
                subtitle="Past conversions and exports",
                action=ft.TextButton("View All", on_click=lambda _: ctrl.select_tab(1))
                if state.history
                else None,
                is_dark=is_dark,
            ),
            ft.Column(controls=recent_controls, spacing=SPACE_MD),
            # Banner Ad Slot
            BannerAdView(),
        ],
        spacing=SPACE_LG,
        expand=True,
    )
