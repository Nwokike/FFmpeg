# flet-audio-recorder 1.0.0 — Complete API Reference

> Package purpose: on-device microphone recording for Flet apps (Service control
> backed by the Flutter `record` plugin). Supports file recording in 9 encoders,
> raw PCM16 streaming (`on_stream`), direct-to-URL streaming uploads, pause/resume,
> permission probing, encoder/device capability queries, and per-platform tuning.
> All platforms supported: Windows, macOS, Linux (needs separate `fmedia` install),
> iOS, Android, Web.

## Files

Python package dir (`.../site-packages/flet_audio_recorder/`) — pure-Python, 3 files:

| File | Contents |
|---|---|
| `__init__.py` | Re-exports `AudioRecorder` + 12 types; defines `__all__` |
| `audio_recorder.py` | `AudioRecorder` Service control (4 props, 9 async methods) |
| `types.py` | 12 public types: 3 events, 2 config values, 3 enums + iOS/Android config |

No `__pycache__` / `.pyc` shipped (only build artifacts in the venv). No
`entry_points.txt` in dist-info — this is an ft-control package, not a console plugin.

Native/Flutter shim (NOT inside the Python package — bundled at
`.../site-packages/flutter/flet_audio_recorder/`):

| File | Role |
|---|---|
| `lib/flet_audio_recorder.dart` | Dart barrel export |
| `lib/src/audio_recorder.dart` | Method-channel bridge for all 9 methods + 3 events |
| `lib/src/extension.dart` | Flet control registration (`@ft.control("AudioRecorder")` counterpart) |
| `lib/src/utils/audio_recorder.dart` | PCM/upload helpers |
| `pubspec.yaml` | Depends on Flutter `record` package |

## Metadata

Source: `flet_audio_recorder-1.0.0.dist-info/METADATA` (Metadata-Version 2.4).

- **Name / Version:** `flet-audio-recorder` 1.0.0
- **Summary:** "Adds audio recording support to Flet apps."
- **License:** `Apache-2.0` (`License-Expression: Apache-2.0`, `License-File: LICENSE` present under `licenses/`)
- **Author:** Flet contributors <hello@flet.dev>
- **Requires-Python:** `>=3.10` (app runs 3.14 — fine)
- **Requires-Dist:** `flet==1.0.0` (exact pin — keep Flet at 1.0.0 or the recorder breaks)
- **URLs:** Homepage <https://flet.dev>; Docs <https://flet.dev/docs/services/audiorecorder>; Repo `flet-dev/flet tree/main/sdk/python/packages/flet-audio-recorder`
- **RECORD:** 16 entries — 3 Python files + dist-info files + 5 Flutter shim files
- **App pin:** `pyproject.toml` requires `flet-audio-recorder>=1.0.0` (line 12)
- **Linux caveat:** encoding provided by `fmedia`, must be installed separately
- **Manifest:** `pyproject.toml [tool.flet.android.permission]` already declares
  `android.permission.RECORD_AUDIO = true` (line 79) and `CAMERA` (line 78)

## Module-by-module API

### `flet_audio_recorder` (`__init__.py`)

```python
from flet_audio_recorder import (
    AndroidAudioSource,
    AndroidRecorderConfiguration,
    AudioEncoder,
    AudioRecorder,
    AudioRecorderConfiguration,
    AudioRecorderState,
    AudioRecorderStateChangeEvent,
    AudioRecorderStreamEvent,
    AudioRecorderUploadEvent,
    AudioRecorderUploadSettings,
    InputDevice,
    IosAudioCategoryOption,
    IosRecorderConfiguration,
)
```

### `audio_recorder.py` — `AudioRecorder(ft.Service)`

Registered as `@ft.control("AudioRecorder")`. Instantiate once, add to
`page.services` (NOT `page.views` / overlay — it is a headless Service):

```python
rec = AudioRecorder(
    configuration=AudioRecorderConfiguration(),  # default config
    on_state_change=None,  # Optional[EventHandler[AudioRecorderStateChangeEvent]]
    on_upload=None,  # Optional[EventHandler[AudioRecorderUploadEvent]]
    on_stream=None,  # Optional[EventHandler[AudioRecorderStreamEvent]]
)
page.services.append(rec)
```

#### `async start_recording(output_path=None, configuration=None, upload=None) -> bool`

```python
await rec.start_recording(
    output_path="rec.m4a",  # Optional[str]
    configuration=AudioRecorderConfiguration(...),  # Optional — falls back to rec.configuration
    upload=AudioRecorderUploadSettings(...),  # Optional — streaming upload
)
```

- Returns `True` if recording started, `False` if the platform refused.
  **Always check the return value** (a `False` is not an exception).
