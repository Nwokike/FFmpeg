"""App theme and color definitions for FFmpeg.

Brand primary is FFmpeg green (#3C8038), constant across light and dark modes.
Surfaces shift from clean Kiri white (#FAFAFA) to deep Kiri slate (#0F1114).
"""

from __future__ import annotations

import flet as ft

from core.constants import KIRI_DARK_2, KIRI_DARK_BG, KIRI_LIGHT_BG, PRIMARY, PRIMARY_DARK

# Accent and status palette
PRIMARY_LIGHT = "#5BA656"
PRIMARY_CONTAINER_DARK = "#1E3E1C"
PRIMARY_CONTAINER_LIGHT = "#E2F4E0"

ACCENT_BLUE = "#3B82F6"
ACCENT_AMBER = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_CYAN = "#06B6D4"
ACCENT_PURPLE = "#8B5CF6"

TEXT_MUTED_DARK = "#8A92A0"
TEXT_MUTED_LIGHT = "#6B7280"
BORDER_DARK = "#272C35"
BORDER_LIGHT = "#E5E7EB"


class AppTheme:
    """Produces Flet 1.0 M3 Themes for light and dark modes."""

    @staticmethod
    def get_light_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme_seed=PRIMARY,
            use_material3=True,
            font_family="sans-serif",
            color_scheme=ft.ColorScheme(
                primary=PRIMARY,
                on_primary="#FFFFFF",
                primary_container=PRIMARY_CONTAINER_LIGHT,
                on_primary_container=PRIMARY_DARK,
                surface=KIRI_LIGHT_BG,
                on_surface="#111827",
                surface_container="#F3F4F6",
                surface_container_high="#E5E7EB",
                surface_container_highest="#D1D5DB",
                outline=BORDER_LIGHT,
                error=ACCENT_RED,
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                bgcolor="#FFFFFF",
                indicator_color=PRIMARY_CONTAINER_LIGHT,
            ),
        )

    @staticmethod
    def get_dark_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme_seed=PRIMARY,
            use_material3=True,
            font_family="sans-serif",
            color_scheme=ft.ColorScheme(
                primary=PRIMARY,
                on_primary="#FFFFFF",
                primary_container=PRIMARY_CONTAINER_DARK,
                on_primary_container="#A8E0A5",
                surface=KIRI_DARK_BG,
                on_surface="#F3F4F6",
                surface_container=KIRI_DARK_2,
                surface_container_high="#242930",
                surface_container_highest="#2D333D",
                outline=BORDER_DARK,
                error=ACCENT_RED,
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                bgcolor=KIRI_DARK_BG,
                indicator_color=PRIMARY_CONTAINER_DARK,
            ),
        )


def is_dark_mode(page: ft.Page) -> bool:
    """Return True if the active presentation mode is dark."""
    if page.theme_mode == ft.ThemeMode.DARK:
        return True
    if page.theme_mode == ft.ThemeMode.LIGHT:
        return False
    # When SYSTEM, inspect host platform brightness
    return page.platform_brightness == ft.Brightness.DARK
