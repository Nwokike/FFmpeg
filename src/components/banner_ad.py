"""Ad banner slot with responsive fallback."""

from __future__ import annotations

import flet as ft

from core.state import use_app_state
from state.service_ctx import use_services


@ft.component
def BannerAdView(slot: str = "default") -> ft.Control:
    """Render one mobile AdMob banner for ``slot``, collapsing when ineligible.

    Each placement needs its own control — a Flet control cannot be mounted in
    two parents at once — so callers pass a slot key. Reads the observable
    ``ads_ready`` flag so slots appear the moment UMP consent settles instead
    of waiting for an unrelated page update (Sherlock/DGS house pattern).
    """
    app_state = use_app_state()
    services = use_services()
    _ = app_state.ads_ready  # observable read → re-render on consent flip
    if not services.ads:
        return ft.Container(height=0, width=0)

    banner_ctrl = services.ads.get_banner_control(slot)
    if getattr(banner_ctrl, "height", 0) == 0:
        return ft.Container(height=0, width=0)

    # No SPONSORED caption — matches the Sherlock/DGS banner placement, which
    # keeps the native ad clean inside a full-width centered wrapper.
    return ft.Container(
        content=banner_ctrl,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.only(top=4, bottom=4),
    )


__all__ = ["BannerAdView"]
