"""AdMob advertising service with UMP consent and test unit management.

Follows the canonical voicelm pattern adapted for Flet 1.0.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import flet as ft

from core.constants import ADMOB_BANNER_UNIT_TEST, ADMOB_INTERSTITIAL_UNIT_TEST

logger = logging.getLogger("AdService")

try:
    import flet_ads as fta

    _HAS_ADS = True
except ImportError:
    _HAS_ADS = False


class AdService:
    """Coordinates Banner and Interstitial ads with Google UMP consent."""

    USE_TEST_IDS = True
    INTERSTITIAL_COOLDOWN_SEC = 90.0

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.interstitial: Any | None = None
        self._consent_manager: Any | None = None
        self._can_request_ads: bool = True
        self._last_interstitial_time: float = 0.0

    @property
    def banner_unit_id(self) -> str:
        return ADMOB_BANNER_UNIT_TEST

    @property
    def interstitial_unit_id(self) -> str:
        return ADMOB_INTERSTITIAL_UNIT_TEST

    def _is_mobile(self) -> bool:
        try:
            return not self.page.web and bool(self.page.platform and self.page.platform.is_mobile())
        except Exception as e:
            logger.debug("Platform detection fallback: %s", e)
            return False

    async def gather_consent(self) -> None:
        """Execute Google UMP consent request on mobile platforms."""
        if not _HAS_ADS or not self._is_mobile():
            self._can_request_ads = True
            return

        try:
            self._consent_manager = fta.ConsentManager()
            if self._consent_manager not in self.page.services:
                self.page.services.append(self._consent_manager)

            await self._consent_manager.request_consent_info_update()
            await self._consent_manager.load_and_show_consent_form_if_required()
            self._can_request_ads = await self._consent_manager.can_request_ads()
            logger.info("UMP consent completed, can_request_ads=%s", self._can_request_ads)
        except Exception as exc:
            logger.warning("UMP consent check failed (allowing ads): %s", exc)
            self._can_request_ads = True

    async def show_privacy_options(self) -> None:
        """Show privacy settings form if required by EU/UK regulation."""
        if not self._consent_manager:
            return
        try:
            status = await self._consent_manager.get_privacy_options_requirement_status()
            if status == fta.PrivacyOptionsRequirementStatus.REQUIRED:
                await self._consent_manager.show_privacy_options_form()
                self._can_request_ads = await self._consent_manager.can_request_ads()
        except Exception as exc:
            logger.warning("Privacy options display error: %s", exc)

    def get_banner_control(self) -> ft.Control:
        """Return a BannerAd widget or transparent placeholder."""
        if not _HAS_ADS or not self._is_mobile() or not self._can_request_ads:
            return ft.Container(height=0, width=0)

        try:
            banner = fta.BannerAd(
                unit_id=self.banner_unit_id,
                width=320,
                height=50,
            )
            return ft.Container(
                content=banner,
                alignment=ft.Alignment.CENTER,
                height=50,
            )
        except Exception as exc:
            logger.warning("Failed creating banner ad: %s", exc)
            return ft.Container(height=0, width=0)

    async def preload_interstitial(self) -> None:
        """Preload an interstitial ad into memory."""
        if not _HAS_ADS or not self._is_mobile() or not self._can_request_ads:
            return

        try:
            ad = fta.InterstitialAd(
                unit_id=self.interstitial_unit_id,
                on_load=lambda e: logger.info("Interstitial ad loaded"),
                on_error=lambda e: logger.warning(
                    "Interstitial ad load error: %s", getattr(e, "data", e)
                ),
            )
            self.interstitial = ad
            if ad not in self.page.services:
                self.page.services.append(ad)
        except Exception as exc:
            logger.warning("Failed preloading interstitial: %s", exc)

    async def show_interstitial(self, on_close: Callable | None = None) -> bool:
        """Display preloaded interstitial if cooldown has elapsed. Returns True if shown."""
        if not _HAS_ADS or not self._is_mobile() or not self._can_request_ads:
            if on_close:
                if asyncio.iscoroutinefunction(on_close):
                    await on_close()
                else:
                    on_close()
            return False

        now = time.time()
        if now - self._last_interstitial_time < self.INTERSTITIAL_COOLDOWN_SEC:
            logger.info("Interstitial skipped: cooldown active")
            if on_close:
                if asyncio.iscoroutinefunction(on_close):
                    await on_close()
                else:
                    on_close()
            return False

        ad = self.interstitial
        self.interstitial = None

        if ad is not None:
            self._last_interstitial_time = now

            async def _handle_close(e):
                if ad in self.page.services:
                    self.page.services.remove(ad)
                if on_close:
                    if asyncio.iscoroutinefunction(on_close):
                        await on_close()
                    else:
                        on_close()
                await self.preload_interstitial()

            ad.on_close = _handle_close
            try:
                await ad.show()
                return True
            except Exception as exc:
                logger.warning("Failed displaying interstitial: %s", exc)
                if ad in self.page.services:
                    self.page.services.remove(ad)

        if on_close:
            if asyncio.iscoroutinefunction(on_close):
                await on_close()
            else:
                on_close()
        await self.preload_interstitial()
        return False
