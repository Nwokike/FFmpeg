# flet-video 1.0.0 — Complete API Reference

> Package purpose: cross-platform video playback control for Flet apps, backed by the
> Flutter `media_kit` package (libmpv on native: Windows/macOS/Linux/iOS/Android, HTML
> video on web). Single control (`Video`) + playlist/controls/subtitle value objects.
> Docs: https://flet.dev/docs/controls/video · Source:
> https://github.com/flet-dev/flet/tree/main/sdk/python/packages/flet-video

## Files

Package dir `<repo>\.venv\Lib\site-packages\flet_video`
contains exactly **3 Python files** (plus `__pycache__/*.pyc`, skipped). Pure-Python
package — **no bundled native assets** in site-packages; the native side ships inside
the wheel as `flutter/flet_video/...` (Dart extension, compiled at app-build time).

| File | Contents |
|---|---|
| `flet_video/__init__.py` | Re-exports only; `__all__` = 19 names (see below) |
| `flet_video/types.py` | 17 exported types: enums, bar items, controls presets, config/subtitle objects |
| `flet_video/video.py` | The `Video` control (`@ft.control("Video")`, extends `ft.LayoutControl`) |

Wheel `RECORD` additionally lists (build-time only, not importable from Python):
`flutter/flet_video/lib/flet_video.dart`, `lib/src/extension.dart`,
`lib/src/utils/file_utils_io.dart`, `lib/src/utils/file_utils_web.dart`,
`lib/src/utils/video.dart`, `lib/src/video.dart`, `flutter/flet_video/pubspec.yaml`.

`__all__` (19): `AdaptiveVideoControls`, `MaterialDesktopVideoControls`,
`MaterialVideoControls`, `PlaylistMode`, `Video`, `VideoBarItem`, `VideoConfiguration`,
`VideoControls`, `VideoControlsMode`, `VideoFullscreenButton`, `VideoMedia`,
`VideoPlayOrPauseButton`, `VideoPositionIndicator`, `VideoSkipNextButton`,
`VideoSkipPreviousButton`, `VideoSpacer`, `VideoSubtitleConfiguration`,
`VideoSubtitleTrack`, `VideoVolumeButton`.

## Metadata

From `flet_video-1.0.0.dist-info/METADATA` (+ `WHEEL`, `INSTALLER`, `top_level.txt`):

- **Name / Version:** `flet-video` **1.0.0** (Metadata-Version 2.4).
- **Summary:** "Cross-platform video playback for Flet apps."
- **License:** `Apache-2.0` (License-Expression; `licenses/LICENSE`, 11357 bytes).
- **Requires-Python:** `>=3.10` (app itself requires `>=3.14`, Python 3.14.7 in venv — OK).
- **Dependency pins:** exactly one — `Requires-Dist: flet==1.0.0` (exact pin).
- **App pin:** `pyproject.toml` declares `"flet-video>=1.0.0"` (floor, unpinned ceiling).
- **Wheel:** pure-Python (`Root-Is-Purelib: true`, `py3-none-any`), built with
  setuptools 84.0.0, installer `uv`.
- **Platform support (per METADATA):** Windows ✅ macOS ✅ Linux ✅ iOS ✅ Android ✅ Web ✅.
- **Linux/WSL note (per METADATA):** needs system libmpv:
  `sudo apt install libmpv-dev libmpv2`, and if `libmpv.so.1` load errors occur,
  `sudo ln -s /usr/lib/x86_64-linux-gnu/libmpv.so /usr/lib/libmpv.so.1`.
- **Entry points:** none (`entry_points` file absent from dist-info — verified via
  `RECORD`, which lists only INSTALLER/METADATA/RECORD/REQUESTED/WHEEL/licenses/
  top_level.txt + package sources). This is a library, not a plugin with entry points.

## Module-by-module API

### `flet_video.video` — `Video`

`class Video(ft.LayoutControl)`, control type name `"Video"`. "A control that displays
a video from a playlist."

