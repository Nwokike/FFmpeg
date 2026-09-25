"""Settings screen for theme, storage cache management, diagnostics, and engine status."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from components.banner_ad import BannerAdView
from core.assets import app_icon_svg
from core.constants import APP_NAME, APP_VERSION, BUILD_NUMBER, GITHUB_RELEASE_URL
from core.engine_probe import probe
from core.logger_handler import MemoryLogHandler
from core.notify import ERROR, SUCCESS, show_snack
from core.state import use_app_state
from core.storage_paths import clear_cache, format_bytes, get_cache_size_bytes
from core.styles import card_container, section_header
from core.theme import (
    ACCENT_AMBER,
    ACCENT_BLUE,
    PRIMARY,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
    is_dark_mode,
)
from core.tokens import (
    FONT_MD,
    FONT_SM,
    FONT_XS,
    RADIUS_MD,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from state.controller_ctx import use_controller
from state.service_ctx import use_services

logger = logging.getLogger(__name__)


@ft.component
def SettingsScreen() -> ft.Control:
    """Preferences, diagnostics terminal, cache cleaner, and engine inspector."""
    page = ft.context.page
    ctrl = use_controller()
    services = use_services()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    cache_size, set_cache_size = ft.use_state(get_cache_size_bytes())
    # Derive this from the subscribed app state instead of caching a second
    # local copy; the header toggle must update this picker immediately.
    active_theme = app_state.settings.get("theme_mode", "system")
    engine_counts, set_engine_counts = ft.use_state("")

    async def _load_engine_counts() -> None:
        # Capability probe off the UI loop; counts fill the subtitle live
        # instead of hardcoded numerals that would rot as the wheel changes.
        try:
            p = await asyncio.to_thread(probe)
            set_engine_counts(
                f"Inspect {p.codec_count} codecs, {p.filter_count} filters, and formats in PyAV 18"
            )
            page.update()
        except Exception as exc:
            logger.warning("Engine counts probe failed: %s", exc)

    ft.use_effect(lambda: page.run_task(_load_engine_counts), [])

    def _update_theme(mode_str: str):
        # Whole-value assignment — a dict-item write would never publish and
        # the header would only re-tint after an unrelated re-render.
        app_state.set_setting("theme_mode", mode_str)
        if mode_str == "dark":
            page.theme_mode = ft.ThemeMode.DARK
        elif mode_str == "light":
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.SYSTEM
        # Mirror main.toggle_theme exactly: publish the observable AND bump the
        # revision, otherwise is_dark_mode's subscription never fires and the
        # whole app keeps the old palette until an unrelated interaction.
        app_state.theme_mode = page.theme_mode
        app_state.theme_revision += 1
        page.update()
        if services.storage:
            services.storage.set("theme_mode", mode_str)

    def _set_hardware_accel(e) -> None:
        enabled = bool(e.control.value)
        app_state.set_setting("hardware_accel", enabled)
        if services.storage:
            services.storage.set("hardware_accel", enabled)
        page.update()

    def _do_clear_cache(_):
        freed = clear_cache()
        set_cache_size(get_cache_size_bytes())
        page.update()
        show_snack(
            page, f"Removed {format_bytes(freed)} of cache & temporary files", bgcolor=SUCCESS
        )

    def _copy_logs(text: str) -> None:
        # services.clipboard defaults to None — tapping Copy without the
        # service raised AttributeError on the None.
        if services.clipboard is None:
            show_snack(page, "Clipboard is unavailable on this platform", bgcolor=ERROR)
            return
        page.run_task(services.clipboard.set, text)

    def _open_link(url: str) -> None:
        # services.url_launcher also defaults to None.
        if services.url_launcher is None:
            show_snack(page, "No browser available to open links", bgcolor=ERROR)
            return
        page.run_task(services.url_launcher.launch_url, url)

    def _open_activity_terminal(_):
        logs = MemoryLogHandler.get_logs()
        log_text = "\n".join(logs[-100:])
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Activity Terminal"),
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                log_text, size=FONT_XS, font_family="monospace", selectable=True
                            ),
                        ],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    width=500,
                    height=350,
                ),
                actions=[
                    ft.TextButton(
                        "Copy",
                        on_click=lambda _: _copy_logs(log_text),
                    ),
                    ft.TextButton("Close", on_click=lambda _: page.pop_dialog()),
                ],
            )
        )

    def _open_engine_inspector(_):
        # Probe off the UI thread (it enumerates every codec/filter on device)
        async def _load():
            try:
                p = await asyncio.to_thread(probe)
            except Exception as exc:
                logger.exception("Engine probe failed")
                show_snack(page, f"Engine probe failed: {exc}")
                return
            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text("FFmpeg Engine Capabilities"),
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    p.to_text(),
                                    size=FONT_XS,
                                    font_family="monospace",
                                    selectable=True,
                                ),
                            ],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        width=500,
                        height=350,
                    ),
                    actions=[
                        ft.TextButton("Close", on_click=lambda _: page.pop_dialog()),
                    ],
                )
            )

        page.run_task(_load)

    def _open_about_update(_):
        ctrl.show_update_dialog()

    about_card = card_container(
        content=ft.Column(
            controls=[
                ft.Image(
                    src=app_icon_svg(),
                    width=64,
                    height=64,
                    fit=ft.BoxFit.CONTAIN,
                    color=ft.Colors.WHITE if is_dark else PRIMARY,
                    color_blend_mode=ft.BlendMode.SRC_IN,
                    semantics_label=f"{APP_NAME} icon",
                ),
                ft.Text(
                    APP_NAME,
                    size=FONT_MD,
                    weight=ft.FontWeight.W_700,
                ),
                ft.Container(
                    content=ft.Text(
                        f"Version {APP_VERSION} (Build {BUILD_NUMBER})",
                        size=FONT_SM,
                        color=muted,
                    ),
                    ink=True,
                    tooltip="Tap to view release notes",
                    on_click=_open_about_update,
                ),
                ft.Text(
                    "On-device media studio powered by FFmpeg 8 via PyAV.",
                    size=FONT_SM,
                    color=muted,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACE_SM,
        ),
        padding=SPACE_LG,
        border_radius=RADIUS_MD,
        is_dark=is_dark,
    )

    return ft.ListView(
        controls=[
            # Header
            section_header("Settings & Diagnostics", "Application preferences", is_dark=is_dark),
            # Appearance Section
            section_header("Appearance", "Theme preference", is_dark=is_dark),
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.DARK_MODE_ROUNDED
                                    if is_dark
                                    else ft.Icons.LIGHT_MODE_ROUNDED,
                                    size=24,
                                    color=PRIMARY,
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "Interface Theme",
                                            size=FONT_MD,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                        ft.Text(
                                            f"Current: {active_theme.title()}",
                                            size=FONT_SM,
                                            color=muted,
                                        ),
                                    ],
                                    spacing=2,
                                ),
                            ],
                            spacing=SPACE_MD,
                        ),
                        ft.SegmentedButton(
                            # Keep the selector on its own row so it remains
                            # comfortable on narrow phones instead of squeezing
                            # the label and control into an overflowing row.
                            selected=[active_theme],
                            segments=[
                                ft.Segment(value="system", label=ft.Text("Auto")),
                                ft.Segment(value="dark", label=ft.Text("Dark")),
                                ft.Segment(value="light", label=ft.Text("Light")),
                            ],
                            show_selected_icon=False,
                            expand=True,
                            on_change=lambda e: _update_theme(
                                next(iter(e.control.selected), active_theme)
                            ),
                        ),
                    ],
                    spacing=SPACE_MD,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
            # Performance
            section_header(
                "Performance", "Use the fastest decoder exposed by this device", is_dark=is_dark
            ),
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.SPEED_ROUNDED, size=24, color=PRIMARY),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "Hardware Decode",
                                            size=FONT_MD,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                        ft.Text(
                                            "Hardware acceleration with software fallback",
                                            size=FONT_SM,
                                            color=muted,
                                        ),
                                    ],
                                    spacing=2,
                                ),
                            ],
                            spacing=SPACE_MD,
                        ),
                        ft.Switch(
                            value=bool(app_state.settings.get("hardware_accel", True)),
                            on_change=_set_hardware_accel,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
            # Storage & Cache Section
            section_header(
                "Storage & Cache", "Cache & temporary files (regenerable)", is_dark=is_dark
            ),
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.CLEANING_SERVICES_ROUNDED, size=24, color=ACCENT_AMBER
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "Scratchpad & Cache",
                                            size=FONT_MD,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                        ft.Text(
                                            f"{format_bytes(cache_size)} in cache & temporary files",
                                            size=FONT_SM,
                                            color=muted,
                                        ),
                                    ],
                                    spacing=2,
                                ),
                            ],
                            spacing=SPACE_MD,
                        ),
                        ft.OutlinedButton(
                            "Clear", icon=ft.Icons.DELETE_SWEEP_ROUNDED, on_click=_do_clear_cache
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
            # UMP is intentionally not a settings row: Sherlock-style consent
            # appears at startup only when the regulated region requires it.
            # Diagnostics & Engine
            section_header("Diagnostics", "Engine and runtime logs", is_dark=is_dark),
            card_container(
                content=ft.Column(
                    controls=[
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=PRIMARY),
                            title=ft.Text("Activity Terminal", weight=ft.FontWeight.W_600),
                            subtitle=ft.Text(
                                "View live in-memory execution logs and errors", color=muted
                            ),
                            on_click=_open_activity_terminal,
                        ),
                        ft.Divider(height=1),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ACCENT_BLUE),
                            title=ft.Text("Engine Capabilities", weight=ft.FontWeight.W_600),
                            subtitle=ft.Text(
                                engine_counts or "Inspect codecs, filters, and formats in PyAV 18",
                                color=muted,
                            ),
                            on_click=_open_engine_inspector,
                        ),
                    ],
                    spacing=0,
                ),
                padding=0,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
            BannerAdView(slot="settings-storage"),
            # About & Updates
            section_header("About", "Application release details", is_dark=is_dark),
            about_card,
            card_container(
                content=ft.ListTile(
                    leading=ft.Icon(ft.Icons.OPEN_IN_BROWSER_ROUNDED, color=PRIMARY),
                    title=ft.Text("GitHub Repository", weight=ft.FontWeight.W_600),
                    subtitle=ft.Text("Source code, releases, and discussions", color=muted),
                    on_click=lambda _: _open_link(GITHUB_RELEASE_URL),
                ),
                padding=0,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
