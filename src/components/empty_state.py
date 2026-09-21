"""Empty state placeholder control for clean zero-data displays."""

from __future__ import annotations

import flet as ft

from core.theme import TEXT_MUTED_DARK, TEXT_MUTED_LIGHT
from core.tokens import FONT_LG, FONT_SM, ICON_HERO, SPACE_MD, SPACE_SM


def empty_state_view(
    icon: ft.IconData,
    title: str,
    subtitle: str,
    action: ft.Control | None = None,
    is_dark: bool = True,
) -> ft.Container:
    """Centered card placeholder with an icon, title, and descriptive subtitle."""
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Icon(icon, size=ICON_HERO, color=muted),
                ft.Text(title, size=FONT_LG, weight=ft.FontWeight.W_600),
                ft.Text(subtitle, size=FONT_SM, color=muted, text_align=ft.TextAlign.CENTER),
                *(
                    [ft.Container(content=action, margin=ft.Margin(0, SPACE_SM, 0, 0))]
                    if action
                    else []
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=SPACE_SM,
        ),
        padding=SPACE_MD,
        alignment=ft.Alignment.CENTER,
    )
