"""AdMob advertising service with UMP consent and test unit management.

Follows the canonical voicelm pattern adapted for Flet 1.0.
"""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Callable
from typing import Any

import flet as ft

from core.constants import (
    ADMOB_BANNER_UNIT_PROD,
    ADMOB_BANNER_UNIT_TEST,
    ADMOB_INTERSTITIAL_UNIT_PROD,
    ADMOB_INTERSTITIAL_UNIT_TEST,
)
from core.state import state

logger = logging.getLogger("AdService")

try:
    import flet_ads as fta

    _HAS_ADS = True
except ImportError:
    _HAS_ADS = False


class AdService:
    """Coordinates Banner and Interstitial ads with Google UMP consent."""

    # Swapped by tools/admob.py swap-ids (test ↔ prod) — a REAL branch: the
    # flag now decides which unit IDs are served, and empty PROD IDs never win.
    USE_TEST_IDS = False
    INTERSTITIAL_COOLDOWN_SEC = 90.0

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.interstitial: Any | None = None
        self._consent_manager: Any | None = None
        # Fail closed: no ad request may go out before UMP has answered.
        self._can_request_ads: bool = False
        self._interstitial_ready: bool = False
        self._banners: dict[str, ft.Control] = {}
        self._failed_banner_slots: set[str] = set()
        self._last_interstitial_time: float = 0.0

    @property
    def banner_unit_id(self) -> str:
        if not self.USE_TEST_IDS and ADMOB_BANNER_UNIT_PROD:
            return ADMOB_BANNER_UNIT_PROD
        return ADMOB_BANNER_UNIT_TEST

    @property
    def interstitial_unit_id(self) -> str:
        if not self.USE_TEST_IDS and ADMOB_INTERSTITIAL_UNIT_PROD:
            return ADMOB_INTERSTITIAL_UNIT_PROD
        return ADMOB_INTERSTITIAL_UNIT_TEST

    def _is_mobile(self) -> bool:
        try:
            return not self.page.web and bool(self.page.platform and self.page.platform.is_mobile())
        except Exception as e:
            logger.debug("Platform detection fallback: %s", e)
            return False

    def _remove_service(self, service: Any) -> None:
        """Remove a service by identity; dataclass equality can match twins."""
        for registered in tuple(self.page.services):
            if registered is service:
                self.page.services.remove(registered)
                break

    async def gather_consent(self) -> None:
        """Execute Google UMP consent request on mobile platforms."""
        if not _HAS_ADS or not self._is_mobile():
            # Ads never render off-mobile; keep the gate shut regardless.
            self._can_request_ads = False
            return

        try:
            if self._consent_manager is None:
                self._consent_manager = fta.ConsentManager()
            if self._consent_manager not in self.page.services:
                self.page.services.append(self._consent_manager)
                # A bare list append does not run Service.init(); sync the
                # page before invoking the native consent method.
                self.page.update()

            await self._consent_manager.request_consent_info_update()
            await self._consent_manager.load_and_show_consent_form_if_required()
            self._can_request_ads = await self._consent_manager.can_request_ads()
            logger.info("UMP consent completed, can_request_ads=%s", self._can_request_ads)
        except Exception as exc:
            # Fail closed: without a consent decision we must not request ads
            # (UMP/Play policy) — a failed check cannot grant permission.
            logger.warning("UMP consent check failed (fail closed, no ads): %s", exc)
            self._can_request_ads = False
        finally:
            # Publish through the observable so every mounted banner slot
            # re-renders immediately; AdService state alone is invisible to
            # Flet's change detection.
            state.ads_ready = self._can_request_ads

    async def show_privacy_options(self) -> None:
        """Show privacy settings form if required by EU/UK regulation."""
        if not _HAS_ADS or not self._is_mobile() or not self._consent_manager:
            return
        try:
            status = await self._consent_manager.get_privacy_options_requirement_status()
            if status == fta.PrivacyOptionsRequirementStatus.REQUIRED:
                await self._consent_manager.show_privacy_options_form()
                self._can_request_ads = await self._consent_manager.can_request_ads()
        except Exception as exc:
            logger.warning("Privacy options display error: %s", exc)

    def get_banner_control(self, slot: str = "default") -> ft.Control:
        """Return a cached BannerAd for ``slot`` or a transparent placeholder.

        Each placement needs its own control — a single Flet control cannot be
        mounted in two parents at once, so reusing one instance across Home's
        grid rows either stole the banner from its first parent or never
        rendered. Slots are cached so repeated renders do not spam ad requests.
        """
        if not _HAS_ADS or not self._is_mobile() or not self._can_request_ads:
            return ft.Container(height=0, width=0)

        cached = self._banners.get(slot)
        if cached is not None:
            return cached
        if slot in self._failed_banner_slots:
            return ft.Container(height=0, width=0)

        try:
            banner = fta.BannerAd(
                unit_id=self.banner_unit_id,
                width=320,
                height=50,
            )
            wrapper = ft.Container(
                content=banner,
                alignment=ft.Alignment.CENTER,
                height=50,
            )
            self._banners[slot] = wrapper
            return wrapper
        except Exception as exc:
            logger.warning("Failed creating banner ad for %r: %s", slot, exc)
            self._failed_banner_slots.add(slot)
            return ft.Container(height=0, width=0)

    async def preload_interstitial(self) -> None:
        """Preload an interstitial ad into memory (ready flag set on on_load)."""
        if not _HAS_ADS or not self._is_mobile() or not self._can_request_ads:
            return
        if not state.is_online:
            logger.info("Interstitial preload skipped: offline")
            return
        if self.interstitial is not None:
            return  # one in flight — never stack duplicates

        def _on_load(_e) -> None:
            self._interstitial_ready = True
            logger.info("Interstitial ad loaded")

        def _on_error(e) -> None:
            logger.warning("Interstitial ad load error: %s", getattr(e, "data", e))
            self._remove_service(ad)
            self.interstitial = None
            self._interstitial_ready = False

        try:
            self._interstitial_ready = False
            ad = fta.InterstitialAd(
                unit_id=self.interstitial_unit_id,
                on_load=_on_load,
                on_error=_on_error,
            )
            self.interstitial = ad
            if ad not in self.page.services:
                self.page.services.append(ad)
                # Service registration happens during the page update cycle.
                self.page.update()
        except Exception as exc:
            self.interstitial = None
            self._interstitial_ready = False
            logger.warning("Failed preloading interstitial: %s", exc)

    async def show_interstitial(self, on_close: Callable | None = None) -> bool:
        """Display preloaded interstitial if cooldown has elapsed. Returns True if shown."""

        async def _notify() -> None:
            """Run the optional close callback whether it is sync or async.

            asyncio.iscoroutinefunction is deprecated as of Python 3.14, so
            inspect.iscoroutinefunction is used instead (no warning in logs).
            """
            if on_close is None:
                return
            if inspect.iscoroutinefunction(on_close):
                await on_close()
            else:
                on_close()

        if not _HAS_ADS or not self._is_mobile() or not self._can_request_ads:
            await _notify()
            return False
        if not state.is_online:
            logger.info("Interstitial skipped: offline")
            await _notify()
            return False

        now = time.time()
        if now - self._last_interstitial_time < self.INTERSTITIAL_COOLDOWN_SEC:
            logger.info("Interstitial skipped: cooldown active")
            await _notify()
            return False

        ad = self.interstitial
        if ad is not None and not self._interstitial_ready:
            # Still loading: show() would throw or silently no-op. Keep the
            # ad (it may finish) and retry on the next natural break.
            logger.info("Interstitial skipped: still loading")
            await _notify()
            return False
        self.interstitial = None
        self._interstitial_ready = False

        if ad is not None:
            self._last_interstitial_time = now

            async def _handle_close(e):
                self._remove_service(ad)
                await _notify()
                await self.preload_interstitial()

            ad.on_close = _handle_close
            # Push the handler to the native service before showing it; a
            # close event can arrive immediately on a cached ad.
            self.page.update()
            try:
                await ad.show()
                return True
            except Exception as exc:
                logger.warning("Failed displaying interstitial: %s", exc)
                self._remove_service(ad)

        await _notify()
        await self.preload_interstitial()
        return False