#### Properties (all settable; mutated values push to the native player on update)

| Property | Type / Default | Notes |
|---|---|---|
| `playlist` | `list[VideoMedia]`, default `[]` | The queue. A/B compare = 2-item playlist + `jump_to` |
| `title` | `str`, default `"flet-video"` | Native window/process name; visible in Windows volume mixer |
| `fit` | `ft.BoxFit`, default `CONTAIN` | How video fills its box |
| `fill_color` | `ft.ColorValue`, default `ft.Colors.BLACK` | Letterbox/background color |
| `wakelock` | `bool`, default `True` | Keeps display awake while playing |
| `autoplay` | `bool`, default `False` | Start playing on load |
| `controls` | `VideoControls \| ft.Control \| dict[VideoControlsMode, VideoControls \| ft.Control \| None] \| None`, default `AdaptiveVideoControls()` | Built-in preset, custom Flet controls, per-mode dict, or `None` = chromeless. Mode fallback: `FULLSCREEN` → `NORMAL` → `DEFAULT`; a mode value of `None` hides controls for that mode only |
| `fullscreen` | `bool`, default `False` | Set `True`/`False` to enter/exit fullscreen programmatically |
| `muted` | `bool`, default `False` | Start muted |
| `playlist_mode` | `Optional[PlaylistMode]`, default `None` | `NONE`/`SINGLE`/`LOOP` (see types); `None` = native default (stop at end) |
| `shuffle_playlist` | `bool`, default `False` | Shuffle playback order |
| `volume` | `ft.Number`, default `100.0` | **0.0–100.0 inclusive** (NOT 0–1). `before_update()` raises `ValueError` outside range |
| `playback_rate` | `ft.Number`, default `1.0` | Speed multiplier — the speed-control API |
| `alignment` | `ft.Alignment`, default `CENTER` | Viewport alignment |
| `filter_quality` | `ft.FilterQuality`, default `LOW` | Texture filter. **Android shows blurry output with `HIGH`; prefer `MEDIUM`** |
| `pause_upon_entering_background_mode` | `bool`, default `True` | Auto-pause when app backgrounds |
| `resume_upon_entering_foreground_mode` | `bool`, default `False` | Auto-resume on foreground (only if pause-on-background is also `True`) |
| `pitch` | `ft.Number`, default `1.0` | Relative audio pitch |
| `configuration` | `VideoConfiguration`, default `VideoConfiguration()` | Native/libmpv tuning |
| `subtitle_configuration` | `VideoSubtitleConfiguration`, default `…()` | Subtitle rendering style |
| `subtitle_track` | `Optional[VideoSubtitleTrack]`, default `None` | Active subtitle track |

#### Events (all `Optional[ft.ControlEventHandler["Video"]]`, default `None`)

| Event | `e.data` payload |
|---|---|
| `on_load` | — (fired when player initialized and ready; **gate seeks/UI on this**) |
| `on_enter_fullscreen` / `on_exit_fullscreen` | — |
| `on_error` | error info string/object |
| `on_complete` | — (current media finished) |
| `on_track_change` | index of the new track |
| `on_duration_change` | current duration as `ft.Duration` |
| `on_position_change` | current position as `ft.Duration` |

There are **no** buffering/progress events and **no** volume-change event — poll or
push state yourself. Position/duration events are the only telemetry.

#### Async methods (all coroutines — `await` them or `page.run_task`)

```python
await video.play() -> None
await video.pause() -> None
await video.play_or_pause() -> None   # toggle
await video.stop() -> None            # stop + reset; the "dispose-lite" cleanup call
await video.next() -> None            # next VideoMedia in playlist
await video.previous() -> None        # previous VideoMedia
await video.seek(position: ft.DurationValue) -> None   # e.g. seek(ft.Duration(milliseconds=1500))
await video.jump_to(media_index: int) -> None
    # Raises IndexError if out of range. Negative indices normalized (dart has none).
await video.is_playing() -> bool
await video.is_completed() -> bool
await video.get_duration() -> ft.Duration
await video.get_current_position() -> ft.Duration
await video.take_screenshot(
    format: Optional[str] = "image/png",   # "image/png" | "image/jpeg" | None (raw BGRA, native only)
    include_libass_subtitles: bool = False,  # native backends w/ libass only; ignored on web
) -> Optional[bytes]
    # Raises ValueError on unsupported format. Returns None if backend can't capture.
    # This is the thumbnail/poster-frame API (no separate thumbnail function exists).
```

