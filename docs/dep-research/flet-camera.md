# flet-camera 1.0.0 — Complete API Reference

> Package: `flet-camera` 1.0.0 — "Camera control for Flet apps", powered by the
> [`camera`](https://pub.dev/packages/camera) Flutter package.
> Docs: https://flet.dev/docs/controls/camera ·
> Repo: https://github.com/flet-dev/flet/tree/main/sdk/python/packages/flet-camera
> Verified against installed source on 2026-09-23 (Flet 1.0.0, Python 3.14, uv venv).

## Files

Package dir: `<repo>\.venv\Lib\site-packages\flet_camera`

| File | Purpose |
|---|---|
| `__init__.py` | Public re-exports only (713 bytes) |
| `camera.py` | `Camera` control: 1 control class, 2 props, 2 events, 26 async methods |
| `types.py` | 7 enums, 2 `@ft.value` dataclasses, 2 event dataclasses |
| `utils.py` | `detect_video_extension()` magic-byte sniffer (627 bytes) |
| `__pycache__/*.cpython-314.pyc` | Bytecode cache — ignore |

Flutter (Dart) side, bundled under site-packages (not in `flet_camera/`, listed in
`RECORD` from the wheel but installed to the shared frontend dir):

- `<repo>\.venv\Lib\site-packages\flutter\flet_camera\lib\flet_camera.dart`
- `.../lib/src/camera.dart`
- `.../lib/src/extension.dart`
- `.../lib/src/utils/camera.dart`
- `.../lib/src/pubspec.yaml` (wait — actual path is `flutter/flet_camera/pubspec.yaml`)

**Native assets:** none in the Python package — pure-Python control + Dart
frontend. No `.so`/`.dll`/`.bin`, no bundled ML models, no data files.
`RECORD` confirms the wheel ships only the 3 `.py` files, the 5 Flutter files,
`LICENSE`, and dist-info files. No entry points (no `entry_points.txt` exists).

## Metadata

From `flet_camera-1.0.0.dist-info\METADATA` (+ `WHEEL`, `top_level.txt`, `INSTALLER`):

| Field | Value |
|---|---|
| Name / Version | `flet-camera` / `1.0.0` |
| Summary | `Camera control for Flet apps.` |
| License | `Apache-2.0` (`License-Expression`, `License-File: LICENSE`) |
| Author | Flet contributors `<hello@flet.dev>` |
| Requires-Python | `>=3.10` (app runs 3.14 — fine) |
| Requires-Dist | **`flet==1.0.0` (exact pin)** — camera 1.0.0 only works with Flet 1.0.0 |
| Wheel | `py3-none-any`, purelib, built by `setuptools (84.0.0)` |
| Installer | `uv` |
| `top_level.txt` | `flet_camera`, `flutter` |
| `REQUESTED` | empty (0 bytes — pulled in as transitive dep) |
| App pin | `pyproject.toml` declares `flet-camera>=1.0.0` (loose; installed 1.0.0 matches) |

Platform support (from METADATA long description):

| iOS | Android | Web | Windows | macOS | Linux |
|---|---|---|---|---|---|
| ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |

Desktop raises at runtime: `Camera.before_update()` raises
`ft.FletUnsupportedPlatformException("Camera is currently only supported on
Android, iOS and Web platforms.")` unless `page.web` or platform is
Android/iOS. There is no `entry_points.txt` — no plugins/console scripts.

Permissions note (METADATA): camera/mic need **runtime** permissions; the
package itself requests none — use `flet-permission-handler` to request
`CAMERA` (and `MICROPHONE` when `enable_audio=True`) *before* `initialize()`.

## Module-by-module API

### `flet_camera/__init__.py` — exports

```python
from flet_camera.camera import Camera
from flet_camera.types import (
    CameraDescription,
    CameraImageEvent,
    CameraLensDirection,
    CameraLensType,
    CameraPreviewSize,
    CameraStateEvent,
    ExposureMode,
    FlashMode,
    FocusMode,
    ImageFormatGroup,
    ResolutionPreset,
)
from flet_camera.utils import detect_video_extension
```

`__all__` = the 13 names above. Import as `import flet_camera as ftc`.

### `flet_camera/camera.py` — `Camera(ft.LayoutControl)`

Registered as `@ft.control("Camera")`. Inherits all `LayoutControl`/
`Control` layout props (size, padding, expand, opacity, …) plus:

**Properties**

```python
preview_enabled: bool = True  # show the preview surface
content: Optional[ft.Control] = None  # child overlaid on top of preview
```

**Events**

```python
on_state_change: Optional[ft.EventHandler[CameraStateEvent]] = None
# Fires when the camera controller state changes (init done, recording
# started/stopped/paused, preview paused, error, orientation/mode change).

on_stream_image: Optional[ft.EventHandler[CameraImageEvent]] = None
# Fires per frame while image streaming is active (see start_image_stream).
```

**Methods — discovery & init**

```python
async def get_available_cameras(self) -> list[CameraDescription]
# Lists camera devices. Returns [] when none. Call on a mounted control
# (after it is in the page tree) before initialize().

async def initialize(
    self,
    description: CameraDescription,      # device from get_available_cameras()
    resolution_preset: ResolutionPreset, # REQUIRED, no default
    enable_audio: bool = True,           # audio track for video recordings
    fps: Optional[int] = None,           # target frames per second
    video_bitrate: Optional[int] = None, # video bitrate override
    audio_bitrate: Optional[int] = None, # audio bitrate override
    image_format_group: Optional[ImageFormatGroup] = None,
) -> None                                # returns None (await completes on ready)
```

**Methods — photo**

```python
async def take_picture(self) -> bytes   # still capture → encoded image bytes
```

**Methods — video recording** (call order: `prepare_for_video_recording()` →
`start_video_recording()` … `pause/resume` … `stop_video_recording()`)

```python
async def prepare_for_video_recording(self) -> None
async def start_video_recording(self) -> None
async def pause_video_recording(self) -> None
async def resume_video_recording(self) -> None
async def stop_video_recording(self) -> bytes  # → encoded VIDEO FILE bytes
# NOTE: returns raw bytes, not a path. Pair with detect_video_extension()
# to pick .mp4/.mov/.webm before writing to disk.
```

**Methods — image streaming** (frame-by-frame, delivered via `on_stream_image`)

```python
async def supports_image_streaming(self) -> bool
async def start_image_stream(self) -> None
async def stop_image_stream(self) -> None
```

**Methods — preview**

```python
async def pause_preview(self) -> None
async def resume_preview(self) -> None
```

**Methods — camera selection**

```python
async def set_description(self, description: CameraDescription) -> None
# Hot-switch front/back/external without rebuilding the control.
```

**Methods — flash / focus / exposure**

```python
async def set_flash_mode(self, mode: FlashMode) -> None
async def set_focus_mode(self, mode: FocusMode) -> None
async def set_focus_point(self, point: Optional[ft.OffsetValue]) -> None
# Normalized 0..1 offset, or None to reset to center/default.

async def set_exposure_mode(self, mode: ExposureMode) -> None
async def set_exposure_offset(self, offset: float) -> float  # EV units, echoes value set
async def set_exposure_point(self, point: Optional[ft.OffsetValue]) -> None
# Normalized 0..1 offset, or None to reset.
```

**Methods — zoom & capability queries**

```python
async def set_zoom_level(self, zoom: float) -> None
async def get_min_zoom_level(self) -> float
async def get_max_zoom_level(self) -> float
async def get_min_exposure_offset(self) -> float
async def get_max_exposure_offset(self) -> float
async def get_exposure_offset_step_size(self) -> float
```

**Methods — orientation**

```python
async def lock_capture_orientation(
    self, orientation: Optional[ft.DeviceOrientation] = None) -> None
# None = lock to current device orientation.
async def unlock_capture_orientation(self) -> None
```

**Exceptions:** methods raise via `_invoke_method` on platform failure
(camera in use, permission denied at OS level, unsupported preset, recording
state violations such as stop-without-start). `before_update()` raises
`ft.FletUnsupportedPlatformException` on desktop (Windows/macOS/Linux
non-web). No package-specific exception types — catch `Exception`.

**Minimal example (photo):**

```python
import flet as ft
import flet_camera as ftc


async def main(page: ft.Page):
    cam = ftc.Camera(on_state_change=lambda e: print(e.is_initialized))
    await page.add_async(cam)
    cameras = await cam.get_available_cameras()
    back = next(c for c in cameras if c.lens_direction == ftc.CameraLensDirection.BACK)
    await cam.initialize(back, ftc.ResolutionPreset.HIGH, enable_audio=False)
    data: bytes = await cam.take_picture()
    Path("photo.jpg").write_bytes(data)
```

**Video example:**

```python
await cam.prepare_for_video_recording()
await cam.start_video_recording()
...
raw: bytes = await cam.stop_video_recording()
ext = ftc.detect_video_extension(raw)  # "mp4" | "mov" | "webm" | "bin"
Path(f"clip.{ext}").write_bytes(raw)
```

### `flet_camera/types.py` — enums, values, events

```python
class ResolutionPreset(Enum):  # REQUIRED arg of initialize()
    LOW = "low"  # small / fast — previews, low-end devices
    MEDIUM = "medium"
    HIGH = "high"  # good default for photos
    VERY_HIGH = "veryHigh"
    ULTRA_HIGH = "ultraHigh"
    MAX = "max"  # sensor maximum; may fail on some devices


class ImageFormatGroup(Enum):  # initialize(image_format_group=…)
    BGRA8888 = "bgra8888"  # raw frames (streaming/processing)
    JPEG = "jpeg"  # compressed stills
    NV21 = "nv21"  # Android YUV
    YUV420 = "yuv420"  # planar YUV
    UNKNOWN = "unknown"


class FlashMode(Enum):
    OFF = "off"
    AUTO = "auto"
    ALWAYS = "always"
    TORCH = "torch"


class ExposureMode(Enum):
    AUTO = "auto"
    LOCKED = "locked"


class FocusMode(Enum):
    AUTO = "auto"
    LOCKED = "locked"


class CameraLensDirection(Enum):
    FRONT = "front"
    BACK = "back"
    EXTERNAL = "external"


class CameraLensType(Enum):
    WIDE = "wide"
    TELEPHOTO = "telephoto"
    ULTRA_WIDE = "ultraWide"
    UNKNOWN = "unknown"
```

```python
@ft.value
class CameraPreviewSize:
    width: ft.Number  # logical pixels
    height: ft.Number  # logical pixels


@ft.value
class CameraDescription:  # one entry from get_available_cameras()
    name: str  # human-readable device id
    lens_direction: CameraLensDirection
    sensor_orientation: int  # 0 | 90 | 180 | 270
    lens_type: CameraLensType = CameraLensType.UNKNOWN
```

```python
@dataclass
class CameraStateEvent(ft.Event["Camera"]):
    # Fires on EVERY controller change — the single source of truth.
    is_initialized: bool
    is_recording_video: bool
    is_recording_paused: bool
    is_taking_picture: bool
    is_streaming_images: bool
    is_preview_paused: bool
    is_capture_orientation_locked: bool
    device_orientation: Optional[ft.DeviceOrientation] = None
    locked_capture_orientation: Optional[ft.DeviceOrientation] = None
    recording_orientation: Optional[ft.DeviceOrientation] = None
    preview_pause_orientation: Optional[ft.DeviceOrientation] = None
    flash_mode: Optional[FlashMode] = None
    exposure_mode: Optional[ExposureMode] = None
    focus_mode: Optional[FocusMode] = None
    exposure_point_supported: Optional[bool] = None
    focus_point_supported: Optional[bool] = None
    preview_size: Optional[CameraPreviewSize] = None
    aspect_ratio: Optional[ft.Number] = None
    error_description: Optional[str] = None
    has_error: Optional[bool] = None
    description: Optional[CameraDescription] = None
```

```python
@dataclass
class CameraImageEvent(ft.Event["Camera"]):  # per-frame, via on_stream_image
    width: int
    height: int
    format: Optional[ImageFormatGroup]
    encoded_format: str  # e.g. "jpeg"
    bytes: bytes  # encoded frame bytes
    lens_aperture: Optional[ft.Number] = None
    sensor_exposure_time: Optional[int] = None  # nanoseconds
    sensor_sensitivity: Optional[ft.Number] = None  # ISO
```

### `flet_camera/utils.py`

```python
def detect_video_extension(data: bytes) -> str:
    """Sniff container magic bytes → "webm" | "mov" | "mp4" | "bin" (unknown).
    EBML header 1A 45 DF A3 → webm; ftyp box → mov iff brand == b"qt  "
    else mp4. App must handle "bin" (fallback to "mp4" + probe-validate)."""
```

## App usage & correctness

Only consumer: `src/screens/capture_screen.py` (guarded `import flet_camera
as ftc`, `_HAS_CAMERA` flag). Permission plumbing via `flet-permission-handler`
in `src/main.py:253-254` (`PermissionHandler` service) and the JIT flow in
`capture_screen.py:235-253`. Tests: `tests/test_capture_helpers.py` covers only
`next_permission_action`/`_write_wav`/`_pcm_rms`/`_can_capture` — **no test
touches any `flet_camera` API**.

**(a) Correct usage**

- Desktop guard `_can_capture()` (`capture_screen.py:117-123`) mirrors the
  package's `before_update` platform guard; desktop shows pick-a-file fallback.
- JIT permission: `_permission_ok()` (`:235-253`) checks → requests → rationale
  (`_perm_rationale`, `:197-233`) → Settings deep link. Correct ordering:
  permission *before* `Camera()` creation (`_prepare_camera`, `:267-280`).
- `on_state_change` wired at construction (`:276`) and surfaces
  `has_error`/`error_description` to a snackbar (`:257-265`).
- Photo bytes written to temp and probed via `EngineService.probe`
  (`:372-375`, `:341-357`) — validates before staging.
- Video bytes + `detect_video_extension()` with `"bin"`→`"mp4"` fallback
  (`:391-396`) — correct pairing of `stop_video_recording()` with the sniffer.
- `prepare_for_video_recording()` → `start_video_recording()` ordering (`:418-419`)
  and pause/resume symmetry (`:429-440`) are correct.

**(b) Misuse / bugs (file:line)**

1. `capture_screen.py:291` — `initialize(cameras[0], HIGH, enable_audio=True)`
   runs for **photo mode too**, yet `_prepare_camera` (`:273`) requests only
   `Permission.CAMERA`. `enable_audio=True` arms the mic path without ever
   requesting `MICROPHONE`. Same hole on the video path — mic permission is
   only requested for the separate mic-recorder flow (`:503`). Fix: pass
   `enable_audio=(mode == "video")` (False for photos), and request
   `MICROPHONE` before video init.
2. `capture_screen.py:291` — always `cameras[0]`. No `lens_direction` check:
   on devices where index 0 is the front camera the app silently shoots selfies.
   Fix: prefer `BACK`, fall back to `[0]`.
3. `capture_screen.py:291` — hardcoded `ResolutionPreset.HIGH`. No quality
   option (LOW/MEDIUM for slow devices, MAX for pro shots); init may fail on
   low-end hardware with no fallback retry at a lower preset.
4. `capture_screen.py:160-163` — unmount `_cleanup()` only stops the ticker.
   The camera controller is never paused/disposed (`pause_preview()` never
   called); navigating away leaves the camera running (battery + privacy).
   `camera_inited_ref` is also never reset, so a stale controller is reused.
5. `capture_screen.py:257-265` — `_on_camera_state` reads only 3 of 21 fields
   (`has_error`, `is_recording_video`, `is_recording_paused`). It ignores
   `is_initialized` (ready-gating is done via the ad-hoc `camera_inited_ref`
   instead), `is_taking_picture` (double-tap can overlap captures; only the
   local `busy` flag guards), `is_preview_paused`, and
   `flash/exposure/focus_mode` echoes. Local `set_recording()` calls (`:402`,
   `:420`, `:425`, `:492`) duplicate what the event already reports — single
   source of truth should be the event.
6. `capture_screen.py:373` — photo bytes hardcoded to `.jpg`. `take_picture()`
   encoding follows `image_format_group` (never set); if the platform returns
   non-JPEG bytes the extension lies. Sniff or set `ImageFormatGroup.JPEG`.
7. `capture_screen.py:372` — no `is_taking_picture` guard: rapid taps queue
   overlapping `take_picture()` calls behind only the local `busy` flag, which
   is also set during unrelated video/mic work.
8. `capture_screen.py:651-683` — preview container is fixed `height=300`;
   `preview_size`/`aspect_ratio` from the state event are never used, so the
   preview can stretch. Size the container from the event.
9. `capture_screen.py:651` — `Camera` is constructed with no `content` overlay
   and default `preview_enabled=True`; recording timer is a separate header
   instead of an overlay — cosmetic, but the overlay prop exists for this.

**(c) Underuse — APIs never called** (grep confirms only `Camera`,
`ResolutionPreset.HIGH`, `detect_video_extension` are used): `set_description`
(front/back switch), `set_flash_mode` (+ `TORCH`), `set_zoom_level` +
`get_min/max_zoom_level`, `set_focus_mode`/`set_focus_point`,
`set_exposure_mode`/`set_exposure_offset` (+ min/max/step queries),
`set_exposure_point`, `supports_image_streaming`/`start/stop_image_stream` +
`on_stream_image`, `pause/resume_preview`, `lock/unlock_capture_orientation`,
`fps`/`video_bitrate`/`audio_bitrate`/`image_format_group` init params,
`preview_enabled`/`content`, `CameraLensType`, `CameraPreviewSize`/`aspect_ratio`.

## Underused APIs to adopt

For the v1 rewrite, in priority order:

1. **`set_description()` + `CameraLensDirection`** — front/back toggle. List
   cameras, split by `lens_direction`, add a switch button. Highest-value gap.
2. **`initialize(enable_audio=False)` for photo mode** (+ request `MICROPHONE`
   only for video) — fixes misuse #1, avoids needless mic permission prompts.
3. **`set_flash_mode()` (`OFF/AUTO/ALWAYS/TORCH`)** — flash cycle button +
   torch toggle for video. Read back `flash_mode` from `CameraStateEvent`.
4. **`set_zoom_level()` + `get_min/max_zoom_level()`** — pinch/slider zoom;
   clamp with the queried range. Zero app support today.
5. **`CameraStateEvent.is_initialized`** — replace `camera_inited_ref` with the
   event as ready-gate; also honor `is_taking_picture` to block overlapping
   captures and `is_preview_paused` for UI state.
6. **`pause_preview()` / `resume_preview()`** — pause on navigate-away /
   app-background; resume on return (fixes misuse #4).
7. **`ResolutionPreset` choice + fallback** — expose quality setting
   (MEDIUM default on low-end, HIGH/MAX option); retry init one preset lower on
   `initialize()` failure instead of erroring out.
8. **`fps` / `video_bitrate` / `audio_bitrate` init params** — wire to the
   app's existing quality/verdict logic for predictable output sizes.
9. **`on_stream_image` + `start/stop_image_stream` (+ `supports_image_streaming`
   gate)** — live frame access for a real viewfinder meter/QR-style preview;
   check support first, always `stop_image_stream()` on unmount.
10. **`content` overlay + `preview_size`/`aspect_ratio`** — timer/level overlays
    on the preview; aspect-correct preview sizing instead of fixed height 300.
11. **Focus/exposure controls** (`set_focus_mode/point`, `set_exposure_mode/
    offset/point`, `lock_capture_orientation`) — tap-to-focus and EV slider for
    the pro path; gate tap-to-focus UI on `focus_point_supported` /
    `exposure_point_supported` from the state event.

## Gotchas

- **`stop_video_recording()` returns bytes, not a path.** Large videos live in
  memory until written — write to temp immediately, then probe (the app already
  does this right). Always run `detect_video_extension()` and handle `"bin"`.
- **`initialize()` needs a mounted control.** `get_available_cameras()` and
  `initialize()` are `_invoke_method` calls — the `Camera` must be in the page
  tree. The app's `camera_ready` → effect chain (`:297-308`) satisfies this;
  don't `await cam.initialize()` on a detached instance.
- **`resolution_preset` is required positional** — no default. Passing `MAX`
  can fail per-device; always have a lower-preset retry.
- **`enable_audio=True` (the default!) implies mic permission.** The most
  likely v1 crash: photo init with default audio on a mic-denied device. Pass
  explicitly per mode.
- **Desktop raises, it doesn't no-op.** `before_update()` throws
  `FletUnsupportedPlatformException` on Windows/macOS/Linux non-web — keep the
  `_can_capture()` gate on every path that mounts `Camera`.
- **All methods are async.** Every camera call must be awaited inside
  `page.run_task(...)` handlers, never called synchronously from build.
- **State events are the source of truth** — `is_recording_video`,
  `is_recording_paused`, `is_initialized` arrive via `on_state_change`; don't
  mirror them with local flags that can drift (current `recording`/`busy`
  duplication).
- **No teardown method exists** on `Camera` — the only lifecycle tools are
  `pause_preview()`/`stop_image_stream()`/unmount. Pausing on navigation is
  mandatory, not optional.
- **Image streaming is platform-gated** — always check
  `supports_image_streaming()` before `start_image_stream()`; frames arrive on
  `on_stream_image` as `CameraImageEvent` (check `encoded_format` before
  decoding `bytes`).
- **Exact pin `flet==1.0.0`.** Upgrading Flet without upgrading `flet-camera`
  (and vice versa) breaks the control channel; keep them locked together.
- **Zero camera-API test coverage.** `tests/test_capture_helpers.py` covers
  permission mapping/WAV/RMS only — add mocked-`Camera` tests for
  init→capture→finalize, the `"bin"` fallback, and the permission-denied paths.
