# Audio Screen Audit — `src/screens/audio_screen.py`

Date: 2026-09-23 · Flet ground truth: `.venv/Lib/site-packages/flet/` · Engine: `src/services/engine_service.py` (`extract_audio`, lines 1284–1452) · Dispatcher: `src/main.py:473–484`

## Verdict: CLEAN — no CRASH items. All constructor kwargs, icons, enums, handlers, hooks, engine invocation, and theme wiring verified against installed Flet 1.0 source.

## Findings

| Severity | File:Line | Check | Problem | Exact correct API / Notes |
|---|---|---|---|---|
| PASS | `audio_screen.py:71,74,87,90,104,120,134,151,164,177` | ctor kwargs | Every `ft.X(...)` kwarg exists on the installed dataclass (verified via `inspect.signature`): `ListView(controls, spacing, expand)`; `Row(controls, spacing, alignment, wrap)`; `Column(controls, spacing, expand)`; `IconButton(icon, on_click, tooltip)`; `Text(value, size, weight, max_lines, overflow, color)`; `Icon(icon, size, color)`; `Chip(label, selected, on_select)`; `OutlinedButton(content, on_click)` (`StrOrControl`); `FilledButton(content, icon, height, disabled, on_click)` | No missing kwargs. `Row`/`Column` take no `padding` — none is passed (only `spacing`); `padding` appears solely inside `card_container` → `ft.Container(padding=…)`, which is valid. |
| PASS | `audio_screen.py:77,89,179` | icons | `ft.Icons.ARROW_BACK_ROUNDED`, `GRAPHIC_EQ_ROUNDED`, `AUTO_AWESOME_ROUNDED` — all confirmed present via `hasattr` | — |
| PASS | `audio_screen.py:81,95,108,97` | colors/enums | No `ft.Colors.*` used; `PRIMARY` is a plain hex (`#3C8038`, `src/core/constants.py:84`). `FontWeight.BOLD`, `MainAxisAlignment.SPACE_BETWEEN`, `TextOverflow.ELLIPSIS` all exist | — |
| PASS | `audio_screen.py:47,125,139,144,156,169,105,78,182` | handlers | `_start_audio_studio(_)` arity 1, sync — correct: `on_click: ControlEventHandler` accepts sync 1-arg callables; downstream `ctrl.start_job` (`src/main.py:600`) is sync. All `on_select` lambdas take the event arg (`lambda _, v=val: …`) and ignore it safely; `chip.py:252` types `on_select` as `ControlEventHandler["Chip"]`. No `e.control.value` reads anywhere → no event-field risk | — |
| PASS | `audio_screen.py:33–37` | hooks | 5× `ft.use_state` at top level, unconditional, before any return. Loop lambdas capture via defaults (`v=val`, `rate=r`, `f=fmt`) — no late-binding bug | — |
| PASS | `audio_screen.py:56–69` → `main.py:473–484` → `engine_service.py:1284–1294` | engine invocation | Screen enqueues `Job(op="extract_audio", params={format_name, bitrate_kbps: 256, target_lufs: float, channels: 2\|1, sample_rate: int})`; dispatcher maps every key to the exact `extract_audio(input_path, output_path, format_name, bitrate_kbps, target_lufs, channels, sample_rate, on_progress, cancel_event)` parameter by name. All 6 chip formats (`m4a mp3 aac flac opus wav`) are keys of engine `codec_map` (lines 1296–1303); dispatcher `.get()` defaults cover the rest | Exact match — no repro needed |
| PASS | `audio_screen.py:25–31,48–49,67,181` | data landmines | No-media: early `return` (line 48) + `disabled=not media_path or is_processing` (line 181) + `"No file selected"`/`"0 B"` fallbacks. `Path.stat()` guarded by `.exists()` (lines 29, 67). `r // 1000` labels render 48/44/32 kHz correctly; `channels` maps stereo→2/mono→1. No `settings[…]` reads → no KeyError surface. No `codec_map None` path reachable from these params | — |
| PASS | `audio_screen.py:20–23` | theme | `is_dark = is_dark_mode(page)` reads `state.theme_revision` observable (`src/core/theme.py:96`) → subscribes this component; flips re-render. No direct `page.theme_mode` reads; `is_dark` threaded into `card_container`/`section_header`/muted text | Correct per CollabShell pattern |
| SMELL | `audio_screen.py:37,50,181` | dead local state | `is_processing` is set `True` and never reset; harmless because `start_job` navigates to `"dashboard"` (unmounts this screen), but a future inline-success path would leave the button permanently disabled | Reset via `set_is_processing(False)` on completion, or drop the flag |
| SMELL | `audio_screen.py:62` | hardcoded bitrate | `bitrate_kbps: 256` has no UI control, unlike `ExtractScreen`'s bitrate slider (`src/screens/extract_screen.py:210–216`) | Product inconsistency only, not a crash |
| SMELL | `audio_screen.py:36` | default divergence | Default format `"m4a"` differs from `settings["default_audio_format"]` (`"mp3"`, `src/core/state.py:152`); the setting is never consulted here | Consider `state.settings.get("default_audio_format", "m4a")` |

## Test output (actual)

`.venv/Scripts/python.exe -m pytest tests/test_all_screens_render.py -q` → **17 passed in 2.56s** (includes `AudioScreen` body render via `Renderer().render`).