There is **no `dispose()`/`release()` method**. Lifecycle = `await stop()` then drop
the reference (and remove from the view tree). Never leak a playing `Video` across
screen navigations — always `stop()` in the unmount cleanup.

#### Minimal + full example

```python
import flet as ft
import flet_video as ftv


def main(page: ft.Page):
    v = ftv.Video(
        playlist=[ftv.VideoMedia("https://example.com/clip.mp4")],
        autoplay=False,
        volume=80.0,  # 0–100!
        playback_rate=1.0,
        playlist_mode=ftv.PlaylistMode.SINGLE,  # loop for preview replay
        filter_quality=ft.FilterQuality.MEDIUM,  # crisp on Android
        controls=ftv.MaterialVideoControls(seek_gesture=True, seek_on_double_tap=True),
        on_load=lambda e: print("ready"),
        on_error=lambda e: print("player error:", e.data),
        on_position_change=lambda e: print("pos:", e.data),
        on_duration_change=lambda e: print("dur:", e.data),
        on_complete=lambda e: print("done"),
    )
    page.add(
        v,
        ft.Row(
            [
                ft.FilledButton("Play", on_click=lambda _: page.run_task(v.play)),
                ft.FilledButton("Pause", on_click=lambda _: page.run_task(v.pause)),
                ft.FilledButton("Shot", on_click=lambda _: page.run_task(_shot)),
            ]
        ),
    )

    async def _shot():
        png: bytes | None = await v.take_screenshot(format="image/png")
        if png:
            page.set_clipboard("shot taken")  # or write bytes to a file + ft.Image


ft.run(main)
```

### `flet_video.types`

#### `PlaylistMode(Enum)` — `playlist_mode` values

- `NONE = "none"` — stop at end of playlist.
- `SINGLE = "single"` — loop the current file indefinitely (result-preview replay).
- `LOOP = "loop"` — loop whole playlist, restart from top.

#### `VideoControlsMode(Enum)` — keys of the per-mode `controls` dict

- `NORMAL` — non-fullscreen; `FULLSCREEN` — fullscreen; `DEFAULT` — fallback when the
  mode-specific entry is absent. Resolution order FULLSCREEN → NORMAL → DEFAULT.

#### `VideoMedia` (`@ft.value`) — one playlist entry

```python
VideoMedia(
    resource: str,                        # required: URL, absolute local path, or asset path
    http_headers: Optional[dict[str, str]] = None,  # auth headers for remote URLs
    extras: Optional[dict[str, str]] = None,        # passthrough metadata
)
```

Sources = URL / local file / asset via the `resource` string; authenticated streams
via `http_headers` (e.g. `{"Authorization": "Bearer …"}`).

#### `VideoConfiguration` (`@ft.value`) — native tuning

```python
VideoConfiguration(
    output_driver: Optional[str] = None,          # mpv --vo; default libmpv (Win/Linux/macOS/iOS), gpu (Android)
    hardware_decoding_api: Optional[str] = None,  # mpv --hwdec; default auto (auto-safe on Android)
    enable_hardware_acceleration: bool = True,    # False => battery drain / heat / CPU
    width: Optional[ft.Number] = None,            # fixed output width
    height: Optional[ft.Number] = None,           # fixed output height
    scale: ft.Number = 1.0,                       # overrides width/height when set
    mpv_properties: Optional[dict[str, str|int|float|bool]] = None,
    # raw mpv options w/o "--"; bools become yes/no. e.g.:
    # {"profile": "low-latency", "untimed": True, "volume": 80}
    # Full list: https://mpv.io/manual/stable/#options
)
```