- Raises `ValueError("output_path must be provided on platforms other than web")`
  when recording to file off-web without `output_path`.
- Raises `ValueError("Streaming recordings require AudioEncoder.PCM16BITS as encoder.")`
  when `upload` or `on_stream` is set with any other encoder.
- File mode: omit `upload` and `on_stream`, pass `output_path`.
- Streaming mode (`upload is not None or rec.on_stream is not None`): encoder MUST be
  `PCM16BITS`; chunks are raw PCM16 — wrap in WAV yourself for a playable file.
- `configuration` param overrides `rec.configuration` for that single session.
- Example (WAV file):
  ```python
  cfg = AudioRecorderConfiguration(
      encoder=AudioEncoder.WAV, channels=2, sample_rate=44100, bit_rate=128000
  )
  if not await rec.start_recording(output_path="/tmp/rec.wav", configuration=cfg):
      show_snack(page, "Recorder refused to start")
  ```
- Example (live PCM stream with level meter):
  ```python
  rec.on_stream = lambda e: meter(e.chunk)  # e: AudioRecorderStreamEvent
  await rec.start_recording(
      output_path="/tmp/raw.pcm",
      configuration=AudioRecorderConfiguration(
          encoder=AudioEncoder.PCM16BITS, sample_rate=44100, channels=2
      ),
  )
  ```

#### `async stop_recording() -> Optional[str]`

Stops recording. Returns the local file path, a Blob URL on web, or `None` when
streaming (`upload`/`on_stream` set — caller owns the bytes).

#### `async cancel_recording() -> None`

Aborts the session and discards the take. No return, no event.

#### `async pause_recording() -> None` / `async resume_recording() -> None`

Pause/resume the ongoing session in place (single output file continues).

#### `async is_recording() -> bool` / `async is_paused() -> bool`

Ground-truth queries — use before toggling UI state or to re-sync after errors.

#### `async is_supported_encoder(encoder: AudioEncoder) -> bool`

```python
if not await rec.is_supported_encoder(AudioEncoder.OPUS):
    enc = AudioEncoder.WAV  # fall back
```

Probe before `start_recording` — encoder support varies by OS/device.

#### `async get_input_devices() -> list[InputDevice]`

Returns `[InputDevice(id=..., label=...)]` from the platform's device map.
Pass a chosen device via `AudioRecorderConfiguration(device=...)`.

#### `async has_permission() -> bool`

Checks mic permission **and requests it if needed**. Returns `True` if granted
now or after the request. Note: it does NOT distinguish denied vs permanently-denied.

### `types.py`

#### `AudioRecorderState` (Enum)

`STOPPED = "stopped"` · `RECORDING = "recording"` · `PAUSED = "paused"`.
Delivered via `AudioRecorderStateChangeEvent.state`.

#### `AudioRecorderStateChangeEvent(ft.Event)` — `on_state_change`

```python
@dataclass
class AudioRecorderStateChangeEvent(ft.Event["AudioRecorder"]):
    state: AudioRecorderState
```
Fires on every stopped/recording/paused transition — the reliable way to drive
Record/Pause/Resume buttons instead of local boolean flags.

#### `AudioRecorderStreamEvent(ft.Event)` — `on_stream`

```python
@dataclass
class AudioRecorderStreamEvent(ft.Event["AudioRecorder"]):
    chunk: bytes  # raw PCM16LE bytes
    sequence: int  # incremental chunk number
    bytes_streamed: int  # cumulative bytes
```
Only fires in streaming mode (encoder must be `PCM16BITS`).

#### `AudioRecorderUploadEvent(ft.Event)` — `on_upload`

```python
@dataclass
class AudioRecorderUploadEvent(ft.Event["AudioRecorder"]):
    file_name: Optional[str] = None
    progress: Optional[float] = None  # 0.0..1.0 (unknown total until stop)
    bytes_uploaded: Optional[int] = None  # best live progress indicator
    error: Optional[str] = None  # set on upload failure
```

#### `AudioRecorderUploadSettings` (`@ft.value`)

```python
AudioRecorderUploadSettings(
    upload_url="https://.../upload",  # required — e.g. page.get_upload_url()
    method="PUT",  # HTTP method, default "PUT"
    headers={"Authorization": "Bearer ..."},  # Optional[dict[str, str]]
    file_name="take.pcm",  # friendly name echoed in upload events
)
```
Uploads send **raw PCM16 bytes with no WAV container**.

#### `AudioEncoder` (Enum, 9 members)

