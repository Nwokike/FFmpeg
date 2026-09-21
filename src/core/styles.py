"""Reusable UI styling components and card helpers."""

from __future__ import annotations

from typing import Any

import flet as ft

from core.theme import (
    BORDER_DARK,
    BORDER_LIGHT,
    KIRI_DARK_2,
    PRIMARY,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
)
from core.tokens import (
    FONT_SM,
    FONT_XL,
    RADIUS_LG,
    RADIUS_SM,
    SPACE_MD,
    SPACE_SM,
)


def card_container(
    content: ft.Control,
    padding: int | ft.Padding = SPACE_MD,
    border_radius: int = RADIUS_LG,
    on_click: Any | None = None,
    is_dark: bool = True,
    border: bool = True,
) -> ft.Container:
    """Build a styled surface container card matching Kiri design language."""
    bg_color = KIRI_DARK_2 if is_dark else "#FFFFFF"
    border_color = BORDER_DARK if is_dark else BORDER_LIGHT
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=border_radius,
        bgcolor=bg_color,
        border=ft.Border.all(1, border_color) if border else None,
        on_click=on_click,
        ink=on_click is not None,
    )


def section_header(
    title: str,
    subtitle: str | None = None,
    action: ft.Control | None = None,
    is_dark: bool = True,
) -> ft.Control:
    """Standard section header with optional subtitle and right action."""
    muted_color = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT
    text_col = ft.Column(
        controls=[
            ft.Text(title, size=FONT_XL, weight=ft.FontWeight.BOLD),
            *([ft.Text(subtitle, size=FONT_SM, color=muted_color)] if subtitle else []),
        ],
        spacing=2,
    )
    if not action:
        return text_col
    return ft.Row(
        controls=[text_col, action],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def status_badge(
    text: str,
    text_color: str = PRIMARY,
    bg_color: str = "#1E3E1C",
    icon: ft.IconData | None = None,
) -> ft.Container:
    """Pill badge for status indicators (e.g. Success, Pending, Codec name)."""
    return ft.Container(
        content=ft.Row(
            controls=[
                *([ft.Icon(icon, size=12, color=text_color)] if icon else []),
                ft.Text(text, size=FONT_SM, color=text_color, weight=ft.FontWeight.W_600),
            ],
            spacing=4,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=4),
        border_radius=RADIUS_SM,
        bgcolor=bg_color,
    )