#### Bar items (`VideoBarItem` subclasses, `@ft.value`) — compose custom button bars

Base `VideoBarItem` has fixed `_type` (init=False). Concrete items:

- `VideoPlayOrPauseButton(icon_size=None, icon_color=None)`
- `VideoSkipNextButton(icon=None, icon_size=None, icon_color=None)` (+ auto-imply flags)
- `VideoSkipPreviousButton(icon=None, icon_size=None, icon_color=None)`
- `VideoFullscreenButton(icon=None, icon_size=None, icon_color=None)`
- `VideoPositionIndicator(text_style=None)` — time readout
- `VideoSpacer(flex: int = 1)` — layout spacer
- `VideoVolumeButton(icon_size=None, icon_color=None, volume_mute_icon=None, volume_low_icon=None, volume_high_icon=None, slider_width=None)` — **rendered ONLY by `MaterialDesktopVideoControls`**; silently absent in touch `MaterialVideoControls`.

Custom bar example (mirrors the documented native defaults):

```python
controls = ftv.MaterialVideoControls(
    primary_button_bar=[
        ftv.VideoSpacer(flex=2),
        ftv.VideoSkipPreviousButton(),
        ftv.VideoSpacer(),
        ftv.VideoPlayOrPauseButton(icon_size=48.0),
        ftv.VideoSpacer(),
        ftv.VideoSkipNextButton(),
        ftv.VideoSpacer(flex=2),
    ],
    bottom_button_bar=[
        ftv.VideoPositionIndicator(),
        ftv.VideoSpacer(),
        ftv.VideoFullscreenButton(),
    ],
)
```

Any `ft.Control` may be mixed into the bar lists. Empty list `[]` hides that bar;
`None` keeps the native default.

#### `MaterialVideoControls` (`@ft.value`) — touch-first (phones/tablets)

Behavior flags (all `bool` unless noted): `display_seek_bar=True`,
`automatically_imply_skip_next_button=True`, `automatically_imply_skip_previous_button=True`,
`volume_gesture=False` (right-edge vertical drag → volume),
`brightness_gesture=False` (left-edge vertical drag → brightness),
`seek_gesture=False` (horizontal drag → seek),
`gestures_enabled_while_controls_visible=True`,
`seek_on_double_tap=False` (+ `seek_on_double_tap_enabled_while_controls_visible=True`,
`seek_on_double_tap_layout_taps_ratios=[1,1,1]`,
`seek_on_double_tap_layout_widget_ratios=[1,1,1]`,
`seek_on_double_tap_backward_duration=10000` ms, `seek_on_double_tap_forward_duration=10000` ms),
`visible_on_mount=False`, `speed_up_on_long_press=False` (+ `speed_up_factor=2.0`),
`vertical_gesture_sensitivity=100`, `horizontal_gesture_sensitivity=1000`
(higher = less sensitive), `backdrop_color="#66000000"`.
Generic: `padding=None`, `controls_hover_duration=3000` ms, `controls_transition_duration=300` ms,
`initial_volume=0.5`, `initial_brightness=0.5` (both 0–1 gesture-indicator seeds).
Bars/seek-bar/subtitle styling: `primary_button_bar` (default: spacer/prev/play/next
cluster shown above), `top_button_bar=None→[]`, `top_button_bar_margin=symmetric(h=16)`,
`bottom_button_bar` (default: position indicator + spacer + fullscreen),
`bottom_button_bar_margin=only(left=16,right=8)`, `button_bar_height=56`,
`button_bar_button_size=24`, `button_bar_button_color="#FFFFFFFF"`,
`seek_bar_margin=0`, `seek_bar_height=2.4`, `seek_bar_container_height=36`,
`seek_bar_color="#3DFFFFFF"`, `seek_bar_position_color="#FFFF0000"`,
`seek_bar_buffer_color="#3DFFFFFF"`, `seek_bar_thumb_size=12.8`,
`seek_bar_thumb_color="#FFFF0000"`, `seek_bar_alignment=BOTTOM_CENTER`,
`shift_subtitles_on_controls_visibility_change=False`.

