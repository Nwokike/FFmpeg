# flet-permission-handler 1.0.3 — audit reference

3 files, exports exactly `Permission`, `PermissionHandler`,
`PermissionStatus`. No `PermissionType`, no `check()`, no `on_status`.
`PermissionHandler(ft.Service)`: zero fields/events. `before_update`
raises unless web or {ANDROID, ANDROID_TV, IOS, WINDOWS} (Linux/macOS
explicitly unsupported). `get_status(permission)`, `request(permission)`
(only prompts if not granted), `open_app_settings() -> bool`.
`PermissionStatus` (6): GRANTED/DENIED/PERMANENTLY_DENIED/LIMITED
(iOS14+/Android14+ picker)/PROVISIONAL (iOS notifications)/RESTRICTED
(iOS lock — user cannot change; Settings link cannot help).
`Permission` (40): ACCESS_MEDIA_LOCATION, ACCESS_NOTIFICATION_POLICY,
ACTIVITY_RECOGNITION, APP_TRACKING_TRANSPARENCY, ASSISTANT, AUDIO
(Android13+), BACKGROUND_REFRESH, BLUETOOTH + ADVERTISE/CONNECT/SCAN,
CALENDAR_FULL/WRITE_ONLY, CAMERA, CONTACTS, CRITICAL_ALERTS,
IGNORE_BATTERY_OPTIMIZATIONS, LOCATION/ALWAYS/WHEN_IN_USE,
MANAGE_EXTERNAL_STORAGE, MEDIA_LIBRARY, MICROPHONE, NEARBY_WIFI_DEVICES,
NOTIFICATION, PHONE, PHOTOS, PHOTOS_ADD_ONLY, REMINDERS,
REQUEST_INSTALL_PACKAGES, SCHEDULE_EXACT_ALARM, SENSORS/SENSORS_ALWAYS,
SMS, SPEECH, STORAGE (deprecated 13+, always denied — use
PHOTOS/VIDEO/AUDIO/MANAGE_EXTERNAL_STORAGE), SYSTEM_ALERT_WINDOW,
UNKNOWN (return-only), VIDEOS (Android13+).

## Used by app (2 of 40)

Registration mirrors the platform guard (main.py:282-299); service
injected via service_ctx. Only capture_screen consumes: `_permission_ok`
(get→ask→request→re-map; None-handler short-circuits to snack),
`_perm_rationale` dialog (CAMERA/MICROPHONE labels, `open_app_settings`
with False/exception handling, retry re-arms camera/mic). Call sites:
CAMERA (camera prepare), MICROPHONE (video-record-audio, mic toggle).
Matching is string-normalized (`_status_value`/`next_permission_action`).

## Unused (38/40)

Directly relevant but never checked: PHOTOS, PHOTOS_ADD_ONLY, VIDEOS,
AUDIO, STORAGE (pre-13), MEDIA_LIBRARY (iOS), MANAGE_EXTERNAL_STORAGE
(11+ escape), ACCESS_MEDIA_LOCATION. File pick/save/convert/library flows
run with NO permission gate — saving captures to gallery or reading
shared media on Android/iOS will hit OS denials the handler could
pre-check. NOTIFICATION (completion notices), SPEECH (Android≡MIC,
iOS distinct — transcription future). `PermissionStatus` import is dead
weight (string matching works incl. None→ask, forfeits exhaustiveness);
LIMITED/PROVISIONAL treated ok without handling. Over-gating: handler
None (Linux/macOS) hard-blocks even desktop mic where
`AudioRecorder.has_permission()` alone could suffice.
