"""Settings screen for theme, storage cache management, diagnostics, and engine status."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core.constants import APP_NAME, APP_VERSION, BUILD_NUMBER, GITHUB_RELEASE_URL
from core.engine_probe import probe
from core.logger_handler import MemoryLogHandler
from core.notify import SUCCESS, show_snack
from core.state import state
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
    SPACE_MD,
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
    is_dark = is_dark_mode(page)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    cache_size, set_cache_size = ft.use_state(get_cache_size_bytes())
    active_theme, set_active_theme = ft.use_state(state.settings.get("theme_mode", "system"))
    engine_counts, set_engine_counts = ft.use_state("")

    async def _load_engine_counts() -> None:
        # Capability probe off the UI loop; counts fill the subtitle live
        # instead of the hardcoded (and rotted) "557 codecs, 468 filters".
        try:
            p = await asyncio.to_thread(probe)
            set_engine_counts(
                f"Inspect {p.codec_count} codecs, {p.filter_count} filters, and formats in PyAV 18"
            )
            page.update()
        except Exception as exc:  # noqa: BLE001 — subtitle is cosmetic
            logger.debug("Engine counts probe failed: %s", exc)

    ft.use_effect(lambda: page.run_task(_load_engine_counts), [])

    def _update_theme(mode_str: str):
        set_active_theme(mode_str)
        state.settings["theme_mode"] = mode_str
        if mode_str == "dark":
            page.theme_mode = ft.ThemeMode.DARK
        elif mode_str == "light":
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.SYSTEM
        page.update()
        if services.storage:
            services.storage.set("theme_mode", mode_str)

    def _do_clear_cache(_):
        freed = clear_cache()
        set_cache_size(get_cache_size_bytes())
        page.update()
        show_snack(
            page, f"Removed {format_bytes(freed)} of temporary files", bgcolor=SUCCESS
        )

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
                        on_click=lambda _: page.run_task(services.clipboard.set, log_text),
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
            except Exception as exc:  # noqa: BLE001 — surface, never crash the click
                logger.error("Engine probe failed: %s", exc)
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

    def _show_ad_privacy(_):
        if services.ads:
            page.run_task(services.ads.show_privacy_options)

    return ft.ListView(
        controls=[
            # Header
            section_header("Settings & Diagnostics", "Application preferences", is_dark=is_dark),
            # Appearance Section
            section_header("Appearance", "Theme preference", is_dark=is_dark),
            card_container(
                content=ft.Row(
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
                            selected={active_theme},
                            segments=[
                                ft.Segment(value="system", label=ft.Text("Auto")),
                                ft.Segment(value="dark", label=ft.Text("Dark")),
                                ft.Segment(value="light", label=ft.Text("Light")),
                            ],
                            on_change=lambda e: _update_theme(list(e.control.selected)[0]),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
            # Storage & Cache Section
            section_header("Storage & Cache", "Temporary processing scratchpad", is_dark=is_dark),
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
                                            f"{format_bytes(cache_size)} used by temporary files",
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
                        ft.Divider(height=1),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.SECURITY_ROUNDED, color=muted),
                            title=ft.Text("Ad Privacy & Consent", weight=ft.FontWeight.W_600),
                            subtitle=ft.Text("Manage Google UMP ad preferences", color=muted),
                            on_click=_show_ad_privacy,
                        ),
                    ],
                    spacing=0,
                ),
                padding=0,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
            # About & Updates
            section_header("About", "Application release details", is_dark=is_dark),
            card_container(
                content=ft.Column(
                    controls=[
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.SYSTEM_UPDATE_ROUNDED, color=PRIMARY),
                            title=ft.Text(
                                f"{APP_NAME} v{APP_VERSION} (Build {BUILD_NUMBER})",
                                weight=ft.FontWeight.W_600,
                            ),
                            subtitle=ft.Text("Tap to check for latest updates", color=muted),
                            on_click=lambda _: ctrl.check_update(),
                        ),
                        ft.Divider(height=1),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.OPEN_IN_BROWSER_ROUNDED, color=muted),
                            title=ft.Text("GitHub Repository", weight=ft.FontWeight.W_600),
                            subtitle=ft.Text("Source code, releases, and discussions", color=muted),
                            on_click=lambda _: page.run_task(
                                services.url_launcher.launch_url, GITHUB_RELEASE_URL
                            ),
                        ),
                    ],
                    spacing=0,
                ),
                padding=0,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
