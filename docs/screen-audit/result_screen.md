# Result Screen Audit — `src/screens/result_screen.py`

Scope: Flet 1.0 dataclass-constructor audit (unknown-kwarg class of bug), enum/icon verification,
event-dataclass field checks, `use_effect` hook semantics, player lifecycle, runtime landmines.
Ground truth: `.venv/Lib/site-packages/flet/`, `flet_video/`, `flet_audio/`.

## Findings

| Severity | File:Line | Problem | Correct API |
|----------|-----------|---------|-------------|
| CRASH | `src/screens/result_screen.py:286` | `ft.SegmentedButton(selected={compare}, ...)` passes a **`set`**, but the installed field is `selected: list[str]` (`flet/controls/material/segmented_button.py:121`). Construction does not raise, but serializing the control for render crashes: `EmbedJsonEncoder` raises `AttributeError: 'set' object has no attribute '__dict__'`. Any video result whose input file still exists (`has_orig=True`) renders this branch → crash. Repro below. | `selected=[compare]` (list). Read-back in `on_change` (`next(iter(e.control.selected))`, line 291) works for both, but only a list survives serialization. |
| WRONG | `src/screens/result_screen.py:186` | No-job guard is `if not job or not Path(job.output_path).exists()` — no truthiness check on `output_path`, unlike the mount effect at line 132 (`if job is None or not job.output_path`). `Path("")` collapses to `Path(".")`, whose `.exists()` is `True` (cwd), so an empty `output_path` slips through into full render with garbage stats; a `None` path raises `TypeError` in `Path()`. | Mirror line 132: `if not job or not job.output_path or not Path(job.output_path).exists():` |
| SMELL | `src/screens/result_screen.py:125-178` | `_mount_players` mutates `video_ref.current` / `audio_ref.current` (no re-render by itself) and then calls `set_players_ready(True)` unconditionally — but on a job change that flag is usually *already* `True`, and `set_compare("output")` / `set_playing(False)` / `set_pos_ms(0)` are typically no-ops too. If Flet bails out on identical state values, no re-render is scheduled and the freshly built `Video` never appears (the "Preparing preview…" spinner at lines 264-280 sticks until an unrelated render). | Reset first, e.g. `set_players_ready(False)` at the top of the effect (or after the setters), so the trailing `set_players_ready(True)` always schedules the render that picks up `video_ref.current`. |
| SMELL | `src/screens/result_screen.py:350-365` | Drag guard is one-directional: `_drag` (`on_change`) sets `dragging_ref.current = True`, `_seek_player` (`on_change_end`) clears it. If `on_change_end` never fires for a gesture (cancelled/interrupted drag), position events stay suppressed forever and the time label freezes. | Clear the flag defensively, e.g. also reset it in `on_position_change` after a timeout, or clear it at the start of `_toggle_play` / in the duration handler. Low probability, cosmetic impact. |
| OK (verified, no change) | — | New lifecycle/enum logic from the recent edit is correct: `AudioState.PLAYING` exists (`flet_audio/types.py:79`); `on_state_change` reads `e.state` (enum, `AudioStateChangeEvent.state: AudioState`) — the string comparison it replaced was indeed always-`False`; `on_position_change` reads `e.position`, which is `int` ms (not `Duration`) — `int(... or 0)` at line 162 handles it; `on_duration_change` reads `e.duration.in_milliseconds` (`AudioDurationChangeEvent.duration: ft.Duration`, `in_milliseconds` exists); video `on_error` reads `e.data` (documented on `Video.on_error`, `video.py:187-193`); `ft.use_effect(setup, deps, cleanup=...)` signature confirmed — `cleanup` kwarg exists; setters in the mount effect can't loop (deps are `[job.id]`, setters don't change the id); `video_ref.current = None` is nulled synchronously *before* the async `stop()` runs on the captured `v`, so no double-stop / `None`-deref; audio release guards `if a in page.services`; `has_orig` (line 244) is exactly the condition `_mount_players` uses to append the 2nd playlist item (line 140), so `jump_to(1)` can't go out of range (`IndexError` is also caught, lines 87, 272); `ctrl.save_result` / `ctrl.share_result` exist on `ControllerMethods`; all 10 `ft.Icons.*` used exist; `release_mode=`, `playlist=`, `filter_quality=`, `VideoMedia(resource)` positional, `Slider(on_change_end=)`, `IconButton(icon_size=)`, `Container(clip_behavior=)`, `TextButton(icon=)`, `FilledButton(icon=, height=)` all match installed fields. No unknown constructor kwargs anywhere in the file. | — |

## CRASH repro (line 286)

```python
import flet as ft, json
from flet.controls.embed_json_encoder import EmbedJsonEncoder

b = ft.SegmentedButton(
    selected={"output"},  # as written at result_screen.py:286
    segments=[ft.Segment(value="output", label=ft.Text("Output"))],
)
json.dumps(b._build_command(), cls=EmbedJsonEncoder)
# AttributeError: 'set' object has no attribute '__dict__'
# With selected=["output"] the same call serializes fine.
```

Note: the failure surfaces at render/update time, not at construction — the dataclass
accepts the set silently. Existing render tests pass because none of them exercise the
video branch with `has_orig=True` (see test output in audit request message).

## Checklist disposition

1. Unknown kwargs: none — every `ft.X(...)`, `ftv.Video(...)`, `Audio(...)` kwarg verified against installed sources.
2. Enums/icons: `AudioState.PLAYING` exists; all icons exist (`ft.Icons`); no repo `icons.json` found — verified against the installed enum instead.
3. Handlers/arity: all single-arg lambdas reading the correct dataclass fields (`state: AudioState`, `position: int`, `duration: ft.Duration`, video error `data`).
4. Hooks: `cleanup=` exists; mount-effect setters can't loop; drag guard works but see SMELL.
5. Lifecycle: ref-null-before-async-stop is safe; `has_orig` matches the 2-item playlist build.
6. Landmines: `Path("")` guard gap (WRONG above); `SegmentedButton.selected` set-vs-list (CRASH above); duration/position `None` guarded.
