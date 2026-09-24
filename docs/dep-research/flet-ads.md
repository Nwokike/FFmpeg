# flet-ads 1.0.0 — Complete API Reference

> Package purpose: Google AdMob ads (banner, interstitial, native-template) plus Google UMP (User Messaging Platform) consent management for Flet mobile apps. Thin Python control/service layer over the `google_mobile_ads` Flutter plugin (bundled under `flutter/flet_ads/`).
> Platform support: Android + iOS only. Every ad/consent control raises `ft.FletUnsupportedPlatformException` on web or desktop (`BaseAd.before_update`, `ConsentManager.before_update`).
> Docs: https://flet.dev/docs/controls/ads · Repo: `sdk/python/packages/flet-ads` in flet-dev/flet · Examples: `sdk/python/examples/extensions/ads`.

## Files

Package dir (`<repo>\.venv\Lib\site-packages\flet_ads`):

| File | Role |
|---|---|
| `__init__.py` | Public re-exports (`__all__`: `AdRequest`, `BannerAd`, `BaseAd`, `ConsentDebugSettings`, `ConsentManager`, `ConsentRequestParameters`, `ConsentStatus`, `DebugGeography`, `InterstitialAd`, `PaidAdEvent`, `PrecisionType`, `PrivacyOptionsRequirementStatus`). NOTE: does **not** export `NativeAd` or the `NativeAd*` template types — `from flet_ads.native_ad import NativeAd` and `from flet_ads.types import NativeAdTemplateStyle, ...` explicitly. |
| `base_ad.py` | `BaseAd(ft.BaseControl)` dataclass: shared `unit_id`, `request`, and 6 lifecycle callbacks. Platform guard. |
| `banner_ad.py` | `BannerAd(ft.LayoutControl, BaseAd)` — inline banner control. Adds `on_will_dismiss`, `on_paid`. Test IDs in docstring. |
| `interstitial_ad.py` | `InterstitialAd(ft.Service, BaseAd)` — full-screen service + `async show()`. One-shot instances. Test IDs in docstring. |
| `native_ad.py` | `NativeAd(BannerAd)` — native template ad. Requires `factory_id` **or** `template_style` (`ValueError` from `init()` otherwise). **Not exported from `flet_ads/__init__`.** |
| `consent_manager.py` | `ConsentManager(ft.Service)` — full UMP async API (8 methods). |
| `types.py` | `AdRequest`, `PaidAdEvent`, `PrecisionType`, `ConsentStatus`, `PrivacyOptionsRequirementStatus`, `ConsentRequestParameters`, `ConsentDebugSettings`, `DebugGeography`, `NativeAdTemplateType`, `NativeAdTemplateStyle`, `NativeAdTemplateTextStyle`, `NativeTemplateFontStyle`. |

Skipped: `__pycache__/*.cpython-314.pyc` only (no other build artifacts in the package dir).

Bundled native/Flutter assets (shipped inside the wheel, `RECORD` lines 15–24): `flutter/flet_ads/lib/flet_ads.dart`, `lib/src/banner.dart`, `lib/src/consent_manager.dart`, `lib/src/extension.dart`, `lib/src/interstitial.dart`, `lib/src/native.dart`, `lib/utils/ads.dart`, `lib/utils/consent.dart`, `lib/utils/native.dart`, `lib/pubspec.yaml` (depends on `google_mobile_ads` Flutter plugin). These are compiled into the Flet mobile client — no Python-side management needed, but they are why ads work only in `flet build apk/ipa`, never in Flet web/desktop.

No `entry_points.txt` in this dist-info (no plugin entry point; Flet 1.0 resolves the extension via the package import + Flutter embedding).

## Metadata

From `flet_ads-1.0.0.dist-info/METADATA` (+ `WHEEL`, `top_level.txt`):

| Field | Value |
|---|---|
| Name / Version | `flet-ads` / `1.0.0` |
| Summary | "Display Google Ads in Flet apps." |
| License | `Apache-2.0` (`License-Expression: Apache-2.0`, `License-File: LICENSE` → `licenses/LICENSE`) |
| Author | Flet contributors <hello@flet.dev> |
| Requires-Python | `>=3.10` (app runs 3.14 — fine) |
| Requires-Dist | **`flet==1.0.0` (exact pin)** — keep Flet at 1.0.0 or ads break |
| Wheel | `py3-none-any`, purelib, setuptools 84.0.0 |
| `top_level.txt` | `flet_ads` |
| Entry points | none (`entry_points.txt` absent) |
| INSTALLER / REQUESTED | uv-installed, direct dependency (`pyproject.toml`: `"flet-ads>=1.0.0"`) |

