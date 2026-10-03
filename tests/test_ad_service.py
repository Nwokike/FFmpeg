"""Ad service lifecycle regressions for Flet service registration and consent."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import services.ad_service as ad_module
from core.state import state
from services.ad_service import AdService


class _Page:
    web = False
    platform = SimpleNamespace(is_mobile=lambda: True)

    def __init__(self):
        self.services = []
        self.updates = 0

    def update(self):
        self.updates += 1


def test_consent_service_is_attached_before_native_call(monkeypatch):
    class Consent:
        async def request_consent_info_update(self):
            return None

        async def load_and_show_consent_form_if_required(self):
            return None

        async def can_request_ads(self):
            return True

    monkeypatch.setattr(ad_module, "_HAS_ADS", True)
    monkeypatch.setattr(ad_module.fta, "ConsentManager", Consent)
    page = _Page()
    service = AdService(page)

    asyncio.run(service.gather_consent())

    assert service._can_request_ads is True
    assert len(page.services) == 1
    assert page.updates >= 1


def test_interstitial_close_handler_is_synced_before_show(monkeypatch):
    class Interstitial:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.on_close = None
            self.shown = False
            kwargs["on_load"](None)

        async def show(self):
            self.shown = True
            return True

    monkeypatch.setattr(ad_module, "_HAS_ADS", True)
    monkeypatch.setattr(ad_module.fta, "InterstitialAd", Interstitial)
    page = _Page()
    service = AdService(page)
    service._can_request_ads = True
    monkeypatch.setattr(state, "is_online", True)

    asyncio.run(service.preload_interstitial())
    assert page.updates >= 1
    assert asyncio.run(service.show_interstitial()) is True
    assert service.interstitial is None


def test_consent_misconfiguration_logs_actionable_error(monkeypatch, caplog):
    """Code-3 / publisher-misconfiguration must log the dashboard fix at error."""
    import logging

    class Consent:
        async def request_consent_info_update(self):
            raise RuntimeError(
                "Consent info update failed (3): Publisher misconfiguration: "
                "Failed to read publisher's account configuration; no form(s) "
                "configured for the input app ID."
            )

        async def load_and_show_consent_form_if_required(self):
            return None  # pragma: no cover

        async def can_request_ads(self):
            return False  # pragma: no cover

    monkeypatch.setattr(ad_module, "_HAS_ADS", True)
    monkeypatch.setattr(ad_module.fta, "ConsentManager", Consent)
    page = _Page()
    service = AdService(page)

    with caplog.at_level(logging.ERROR, logger="AdService"):
        asyncio.run(service.gather_consent())

    assert service._can_request_ads is False
    assert any("UMP form" in r.message or "consent form" in r.message for r in caplog.records), (
        "misconfiguration must name the AdMob UMP-form fix"
    )


def test_privacy_revoke_publishes_ads_ready(monkeypatch):
    """Withdrawing consent must collapse banners now, not on a later render."""

    class Consent:
        def __init__(self):
            self.granted = True

        async def get_privacy_options_requirement_status(self):
            return ad_module.fta.PrivacyOptionsRequirementStatus.REQUIRED

        async def show_privacy_options_form(self):
            self.granted = False

        async def can_request_ads(self):
            return self.granted

    monkeypatch.setattr(ad_module, "_HAS_ADS", True)
    page = _Page()
    service = AdService(page)
    service._consent_manager = Consent()
    service._can_request_ads = True
    state.ads_ready = True

    asyncio.run(service.show_privacy_options())

    assert service._can_request_ads is False
    assert state.ads_ready is False
    state.ads_ready = False  # leave global clean for other tests


def test_gather_consent_off_mobile_publishes_closed_gate(monkeypatch):
    monkeypatch.setattr(ad_module, "_HAS_ADS", False)
    page = _Page()
    service = AdService(page)
    state.ads_ready = True

    asyncio.run(service.gather_consent())

    assert service._can_request_ads is False
    assert state.ads_ready is False
    state.ads_ready = False


def test_banner_carries_request_and_lifecycle_callbacks(monkeypatch):
    seen = {}

    class Banner:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr(ad_module, "_HAS_ADS", True)
    monkeypatch.setattr(ad_module.fta, "BannerAd", Banner)
    page = _Page()
    service = AdService(page)
    service._can_request_ads = True

    ctrl = service.get_banner_control("slot-x")

    assert seen["unit_id"] == service.banner_unit_id
    assert seen["request"].non_personalized_ads is False
    assert "video" in seen["request"].keywords
    for cb in ("on_load", "on_error", "on_open", "on_impression", "on_click", "on_paid"):
        assert callable(seen[cb]), f"banner missing {cb}"
    assert ctrl is not None


def test_interstitial_carries_request_and_lifecycle_callbacks(monkeypatch):
    seen = {}

    class Interstitial:
        def __init__(self, **kwargs):
            seen.update(kwargs)
            kwargs["on_load"](None)

    monkeypatch.setattr(ad_module, "_HAS_ADS", True)
    monkeypatch.setattr(ad_module.fta, "InterstitialAd", Interstitial)
    page = _Page()
    service = AdService(page)
    service._can_request_ads = True
    monkeypatch.setattr(state, "is_online", True)

    import asyncio as _asyncio

    _asyncio.run(service.preload_interstitial())

    assert seen["request"].non_personalized_ads is False
    for cb in ("on_open", "on_impression", "on_click"):
        assert callable(seen[cb]), f"interstitial missing {cb}"
    assert service._interstitial_ready is True
