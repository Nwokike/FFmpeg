# Audit: `src/screens/convert_screen.py` vs installed Flet 1.0

Ground truth: Flet `1.0.0` at `.venv/Lib/site-packages/flet/` (read control
dataclasses directly). Engine: `src/services/engine_service.py::convert`
(sig at L649). Dispatch: `src/main.py::_job_runner` (L421+) /
`start_job` (L600). State: `src/core/state.py` (`AppState`, `@ft.observable`).
Theme: `src/core/theme.py::is_dark_mode`.

**Verdict: zero CRASH items.** Every `ft.X(...)` kwarg exists on the installed
dataclass, all icons/enums resolve, handlers/hooks/theme are correct, and the
screen renders green. Findings below are WRONG/SMELL only (runtime job
failures or dead code — no Python-side crash).

## Findings

| Severity | file:line | Problem | Correct API / fix |
|---|---|---|---|
| CLEAN | 100–210 | All ctor kwargs exist: `ListView(controls, spacing, expand)`; `Row(controls, alignment, vertical_alignment, spacing, wrap)`; `Column(controls, spacing, expand)`; `IconButton(icon, on_click, tooltip)` (`tooltip`, `disabled`, `expand` inherited from `Control`; `height` from `LayoutControl`); `Text(value, size, weight, max_lines, overflow, color)`; `Icon(icon, size, color)`; `Dropdown(value, options, on_select)`; `DropdownOption(key, text)`; `Chip(label, selected, on_select)`; `Slider(value, min, max, divisions, on_change)`; `FilledButton(content, icon, height, disabled, on_click)` (Button base); `OutlinedButton(content, on_click)`. No `padding` on any Row/Column. | n/a — verified against `controls/material/{dropdown,chip,slider,button,filled_button,outlined_button,icon_button}.py`, `controls/core/{row,column,list_view,icon,text}.py`, `controls/{control,layout_control}.py` |
| CLEAN | 106,118,202 | Icons `ARROW_BACK_ROUNDED`, `VIDEO_FILE_ROUNDED`, `PLAY_ARROW_ROUNDED` all present in `controls/material/icons.json` (8825 keys, exact-match verified). | n/a |
| CLEAN | 110,126,143 | Enums `FontWeight.BOLD`, `TextOverflow.ELLIPSIS`, `MainAxisAlignment.SPACE_BETWEEN`, `CrossAxisAlignment.CENTER` all resolve at runtime (verified via interpreter). | n/a |
| CLEAN | 49,154,190,197,205 | Handler arity/events correct: `on_select`/`on_change`/`on_click` are `ControlEventHandler[…]`; `e.control.value` valid (`Event.control` → typed control; `Dropdown.value`, `Slider.value` exist). Mutating handlers are sync and call sync `ctrl.start_job` (`main.py:600`) — no missing `await`. | n/a |
| CLEAN | 27–47 | Hooks: 6× `use_state` unconditional, top-of-body, before any return; no `use_ref`/`use_effect`, no conditional/after-return calls. `ft.context.page` read once at top. | n/a |
| CLEAN | 29–30,115–150 | Theme: `is_dark = is_dark_mode(page)` reads observable `state.theme_revision` (`core/theme.py:96`), subscribing this component — re-renders on flip. No direct `page.theme_mode` read in this screen; `is_dark` threaded into `card_container`/`section_header`/muted text on every path. (`main.py:667` reads `page.theme_mode`, but that is the controller toggle, out of scope.) | n/a |
| CLEAN | 32–39,78,129 | None-guards: `media_path=None` → fallback name, `"0 B"`, disabled button; `info=None` → ternary at L129 skips `duration_s`; both `.stat()` calls guarded by `.exists()`. `state.settings` never read here → no KeyError surface. | n/a |
| WRONG | 90–98 + 160–174 | Container/codec matrix ungated: `mp3`/`m4a` outputs keep `video_codec=libx264` (and `webm`+`libx264`, `avi`+`vp9` are invalid combos). `engine.convert` will raise inside PyAV → job lands `failed`, not a crash, but the UI offers it as valid. No encoder-availability check for `libx265`/`vp9` either — only `libx264` has the `h264` fallback (`engine_service.py:712`). | Gate chips/options per container (e.g. audio-only containers force audio path / disable codec chips), or preflight with `_codec_supports_mode(name, "w")` (`engine_service.py:41`) before `start_job`. |
| SMELL | 54–61 | Resolution sets width only (`scale_height=None`). Engine keeps source height (`engine_service.py:723–724`: `target_h = scale_height or in_video.height`), so 720p/480p may stretch instead of preserving aspect — verify scaling code preserves DAR when only one dim is set. | Pass both dims, or confirm engine aspect handling; label says "downscale" but height is untouched. |
| SMELL | 44 | `_set_a_codec` dead: audio codec hardwired `"aac"`, no UI to change it. | Prefix is honest (`_`), but either expose an audio-codec picker or drop the state. |
| SMELL | 47,80,204 | `is_processing` set `True` and never reset; only unmount-via-`navigate("dashboard")` in `start_job` clears it. Harmless today, fragile if navigation ever stops unmounting. | Reset on unmount/finish, or derive from `state.active_job`. |
| SMELL | 71 + `main.py:437–457` | `params["container"]` is written but `_job_runner` never reads it — the container travels implicitly via `output_path` extension (`out_name`, L63–64). Works, but implicit. Adjacent drift: runner maps `p.get("crop")` → `crop_aspect` while the engine kwarg is `crop_aspect`; any future caller passing `"crop_aspect"` in params would be silently dropped. | Document canonical Job-param keys (`container` informational; `crop` consumed) or read `container` explicitly in the runner. |

## Checklist item 5 — `EngineService.convert` kwargs

Screen never calls `convert` directly; it enqueues `Job(op="convert",
params={container, video_codec, audio_codec, crf, scale_width,
scale_height})`. Runner forwards `video_codec, audio_codec, crf, fps,
scale_width, scale_height, speed, volume_pct, rotation, crop_aspect, eq,
denoise, sharpen, watermark, on_progress, cancel_event` — every one exists
in the real signature (`engine_service.py:649–669`, incl. `preset`,
`scale_width/height`, `fps`, `speed`, `volume_pct`, `rotation`,
`crop_aspect`, `eq`, `denoise`, `sharpen`, `watermark`, `on_progress`,
`cancel_event`). `preset` is left at engine default `"medium"` (no UI —
matches dead-`_set_a_codec` pattern, consider a preset picker).

## Test output (actual)

```
.venv/Scripts/python.exe -m pytest tests/test_all_screens_render.py -q
17 passed in 0.70s
```

All 17 screen bodies render, `ConvertScreen` included. No repro needed:
there are no CRASH items, so no minimal-repro applies.