## Module-by-module API

### `flet_ads.base_ad` — `BaseAd`

```python
@dataclass(kw_only=True)
class BaseAd(ft.BaseControl):
    unit_id: str  # required, kw-only. AdMob ad unit ID.
    request: AdRequest = AdRequest()  # targeting info (default: empty request)
    on_load: Optional[ft.ControlEventHandler["BaseAd"]] = None  # loaded OK
    on_error: Optional[ft.ControlEventHandler["BaseAd"]] = None  # failed; e.data has error info
    on_open: Optional[ft.ControlEventHandler["BaseAd"]] = (
        None  # full-screen overlay opened (pause timers/animations)
    )
    on_close: Optional[ft.ControlEventHandler["BaseAd"]] = None  # overlay closed (resume)
    on_impression: Optional[ft.ControlEventHandler["BaseAd"]] = None  # impression logged
    on_click: Optional[ft.ControlEventHandler["BaseAd"]] = None  # ad tapped
```

- Inherits all `ft.BaseControl`/`LayoutControl` plumbing (for `BannerAd`: `width`, `height`, `visible`, `opacity`, etc.).
- `before_update()` raises `ft.FletUnsupportedPlatformException` when `page.web or not page.platform.is_mobile()`.
- Returns: constructor returns the control; events deliver `ft.ControlEvent` with `.control` = the ad, `.data` = error string for `on_error`.
- Exceptions: `FletUnsupportedPlatformException` (web/desktop). No Python-side validation of `unit_id` format.

### `flet_ads.banner_ad` — `BannerAd`

```python
@ft.control("BannerAd")
class BannerAd(ft.LayoutControl, BaseAd):
    on_will_dismiss: Optional[ft.ControlEventHandler["BannerAd"]] = (
        None  # iOS-only, before full-screen dismiss
    )
    on_paid: Optional[ft.ControlEventHandler[PaidAdEvent["BannerAd"]]] = (
        None  # revenue event (allowlisted accounts)
    )
```

- Full constructor = `BaseAd` fields + `LayoutControl` size fields + the two above. Typical:
  ```python
  import flet_ads as fta

  banner = fta.BannerAd(
      unit_id="ca-app-pub-.../...",
      width=320,
      height=50,
      request=fta.AdRequest(keywords=["video", "editing"]),
      on_load=lambda e: print("banner loaded"),
      on_error=lambda e: print("banner error:", e.data),
      on_paid=lambda e: print(e.data.value, e.data.currency_code),
  )
  page.add(banner)
  ```
- Test unit IDs (replace in prod): Android `ca-app-pub-3940256099942544/9214589741`, iOS `ca-app-pub-3940256099942544/2435281174`.
- No `load()`/`show()` — rendering the control requests the ad automatically.

### `flet_ads.interstitial_ad` — `InterstitialAd`

```python
@ft.control("InterstitialAd")
class InterstitialAd(ft.Service, BaseAd):
    async def show(self) -> None: ...
```

- It is a **`ft.Service`**: must be in `page.services` (`page.services.append(ad)`) to function; distinct from visible controls.
- **One-shot**: each instance may be `show()`n at most once; create + append a fresh instance per impression.
- Flow:
  ```python
  ad = fta.InterstitialAd(unit_id=UNIT, on_load=..., on_error=..., on_close=...)
  page.services.append(ad)  # starts loading via request
  # ... wait for on_load ...
  await ad.show()  # full-screen overlay; on_close fires after dismiss
  page.services.remove(ad)  # cleanup; build a new instance for the next break
  ```
- Test unit IDs: Android `ca-app-pub-3940256099942544/1033173712`, iOS `ca-app-pub-3940256099942544/4411468910`.
- Exceptions: `FletUnsupportedPlatformException` (web/desktop); calling `show()` before load completes errors/no-ops natively.

### `flet_ads.native_ad` — `NativeAd` (NOT in `__init__.__all__`)

```python
@ft.control("NativeAd")
class NativeAd(BannerAd):
    factory_id: str = None  # custom platform-view factory id
    template_style: NativeAdTemplateStyle = None  # OR a prebuilt template style

    def init(self): ...  # raises ValueError("factory_id or template_style must be set")
```

