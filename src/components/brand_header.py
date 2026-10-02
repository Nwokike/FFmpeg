"""Brand header — icon + title | version/update chip, theme cycle, settings gear.

Persistent dashboard chrome with the icon tinted per theme (SRC-IN blend over
the adaptive SVG, same as onboarding), a version chip that flips to an Update
action when the manifest is newer, the 3-way theme cycle, and a gear that
jumps to Settings.
"""

from __future__ import annotations

import flet as ft

from core.assets import app_icon_svg
from core.constants import APP_NAME, APP_VERSION
from core.state import use_app_state
from core.theme import (
    ACCENT_AMBER,
    PRIMARY_DARK,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
    is_dark_mode,
)
from core.tokens import FONT_LG, FONT_XS, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


@ft.component
def BrandHeader() -> ft.Control:
    """Dashboard header: brand left, actions right (all controller-driven)."""
    page = ft.context.page
    ctrl = use_controller()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT
    _ = app_state.update_available  # observable read → chip flips when the check lands

    theme_icon = {
        ft.ThemeMode.DARK: ft.Icons.LIGHT_MODE_ROUNDED,
        ft.ThemeMode.LIGHT: ft.Icons.DARK_MODE_ROUNDED,
        ft.ThemeMode.SYSTEM: ft.Icons.AUTO_MODE_ROUNDED,
    }.get(app_state.theme_mode, ft.Icons.AUTO_MODE_ROUNDED)

    actions: list[ft.Control] = []
    if app_state.update_available:
        actions.append(
            ft.FilledButton(
                "Update",
                height=32,
                tooltip="An update is available",
                style=ft.ButtonStyle(
                    bgcolor=ACCENT_AMBER,
                    color=ft.Colors.BLACK,
                    shape=ft.RoundedRectangleBorder(radius=999),
                ),
                on_click=lambda _: ctrl.show_update_dialog(),
            )
        )
    else:
        actions.append(
            ft.TextButton(
                f"v{APP_VERSION}",
                tooltip="Release notes",
                on_click=lambda _: ctrl.show_update_dialog(),
            )
        )
    actions.append(
        ft.IconButton(
            icon=theme_icon,
            tooltip="Theme: tap to cycle Dark → Light → System",
            on_click=lambda _: ctrl.toggle_theme(),
        )
    )
    actions.append(
        ft.IconButton(
            icon=ft.Icons.SETTINGS_ROUNDED,
            tooltip="Settings",
            on_click=lambda _: ctrl.select_tab(2),
        )
    )

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Image(
                            src=app_icon_svg(),
                            width=34,
                            height=34,
                            fit=ft.BoxFit.CONTAIN,
                            color=ft.Colors.WHITE if is_dark else PRIMARY_DARK,
                            color_blend_mode=ft.BlendMode.SRC_IN,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    APP_NAME,
                                    size=FONT_LG,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text("Mobile Media Studio", size=FONT_XS, color=muted),
                            ],
                            spacing=0,
                        ),
                    ],
                    spacing=SPACE_SM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(expand=True),
                *actions,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACE_SM,
        ),
        padding=ft.Padding.symmetric(horizontal=SPACE_MD, vertical=SPACE_SM),
    )


__all__ = ["BrandHeader"]
