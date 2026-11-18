"""Home dashboard: the studio front door.

Layout follows the modern media-app pattern: one hero import action, a source
row (files / camera / mic / stream), tools grouped by intent instead of one
endless alphabetical grid, then recent jobs. The grouped grid keeps the single
adaptive ResponsiveRow per group (1-2-3-4-6 columns by width).
"""

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
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    ICON_LG,
    ICON_MD,
    RADIUS_LG,
    RADIUS_MD,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from state.controller_ctx import use_controller

# (key, name, description, icon, colour) — grouped by intent, not alphabet.
_TOOL_GROUPS: list[tuple[str, list[tuple[str, str, str, ft.IconData, str]]]] = [
    (
        "Create",
        [
            (
                "convert",
                "Convert",
                "Container & codec transcode",
                ft.Icons.TRANSFORM_ROUNDED,
                PRIMARY,
            ),
            (
                "compress",
                "Compress",
                "Target size for chat apps",
                ft.Icons.COMPRESS_ROUNDED,
                ACCENT_BLUE,
            ),
            (
                "cut",
                "Cut & Trim",
                "Lossless or frame-accurate",
                ft.Icons.CONTENT_CUT_ROUNDED,
                ACCENT_AMBER,
            ),
            ("join", "Join", "Merge clips end-to-end", ft.Icons.MERGE_TYPE_ROUNDED, ACCENT_AMBER),
        ],
    ),
    (
        "Shape",
        [
            (
                "filters",
                "Filters",
                "Crop, rotate, colour, text",
                ft.Icons.TUNE_ROUNDED,
                ACCENT_PURPLE,
            ),
            (
                "audio",
                "Audio Studio",
                "Loudness, fades, resample",
                ft.Icons.GRAPHIC_EQ_ROUNDED,
                PRIMARY,
            ),
        ],
    ),
    (
        "Analyze",
        [
            (
                "extract",
                "Extract",
                "Audio, frames, GIFs, subs",
                ft.Icons.FILE_DOWNLOAD_OUTLINED,
                ACCENT_CYAN,
            ),
            (
                "probe",
                "Dossier",
                "Streams, chapters, metadata",
                ft.Icons.ANALYTICS_OUTLINED,
                ACCENT_BLUE,
            ),
            (
                "engine_info",
                "Engine",
                "Live capability report",
                ft.Icons.INFO_OUTLINE_ROUNDED,
                ACCENT_BLUE,
            ),
        ],
    ),
    (
        "Capture",
        [
            (
                "capture",
                "Camera & Mic",
                "Photo, video and voice",
                ft.Icons.CAMERA_ALT_ROUNDED,
                ACCENT_RED,
            ),
            (
                "streams",
                "Streams",
                "Record HTTP / HLS live",
                ft.Icons.CELL_TOWER_ROUNDED,
                ACCENT_CYAN,
            ),
        ],
    ),
]
_NEEDS_MEDIA = {"convert", "compress", "cut", "extract", "filters", "audio", "probe"}


@ft.component
def HomeScreen() -> ft.Control:
    """Dashboard presenting the studio tools, recent jobs and engine status."""
    page = ft.context.page
    ctrl = use_controller()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    def _open(key: str) -> None:
        if key in _NEEDS_MEDIA:
            ctrl.pick_media_for(key)
        else:
            ctrl.navigate(key)

    def _tile(key: str, name: str, desc: str, icon: ft.IconData, color: str) -> ft.Control:
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
            on_click=lambda _, k=key: _open(k),
            is_dark=is_dark,
        )

    def _hero() -> ft.Control:
        """One primary import action — the first thing a media app offers."""
        probe = app_state.probe_info
        status = (
            "Engine probed and ready" if probe is not None else "Probing this build's encoders…"
        )
        hero = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED, size=44, color=PRIMARY),
                    ft.Text("Choose media to begin", size=FONT_LG, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Video, audio, stills or an image sequence — every tool opens from here.",
                        size=FONT_SM,
                        color=muted,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.FilledButton(
                        "Choose file",
                        icon=ft.Icons.FOLDER_OPEN,
                        height=44,
                        on_click=lambda _: ctrl.pick_media_for("convert"),
                    ),
                ],
                spacing=SPACE_SM,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=SPACE_LG,
            border_radius=RADIUS_LG,
            bgcolor=f"{PRIMARY}18",
            border=ft.Border.all(1, f"{PRIMARY}55"),
            on_click=lambda _: ctrl.pick_media_for("convert"),
            ink=True,
        )
        sources = ft.Row(
            controls=[
                _source("Files", ft.Icons.FOLDER_OPEN, lambda: ctrl.pick_media_for("convert")),
                _source("Camera", ft.Icons.CAMERA_ALT_ROUNDED, lambda: ctrl.navigate("capture")),
                _source("Mic", ft.Icons.MIC_ROUNDED, lambda: ctrl.navigate("capture")),
                _source("Stream", ft.Icons.CELL_TOWER_ROUNDED, lambda: ctrl.navigate("streams")),
            ],
            spacing=SPACE_LG,
            scroll=ft.ScrollMode.AUTO,
        )
        return ft.Column(
            controls=[hero, sources, ft.Text(status, size=FONT_XS, color=muted)],
            spacing=SPACE_SM,
        )

    def _source(label: str, icon: ft.IconData, on_click) -> ft.Control:
        return ft.Column(
            controls=[
                ft.IconButton(
                    icon=icon, icon_size=ICON_MD, tooltip=label, on_click=lambda _e: on_click()
                ),
                ft.Text(label, size=FONT_XS, color=muted),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    group_blocks: list[ft.Control] = []
    for group_name, tools in _TOOL_GROUPS:
        group_blocks.append(
            ft.ResponsiveRow(
                controls=[
                    ft.Container(content=_tile(*tool), col={"xs": 12, "sm": 6, "md": 4, "lg": 3})
                    for tool in tools
                ],
                spacing=SPACE_MD,
                run_spacing=SPACE_MD,
            )
        )
        # The group title sits directly above its grid.
        group_blocks.insert(
            len(group_blocks) - 1,
            ft.Text(group_name, size=FONT_SM, weight=ft.FontWeight.W_600, color=muted),
        )

    recent_items = app_state.history[:3] if app_state.history else []
    recent_controls = (
        [job_card_view(j, is_dark=is_dark) for j in recent_items]
        if recent_items
        else [
            empty_state_view(
                icon=ft.Icons.AUTO_AWESOME_MOTION_OUTLINED,
                title="No recent jobs",
                subtitle="Pick a file above — your exports and conversions land here.",
                is_dark=is_dark,
            )
        ]
    )

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            _hero(),
            section_header("Tools", "Grouped by what you want to do", is_dark=is_dark),
            *group_blocks,
            BannerAdView(slot="home-recent"),
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
