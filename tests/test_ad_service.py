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