#### `MaterialDesktopVideoControls` (`@ft.value`) — desktop-first

`display_seek_bar=True`, auto-imply skip next/prev `True`,
`modify_volume_on_scroll=True`, `toggle_fullscreen_on_double_press=True`,
`hide_mouse_on_controls_removal=False`, `play_and_pause_on_tap=False`,
`visible_on_mount=False`; `padding=None`, hover `3000` ms, transition `150` ms;
`primary_button_bar=None→[]`, `top_button_bar=None→[]`, `top_button_bar_margin=symmetric(h=16)`,
`bottom_button_bar` default = prev + play/pause + next + spacer + position + fullscreen + **volume**,
margin symmetric(h=16), height 56, button size 28, color white;
seek-bar extras vs touch: `seek_bar_transition_duration=300`,
`seek_bar_thumb_transition_duration=150`, margin symmetric(h=16), height 3.2,
hover height 5.6, container 36, colors as touch + `seek_bar_hover_color`;
volume-bar styling: `volume_bar_color`, `volume_bar_active_color="#FFFFFFFF"`,
`volume_bar_thumb_size=12`, `volume_bar_thumb_color="#FFFFFFFF"`,
`volume_bar_transition_duration=150`; `shift_subtitles_on_controls_visibility_change=True`.

#### `AdaptiveVideoControls` (`@ft.value`) — the default `controls` value

Selects at runtime by `page.platform`: Android/iOS → Material; macOS/Windows/Linux →
MaterialDesktop; other platforms → no built-in controls.

```python
AdaptiveVideoControls(
    material: Optional[MaterialVideoControls] = None,               # phone config override
    material_desktop: Optional[MaterialDesktopVideoControls] = None, # desktop config override
)
```

#### `VideoSubtitleTrack` (`@ft.value`)

```python
VideoSubtitleTrack(
    src: str,  # required. URL ("https://…/s.vtt"), absolute local path (NOT on web), or raw SRT/VTT text
    title: Optional[str] = None,        # e.g. "English"
    language: Optional[str] = None,     # e.g. "en"
    # -- probe/media override fields (all Optional, default None) --
    channels_count: Optional[int], channels: Optional[str], sample_rate: Optional[int],
    fps: Optional[ft.Number], bitrate: Optional[int], rotate: Optional[int],
    par: Optional[ft.Number], audio_channels: Optional[int], album_art: Optional[bool],
    codec: Optional[str], decoder: Optional[str],
)
VideoSubtitleTrack.none()  # src="none" — disable subtitles
VideoSubtitleTrack.auto()  # src="auto" — first track
```

#### `VideoSubtitleConfiguration` (`@ft.value`)

```python
VideoSubtitleConfiguration(
    text_style: ft.TextStyle = TextStyle(height=1.4, size=32, letter_spacing=0,
                                         word_spacing=0, color=WHITE, weight=NORMAL,
                                         bgcolor=BLACK_54),
    text_scale_factor: ft.Number = 1.0,
    text_align: ft.TextAlign = ft.TextAlign.CENTER,
    padding = Padding(left=16, top=0, right=16, bottom=24),
    visible: bool = True,
)
```

## App usage & correctness

Only two screens use `flet_video`, both lazily (`try: import flet_video as ftv`
+ `_HAS_VIDEO` guard — correct pattern for a desktop/mobile optional dep).
`convert_screen.py` / `compress_screen.py` have **zero** preview usage (grep-verified).
All `engine_service.py` `.seek(` hits are PyAV container seeks — unrelated.

### (a) Correct usage worth keeping

- Lazy import with `_HAS_VIDEO` fallback UI (`cut_screen.py:22-27`,
  `result_screen.py:31-36`).
- Stable player instance held in `ft.use_ref`, built once — no rebuild-per-render
  (`cut_screen.py:103`, `result_screen.py:133`).