- Import path: `from flet_ads.native_ad import NativeAd`; style types from `flet_ads.types`.
- Template example (no native factory code needed):
  ```python
  from flet_ads.native_ad import NativeAd
  from flet_ads.types import (
      NativeAdTemplateStyle,
      NativeAdTemplateType,
      NativeAdTemplateTextStyle,
      NativeTemplateFontStyle,
  )

  ad = NativeAd(
      unit_id="ca-app-pub-.../...",
      template_style=NativeAdTemplateStyle(
          template_type=NativeAdTemplateType.MEDIUM,
          main_bgcolor="#FFFFFF",
          corner_radius=12,
          call_to_action_text_style=NativeAdTemplateTextStyle(
              size=14, text_color="#FFFFFF", bgcolor="#3C8038", style=NativeTemplateFontStyle.BOLD
          ),
      ),
  )
  ```
- Inherits the full `BannerAd` event set (`on_load/on_error/.../on_paid`).

### `flet_ads.consent_manager` — `ConsentManager`

```python
@ft.control("ConsentManager")
class ConsentManager(ft.Service):
    async def request_consent_info_update(
        self, params: Optional[ConsentRequestParameters] = None
    ) -> None: ...
    async def is_consent_form_available(self) -> bool: ...
    async def get_consent_status(self) -> ConsentStatus: ...  # cached between sessions
    async def can_request_ads(self) -> bool: ...  # gate ALL ad loads on this
    async def get_privacy_options_requirement_status(self) -> PrivacyOptionsRequirementStatus: ...
    async def load_and_show_consent_form_if_required(self) -> None: ...  # no-op if not required
    async def show_privacy_options_form(self) -> None: ...  # only when status == REQUIRED
    async def reset(self) -> None: ...  # TESTING ONLY, never in prod
```

- Also a `ft.Service` → `page.services.append(ConsentManager())`, same mobile-only guard.
- Canonical startup (await in order — do **not** fire-and-forget independently):
  ```python
  cm = fta.ConsentManager()
  page.services.append(cm)
  await cm.request_consent_info_update()
  await cm.load_and_show_consent_form_if_required()
  if await cm.can_request_ads():
      page.services.append(fta.BannerAd(unit_id=...))
  ```
- Debug/testing flow:
  ```python
  params = fta.ConsentRequestParameters(
      consent_debug_settings=fta.ConsentDebugSettings(
          debug_geography=fta.DebugGeography.EEA, test_identifiers=["<hashed-device-id>"]
      )
  )
  await cm.request_consent_info_update(params)
  ```

### `flet_ads.types`

```python
class PrecisionType(Enum): UNKNOWN="unknown"; ESTIMATED="estimated";
    PUBLISHER_PROVIDED="publisherProvided"; PRECISE="precise"

@dataclass
class PaidAdEvent(ft.Event[ft.EventControlType]):
    value: float; precision: PrecisionType; currency_code: str
    # delivered as e.data on BannerAd.on_paid

@ft.value
class AdRequest:
    keywords: Optional[list[str]] = None
    content_url: Optional[str] = None
    neighboring_content_urls: Optional[list[str]] = None
    non_personalized_ads: Optional[bool] = None   # True => NPA/GDPR-safe request
    http_timeout: Optional[int] = None            # ms; Android only, ignored on iOS
    extras: Optional[dict[str, str]] = None       # adapter extras

class ConsentStatus(Enum):  # what stage consent collection is at (NOT grant/deny)
    NOT_REQUIRED="notRequired"; OBTAINED="obtained"; REQUIRED="required"; UNKNOWN="unknown"
    # OBTAINED = user finished the form (consent OR decline OR custom) — check can_request_ads(), not this.

class PrivacyOptionsRequirementStatus(Enum):
    NOT_REQUIRED="notRequired"; REQUIRED="required"; UNKNOWN="unknown"

class DebugGeography(Enum):
    DISABLED="disabled"; EEA="eea"; REGULATED_US_STATE="regulatedUsState"; OTHER="other"

@ft.value
class ConsentDebugSettings:
    debug_geography: Optional[DebugGeography] = None
    test_identifiers: Optional[list[str]] = None  # hashed IDs from adb logcat / Xcode console; emulators auto-registered

@ft.value
class ConsentRequestParameters:
    tag_for_under_age_of_consent: Optional[bool] = None  # True => form suppressed; handle minors separately
    consent_debug_settings: Optional[ConsentDebugSettings] = None

class NativeAdTemplateType(Enum): SMALL="small"; MEDIUM="medium"
class NativeTemplateFontStyle(Enum): NORMAL="normal"; BOLD="bold"; ITALIC="italic"; MONOSPACE="monospace"

@ft.value
class NativeAdTemplateTextStyle:
    size: Optional[ft.Number] = None; text_color: Optional[ft.ColorValue] = None
    bgcolor: Optional[ft.ColorValue] = None; style: Optional[NativeTemplateFontStyle] = None

@ft.value
class NativeAdTemplateStyle:
    template_type: NativeAdTemplateType = NativeAdTemplateType.MEDIUM
    main_bgcolor: Optional[ft.ColorValue] = None; corner_radius: Optional[ft.Number] = None
    call_to_action_text_style: Optional[NativeAdTemplateTextStyle] = None
    primary_text_style: Optional[NativeAdTemplateTextStyle] = None
    secondary_text_style: Optional[NativeAdTemplateTextStyle] = None
    tertiary_text_style: Optional[NativeAdTemplateTextStyle] = None
```

