# flet-audio 1.0.0 — Complete API Reference

> Package purpose: official Flet extension for audio **playback** (decode + play).
> Flutter backend: [`audioplayers`](https://pub.dev/packages/audioplayers) via Dart bridge.
> Python surface is tiny (3 files, ~311 lines) — one `Audio` service control + 5 type/event symbols.
> This report is the sole reference for the v1.0 rewrite. All signatures verified against installed source.

---

## Files

Package dir: `<repo>\.venv\Lib\site-packages\flet_audio`

| File | Lines | Role |
|------|-------|------|
| `flet_audio/__init__.py` | 17 | Public re-exports + `__all__` |
| `flet_audio/audio.py` | 175 | `Audio` control (props, events, 7 async methods) |
| `flet_audio/types.py` | 119 | `ReleaseMode`, `AudioState`, 3 event dataclasses |
| `flet_audio/__pycache__/*.pyc` | — | Skipped (build cache, not API) |

Full `find` output (sorted, `__pycache__`/`.pyc` excluded from API surface):

```text
flet_audio/__init__.py
flet_audio/audio.py
flet_audio/types.py
```

### Bundled native assets

**None inside `flet_audio/`.** No `.so` / `.dll` / `.dylib` / `.ffmpeg` binaries — it is a
pure-Python control package (`Root-Is-Purelib: true`, wheel tag `py3-none-any`).
Playback itself happens in the Flutter host via the `audioplayers` plugin.

Wheel `RECORD` additionally ships the Dart bridge (installed next to site-packages as
top-level `flutter/`, visible via `ls .../site-packages | grep flutter`):

```text
flutter/flet_audio/lib/flet_audio.dart
flutter/flet_audio/lib/src/audio.dart
flutter/flet_audio/lib/src/extension.dart
flutter/flet_audio/lib/src/utils/audio.dart
flutter/flet_audio/pubspec.yaml
```

These are build-time bridge sources only — the Python app never imports them directly.
There is no `entry_points.txt` / console script / Flet plugin entry point; the control
registers via the `@ft.control("Audio")` decorator at import time.

---

## Metadata

From `flet_audio-1.0.0.dist-info/METADATA` (+ `WHEEL`, `INSTALLER`, `top_level.txt`, `RECORD`):

| Field | Value |
|-------|-------|
| Name | `flet-audio` |
| Version | `1.0.0` |
| Summary | `Provides audio integration and playback in Flet apps.` |
| License | `Apache-2.0` (`License-Expression: Apache-2.0`, `License-File: LICENSE` in `licenses/`) |
| Author | `Flet contributors <hello@flet.dev>` |
| Requires-Python | `>=3.10` (app runs 3.14 — compatible) |
| **Dependency pin** | **`Requires-Dist: flet==1.0.0`** — exact pin; upgrading `flet` without `flet-audio` breaks |
| Description-Content-Type | `text/markdown` (README body embedded in METADATA) |
| Homepage / Docs / Repo / Issues | `https://flet.dev`, `https://flet.dev/docs/services/audio`, `https://github.com/flet-dev/flet/tree/main/sdk/python/packages/flet-audio`, `https://github.com/flet-dev/flet/issues` |
| Wheel | `Wheel-Version: 1.0, Generator: setuptools (84.0.0), Tag: py3-none-any` |
| Installer | `uv` |
| `top_level.txt` | `flet_audio` |
| Entry points | **None** (no `entry_points.txt` in dist-info) |
| Platform support (README table) | Windows / macOS / Linux / iOS / Android / Web — all ✅ |
| Linux prerequisite (README note) | GStreamer required: `apt install -y libgstreamer1.0-0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav gstreamer1.0-tools`; missing lib → `error while loading shared libraries: libgstapp-1.0.so.0` |
| Supported codecs | Not enumerated in package; docstring points to [audioplayers supported formats](https://github.com/bluefireteam/audioplayers/blob/main/troubleshooting.md#supported-formats--encodings) — MP3/AAC/M4A/FLAC/OPUS/WAV per app's `_AUDIO_EXTS` are all covered |

---

## Module-by-module API

### 1. `flet_audio/__init__.py` — public surface

```python
from flet_audio.audio import Audio
from flet_audio.types import (
    AudioDurationChangeEvent,
    AudioPositionChangeEvent,
    AudioState,
    AudioStateChangeEvent,
    ReleaseMode,
)

__all__ = [
    "Audio",
    "AudioDurationChangeEvent",
    "AudioPositionChangeEvent",
    "AudioState",
    "AudioStateChangeEvent",
    "ReleaseMode",
]
```

Import in app code as `from flet_audio import Audio, ReleaseMode` (optionally `AudioState`).
Nothing else is public. There are **no playlists, queues, mixers, recorders, or visualizers** —
for recording see sibling package `flet_audio_recorder`; `flet-audio` is playback-only,
one `Audio` instance = one native player, but many instances may coexist
(class docstring: *"A control to simultaneously play multiple audio sources."*).

### 2. `flet_audio/audio.py` — `Audio` control

```python
@ft.control("Audio")
class Audio(ft.Service):
```

`Audio` is an `ft.Service`, **not** a visible `ft.Control`. It must live in
`page.services` (or `page.overlay`), never in a layout `Column`/`Row`:

```python
player = Audio(src="output.mp3")
page.services.append(player)
```

#### Constructor properties (all settable at construction; mutable post-mount unless noted)

| Property | Type / Default | Semantics |
|----------|---------------|-----------|
| `src` | `Optional[Union[str, bytes]] = None` | Audio source. Three forms: (a) URL (`https://…`) or local asset/file path string; (b) base64-encoded `str`; (c) raw `bytes` (e.g. in-memory transcoded clip). Changing `src` reloads and re-buffers. |
| `autoplay` | `bool = False` | Start playing as soon as the control is added to the page. **Does not work in Chrome/Edge** (browser autoplay policy); works on desktop, mobile, Safari. Never rely on it for web. |
| `volume` | `ft.Number = 1.0` | Amplitude `0.0` (mute) … `1.0` (max), linearly interpolated. Runtime-mutable for a preview volume slider. |
| `balance` | `ft.Number = 0.0` | Stereo pan: `-1` = full left / right silent, `0` = centered, `1` = full right. Runtime-mutable — ideal for L/R channel-check buttons. |
| `playback_rate` | `ft.Number = 1.0` | Speed multiplier. Docstring: *"Should ideally be set when creating the constructor."* Limits: iOS/macOS clamp to `0.5x`–`2x`; Android requires SDK ≥ 23. Runtime changes may be ignored on some platforms — prefer construct-time. |
| `release_mode` | `ReleaseMode = ReleaseMode.RELEASE` | Resource lifecycle after stop/completion (see `types.py`). Default `RELEASE` frees everything. |

#### Events (all optional, default `None`)

| Event | Handler type | Fires when |
|-------|-------------|------------|
| `on_loaded` | `Optional[ft.ControlEventHandler["Audio"]]` | Audio finished loading/buffering; safe point to enable Play and read duration. |
| `on_duration_change` | `Optional[ft.EventHandler[AudioDurationChangeEvent]]` | Duration becomes known (may lag for remote/large files — download/buffer first). Use to size the scrub slider. |
| `on_state_change` | `Optional[ft.EventHandler[AudioStateChangeEvent]]` | Player state transitions (`AudioState`). Drive Play/Pause icon, reset position on `COMPLETED`, guard `DISPOSED`. Payload: `e.state: AudioState` (enum, **not** a string). |
| `on_position_change` | `Optional[ft.EventHandler[AudioPositionChangeEvent]]` | Position updates **every ~1 second while status is playing**. Payload: `e.position: int` = milliseconds. Designed for progress bars; too coarse for sample-accurate UI. |
| `on_seek_complete` | `Optional[ft.ControlEventHandler["Audio"]]` | A `seek()` finished. Use to re-enable the slider / confirm scrub. |

> Note: there is **no `on_error` event** on `Audio` (unlike `flet_video.Video`'s
> `on_error`). Load/decode/playback failures are silent to the UI — poll
> `get_duration()` / `get_current_position()` or wrap method calls in `try/except`.

#### Async methods (all coroutines — must be `await`ed, e.g. via `page.run_task`)

```python
async def play(self, position: ft.DurationValue = 0) -> None
```

Starts playback from `position` (default: beginning). `ft.DurationValue` accepts
`ft.Duration(...)` or `datetime.timedelta` or numeric forms depending on Flet version;
the app's working idiom is `ft.Duration(milliseconds=ms)`. Example — preview from a marker:

```python
await player.play()  # from start
await player.play(ft.Duration(milliseconds=30_000))  # from 0:30
```

```python
async def pause(self) -> None
```

Pauses; a later `resume()` continues from the pause point.

```python
async def resume(self) -> None
```

Resumes a paused **or stopped** player. After `COMPLETED`, prefer `play()` (or
`seek(0)` + `play()`) — `resume()` semantics at end-of-stream are backend-dependent.

```python
async def release(self) -> None
```

Frees buffered audio + native player. Source is re-fetched/re-buffered on next
`src` change or `resume()`. Call on unmount / before abandoning a player, then remove
the service from the page:

```python
await player.release()
if player in page.services:
    page.services.remove(player)
```

```python
async def seek(self, position: ft.DurationValue) -> None
```

Moves the play cursor. Completion is signalled via `on_seek_complete` (not by return):

```python
await player.seek(ft.Duration(milliseconds=target_ms))
```

```python
async def get_duration(self) -> Optional[ft.Duration]
```

Returns total duration once known, else `None` (remote file still buffering).
Use as fallback when `on_duration_change` hasn't fired yet.

```python
async def get_current_position(self) -> Optional[ft.Duration]
```

Returns current play cursor, else `None`. Use to init/restore slider state or to
detect a stalled player (position stops advancing while state claims `PLAYING`).

Exceptions: methods raise backend/transport errors to the caller (no package-defined
exception hierarchy) — always `try/except Exception` around `await` calls and log.

Minimal full example:

```python
import flet as ft
from flet_audio import Audio, AudioState, ReleaseMode


async def main(page: ft.Page):
    status = ft.Text("idle")

    async def on_state(e):
        status.value = e.state.value
        status.update()

    player = Audio(
        src="https://example.com/preview.mp3",
        volume=0.8,
        release_mode=ReleaseMode.STOP,  # instant replay of short clips
        on_state_change=on_state,
        on_duration_change=lambda e: print("dur ms:", e.duration.in_milliseconds),
        on_position_change=lambda e: print("pos ms:", e.position),
        on_seek_complete=lambda e: print("seek done"),
        on_loaded=lambda e: print("buffered"),
    )
    page.services.append(player)

    async def toggle(_):
        pos = await player.get_current_position()
        dur = await player.get_duration()
        print(pos, dur)
        # real code should branch on e.state, not wall clock
        await player.play()

    page.add(ft.FilledButton("Play", on_click=toggle), status)
    await player.play(ft.Duration(seconds=5))


ft.run(main)
```

### 3. `flet_audio/types.py` — enums + events

```python
class ReleaseMode(Enum):
    RELEASE = "release"
    LOOP = "loop"
    STOP = "stop"
```

| Member | Value | Behaviour — when to use |
|--------|-------|-------------------------|
| `RELEASE` | `"release"` | **Default.** Auto-`release()` on completion: buffer + native player freed, nothing held in memory. Replay re-loads from scratch (remote file re-downloaded → short delay). Best for rare/never-repeated playback and minimal memory. On Android also drops the resource-heavy native `MediaPlayer`. |
| `LOOP` | `"loop"` | Auto-restart from 0 on every completion — infinite loop, buffer retained. Best for background music / loop audition. **Never auto-releases**: must call `release()` or change `src` to free. |
| `STOP` | `"stop"` | Stop at end but **keep** buffer + native player: replay is immediate, no reload, no network. Costs memory while idle. Best for short SFX / repeated audition of the same export (the app's correct choice in `result_screen.py:146`). |

```python
class AudioState(Enum):
    STOPPED = "stopped"  # idle / stopped
    PLAYING = "playing"  # currently playing
    PAUSED = "paused"  # paused, resumable
    COMPLETED = "completed"  # reached end of stream
    DISPOSED = "disposed"  # terminal — do not reuse the instance
```

```python
@dataclass
class AudioStateChangeEvent(ft.Event["Audio"]):
    state: AudioState  # current player state (ENUM)


@dataclass
class AudioPositionChangeEvent(ft.Event["Audio"]):
    position: int  # play cursor in MILLISECONDS (not a Duration)


@dataclass
class AudioDurationChangeEvent(ft.Event["Audio"]):
    duration: ft.Duration  # total duration (use `.in_milliseconds`)
```

Importantly: `AudioStateChangeEvent.state` is an `AudioState` member. Compare with
`e.state == AudioState.PLAYING` (or `e.state is AudioState.PLAYING` / `.value`),
never with a bare string (see bug §4.1).

---

## App usage & correctness

Only playback call-site: `src/screens/result_screen.py` (guarded import lines 38–43).
`src/screens/audio_screen.py` (the Audio Studio: loudness/resample/channel-mix) has
**zero** `flet_audio` usage — no input/output preview at all.
No `flet_audio` usage in `tests/` (only `flet_audio_recorder` in `main.py:31`, `capture_screen.py:53`).

### (a) Correct usage (keep in rewrite)

- Import guard with feature flag — `result_screen.py:38-43` (`try: from flet_audio import
  Audio, ReleaseMode / _HAS_AUDIO_PLAYER`) so the screen renders without the package.
- Extension gate — `result_screen.py:29` `_AUDIO_EXTS`, mount only for audio suffixes
  (`result_screen.py:142`), video path uses `flet_video` separately.
- Single player per job mount — `audio_ref.current is None` guard (`:142`), stored in
  `audio_ref`, created in `use_effect` keyed on `job.id` (`:163-167`).
- `ReleaseMode.STOP` (`:146`) — right call for an export-preview screen where the user
  replays the same short file repeatedly: instant, network-free replay.
- Lifecycle cleanup — `use_effect … cleanup=lambda: (_stop_video_player(), _release_audio())`
  (`:166`); `_release_audio` (`:105-120`) awaits `release()`, catches/log-warns, and removes
  the service from `page.services` in `finally` (`:117-118`).
- Progress UI wiring — `on_position_change → set_pos_ms` (`:148`) + `on_duration_change →
  set_dur_ms` (`:149-153`) feeding a scrub `Slider` + `mm:ss / mm:ss` labels
  (`:337-366`) with `_fmt_ms` (`:46-49`).
- Scrub split — slider `on_change` only moves local state (`:352`), actual `seek()` fires on
  `on_change_end` (`:353` + `_seek_player :325-335`), avoiding a seek storm per drag tick.
- `seek` payload form `ft.Duration(milliseconds=target)` (`:331`) — correct `DurationValue`.
- `play()` with no args for fresh start (`:319`) — correct (defaults to position 0).
- Async hygiene — every `await player.*` wrapped in `try/except Exception` + log
  (`:313-321`, `:329-333`, `:111-115`).

### (b) Misuse / bugs (fix in rewrite — file:line)

1. **`on_state_change` string-vs-enum comparison — `playing` flag never becomes True
   (`result_screen.py:147`).**
   `lambda e: set_playing(getattr(e, "state", "") == "playing")` compares the
   `AudioState` enum to the string `"playing"`. `AudioState.PLAYING == "playing"` is
   `False`, so `playing` stays `False` forever. Consequences: Play/Pause icon
   (`:342-345`) never shows PAUSE; the toggle (`:311-323`) can never reach the
   `await player.pause()` branch — the user **cannot pause**. Fix:
   `from flet_audio import AudioState` + `set_playing(e.state == AudioState.PLAYING)`
   (handle `COMPLETED` → `set_playing(False)` + reset affordance).
2. **Unreachable pause + wrong resume-after-completion (`result_screen.py:311-323`).**
   Toggle is `if playing: pause / elif pos_ms > 0: resume / else: play`. Once bug 1 is
   fixed this mostly works, but after `COMPLETED` (`pos_ms == dur_ms > 0`) it calls
   `resume()`, whose end-of-stream behaviour is backend-dependent — should call
   `play()` (restart from 0). Also `resume()` while already `PLAYING` is a no-op that
   masks state bugs; branch on the real `AudioState`, not on `pos_ms`.
3. **No `COMPLETED` handling — stale slider.** Nothing listens for
   `AudioState.COMPLETED` to reset `pos_ms`/icon. After a file finishes, the slider sits
   at the end and the icon still claims the pre-finish state. Add: on `COMPLETED`,
   `set_playing(False)` and offer replay via `play()`.
4. **Position-event re-render churn (`:148`).** `on_position_change` fires every second
   while playing and each fire calls `set_pos_ms` → full screen re-render (60/min).
   Acceptable for v1 but wasteful; throttle (update only if `abs(new-old) >= 500ms`) or
   isolate the progress row in a sub-component so stats/actions don't rebuild. Also
   fights slider drags: a position event mid-drag snaps the thumb — suppress
   position-driven `set_pos_ms` while the user is dragging (track scrub-in-progress flag).
5. **Silent failures — no error surface.** `Audio` exposes no `on_error`; the screen only
   logs *construction* failure (`:157-158`). Decode/play/seek failures surface only as
   caught warnings in console. Add a user-visible error line (e.g. check
   `get_duration() is None` after `on_loaded` timeout; surface `except` messages in a
   `Text(color=ERROR)`), especially for corrupt/unsupported exports.
6. **Premature-seek window.** Slider is live with `max = max(dur_ms, 1)` (`:337`) before
   `on_duration_change` arrives, so early drags `seek()` into an unbuffered player and
   fail silently (`:329-333` logs only). Disable the slider until `dur_ms > 0` (or
   `on_loaded` fired); optionally confirm via `on_seek_complete` (currently unwired).
7. **`audio_ref.current = None` races async release (`:109`).** The ref is cleared
   synchronously, then `_release()` runs later. A fast job-switch can mount player B
   while player A's native release is still in flight → two native players briefly (double
   audio on loop-y clips). Serialize: await release before clearing, or guard with a
   generation counter.
8. **Absolute filesystem `src` (`:145` `src=str(out_p)`).** Works on desktop, but absolute
   paths outside Flet assets are fragile on mobile/web (needs asset mount or `file://`
   URI / bytes upload). For v1 mobile target, verify on-device; fallback: serve via
   assets dir or pass `bytes` (`src=out_p.read_bytes()`) for short previews.
9. **`_fmt_ms` truncates hours (`:46-49`).** `mm:ss` only — a 90-min mix shows `90:00`,
   fine, but sub-second precision is dropped; position event is already ms-coarse, so
   don't promise sample accuracy in UI copy.
10. **No `page.services` duplicate guard (`:155`).** `page.services.append(player)` is
    protected only by the `audio_ref.current is None` check. A double-mount (strict-mode
    double effect, hot reload) would append twice → dual playback. Guard with
    `if player not in page.services`.

### (c) Underuse summary (detail in next section)

The screen uses `play / pause / resume / seek / release` + 3 of 5 events. Untouched:
`get_duration`, `get_current_position`, `on_loaded`, `on_seek_complete`, `volume`,
`balance`, `playback_rate`, `autoplay` (correctly avoided), `ReleaseMode.LOOP`,
`bytes`/`base64`/`URL` sources, and multi-instance A/B or loop audition.

---

## Underused APIs to adopt

Ranked by v1 value for an FFmpeg mobile app (preview = trust):

1. **`on_state_change` with the full `AudioState` enum** — today only (buggily) derives a
   boolean. Adopt `STOPPED/PLAYING/PAUSED/COMPLETED/DISPOSED` to drive the transport icon,
   disable controls when `DISPOSED`, and auto-offer replay on `COMPLETED`.
2. **`play(position)` with start offset** — "preview from 0:30 / from cut point" and
   A/B-compare output vs original at the same timestamp. Costs nothing; currently always
   starts at 0.
3. **`seek()` + `on_seek_complete`** — wire `on_seek_complete` to clear a "seeking…"
   indicator and to serialize rapid scrubs (ignore slider input until the pending seek
   completes). Required for long-file scrubbing UX.
4. **`on_loaded`** — gate the transport UI ("Preparing preview…" → enabled) instead of
   inferring readiness from `players_ready`. Eliminates bug 6 class entirely.
5. **`get_duration()` fallback poll** — if `on_duration_change` is delayed (large/remote
   file), poll once after `on_loaded`/first `play()` to size the slider. Also validates
   the export (duration `None` ⇒ broken file ⇒ show error, don't show `00:00/00:00`).
6. **`get_current_position()` restore/sync** — re-sync slider after navigation back,
   verify pause actually held position, detect stalls (state `PLAYING` but position frozen
   ⇒ show "buffering…").
7. **`volume`** — a preview-volume slider (0–100 → 0.0–1.0). Trivial, high user value on
   mobile; also lets loudness-normalization results be auditioned at matched level.
8. **`playback_rate`** — 0.5x/1x/1.5x/2x audition buttons for speech exports and
   long-form QA. Set at construction (per docstring) within iOS/macOS `0.5–2.0` limits;
   verify Android SDK ≥ 23 in CI matrix.
9. **`balance`** — L/R channel-check buttons (`-1` / `0` / `+1`) for the channel-mixing
   features `audio_screen.py` ships blind. Directly validates dual-mono/stereo swaps.
10. **`ReleaseMode.LOOP` audition toggle** — loop a short ringtone/SFX/alarm export
    without press-play-again fatigue; remember it never auto-frees, so flip back to
    `STOP`/`RELEASE` + `release()` on exit. (Keep `STOP` as the default preview mode —
    that choice is already right.)
11. **`bytes` / base64 `src`** — preview in-memory or pipe-transcoded snippets without
    temp files (e.g. 10-s loudness sample). Watch memory: base64 inflates ~33%; prefer
    raw `bytes` for clips > a few MB.
12. **Second simultaneous `Audio` instance** — true A/B: mount original + output players,
    `pause()` one / `play(offset)` the other on segment switch, for gapless compare.
    The class explicitly supports concurrent players; the current single-player design
    restarts from 0 on every compare flip.

Explicitly **do not** adopt `autoplay=True` for web builds (Chrome/Edge block it) and do
not depend on sub-second `on_position_change` precision (1 Hz cadence is by design).

---

## Gotchas

1. **State payload is an enum, not a string** (`types.py:93-99`). `e.state == "playing"`
   is always `False`. Compare against `AudioState`. Same trap for `e.position` (an `int`
   of ms, `types.py:102-109`) vs `e.duration` (an `ft.Duration`, `types.py:112-119`) —
   don't call `.in_milliseconds` on position or `int()` a Duration.
2. **`Audio` is a `Service`, not a `Control`.** Never place it in `controls=[…]` layouts;
   `page.services.append(player)` is mandatory or no sound plays and no events fire.
   Forgetting `page.services.remove()` on dispose leaks the native player (audible ghost
   playback after navigating away).
3. **`DISPOSED` is terminal** (`AudioState.DISPOSED`). After dispose/release-race, create
   a new `Audio` — never reuse the instance.
4. **`LOOP` never frees** — each looped preview left mounted holds buffer + native player
   indefinitely. Always pair with explicit `release()` on unmount.
5. **Default `RELEASE` re-downloads remotes** — replaying a URL-sourced preview pays full
   re-buffer each time. Use `STOP` for repeated audition (as the app does), `RELEASE` for
   one-shot plays of large files.
6. **Position cadence is 1 Hz while playing only** (`audio.py:89-96`). Paused/stopped
   players emit nothing — don't animate smooth progress from it; interpolate locally if
   needed and re-sync on the next event.
7. **Duration may arrive late or never.** Remote/unbuffered sources fire
   `on_duration_change` only when the header parses; corrupt files may never fire.
   Never divide by `dur_ms` without a zero guard (the app's `max(dur_ms, 1)` at `:337`
   is the right pattern — keep it).
8. **Autoplay dead on Chrome/Edge** (`audio.py:32-39`). Any web flow that assumes
   sound-on-mount is broken by design; always require a tap-to-play on web.
9. **`playback_rate` is construct-time + platform-clamped** (`audio.py:57-66`):
   iOS/macOS `0.5–2.0`, Android SDK ≥ 23. Out-of-range values are silently clamped or
   ignored — validate in UI (slider min 0.5, max 2.0).
10. **Volume/balance are linear, not perceptual** (`audio.py:41-55`). A 0.5 volume slider
    sounds louder than "half"; apply a perceptual (e.g. square/exponential) mapping in
    the slider handler for a natural feel.
11. **Linux needs GStreamer** (METADATA README). CI/dev containers without
    `libgstreamer*` fail with `libgstapp-1.0.so.0` errors that look like package bugs.
12. **Exact pin `flet==1.0.0`.** Dependabot-style `flet` bumps without a matching
    `flet-audio` release will break imports at runtime. Pin both together in
    `pyproject.toml` / `uv.lock` and upgrade atomically.
13. **No `on_error`.** All failure detection must be built from `on_loaded` timeouts +
    `get_duration()`/`get_current_position()` `None` checks + `try/except` on awaits.
14. **`bytes`/`base64` sources live in Dart-bridge memory.** Convenient for short clips;
    pushing a 500 MB export as `bytes` will OOM mobile. Rule of thumb: paths/URLs for
    full exports, `bytes` only for < ~10 MB snippets.