- `autoplay=False` on both previews — no surprise audio.
- `filter_quality=ft.FilterQuality.MEDIUM` — the documented Android-safe choice.
- Throttled scrub seeks (0.3 s window, `cut_screen.py:79-84`) — right instinct; native
  `seek` storms would stutter.
- `stop()` in the effect cleanup (`cut_screen.py:86-97,131`;
  `result_screen.py:92-103,163-167`) — the correct no-`dispose()` lifecycle.
- A/B compare via 2-item playlist + `jump_to(idx)` with `IndexError` guard
  (`result_screen.py:73-90`) — textbook use of the playlist API.
- `on_error` wired on the result preview (`result_screen.py:137`).

### (b) Misuse / bugs (file:line)

1. **`result_screen.py:128` — stale preview across consecutive jobs (real bug).**
   `_mount_players` only builds when `video_ref.current is None`, but the effect
   re-runs per `job.id` (`:163-167`) while cleanup (`_stop_video_player`) never resets
   `video_ref.current = None`. Job #2 reuses job #1's player *and playlist* — user sees
   the previous output. Fix: in cleanup (or before rebuild) `await v.stop()` then set
   `video_ref.current = None` so the new job mounts a fresh playlist. (Audio side already
   does this correctly at `:109`.)
2. **`cut_screen.py:99-111 + :131` — scrub preview never follows a new file (real bug).**
   `_mount_scrub` early-returns when `scrub_ref.current is not None` and the effect has
   `[]` deps, so pressing "Change" (`:203`) leaves the old file's player mounted while
   duration/thumbs update. Fix: key the effect on `media_path`, `stop()` + reset ref,
   rebuild playlist.
3. **`cut_screen.py:103-107` — scrub player keeps default `AdaptiveVideoControls`.**
   A chromeless scrub (`controls=None`) is wanted here: visible play/pause competes with
   programmatic `_scrub_to` seeks and the container is only 160px tall (`:292`), where
   full Material bars cover the frame being judged. Same for the A/B player only if you
   add external transport buttons — otherwise keep built-ins there.
4. **`cut_screen.py:103-107` — no `on_error`, and `scrub_ready` is set at construction,
   not on `on_load`.** A missing-codec file leaves "Loading preview…" replaced by a dead
   frame, and seeks issued before the native backend is ready fail into the
   `logger.debug` swallower (`:74-77`). Fix: `on_load=lambda e: set_scrub_ready(True)`,
   `on_error=…` → error placeholder text.
5. **`result_screen.py:264-271` — "Original" segment shown even for single-item playlists.**
   When `job.input_path` is missing, playlist has 1 entry (`:130-132`) and tapping
   "Original" fires a doomed `jump_to(1)` (caught `IndexError`, `:84-86`, but the UI
   implies it worked). Fix: only render the `SegmentedButton` when `len(playlist) == 2`.