`AACLC="aacLc"` (general) · `AACELD="aacEld"` (VoIP) · `AACHE="aacHe"`
(low-bitrate quality) · `AMRNB="amrNb"` / `AMRWB="amrWb"` (speech) ·
`OPUS="opus"` (versatile) · `FLAC="flac"` (lossless) · `WAV="wav"` (uncompressed) ·
`PCM16BITS="pcm16bits"` (required for streaming).

#### `AudioRecorderConfiguration` (`@ft.value`)

```python
AudioRecorderConfiguration(
    encoder=AudioEncoder.WAV,  # output format
    suppress_noise=False,  # may lower volume
    cancel_echo=False,  # may lower volume
    auto_gain=False,  # may lower volume
    channels=2,  # 1 = mono, 2 = stereo (platform max is usually 2)
    sample_rate=44100,
    bit_rate=128000,  # ft.Number, bits/sec where applicable
    device=None,  # Optional[InputDevice] — None = default
    android_configuration=AndroidRecorderConfiguration(),
    ios_configuration=IosRecorderConfiguration(),
)
```

#### `InputDevice` (`@ft.value`) — `id: str`, `label: str`

#### `AndroidAudioSource` (Enum, 11 members)

`DEFAULT_SOURCE` · `MIC` · `VOICE_UPLINK` · `VOICE_DOWNLINK` · `VOICE_CALL` ·
`CAMCORDER` · `VOICE_RECOGNITION` · `VOICE_COMMUNICATION` · `REMOTE_SUBMIX` ·
`UNPROCESSED` · `VOICE_PERFORMANCE`. Prefer `DEFAULT_SOURCE`/`MIC`.

#### `AndroidRecorderConfiguration` (`@ft.value`)

```python
AndroidRecorderConfiguration(
    use_legacy=False,  # True = stability-oriented MediaRecorder; False = advanced
    mute_audio=False,  # mute alarms/music/ring during take, restored on stop
    manage_bluetooth=True,  # try Bluetooth SCO headset connection
    audio_source=AndroidAudioSource.DEFAULT_SOURCE,
)
```

#### `IosAudioCategoryOption` (Enum, 8 members)

`MIX_WITH_OTHERS` · `DUCK_OTHERS` · `ALLOW_BLUETOOTH` · `DEFAULT_TO_SPEAKER` ·
`INTERRUPT_SPOKEN_AUDIO_AND_MIX_WITH_OTHERS` · `ALLOW_BLUETOOTH_A2DP` (10.0+) ·
`ALLOW_AIRPLAY` (10.0+) · `OVERRIDE_MUTED_MICROPHONE_INTERRUPTION` (14.5+).

#### `IosRecorderConfiguration` (`@ft.value`)

```python
IosRecorderConfiguration(
    options=[DEFAULT_TO_SPEAKER, ALLOW_BLUETOOTH, ALLOW_BLUETOOTH_A2DP]
)  # the default
```

## App usage & correctness

Single integration point: **mic capture** in `src/screens/capture_screen.py`,
wired in `src/main.py:259-276`, typed `audio_recorder: Any` in
`src/state/service_ctx.py:23`. `tests/test_record.py` is unrelated
(stream-remux engine tests, not the recorder package).

**(a) Correct usage**

- `src/main.py:262-263` — one `AudioRecorder()` appended to `page.services`
  inside try/except with graceful `None` fallback. Correct (Service, not View).
- `src/capture_screen.py:503` — JIT mic permission via
  `flet-permission-handler` *before* `start_recording`. Correct ordering.
- `src/capture_screen.py:508` — `is_supported_encoder()` probe with WAV fallback.
  Correct; matches v1 guidance.
- `src/capture_screen.py:515-526` — PCM16/streaming only for WAV; Opus/AAC use
  pure file mode (`on_stream = None`). Correct — respects the PCM16 constraint.
- `src/capture_screen.py:536` — checks `start_recording()` return value and shows
  "Recorder refused to start". Correct.
- `src/capture_screen.py:444-456, 477` — accumulates `on_stream` chunks, RMS meter,
  200 MB safety cap, self-WAV-wraps on stop. Correct workaround for raw-PCM stream.

**(b) Misuse / bugs**

1. **`src/screens/capture_screen.py:160-161` (`_cleanup`) — recorder never
   stopped on unmount.** The effect cleanup only clears `ticking_ref`; if the
   user navigates away mid-take, `stop_recording()`/`cancel_recording()` is never
   called — the native session leaks and keeps the mic open. Fix: run an async
   stop/cancel in the unmount cleanup.
2. **`src/screens/capture_screen.py:556` — pause UI flips local flag instead of
   ground truth.** `_pause_mic` calls `set_rec_paused(not rec_paused)` after
   `pause/resume_recording()` without consulting `is_paused()` or
   `on_state_change`; a failed native pause desyncs the button label. Fix:
   subscribe `on_state_change` or re-read `is_paused()`.