## App usage & correctness

Call graph: `src/main.py` constructs one `AdService(page)` (line 194), fires `ads.gather_consent` + `ads.preload_interstitial` as background tasks (lines 712–713), shows an interstitial on result→dashboard navigation (lines 356–370), renders `BannerAdView()` at the bottom of `home_screen.py` (line 225), and exposes privacy options in `settings_screen.py` (line 151 via `show_privacy_options`).

**(a) Correct usage**

- `src/services/ad_service.py:75-77` — `ConsentManager()` appended to `page.services` with a membership check. Correct (it is a service).
- `src/services/ad_service.py:79-81` — consent order (`request_consent_info_update` → `load_and_show_consent_form_if_required` → `can_request_ads`) matches the canonical flow; fail-closed on exception (lines 83–87) is Play-policy correct.
- `src/services/ad_service.py:89-97` — privacy-options form gated on `PrivacyOptionsRequirementStatus.REQUIRED` and refreshes `can_request_ads`. Correct.
- `src/services/ad_service.py:130-139` — interstitial created as a service and appended to `page.services`; one-shot handling (`self.interstitial=None` after take, line 172) respects the single-`show()` rule.
- `src/services/ad_service.py:61-66,103` — mobile/web guard (`_is_mobile`) before building any ad, avoiding the `FletUnsupportedPlatformException`. Correct.
- `src/main.py:356-370` — interstitial fires on leaving the result screen (after value delivered), not mid-task. Placement-policy correct.
- `pyproject.toml:65-80` — `APPLICATION_ID` meta-data + `INTERNET`/`ACCESS_NETWORK_STATE` permissions present. Correct.
- `src/core/constants.py:61-69` — test IDs isolated with empty-PROD fallback; `tools/admob.py swap-ids` release path documented. Correct hygiene.

**(b) Misuse / bugs**

1. **Consent/load race — `src/main.py:712-713`.** `gather_consent` and `preload_interstitial` are launched as two independent `page.run_task` calls. Nothing awaits consent before the preload, so the first interstitial (and the first banner, built on first render of `home_screen.py:225`) can request ads before `can_request_ads` is known — a UMP/Play-policy violation on EEA first launches. Fix (v1): `await gather_consent()` first, then preload; gate banner construction on the consent future, not just the boolean default.
2. **Ads-permitted default is `True` — `src/services/ad_service.py:46`.** `_can_request_ads=True` initially, so any banner built before `gather_consent` finishes serves ads without a consent decision. Combined with (1), first-launch EEA users get ad requests pre-consent. Fix: default `False` (fail closed) until `can_request_ads()` resolves.
3. **Test IDs still live — `src/services/ad_service.py:39` (`USE_TEST_IDS=True`) + `src/core/constants.py:61-63`.** Expected pre-release, but this plus the prod-ID blanks (lines 67–69) means a v1.0 tag built as-is serves test ads / fails the CI AdMob guard. Release checklist must flip the flag via `tools/admob.py swap-ids --mode prod`.
4. **Banner rebuilt on every render — `src/components/banner_ad.py:17` + `src/services/ad_service.py:101-116`.** `BannerAdView()` is a component invoked per `home_screen` rebuild; `get_banner_control()` constructs a **new** `BannerAd` each call with no caching/dispose. Each rebuild = a fresh ad request (extra fill/latency/battery) and orphaned native views. Fix: memoize one banner per session (or per unit-id) and reuse; only rebuild on consent change.
5. **`show()` raced with load — `src/services/ad_service.py:143-202`.** `preload_interstitial` returns right after appending the service; `show_interstitial` will `await ad.show()` even if `on_load` never fired (no loaded-flag, no `await` on the load event). If the user exits the result screen quickly, `show()` throws/no-ops and the break is lost; the error path (lines 191–194) discards without retry-backoff. Fix: track `on_load`/`on_error` state, only `show()` when loaded, re-preload on error with backoff.
6. **Interstitial never preloaded again after success until next close — logic OK but cooldown + single-slot interact badly.** 90 s cooldown (line 40) with one slot means rapid result→dashboard→result cycles silently skip; acceptable, but log-only (line 163) leaves product blind. Minor.
7. **No `is_consent_form_available()` check** before `load_and_show_consent_form_if_required` — harmless (the latter no-ops), but diagnostics lose a signal; log it.
8. **`get_banner_control()` hardcodes 320×50** (lines 109–110). Fine for phones, but tablets/landscape should use adaptive sizing (see Underused). Not a crash, a yield issue.

