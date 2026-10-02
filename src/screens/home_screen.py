"""Home dashboard screen featuring quick actions grid and recent tasks."""

from __future__ import annotations

import flet as ft

from components.banner_ad import BannerAdView
from components.empty_state import empty_state_view
from components.job_card import job_card_view
from core.state import use_app_state
from core.styles import card_container, section_header
from core.theme import (
    ACCENT_AMBER,
    ACCENT_BLUE,
    ACCENT_CYAN,
    ACCENT_PURPLE,
    ACCENT_RED,
    PRIMARY,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
    is_dark_mode,
)
from core.tokens import (
    FONT_MD,
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
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
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
            "Loudness presets & resample",
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
            "capture",
            "Capture",
            "Photo, video & mic into tools",
            ft.Icons.CAMERA_ALT_ROUNDED,
            ACCENT_RED,
        ),
        (
            "streams",
            "Streams",
            "Record live HTTP/HLS streams",
            ft.Icons.CELL_TOWER_ROUNDED,
            ACCENT_CYAN,
        ),
        (
            "join",
            "Join",
            "Merge clips end-to-end",
            ft.Icons.MERGE_TYPE_ROUNDED,
            ACCENT_AMBER,
        ),
        (
            "engine_info",
            "Engine Info",
            "Capability status (probed live)",
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

    # Tool grid — single adaptive ResponsiveRow, not chunked fixed rows.
    # col={"xs":12,"sm":6,"md":4,"lg":3,"xl":2} flows 1-2-3-4-6 columns by
    # 12/span math (never 5) as the window widens; phone shows 1-2.
    # The prior 3-per-row chunking forced "3" on every width and inserted
    # banners as row separators.
    tool_controls = [
        ft.Container(
            content=_build_tool_tile(k, n, d, ic, col),
            col={"xs": 12, "sm": 6, "md": 4, "lg": 3, "xl": 2},
        )
        for k, n, d, ic, col in tools
    ]
    # Home banner: one slot between tools and recent jobs.
    grid_rows: list[ft.Control] = [
        ft.ResponsiveRow(
            controls=tool_controls,
            spacing=SPACE_MD,
            run_spacing=SPACE_MD,
        )
    ]

    # Recent items list
    recent_items = app_state.history[:3] if app_state.history else []
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

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            # Tools Section
            section_header("Studio Tools", "Select an operation to pick a file", is_dark=is_dark),
            *grid_rows,
            # Banner Ad Slot immediately above Recent Jobs (house placement).
            BannerAdView(slot="home-recent"),
            # Recent Activity
            section_header(
                "Recent Jobs",
                subtitle="Past conversions and exports",
                action=ft.TextButton("View All", on_click=lambda _: ctrl.select_tab(1))
                if app_state.history
                else None,
                is_dark=is_dark,
            ),
            ft.Column(controls=recent_controls, spacing=SPACE_MD),
            # Nav-bar clearance INSIDE the scroll: without this the last card
            # sits under the NavigationBar on gesture-nav phones.
            ft.Container(height=88),
        ],
        spacing=SPACE_LG,
        expand=True,
    )
