"""Engine Info screen — full FFmpeg/PyAV capability report.

Fixes the previously dead "Engine Info" home tile: probe runs off the UI
thread (asyncio.to_thread) and renders as a selectable monospace report with
a refresh action.
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core.engine_probe import probe
from core.state import use_app_state
from core.styles import card_container, section_header
from core.theme import ACCENT_BLUE, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_SM, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller

logger = logging.getLogger(__name__)


@ft.component
def EngineInfoScreen() -> ft.Control:
    """Capability report: codecs, encoders, filters, formats, protocols."""
    page = ft.context.page
    ctrl = use_controller()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    report, set_report = ft.use_state("")
    loading, set_loading = ft.use_state(True)

    def _load_sync() -> str:
        try:
            return probe().to_text()
        except Exception as exc:
            logger.exception("Engine probe failed")
            return f"Engine probe failed: {exc}"

    async def _load() -> None:
        set_loading(True)
        page.update()
        text = await asyncio.to_thread(_load_sync)
        set_report(text)
        set_loading(False)
        page.update()

    ft.use_effect(lambda: page.run_task(_load), [])

    return ft.ListView(
        controls=[
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Engine Info", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            section_header(
                "FFmpeg 8 Capability Status", "Probed live on this device", is_dark=is_dark
            ),
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.ProgressRing(width=20, height=20)
                                if loading
                                else ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED, size=20, color=ACCENT_BLUE
                                ),
                                ft.Text(
                                    "Probing device capabilities..."
                                    if loading
                                    else "Capability report ready",
                                    size=FONT_SM,
                                    color=muted,
                                ),
                            ],
                            spacing=SPACE_SM,
                        ),
                        ft.Text(
                            report or "Waiting for probe result...",
                            size=12,
                            font_family="monospace",
                            selectable=True,
                            visible=bool(report),
                        ),
                    ],
                    spacing=SPACE_MD,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            ft.OutlinedButton(
                "Refresh Probe",
                icon=ft.Icons.REFRESH_ROUNDED,
                on_click=lambda _: page.run_task(_load),
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
