# flet-permission-handler 1.0.0 — Complete API Reference

> Package purpose: Flet service wrapper around the Flutter
> [`permission_handler`](https://pub.dev/packages/permission_handler) (Dart 12.0.1)
> plugin. Exposes runtime permission check / request / open-settings flows to
> Flet Python apps on Android, iOS, Windows and Web. Raises
> `ft.FletUnsupportedPlatformException` on macOS/Linux desktops.
> Docs: <https://flet.dev/docs/services/permissionhandler>.
> App context: FFmpeg mobile app (`src/main.py`, `src/screens/capture_screen.py`).

## Files

Python sources (only 3 files; pure-python wheel, no compiled extensions):

| File | Role |
|---|---|
| `flet_permission_handler/__init__.py` | Re-exports `Permission`, `PermissionHandler`, `PermissionStatus`; defines `__all__` |
| `flet_permission_handler/permission_handler.py` | `PermissionHandler(ft.Service)` control, `@ft.control("PermissionHandler")`; the only service class |
| `flet_permission_handler/types.py` | `Permission` enum (~36 members) + `PermissionStatus` enum (6 members) |

Skipped: `__pycache__/*.cpython-314.pyc` (bytecode only).

Bundled native assets (shipped inside the wheel but only unpacked at Flutter
build time under `site-packages/flutter/flet_permission_handler/`):

| Asset | Notes |
|---|---|
| `flutter/flet_permission_handler/pubspec.yaml` | Dart package `flet_permission_handler 0.1.0`, depends on `permission_handler: 12.0.1`, `collection`, local `flet` SDK path |
| `flutter/flet_permission_handler/lib/flet_permission_handler.dart` | Barrel export (78 bytes) |
| `flutter/flet_permission_handler/lib/src/extension.dart` | `Extension extends FletExtension`; `createService` maps control type `"PermissionHandler"` → `PermissionHandlerService` |
| `flutter/flet_permission_handler/lib/src/permission_handler.dart` | Dart service: async `get_status`, `request`, `open_app_settings` method-channel handlers |
| `flutter/flet_permission_handler/lib/src/utils/permission_handler.dart` | `parsePermission(String?)`: case-insensitive name match over `Permission.values` via `firstWhereOrNull`, falls back to default |

No `.so`/`.dll`/model blobs — the runtime native code comes from the
pub.dev `permission_handler` dependency at Flutter build time, not from this wheel.

## Metadata

From `flet_permission_handler-1.0.0.dist-info/METADATA` (+ `WHEEL`, `top_level.txt`, `INSTALLER`):

| Field | Value |
|---|---|
| Name / Version | `flet-permission-handler` / `1.0.0` |
| Summary | "Manage runtime permissions in Flet apps." |
| License | `Apache-2.0` (`License-Expression`, `licenses/LICENSE`) |
| Author | Flet contributors <hello@flet.dev> |
| Requires-Python | `>=3.10` (app runs 3.14) |
| Sole dependency pin | `Requires-Dist: flet==1.0.0` (exact pin — keep app's `flet` at 1.0.0) |
| Wheel | `py3-none-any`, setuptools 84.0.0, `Root-Is-Purelib: true` |
| Top-level import | `flet_permission_handler` (+ `flutter` build shim dir) |
| Entry points | None (`entry_points.txt` absent; no console scripts or plugin auto-registration — you must instantiate `PermissionHandler()` and append to `page.services` yourself) |
| Homepage / Docs / Repo / Issues | <https://flet.dev>, <https://flet.dev/docs/services/permissionhandler>, <https://github.com/flet-dev/flet/tree/main/sdk/python/packages/flet-permission-handler>, <https://github.com/flet-dev/flet/issues> |
| Installer | `uv` (`INSTALLER` file contains `uv`) |

Platform support (README matrix): Windows ✅, iOS ✅, Android ✅, Web ✅,
macOS ❌, Linux ❌. The Python `before_update` guard enforces a subset:
`page.web` OR platform in `{ANDROID, ANDROID_TV, IOS, WINDOWS}` — note
`ANDROID_TV` is allowed by the guard though absent from the README table.

App pin: `pyproject.toml:14` declares `"flet-permission-handler>=1.0.0"`.
Android manifest block `pyproject.toml:74-83` (`[tool.flet.android.permission]`)
declares only `INTERNET`, `ACCESS_NETWORK_STATE`, `WAKE_LOCK`, `CAMERA`,
`RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS` — deliberately no broad storage /
media-read permissions (SAF picker + MediaStore cover file I/O; see comment
at `pyproject.toml:70-73`).

## Module-by-module API

### `flet_permission_handler/__init__.py`

```python
from flet_permission_handler.permission_handler import PermissionHandler
from flet_permission_handler.types import Permission, PermissionStatus

__all__ = ["Permission", "PermissionHandler", "PermissionStatus"]
```

That is the entire public surface: 1 service class + 2 enums.

### `flet_permission_handler/types.py` — `PermissionStatus` (6 members)

| Member | Wire value | Meaning |
|---|---|---|
| `GRANTED` | `"granted"` | User granted access. Proceed. |
| `DENIED` | `"denied"` | User denied (or not asked yet); you may call `request()` — the OS dialog can still appear. |
| `PERMANENTLY_DENIED` | `"permanentlyDenied"` | Dialog will NOT show again; user must flip it in OS Settings. Android 11+ (API 30+): second denial latches here. Below API 30: "never ask again" checkbox. iOS: any denial maps here. |
| `LIMITED` | `"limited"` | Limited grant (photo-library picker scope). iOS 14+, Android 14+. Treat as usable-but-partial. |
| `PROVISIONAL` | `"provisional"` | Provisional notification authorization (non-interruptive posts). iOS 12+ only. Treat as usable for notify. |
| `RESTRICTED` | `"restricted"` | OS-level restriction (e.g. parental controls); user cannot change it. iOS only. Never retry-request; show guidance only. |

Helper pattern (app already uses this in `capture_screen.py:67-69`):
`getattr(status, "value", status)` normalizes enum-or-string uniformly.

### `flet_permission_handler/types.py` — `Permission` (~36 members)

Wire values are camelCase strings (e.g. `Permission.CAMERA.value == "camera"`),
parsed Dart-side case-insensitively.

Media/capture-relevant (the app's domain):

| Member | Wire | Platform notes |
|---|---|---|
| `CAMERA` | `"camera"` | Android Camera / iOS Photos+Camera |
| `MICROPHONE` | `"microphone"` | Both platforms |
| `SPEECH` | `"speech"` | Android = same as MIC; iOS = separate speech-recognition grant — request BOTH on iOS if transcribing |
| `PHOTOS` | `"photos"` | Read+write photo library |
| `PHOTOS_ADD_ONLY` | `"photosAddOnly"` | iOS 14+ write-only (cheaper ask when only saving) |
| `MEDIA_LIBRARY` | `"mediaLibrary"` | iOS 9.3+ Apple-Music-style media library |
| `AUDIO` | `"audio"` | Android 13+ (API 33+) external-storage audio |
| `VIDEOS` | `"videos"` | Android 13+ external-storage video |
| `ACCESS_MEDIA_LOCATION` | `"accessMediaLocation"` | Android 10+ geo-tags inside shared media |
| `STORAGE` | `"storage"` | **Deprecated on Android 13+**: always returns `denied`; use `PHOTOS`/`VIDEO`/`AUDIO`/`MANAGE_EXTERNAL_STORAGE` instead. Below API 33 requests READ/WRITE_EXTERNAL_STORAGE per manifest. iOS: implicitly granted (Documents/Downloads) |
| `MANAGE_EXTERNAL_STORAGE` | `"manageExternalStorage"` | Android 11+ all-files access; needs Play Store declaration form — avoid unless SAF/MediaStore insufficient |

Location / sensors / misc (full enumeration for completeness):

| Member | Wire | Platform notes |
|---|---|---|
| `LOCATION` | `"location"` | Android fine+coarse / iOS always+whenInUse |
| `LOCATION_ALWAYS` | `"locationAlways"` | iOS always |
| `LOCATION_WHEN_IN_USE` | `"locationWhenInUse"` | Foreground-only |
| `SENSORS` / `SENSORS_ALWAYS` | `"sensors"` / `"sensorsAlways"` | Body sensors / CoreMotion; Always variant Android 13+ only |
| `ACTIVITY_RECOGNITION` | `"activityRecognition"` | Android 10+ |
| `NOTIFICATION` | `"notification"` | Push; iOS provisional flow returns PROVISIONAL |
| `CRITICAL_ALERTS` | `"criticalAlerts"` | iOS only (override ringer) |
| `ACCESS_NOTIFICATION_POLICY` | `"accessNotificationPolicy"` | Android 6+ DND policy |
| `CONTACTS` | `"contacts"` | AddressBook/Contacts |
| `CALENDAR_FULL_ACCESS` / `CALENDAR_WRITE_ONLY` | `"calendarFullAccess"` / `"calendarWriteOnly"` | Identical on iOS ≤16 |
| `REMINDERS` | `"reminders"` | iOS only |
| `PHONE` / `SMS` | `"phone"` / `"sms"` | Android only |
| `BLUETOOTH` / `BLUETOOTH_SCAN` / `BLUETOOTH_ADVERTISE` / `BLUETOOTH_CONNECT` | `"bluetooth…"` | Scan/Advertise/Connect need Android 12+ (API 31+) |
| `NEARBY_WIFI_DEVICES` | `"nearbyWifiDevices"` | Android 13+ |
| `APP_TRACKING_TRANSPARENCY` | `"appTrackingTransparency"` | iOS only (ATT prompt) |
| `BACKGROUND_REFRESH` | `"backgroundRefresh"` | iOS only, read-only status |
| `ASSISTANT` | `"assistant"` | SiriKit (iOS) |
| `IGNORE_BATTERY_OPTIMIZATIONS` | `"ignoreBatteryOptimizations"` | Android only |
| `SYSTEM_ALERT_WINDOW` | `"systemAlertWindow"` | Android only (draw over apps) |
| `REQUEST_INSTALL_PACKAGES` | `"requestInstallPackages"` | Android 6+ |
| `SCHEDULE_EXACT_ALARM` | `"scheduleExactAlarm"` | Android 12+ |
| `UNKNOWN` | `"unknown"` | **Return-type sentinel only — never request it** |

### `flet_permission_handler/permission_handler.py` — `PermissionHandler(ft.Service)`

```python
@ft.control("PermissionHandler")
class PermissionHandler(ft.Service):
    def before_update(self): ...  # raises ft.FletUnsupportedPlatformException off-platform

    async def get_status(self, permission: Permission) -> Optional[PermissionStatus]:
    async def request(self, permission: Permission) -> Optional[PermissionStatus]:
    async def open_app_settings(self) -> bool:
```

Full semantics:

- `get_status(permission)` — passive check, never shows UI. Returns
  `PermissionStatus(status)` for a known wire string, else `None` when the
  native side returns null (unknown/unsupported permission on this device).
  **Always `None`-check**: `None` ≠ denied; it means "unknown".
- `request(permission)` — shows the OS dialog **only if** current status
  allows it (first ask, or plain `DENIED`). On `PERMANENTLY_DENIED` /
  `RESTRICTED` it returns the unchanged status with no dialog.
  Returns the post-request status or `None` on native failure.
  **There is no batch API** — request each permission with its own `await`
  (sequentially or via `asyncio.gather`); one denial must not abort the others.
- `open_app_settings()` — deep-links the app's OS Settings page. Returns
  `True` if the page could be opened, `False` otherwise. The only recovery
  path for `PERMANENTLY_DENIED`.
- `before_update()` — on attach, raises `ft.FletUnsupportedPlatformException`
  unless `page.web` or `page.platform ∈ {ANDROID, ANDROID_TV, IOS, WINDOWS}`.
  Registration must therefore be platform-gated (app does this correctly —
  see below). Both methods are `async` and must be driven with
  `page.run_task(...)` from sync callbacks.

Minimal example:

```python
from flet_permission_handler import Permission, PermissionHandler, PermissionStatus

ph = PermissionHandler()
page.services.append(ph)  # gate: page.web or page.platform in (ANDROID, ANDROID_TV, IOS, WINDOWS)

status = await ph.get_status(Permission.CAMERA)
if status is not PermissionStatus.GRANTED:
    status = await ph.request(Permission.CAMERA)
if status is PermissionStatus.PERMANENTLY_DENIED:
    await ph.open_app_settings()
```

Exceptions: `FletUnsupportedPlatformException` (off-platform attach);
`_invoke_method` channel errors propagate as generic `Exception` (app wraps
in try/except — keep that). No package-specific exception types exist.

## App usage & correctness

### (a) Correct usage

- `src/main.py:38-42` — imports guarded by `try/except ImportError` with
  `_HAS_PERM_HANDLER` flag. Correct: desktop/CI without the extra survives.
- `src/main.py:240-257` — registration is platform-gated on
  `page.web or page.platform in (ANDROID, ANDROID_TV, IOS, WINDOWS)` before
  `page.services.append(permission_handler)`, matching the package's own
  `before_update` guard; construction failure falls back to `None` with a log.
  Correct and complete.
- `src/state/service_ctx.py:22` — `Services.permission_handler: Any = None`;
  nullable slot forces every consumer to `None`-check. Correct pattern.
- `src/screens/capture_screen.py:235-253` (`_permission_ok`) — canonical
  just-in-time flow: `get_status` → request only when action is `"ask"` →
  re-map to a UI action; whole body wrapped in try/except with snackbar
  fallback. Correct: never requests blindly, never assumes granted.
- `capture_screen.py:72-87` (`next_permission_action`) — full 6-status mapping:
  `granted/limited/provisional → ok`; `permanentlyDenied/restricted → settings`;
  `denied → ask/explain`; `None/unknown → ask/explain`. Treating LIMITED and
  PROVISIONAL as usable is correct per the enum docs.
- `capture_screen.py:197-233` (`_perm_rationale`) — distinct dialogs for
  first-ask rationale vs settings-only blocked state; settings-only dialog
  omits the futile "Try Again" button. Correct UX split.
- `capture_screen.py:273,503` — status is re-checked before **each** capture
  (`_prepare_camera`, `_toggle_mic`), not cached at screen entry. Correct:
  user can revoke mid-session.
- `tests/test_capture_helpers.py` — 6 tests pin the status→action mapping
  (granted/limited/provisional ok; denied ask→explain; permanent/restricted
  settings; None→ask). Good coverage of the mapping layer.

### (b) Misuse / bugs found

1. **`capture_screen.py:210-213` — fire-and-forget settings deep-link.**
   `_open_settings` calls `page.run_task(services.permission_handler.open_app_settings)`
   without awaiting the returned `bool`. If the OS refuses to open Settings
   (`False`), the user gets a dead tap with no feedback. Should capture the
   result and snackbar on `False`.
2. **`capture_screen.py:198` — rationale names only two permissions.**
   `_perm_rationale` maps `CAMERA → "camera"`, everything else → `"microphone"`.
   Works today (only CAMERA/MICROPHONE requested) but silently mislabels any
   future permission (e.g. PHOTOS would be called "microphone"). Use
   `perm.value`/`perm.name` for the label.
3. **`capture_screen.py:215-220` — `_retry` re-dispatches the whole capture
   entry (`_prepare_camera` / `_toggle_mic`), which re-runs `get_status`
   first — fine — but `_prepare_camera:268` early-returns when
   `camera_ref.current is not None`, so a retry after a mid-init failure can
   no-op while `camera_ready` stays False with no feedback.** Minor; reset
   `camera_ref` on init failure or surface a message.
4. **`capture_screen.py:291` — video path enables audio without a mic grant.**
   `_init_camera` calls `cam.initialize(..., enable_audio=True)` after only a
   CAMERA check; no MICROPHONE request precedes video recording. On Android
   the video records silent (or throws on strict OEM skins) with no rationale
   shown. Request MIC alongside CAMERA when `mode == "video"`.
5. **No `get_status` re-check in `_save_capture` (`capture_screen.py:570`).**
   Saving routes through `media_io` (SAF/MediaStore, no permission needed —
   consistent with the Play-safe manifest), so this is currently fine, but if
   a future direct-save path uses `PHOTOS_ADD_ONLY`, a check will be needed.
   Flagged as latent, not a live bug.
6. **`next_permission_action` lowercases the wire value (`capture_screen.py:79`),
   so `"permanentlyDenied"` matches `"permanentlydenied"` — good — but any
   future `PermissionStatus.UNKNOWN`-style sentinel would fall into
   "ask" and trigger a pointless `request(UNKNOWN)`;** guard `perm ==
   Permission.UNKNOWN` before requesting (package docs: never request it).

### (c) Underuse (see next section for the adopt list)

Only 2 of ~36 `Permission` members are used (`CAMERA`, `MICROPHONE`); only 2
of 3 service methods are used (`get_status`, `request` — `open_app_settings`
is invoked but its result ignored). NOTIFICATION, PHOTOS/PHOTOS_ADD_ONLY,
AUDIO/VIDEOS (API 33+), SPEECH-vs-MICROPHONE split on iOS are all unrequested.

## Underused APIs to adopt

1. **`await ph.open_app_settings() -> bool` (honor the return).**
   Already called; start branching on it — `False` → error snackbar.
   Sole recovery for PERMANENTLY_DENIED.
2. **`Permission.NOTIFICATION` + `get_status` at startup.**
   Update/job-complete pings (`update_service`, `job_queue`) currently post
   without checking the grant; PROVISIONAL on iOS 12+ is usable, DENIED needs
   a pre-prompt rationale. Add a settings-screen status row + request button.
3. **`Permission.PHOTOS_ADD_ONLY` for saving captures.**
   Cheaper, Play-friendly write-only grant on iOS 14+; pair with a
   `get_status(PHOTOS)` check before `_save_capture` if direct-save lands.
4. **`Permission.AUDIO` / `Permission.VIDEOS` on Android 13+.**
   `Permission.STORAGE` is deprecated and always returns `denied` on API 33+;
   any future gallery-import feature must request the granular pair, never STORAGE.
5. **`Permission.SPEECH` alongside `MICROPHONE` on iOS.**
   Any transcription/subtitle-from-speech feature needs both grants on iOS
   (they are distinct); Android needs only MIC.
6. **Sequential multi-permission request for video mode.**
   No batch API exists — `await` CAMERA then MICROPHONE (or
   `asyncio.gather`, handling each result independently) before
   `cam.initialize(enable_audio=True)`. Fixes misuse #4.
7. **`PermissionStatus.LIMITED` handling for gallery reads.**
   Already mapped to "ok"; extend to degrade gracefully (e.g. "only selected
   photos visible — change in Settings") when it appears.
8. **`PermissionStatus.RESTRICTED` guidance copy.**
   Already routed to settings dialog; keep the "Try Again" button suppressed
   there (requesting again can never succeed) — already correct, pin with a test.
9. **`None`-status path (unsupported permission/device).**
   `get_status` returns `None` when the native side has no answer; the app
   maps it to ask — reasonable — but log it distinctly so unknown-device
   reports are diagnosable.
10. **Settings-screen permission dashboard.**
    `settings_screen.py` has no permission rows today. Add per-permission
    `get_status` rows (camera, mic, notification) each with
    request-or-open-settings action — the natural home for re-grants after
    permanent denial, instead of only in-capture dialogs.

## Gotchas

- **No batch request.** The package exposes only single-permission
  `request()`; loop/`gather` manually, and never let one denial cancel siblings.
- **`STORAGE` is a trap on Android 13+.** Always resolves `denied` by OS
  design; use AUDIO/VIDEOS/PHOTOS or MANAGE_EXTERNAL_STORAGE (the latter needs
  a Play declaration — prefer SAF/MediaStore, as the app already does).
- **`PERMANENTLY_DENIED` is sticky.** `request()` shows no dialog; only
  `open_app_settings()` can recover. iOS maps *any* denial here, so the
  settings fallback is the common path on iPhones, not an edge case.
- **`RESTRICTED` is unfixable in-app.** Do not loop `request()`; show static
  guidance (parental controls / device policy).
- **`None` ≠ denied.** Both `get_status` and `request` can return `None`
  (unknown permission, unsupported device, channel failure). Branch it before
  comparing to `DENIED`.
- **Platform guard bites on macOS/Linux.** Attaching `PermissionHandler()`
  there raises `FletUnsupportedPlatformException` in `before_update`; keep the
  `main.py:249-251` gate (web OR android/tv/ios/windows) on every registration
  site, and keep consumers `None`-tolerant.
- **`flet==1.0.0` exact pin.** Upgrading `flet` without upgrading
  `flet-permission-handler` breaks the install; upgrade them in lockstep.
- **Manifest must match requests.** Every requested permission needs its
  `android.permission.*` entry (`CAMERA`, `RECORD_AUDIO` present — good);
  add entries *before* requesting any new permission (e.g. `POST_NOTIFICATIONS`).
- **`UNKNOWN` must never be requested.** Sentinel for return types only.
- **Video-with-audio needs two grants.** `enable_audio=True` without a MIC
  grant yields silent video or OEM-specific throws — always pair CAMERA + MICROPHONE.
- **Dart name matching is case-insensitive** (`parsePermission`), but Python
  wire values are camelCase (`permanentlyDenied`, `photosAddOnly`) — compare
  via the enum or lowercase-normalize like `_status_value` does.
