# flet-video 1.0.3 — audit reference

Exports: `Video`, `VideoMedia`, `VideoConfiguration`, `VideoControls`,
`VideoControlsMode`, `AdaptiveVideoControls`, `MaterialVideoControls`,
`MaterialDesktopVideoControls`, `VideoBarItem`, `VideoPlayOrPauseButton`,
`VideoSkipNextButton`, `VideoSkipPreviousButton`, `VideoFullscreenButton`,
`VideoPositionIndicator`, `VideoSpacer`, `VideoVolumeButton`,
`PlaylistMode`, `VideoSubtitleTrack`, `VideoSubtitleConfiguration`.

`Video` (`video.py:23-344`, `@ft.control("Video")`): fields `playlist:
list[VideoMedia]`, `title="flet-video"`, `fit=CONTAIN`, `fill_color=BLACK`,
`wakelock=True`, `autoplay=False`, `controls=AdaptiveVideoControls()`
(None hides; dict allows per-NORMAL/FULLSCREEN/DEFAULT chrome),
`fullscreen`, `muted`, `playlist_mode`, `shuffle_playlist`, `volume`
0–100 (ValueError outside), `playback_rate`, `alignment`, `filter_quality`,
`pause_upon_entering_background_mode=True`,
`resume_upon_entering_foreground_mode=False`, `pitch`, `configuration`,
`subtitle_configuration`, `subtitle_track`. Events: `on_load`,
`on_enter/exit_fullscreen`, `on_error` (e.data), `on_complete`,
`on_track_change` (index), `on_position_change`/`on_duration_change`
(Duration). Methods (async): `play/pause/play_or_pause/stop/next/
previous/seek(Duration)/jump_to(index)` (IndexError out of range,
negatives normalized), `is_playing/is_completed/get_duration/
get_current_position`, `take_screenshot("image/png"|"image/jpeg",
include_libass_subtitles)` (ValueError on bad format).

Types: `PlaylistMode` NONE/SINGLE/LOOP; `VideoControlsMode`
NORMAL/FULLSCREEN/DEFAULT; `VideoMedia(resource, http_headers, extras)`;
`VideoConfiguration(output_driver/hardware_decoding_api/
enable_hardware_acceleration/width/height/scale/mpv_properties)`;
full BarItem set (play/pause, skip next/prev, fullscreen, position,
spacer, volume w/ slider); Material + MaterialDesktop controls (seek
bar, gestures, double-tap seek, long-press speed, volume on scroll,
play-on-tap, hover heights, subtitle shift); `VideoSubtitleTrack(src
URL|abs path|raw SRT/VTT, title/language/channels/sample_rate/fps/
bitrate/rotate/par/codec/decoder)` + `.none()`/`.auto()`;
`VideoSubtitleConfiguration(text_style/scale/align/padding/visible)`.

## Used by app (2 files only)

- `screens/cut_screen.py:23,152-159` — `Video(playlist=[VideoMedia(path)],
  autoplay=False, controls=None, filter_quality=MEDIUM, on_error)`;
  `seek()` throttled 0.3s, `stop()` cleanup, `pause()` pre-encode.
- `screens/result_screen.py:32,180-203` — 1–2 item playlist
  (output + original A/B); `controls` left at adaptive default;
  `jump_to(idx)` compare; `stop()` on job change.
- (`on_position/on_duration` at result:215,220 belong to flet-audio.)

## Unused

Custom controls (never passes `controls=` except scrubber None; no
BarItem, no per-mode dict, no overlay Control). Subtitles entirely
(`subtitle_track/configuration`, SRT/VTT preview for extracted subs).
Volume/rate/pitch/mute (no preview-speed/loudness check despite owning
those encode params). Fullscreen (no set, no enter/exit handlers).
Playlist underused (1–2 items; no `playlist_mode/shuffle/headers/extras`;
only `jump_to`, never `next/previous`). Transport/query untouched (no
`play/play_or_pause/is_playing/is_completed/get_duration/
get_current_position`; no `on_load/on_complete/on_track_change/
on_position/on_duration` at Video level — custom position UI impossible
without them). `take_screenshot` (verify trims from player frame).
`configuration` tuning (output_driver/hwaccel/size/mpv props); `fit/
fill_color/alignment/wakelock/bg-pause/title` all default (`title`
stays `"flet-video"` in the volume mixer). `on_error` only warns;
`on_load` never gates readiness.
