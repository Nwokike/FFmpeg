# Join screen audit — `src/screens/join_screen.py` vs installed Flet 1.0

Date: 2026-09-23 · Auditor: API-audit agent · Scope: read-only, no app code modified.
Ground truth: `.venv/Lib/site-packages/flet/` (controls source, `icons.json`),
`src/services/engine_service.py` (`concat`, `_crossfade_gate`),
`src/services/media_io.py` (`pick_media_files`), `src/main.py` (concat dispatch),
`src/core/*`, `src/state/*`. Tests run with `.venv/Scripts/python.exe -m pytest`.

## Verdict

No crashes, no wrong API usage. Every control kwarg, enum, icon, handler arity,
hook, and `EngineService.concat` param verified against installed source.
Three SMELL-grade findings below; none blocks shipping.

## Findings

| Severity | file:line | Problem | Exact correct API / fix reference |
|---|---|---|---|
| SMELL (med) | `src/screens/join_screen.py:154` | Temp output name `joined_{int(time.time())}.{ext}` has 1-second resolution — two joins inside the same second collide on one path (second job overwrites the first's output; history entries alias). | `get_temp_dir()` (`src/core/storage_paths.py:35`) is fine; make the stem unique, e.g. `f"joined_{int(time.time()*1000)}"` or embed `Job.id` (8-hex uuid, `src/core/state.py:95`). Engine does not dedupe — it `av.open(output_path, "w")`. |
| SMELL (low) | `src/screens/join_screen.py:65` (`if avail:`) | Filter-presence check is skipped while `avail` is still empty (probe in flight). Crossfade chips can read enabled for one render before `available_filters()` resolves; a very fast click-through submits `transition="crossfade"` that the engine then silently downgrades (see next row). | `available_filters() -> set[str]` (`engine_service.py:443`). Gate on `avail is None` (not-yet-loaded) vs empty set, or treat empty as "unknown, keep disabled" until load completes. Self-heals in practice: file probing takes longer than the filters probe. |
| SMELL (low) | `src/screens/join_screen.py:301-312` | One shared `gate_reason` (computed with the *current* `fade_s`) drives `disabled` on *both* fade chips, so the non-selected duration's chip can be stale-enabled for one click (e.g. 0.5s passes, 1.0s wouldn't). | Harmless: selecting it re-renders with the new `fade_s`, the gate then fails with an explanatory line (L317-329), the "Instant (hard cut)" chip is never disabled so there is no stuck state, and `_start_join` (L148-152) re-validates before dispatch. Per-value gate (`_crossfade_reason(fade)`) would remove the one-click lag. |
| INFO | `src/screens/join_screen.py:350` | `f"Join {len(entries) or ''} Clips".replace("  ", " ")` works (renders "Join Clips" at 0) but is fragile string surgery. | Cosmetic only; conditional expression would be clearer. Not a bug. |
| INFO | `join_screen.py:148-152` vs `engine_service.py:1950` | Deliberate divergence, both correct: the screen *blocks* crossfade with an error snack when its gate fails; the engine *falls back* to instant join with `logger.warning("…falling back to instant join")`. Screen pre-validation means the engine fallback is unreachable from this screen. | Keep as-is; do not "align" by removing either layer (engine fallback protects other callers, e.g. `command_parser.py:352`). |

## Checklist evidence

### (1) Control kwargs — all exist on installed dataclasses

| Usage (join_screen.py) | Installed declaration |
|---|---|
| `ft.ListView(controls, spacing, expand)` (L235-359) | `class ListView(LayoutControl, ScrollableControl, AdaptiveControl)`, `spacing` on `list_view.py:55`, `expand` on base `control.py:21` |
| `ft.Row(controls, spacing, wrap)` (L182,237,253,294,338) | `row.py`: `controls`, `spacing`, `wrap: bool = False` (line 80) |
| `ft.Column(controls, spacing, expand)` (L188,292) | `column.py:33/48`; `expand` inherited from `Control` |
| `ft.Container(width, content)` (L184) | `width` on `layout_control.py:66`; `content` on `container.py:45` |
| `ft.Text(value positional, size, weight, max_lines, overflow, color)` (L186,190,197…) | `text.py`: `value`, `size`, `weight`, `max_lines`, `overflow`, `color` all present |
| `ft.IconButton(icon, icon_size, tooltip, disabled, on_click)` (L206-225,239) | `icon/icon_size/on_click` on `icon_button.py`; `disabled` + `tooltip` on base `control.py:115/96` (universal) |
| `ft.Chip(label, selected, disabled, on_select)` (L296-310,340-344) | `chip.py: Chip(LayoutControl)`: `label`, `selected: bool = False` (55), `on_select` (252); `disabled` inherited from `Control` (`disabled_color` doc confirms disabled state) |
| `ft.FilledButton(content positional, icon, disabled, height, on_click)` (L255,349) | `FilledButton(Button)`; `button.py`: `content`, `icon`, `on_click`; `height`/`disabled` inherited |
| `card_container(content, padding, border_radius, is_dark)` / `section_header(title, subtitle, is_dark)` | Match local signatures exactly (`core/styles.py:27`, `:49`) |

