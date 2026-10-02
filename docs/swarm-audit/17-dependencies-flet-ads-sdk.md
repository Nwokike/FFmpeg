# flet-ads 1.0.3 SDK — audit reference (the SDK, not app ad_service)

Exports: `AdRequest, BannerAd, BaseAd, ConsentDebugSettings,
ConsentManager, ConsentRequestParameters, ConsentStatus, DebugGeography,
InterstitialAd, PaidAdEvent, PrecisionType,
PrivacyOptionsRequirementStatus`. No `RewardedAd` file/class anywhere;
`NativeAd(BannerAd)` exists on disk (`factory_id`, `template_style`,
raises if both None) but NOT re-exported (must import from
`flet_ads.native_ad`).
`BaseAd`: `unit_id`, `request=AdRequest()`; events `on_load/on_error/
on_open/on_close/on_impression/on_click`; `before_update` raises unless
mobile (web or non-mobile → `FletUnsupportedPlatformException`).
`BannerAd(LayoutControl+BaseAd)`: adds `on_will_dismiss` (iOS),
`on_paid` (allowlisted). Google test IDs in docstrings (Android
banner …/9214589741 vs iOS …/2435281174; interstitial …/1033173712 vs
…/4411468910). `InterstitialAd(Service+BaseAd)`: single `async show()`,
single-use instance. `ConsentManager(Service, UMP)`: same mobile guard;
`request_consent_info_update(params?)`,
`is_consent_form_available/get_consent_status/can_request_ads/
get_privacy_options_requirement_status/
load_and_show_consent_form_if_required/show_privacy_options_form/reset`
(test-only). Types: `PrecisionType`; `PaidAdEvent(value/precision/
currency_code)`; `AdRequest(keywords/content_url/
neighboring_content_urls/non_personalized_ads/extras/http_timeout
Android-only)`; `NativeAdTemplateType/FontStyle/TextStyle/Style`;
`ConsentStatus`; `DebugGeography`; `ConsentDebugSettings`;
`ConsentRequestParameters(tag_for_under_age/consent_debug_settings)`.

## Used by app

Guarded import + fail-closed everywhere. Consent (`ConsentManager`,
append+update, `request_consent_info_update()` no params,
`load_and_show_consent_form_if_required`, `can_request_ads` →
`ads_ready`; once at startup). Privacy (`get_privacy_options...
+ REQUIRED → show_privacy_options_form` → refresh). Banner
(`BannerAd(unit_id, 320×50)` in fixed-height wrapper, per-slot cache;
3 slots: home-recent/join-action/settings-storage). Interstitial
(`on_load/on_error`, services entry, `on_close` before `show()`,
auto-preload after close/fail; triggers: startup preload,
result-exit, HIGH_VALUE submit gate).

## Unused

Rewarded ads: NOT implementable on 1.0.3 (no class). Native ads:
never imported (one comment mention); usable via `flet_ads.native_ad`
+ template types for in-feed placements. `on_paid` revenue logging
never wired. Lifecycle gap: `on_open/on_impression/on_click/
on_will_dismiss` unused; banner has zero callbacks (failures invisible).
Targeting: `AdRequest` fields never set (default `request` both
constructors; no NPA/GDPR path). Consent dead code:
`request_consent_info_update(params=None)` never passes params;
`is_consent_form_available/get_consent_status/reset` never called;
`show_privacy_options` has ZERO call sites and settings declines an
entry point — EEA users have no in-app re-consent path.
