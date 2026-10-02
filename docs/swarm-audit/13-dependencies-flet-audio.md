# flet-audio 1.0.3 — audit reference

`Audio(@ft.control("Audio"), ft.Service)` — multiple simultaneous
sources supported. Fields: `src: str|bytes|None` (URL, asset path,
base64, raw bytes); `autoplay=False` (broken in Chrome/Edge per docs);
`volume=1.0` (0–1); `balance=0.0` (−1 left, 1 right); `playback_rate=1.0`
(iOS/macOS clamp 0.5–2, Android needs SDK 23+); `release_mode=RELEASE`.
Events: `on_loaded`, `on_duration_change` (Duration, may lag remote),
`on_state_change` (AudioState), `on_position_change` (int ms, ~1s tick),
`on_seek_complete`. Methods (async): `play(position=0)`, `pause()`,
`resume()`, `release()`, `seek(position)`, `get_duration()`,
`get_current_position()`.
`ReleaseMode`: RELEASE (default, frees on completion), LOOP
(auto-restart, keeps resources), STOP (stops, retains buffer, costs
memory). `AudioState`: STOPPED/PLAYING/PAUSED/COMPLETED/DISPOSED.
Position event = ms int; duration event = `ft.Duration`.

## Used by app (result_screen.py only)

Guarded import + `_HAS_AUDIO_PLAYER`; `_AUDIO_EXTS` gate. `Audio(
src=out_path, release_mode=STOP, on_state_change/on_position_change/
on_duration_change)` → `page.services.append`; COMPLETED pins slider;
toggle play/pause/resume; seek on `on_change_end`; `release()` + remove
on cleanup effect.

## Unused

`balance` (Audio Studio channel-mix preview — screen has no player at
all); `playback_rate` (tempo audition without re-encode); `volume` (no
player mute/slider — all `volume` hits are FFmpeg `-af volume`);
`autoplay`; `on_loaded` (no buffering indicator); `on_seek_complete`
(fire-and-forget seek); `get_duration/get_current_position` (no pull
path); `play(position)` offset; LOOP (preview toggle) / RELEASE
(low-memory path); PAUSED/STOPPED/DISPOSED never distinguished
(pause inferred from `not playing`).