**(c) Coverage summary.** Banner ✓, Interstitial ✓, ConsentManager core flow ✓, privacy options ✓. Unused: `NativeAd` (+ template styles), `AdRequest` targeting, `on_paid` revenue events, full lifecycle callbacks, debug-geography testing, `is_consent_form_available`/`get_consent_status` diagnostics. No `flet_ads` usage in `tests/` at all (grep empty) — zero ad test coverage.

## Underused APIs to adopt

1. **`NativeAd` + `NativeAdTemplateStyle`** — in-feed native template (MEDIUM) inside the home-screen job list would monetize the highest-traffic surface; currently only the bottom banner exists. Remember the separate import (`flet_ads.native_ad`, `flet_ads.types`) since `__init__` omits it.
2. **`AdRequest(keywords=..., content_url=...)`** — every ad is built with the default empty request; pass media-operation keywords (`["video", "transcode", ...]`) and the help/docs URL to lift relevance/fill.
3. **`AdRequest(non_personalized_ads=True)`** — no NPA fallback when `can_request_ads` is False/UNKNOWN; currently the app just hides ads. NPA preserves (reduced) yield under GDPR decline.
4. **`BannerAd.on_paid` + `PaidAdEvent`/`PrecisionType`** — zero revenue telemetry; attach `on_paid` and log `value/currency_code/precision` to analytics.
5. **Full `BaseAd` lifecycle (`on_open/on_close/on_click/on_impression`) on the banner** — banner wires none; `on_open/on_close` should pause/resume the job-queue progress timers.
6. **`InterstitialAd.on_load/on_error` as load-state, not just logs** — promote to a ready-flag + retry/backoff (see bug 5); also add `on_impression` for funnel metrics.
7. **`ConsentManager.is_consent_form_available()` + `get_consent_status()`** — log both at startup for EEA debugging instead of inferring from failures.
8. **`ConsentRequestParameters`/`ConsentDebugSettings`/`DebugGeography`** — no EEA/regulated-US simulation path; add a dev-only settings toggle so QA can exercise the consent form without flying to Europe.
9. **`show_privacy_options_form` entry-point visibility** — wired (settings screen) but never gated in UI by `get_privacy_options_requirement_status`; hide/show the settings row on the live status per GDPR "persistent entry point" guidance.
10. **Adaptive banner sizing** — replace fixed 320×50 with a width derived from `page.width` (e.g. full-width × 50/90/250 buckets) for tablets and landscape.

## Gotchas

- **Mobile-only, always.** Any ad or `ConsentManager` on web/desktop raises `FletUnsupportedPlatformException`. Keep the `_is_mobile()` guards; also guard Flet preview runs on dev laptops.
- **Exact pin `flet==1.0.0`.** Upgrading Flet without a matching `flet-ads` breaks the extension bridge. Upgrade both atomically.
- **`NativeAd` import trap.** `import flet_ads as fta; fta.NativeAd` → `AttributeError`. Must `from flet_ads.native_ad import NativeAd`.
- **`OBTAINED ≠ granted`.** `ConsentStatus.OBTAINED` means the user *finished* the form (possibly "Do not consent"). Never branch on it — branch on `await can_request_ads()`.
- **`reset()` is testing-only.** Never ship a call path to it; it simulates first-launch.
- **`tag_for_under_age_of_consent=True` suppresses the form.** If the app ever adds age-gating, handle under-age users with NPA/no-ads logic, not the consent form.
- **`http_timeout` is Android-only** (silently ignored on iOS). `on_will_dismiss` is iOS-only. `on_paid` needs an allowlisted AdMob account — code defensively for `None`.
- **Interstitials are single-use.** Re-`show()`ing an instance errors; always mint a fresh `InterstitialAd` per break (the service already does — keep it).
- **Test IDs + test App ID must vanish from release.** `ca-app-pub-3940256099942544/...` and `...~3347511713` in `constants.py:61-63` + `pyproject.toml:68` + `USE_TEST_IDS=True`; AdMob bans real-click testing and Play rejects test App IDs. CI guard exists — do not bypass it.
- **`extras` is `dict[str, str]`** — stringify mediation extras; non-string values fail serialization.
