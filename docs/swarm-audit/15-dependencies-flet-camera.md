# flet-camera 1.0.3 — audit reference

`Camera(ft.LayoutControl)` (`@ft.control("Camera")`): fields
`preview_enabled=True`, `content=None` (overlay), `on_state_change`,
`on_stream_image`. Discovery/init: `get_available_cameras()->
list[CameraDescription]`; `initialize(description, resolution_preset,
enable_audio=True, fps, video_bitrate, audio_bitrate, image_format_group)`.
Photo/video: `take_picture()->bytes`; `prepare_for_video_recording/
start/pause/resume/stop_video_recording` (stop→bytes). Preview:
`pause/resume_preview`. Image stream: `supports_image_streaming`,
`start/stop_image_stream`. Settings: `set_description`,
`set_flash_mode`, `set_zoom_level`, `set_exposure_mode/offset/point`,
`set_focus_mode/point`. Queries: min/max zoom, min/max/step exposure
offset. Orientation: `lock/unlock_capture_orientation`. Guard:
`before_update` raises `FletUnsupportedPlatformException` unless
web or ANDROID/IOS.
Types: `ResolutionPreset` LOW/MEDIUM/HIGH/VERY_HIGH/ULTRA_HIGH/MAX;
`ImageFormatGroup` BGRA8888/JPEG/NV21/YUV420/UNKNOWN; `FlashMode`
OFF/AUTO/ALWAYS/TORCH; `ExposureMode` AUTO/LOCKED; `FocusMode`
AUTO/LOCKED; `CameraLensDirection` FRONT/BACK/EXTERNAL; `CameraLensType`
WIDE/TELEPHOTO/ULTRA_WIDE/UNKNOWN; `CameraPreviewSize`;
`CameraDescription(name/lens_direction/sensor_orientation/lens_type)`;
`CameraStateEvent` (is_initialized/recording_video/recording_paused/
taking_picture/streaming_images/preview_paused/orientation locks/
flash/exposure/focus/exposure_point_supported/focus_point_supported/
preview_size/aspect_ratio/error_description/has_error/description);
`CameraImageEvent` (w/h/format/bytes/aperture/exposure/sensitivity).
`detect_video_extension(bytes)` → webm/mov/mp4/bin.

## Used by app (capture_screen only; main only routes)

`ftc.Camera(on_state_change=...)`; enumerate + prefer BACK lens;
`initialize(target, HIGH→MEDIUM fallback, enable_audio=(mode==video))`;
`take_picture()` → jpg → probe; prepare+start / pause+resume / stop
video; `detect_video_extension` + bin→mp4; `pause_preview` on unmount +
mode-switch; recreate on photo↔video audio change.

## Unused

`preview_enabled=False` (blind audio-take). `content=` overlay
(grid/REC badge). Image stream (QR/thumbs; frame feed without photo
take). `set_flash_mode` (torch). Zoom + range queries. Exposure
mode/offset/point + queries. Focus mode/point (+supported flags,
tap-to-focus). `set_description` (front/back without destroy).
FRONT/EXTERNAL lens + lens_type/sensor_orientation (selfie/external
picker). Orientation lock. `resume_preview` (pause-only today).
`initialize(fps/bitrate)` caps. `image_format_group`. LOW/VERY_HIGH/
ULTRA_HIGH/MAX presets (quality picker beyond HIGH/MEDIUM).
`preview_size/aspect_ratio` (size preview without stretch). Busy flags
(`is_taking_picture/is_streaming_images/is_preview_paused` — truthful
shutter disable). Hardware state reflection (flash/exposure/focus/
orientations after OEM overrides).