6. **`result_screen.py:148` — fragile audio-event attribute access.**
   `getattr(e, "position", 0)` / `e.duration.in_milliseconds` assume flet-audio event
   shape; the *video* preview has no `on_position_change`/`on_duration_change` at all,
   so `pos_ms`/`dur_ms` state never reflects video playback. (Carried as underuse #3.)
7. **Playing during queue jobs (both screens).** `_start_cut` (`cut_screen.py:144-164`)
   never pauses/stops the scrub player; navigating to results while the result preview
   plays keeps decoding under an active FFmpeg encode — CPU/battery contention on mobile.
   Fix: `await v.pause()` (or `stop()`) when a job starts / on navigate-away.
8. **Fire-and-forget `page.run_task(_stop)` in cleanups** (`cut_screen.py:97`,
   `result_screen.py:103`) is acceptable (stop is idempotent) but un-awaited — under
   rapid screen churn a stopped player can briefly linger; prefer awaiting where the
   component framework allows.

### Underused APIs — what v1 should adopt (mapped to the rewrite)

Covered in detail in the next section; the headline list: `controls=None` chromeless
scrub, `on_load` gating, video `on_position_change`/`on_duration_change` transport,
`take_screenshot` thumbnails, `playback_rate` slow-mo verification,
`PlaylistMode.SINGLE` preview loop, `on_track_change` A/B sync + `next`/`previous`,
mpv `VideoConfiguration` low-latency scrub profile, subtitle track/config preview,
fullscreen + background-mode policies, per-mode `controls` dict.

## Underused APIs to adopt

1. **`controls=None` (chromeless) for the cut scrubber** — `cut_screen.py:103`.
   External RangeSlider + chips are already the transport; built-ins fight them.
2. **`on_load`** — gate `scrub_ready` and first seek on it (both screens); eliminates
   pre-ready seek failures.
3. **Video `on_position_change` / `on_duration_change`** — result screen has the state
   (`pos_ms`/`dur_ms`) but wires it only to the audio player. Add both handlers to the
   `ftv.Video` + a `Slider` (mirror the existing audio slider at
   `result_screen.py:347-354`) for output verification scrubbing.
4. **`take_screenshot(format="image/png")`** — replace/augment engine thumbnail strips
   for instant poster frames; verify cut boundaries visually without re-decode. No other
   thumbnail API exists — this *is* it.
5. **`playback_rate`** — 0.25×/0.5× slow-mo toggle on the cut screen to verify
   frame-accurate re-encode cuts; long-press speedup already exists in
   `MaterialVideoControls(speed_up_on_long_press=True, speed_up_factor=2.0)`.
6. **`PlaylistMode.SINGLE`** on the result preview — loop the output until the user
   acts; `LOOP` for the A/B pair.
7. **`on_track_change` + `next()`/`previous()`** — sync the Output/Original
   `SegmentedButton` to actual track state instead of assumed indices.
8. **`VideoConfiguration(mpv_properties={"profile": "low-latency"})`** for the scrub
   player; `enable_hardware_acceleration=True` (default) is already right for
   battery — assert it, don't unset it.
9. **`VideoSubtitleTrack` / `VideoSubtitleConfiguration`** — result screen for
   `extract_subtitles` jobs currently shows only an icon (`result_screen.py:234-236`);
   preview the extracted track over the output video.
10. **Fullscreen + background policy** — `fullscreen=True` w/ `on_enter/exit_fullscreen`
    for result review; `MaterialVideoControls(seek_gesture=True,
    seek_on_double_tap=True)` for mobile cut verification; keep
    `pause_upon_entering_background_mode=True` (default) so previews never play blind.

## Gotchas

- `volume` is **0–100**, not 0–1 (`ValueError` from `before_update` otherwise);
  gesture seeds `initial_volume`/`initial_brightness` are 0–1 — don't mix them up.
- Every transport method is **async**: `await v.play()` / `page.run_task(v.play)` —
  calling without await silently does nothing useful.
- `jump_to` raises `IndexError` out of range but **normalizes negatives** — don't
  pre-convert; do catch.
- `take_screenshot(format=None)` = raw BGRA (native only); `ValueError` on anything
  but `"image/png"`/`"image/jpeg"`/`None`; may return `None` on web — always null-check.
- `VideoVolumeButton` renders **only** under `MaterialDesktopVideoControls`.
- `filter_quality=HIGH` blurs on Android — `MEDIUM` is the ceiling there.
- Linux/WSL needs system `libmpv` (see Metadata); subtitle `src` as absolute path is
  **not supported on web** (use URL or raw text).
- Per-mode `controls` dict fallback is FULLSCREEN → NORMAL → DEFAULT; `None` for one
  mode hides just that mode.
- No `dispose()` exists: `stop()` + deref + unmount is the full lifecycle. No buffering
  events exist: use `on_load` + `on_error` to bracket readiness.
- `title` leaks into the OS volume mixer — set a user-meaningful name per preview.
- `seek()` takes `ft.DurationValue` (`ft.Duration(milliseconds=…)`), not seconds.
