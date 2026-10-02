"""Ad banner slot — fixed-size AdMob banner that collapses when ineligible."""

from __future__ import annotations

import flet as ft

from core.state import use_app_state
from state.service_ctx import use_services


@ft.component
def BannerAdView(slot: str) -> ft.Control:
    """Render one mobile AdMob banner for ``slot``, collapsing when ineligible.

    Each placement needs its own control — a Flet control cannot be mounted in
    two parents at once — so callers pass an explicit slot key (no default:
    the easy call must not be the double-mount footgun). Subscribes to the
    whole AppState via ``use_app_state()``; the ``ads_ready`` read below is
    documentation, not mechanism — Flet tracks at object granularity, and the
    branch on the flag is what collapses banners the moment UMP consent
    settles or is revoked.
    """
    app_state = use_app_state()
    services = use_services()
    ads = getattr(services, "ads", None)
    get_banner = getattr(ads, "get_banner_control", None)
    if get_banner is None:
        return ft.Container(height=0, width=0, visible=False)

    ready = bool(app_state.ads_ready)
    banner_ctrl = None
    if ready:
        try:
            banner_ctrl = get_banner(slot)
        except Exception:
            banner_ctrl = None
    if banner_ctrl is None or getattr(banner_ctrl, "height", 0) == 0:
        # Ineligible, failed, or consent revoked: collapse to nothing. The
        # height check reads the service's own collapsed-wrapper contract
        # (zero-size Container), not a layout value we own.
        return ft.Container(key=f"banner-{slot}-collapsed", height=0, width=0, visible=False)

    # Centered Row: never set alignment on a wide Container inside a scroll
    # view — it can expand vertically to fill the parent and break Flutter's
    # scroll layout. The Row is explicitly full-width so CENTER is meaningful.
    return ft.Row(
        key=f"banner-{slot}",
        controls=[banner_ctrl],
        alignment=ft.MainAxisAlignment.CENTER,
        tight=False,
    )


__all__ = ["BannerAdView"]