3. **`src/screens/capture_screen.py:518,523,526` — `rec.on_stream` reassigned
   per take with no reset on failure paths.** If `start_recording` raises
   (line 537) after `on_stream` was set, the stale handler leaks into the next
   non-streaming take (mitigated only because file branches clear it explicitly).
   Fix: clear `on_stream` in the exception handler and after `_finish_mic`.
4. **`src/screens/capture_screen.py:495-504` — no `has_permission()` / device
   pre-check via the recorder itself.** Mic access relies solely on
   `flet-permission-handler`; the recorder's own `has_permission()` (which
   requests if needed) is never called, so a grant revoked mid-session surfaces
   only as a generic "Recorder refused to start". Fix: call
   `await rec.has_permission()` right before `start_recording` and gate on it.
5. **`src/screens/capture_screen.py:474` — `stop_recording()` return ignored in
   PCM branch, no `cancel_recording()` anywhere.** `_finish_mic` discards the
   Blob-URL/file path for WAV (uses its own `mic_out_ref`) and there is no
   discard-take path — every stop finalizes. A failed/abandoned take leaves a
   temp file with no cleanup. Fix: use the return value to validate, add a
   Cancel button calling `cancel_recording()`.
6. **`src/screens/capture_screen.py:508-513` — encoder-probe exception path
   doesn't reassign codec consistently.** On probe exception `codec_name` stays
   at the requested codec while `enc` falls back to WAV — actually the code does
   fall back correctly, but it never verifies `started` against `is_recording()`,
   so a `True` with an immediately-dying session still starts the ticker.
   Verify with `await rec.is_recording()` after start.

**(c) Coverage note** — the mic flow itself uses start/stop/pause/resume well;
gaps are all in state-sync, teardown, and capability APIs (see below).

## Underused APIs to adopt

1. **`on_state_change` + `AudioRecorderState`** — drive Record/Pause/Resume UI
   from native transitions; eliminates bug (b2) entirely.
2. **`has_permission()`** — call before every `start_recording`; handles the
   revoked-mid-session case the permission-handler flow misses (b4).
3. **`cancel_recording()`** — add a "Discard take" button; also the correct
   unmount cleanup (b1, b5).
4. **`is_recording()` / `is_paused()`** — re-sync UI after errors, app resume,
   and post-`start_recording` verification (b2, b6).
5. **`get_input_devices()` + `AudioRecorderConfiguration(device=...)`** —
   device picker for USB/Bluetooth mics; currently always the OS default.
6. **`suppress_noise` / `cancel_echo` / `auto_gain`** — voice-memo toggles;
   never set (all `False` defaults pass through).
7. **`on_upload` + `AudioRecorderUploadSettings`** — direct-to-URL streaming
   upload path (`page.get_upload_url()`); completely unused.
8. **`AndroidRecorderConfiguration` tuning** — `VOICE_RECOGNITION` source,
   `mute_audio=True` for clean takes, `manage_bluetooth` for headset capture.
9. **`IosRecorderConfiguration.options`** — e.g. `MIX_WITH_OTHERS` vs the
   default duck/speaker behavior; never customized.
10. **More encoders** — `FLAC` (lossless), `AACELD`/`AACHE` (voice quality),
    `OPUS` bit-rate ladder; app exposes only WAV/Opus/AAC-LC at fixed bit-rates.

## Gotchas

- **Streaming forces PCM16:** setting `on_stream`/`upload` with any other encoder
  raises `ValueError` — set file branches to `on_stream = None` (the app does).
- **Stream chunks are NOT playable:** raw PCM16, wrap with a WAV header
  (app's `_write_wav`) before probing/converting.
- **`stop_recording()` returns `None` in streaming mode** — keep your own path.
- **`output_path` required off-web** for file mode (`ValueError` otherwise);
  web may return a Blob URL instead of a path.
- **`has_permission()` requests if needed** — don't call it speculatively on
  screen load or it pops a system dialog; call JIT before recording.
- **`upload.progress` is unreliable mid-take** — total size unknown until stop;
  use `bytes_uploaded`. Uploads also send raw PCM16 (no container).
- **Noise/echo/gain flags can lower volume** — expose as opt-in toggles, not defaults.
- **`flet==1.0.0` exact pin** — upgrading Flet without the recorder breaks the bridge.
- **Linux needs `fmedia`** installed separately for any encoding.
- **`AudioRecorder` is a `Service`** — must live in `page.services`; never mount
  it in the view tree. `on_stream` handlers run per-chunk — keep them cheap
  (the app throttles meter updates to 10 Hz; do the same).
