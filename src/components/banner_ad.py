"""Ad banner container with responsive fallback."""

from __future__ import annotations

import flet as ft

from state.service_ctx import use_services


@ft.component
def BannerAdView() -> ft.Control:
    """Renders the mobile AdMob banner via Services context, or collapses on desktop."""
    services = use_services()
    if not services.ads:
        return ft.Container(height=0, width=0)

    banner_ctrl = services.ads.get_banner_control()
    if getattr(banner_ctrl, "height", 0) == 0:
        return ft.Container(height=0, width=0)

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("SPONSORED", size=9, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_600),
                banner_ctrl,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
            tight=True,
        ),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.only(top=4, bottom=4),
    )
