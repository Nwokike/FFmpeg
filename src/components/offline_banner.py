"""Offline warning banner strip displayed when device loses network connectivity."""

from __future__ import annotations

import flet as ft

from core.theme import ACCENT_AMBER
from core.tokens import FONT_SM, SPACE_MD, SPACE_SM


def offline_banner_view(is_online: bool) -> ft.Container:
    """Yellow warning banner rendered when offline."""
    if is_online:
        return ft.Container(height=0, width=0, visible=False)

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=16, color="#000000"),
                ft.Text(
                    "You are currently offline. Local media processing works 100% offline.",
                    size=FONT_SM,
                    color="#000000",
                    weight=ft.FontWeight.W_500,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=SPACE_SM,
        ),
        bgcolor=ACCENT_AMBER,
        padding=ft.Padding.symmetric(horizontal=SPACE_MD, vertical=SPACE_SM),
    )