No drag targets / reorder controls on this screen by design (docstring L6: explicit ↑/↓ buttons, no drag API). Swap logic L136-142 is bounds-checked; all three row lambdas bind `idx=i` as a default arg — no stale-closure bug.

### (2) Enums / icons — all verified

`ft.FontWeight.W_600`, `ft.FontWeight.BOLD`, `ft.TextOverflow.ELLIPSIS` confirmed at runtime.
All six icons present in installed `icons.json`: `PLAYLIST_ADD_ROUNDED`,
`MERGE_TYPE_ROUNDED`, `ARROW_UPWARD_ROUNDED`, `ARROW_DOWNWARD_ROUNDED`,
`CLOSE_ROUNDED`, `ARROW_BACK_ROUNDED`.

### (3) Handler arity / async / events

- `on_click=lambda _: ...` / `def _start_join(_)` — single positional event arg, matches `ControlEventHandler` (`on_click: Optional[ControlEventHandler[…]]`).
- `on_select=lambda _, v=value: (…)` — same single-event convention (`chip.py:252`).
- `_add_files(_=None)` is `async`; invoked as `page.run_task(_add_files)` — matches `Page.run_task(handler, *args, **kwargs)` (`page.py:837`) and the 5-screen established idiom. `pick_media_files() -> list[str]` (`media_io.py:65`) awaited correctly; empty-pick early-returns with `busy` reset in `finally`.
- No drag events, no file-picker result objects touched directly on this screen (encapsulated in `MediaIOService`).

### (4) Hooks

`@ft.component`, `ft.context.page`, `ft.use_state`, `ft.use_effect(setup, [])`, `use_controller()`, `use_services()` — all exist (`ft.component`, `ft.context`, `ft.use_state`, `ft.use_effect` runtime-confirmed). Effect setup returns the `run_task` Future; cleanup scheduling only fires `if callable(hook.cleanup)` (`component.py:344,357`) and `cleanup` is `None` here — safe. Effect body `_load_avail` swallows exceptions internally, so mount can never crash.

### (5) `EngineService.concat` params — exact match end to end

Engine (`engine_service.py:1922-1930`): `concat(paths, output_path, container_format="mp4", transition="cut", fade_s=0.5, on_progress=None, cancel_event=None)`.
Screen dispatches via `Job(params={"paths", "container", "transition", "fade_s"})` (L159-164) → `main.py:512-522` reads `p.get("paths", [job.input_path])`, `p.get("container", "mp4")`, `p.get("transition", "cut")`, `p.get("fade_s", 0.5)` → calls `engine.concat(paths=…, container_format=…, transition=…, fade_s=…)`. Container mapping `"mkv"→"matroska"` matches `test_concat_to_mkv` (`container_format="matroska"`). `Job(op, input_path, output_path, params, original_size_bytes)` matches the `Job` dataclass (`core/state.py:88-103`); `ctrl.start_job` / `ctrl.navigate` exist on `ControllerMethods` (`controller_ctx.py:21`).

### (6) Runtime landmines

- **<2 clips**: guarded twice — button `disabled=len(entries) < 2 or busy` (L353) + `_start_join` snack-and-return (L145-147) + engine `ValueError("Pick at least two…")` (`engine_service.py:1934`). Defense in depth, PASS.
- **Reorder math**: adjacent swap with bounds guard (L136-142), PASS.
- **Crossfade gate**: screen mirror (`_crossfade_reason`, L58-89) matches engine `_crossfade_gate` (`engine_service.py:1963-2006`) check-for-check — filters (`alphamerge`+`overlay`+`acrossfade` iff audio), per-clip video presence, fps ±0.05, ≤1080p, `dur <= fade*2+0.2`, audio presence/layout match, frame-grid snap `|round(fade*fps)−fade*fps| ≤ 1e-6`. Expected-duration label `total − fade*(n−1)` matches `test_crossfade_three_clip_duration`. Probe fields used (`video_stream.fps/width/height`, `audio_stream.sample_rate/channels`, `file_size_bytes`, `duration_s`) all confirmed on `MediaInfo`/probe path; `None`-fps/`None`-dims degrade to safe rejection strings, never `TypeError`.
- **Probe failure isolation**: per-file try/except in `_add_files` (L125-126) — one corrupt pick can't kill the batch; cap-at-8 with `ERROR` snack (L99-101).

### (7) Theme re-render

`is_dark_mode(page)` (`core/theme.py:85`) reads observable `state.theme_mode`, subscribing the component — flip re-renders and recomputes `muted`, `is_dark` for cards/headers. No stale-hex path on this screen.

## Test output

`.venv\Scripts\python.exe -m pytest tests/test_concat.py tests/test_crossfade.py tests/test_all_screens_render.py -q` → **29 passed in 47.61s**. Covers lossless join, re-encode-on-mismatch, mkv container, cancel cleanup, crossfade duration math (2- and 3-clip), pixel-blend proof, undersized-clip and missing-filter fallbacks, and in-process body render of all 17 screens including `JoinScreen`.
