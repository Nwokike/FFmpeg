"""App theme and color definitions for FFmpeg.

Brand primary is FFmpeg green (#3C8038), constant across light and dark modes.
Surfaces shift from clean Kiri white (#FAFAFA) to deep Kiri slate (#0F1114).
"""

from __future__ import annotations

import flet as ft

from core.constants import KIRI_DARK_2, KIRI_DARK_BG, KIRI_LIGHT_BG, PRIMARY, PRIMARY_DARK
from core.state import state

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
            color_scheme=ft.ColorScheme(
                primary=PRIMARY,
                on_primary="#FFFFFF",
                primary_container=PRIMARY_CONTAINER_LIGHT,
                on_primary_container=PRIMARY_DARK,
                secondary="#4F6350",
                on_secondary="#FFFFFF",
                secondary_container="#DDEBDD",
                on_secondary_container="#0B1F0D",
                tertiary="#3C6590",
                on_tertiary="#FFFFFF",
                tertiary_container="#D5E7FF",
                on_tertiary_container="#0B1E33",
                error=ACCENT_RED,
                on_error="#FFFFFF",
                error_container="#FFDAD6",
                on_error_container="#410002",
                surface=KIRI_LIGHT_BG,
                on_surface="#111827",
                on_surface_variant="#424740",
                surface_tint=PRIMARY,
                surface_container_lowest="#FFFFFF",
                surface_container_low="#F7F8F6",
                surface_container="#F3F4F6",
                surface_container_high="#E5E7EB",
                surface_container_highest="#D1D5DB",
                surface_dim="#E1E4DF",
                outline=BORDER_LIGHT,
                outline_variant="#C5CCC3",
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                bgcolor="#FFFFFF",
                indicator_color=PRIMARY_CONTAINER_LIGHT,
                label_text_style=ft.TextStyle(color=TEXT_MUTED_LIGHT, size=12),
            ),
        )

    @staticmethod
    def get_dark_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme_seed=PRIMARY,
            use_material3=True,
            color_scheme=ft.ColorScheme(
                primary="#7BC477",
                on_primary="#0B210C",
                primary_container=PRIMARY_CONTAINER_DARK,
                on_primary_container="#A8E0A5",
                secondary="#B1CCB2",
                on_secondary="#1D351F",
                secondary_container="#334B35",
                on_secondary_container="#CDE8CE",
                tertiary="#A5C9EE",
                on_tertiary="#123352",
                tertiary_container="#294B6B",
                on_tertiary_container="#D5E7FF",
                error="#FFB4AB",
                on_error="#690005",
                error_container="#93000A",
                on_error_container="#FFDAD6",
                surface=KIRI_DARK_BG,
                on_surface="#F3F4F6",
                on_surface_variant="#C1C9BE",
                surface_tint="#7BC477",
                surface_container_lowest="#090B0D",
                surface_container_low="#14171A",
                surface_container=KIRI_DARK_2,
                surface_container_high="#242930",
                surface_container_highest="#2D333D",
                surface_dim="#0F1114",
                outline=BORDER_DARK,
                outline_variant="#424940",
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                bgcolor=KIRI_DARK_BG,
                indicator_color=PRIMARY_CONTAINER_DARK,
                label_text_style=ft.TextStyle(color=TEXT_MUTED_DARK, size=12),
            ),
        )


def is_dark_mode(page: ft.Page | None, app_state=None) -> bool:
    """True when the active presentation mode is dark.

    ``app_state`` is normally supplied by ``use_app_state()`` in a Flet
    component.  Keeping the optional fallback makes this helper usable from
    small non-rendered tests without pretending that a raw singleton read
    creates a subscription.

    Mirrors Sherlock: if the page is unavailable (test stub, early lifecycle),
    fall back through ``ft.context.page`` rather than crashing the whole
    screen build — a None page must never poison history/settings.
    """
    if app_state is None:
        app_state = state
    _ = app_state.theme_revision  # observable read → re-render on theme flip
    if app_state.theme_mode == ft.ThemeMode.DARK:
        return True
    if app_state.theme_mode == ft.ThemeMode.LIGHT:
        return False
    # When SYSTEM, inspect host platform brightness
    resolved = page
    if resolved is None:
        try:
            resolved = ft.context.page  # type: ignore[attr-defined]
        except Exception:
            resolved = None
    if resolved is None:
        return True
    try:
        return resolved.platform_brightness == ft.Brightness.DARK
    except Exception:
        return True
