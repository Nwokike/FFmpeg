# Audit: `src/screens/settings_screen.py` (Flet 1.0.0)

Ground truth: `.venv/Lib/site-packages/flet/` (Flet 1.0.0). All constructor
signatures dumped from the installed package; protocol encoder read at
`flet/messaging/protocol.py`; `run_task` at `flet/controls/page.py:837`;
effect scheduler at `flet/messaging/session.py:667-737`.

Test output (actual):
`./../ffmpeg/.venv/Scripts/python.exe -m pytest tests/test_all_screens_render.py -q`
-> `17 passed in 4.13s` (includes `SettingsScreen`; render-only pass, see note below).

> Why the suite passes but the screen still crashes: the render test only
> executes the component body. Both CRASH items below fire *after* render —
> one on the msgpack transport during `page.update()`, the other on tap of a
> dialog button. Neither path is exercised by `test_all_screens_render.py`.

## Findings

| Severity | File:Line | Problem | Correct API (installed source) |
|---|---|---|---|
| CRASH | `settings_screen.py:197` | `selected={active_theme}` passes a **`set`**; the field is declared `selected: list[str]` (`segmented_button.py`, `SegmentedButton.__dataclass_fields__['selected'].type == list[str]`). Construction and `before_update()` accept it (duck-typed `len()` checks in `__validation_rules__`), but the transport encoder `configure_encode_object_for_msgpack` (`protocol.py`) handles only `list`/`dict`/dataclass/scalar — a `set` falls through to msgpack, which raises `TypeError: can not serialize 'set' object` on the first `page.update()` that ships the control. Render tests never serialize, so they stay green. | `selected=[active_theme]` (`list[str]`). Minimal repro: `sb = ft.SegmentedButton(selected={'dark'}, segments=[ft.Segment(value='dark', label=ft.Text('Dark'))]); msgpack.packb({'s': sb}, default=configure_encode_object_for_msgpack(ft.Control))` -> `TypeError: can not serialize 'set' object`; with `selected=['dark']` it packs (111 bytes). |
| CRASH | `settings_screen.py:114` | Copy button: `page.run_task(services.clipboard.set, log_text)` dereferences `services.clipboard` with **no None guard**. In the test harness `Services()` defaults `clipboard=None`, and any wiring gap (desktop/dev, late registration) makes this `AttributeError: 'NoneType' object has no attribute 'set'` at tap time. Same latent pattern at line 308-310 (`services.url_launcher.launch_url`, line 309) — `UrlLauncher` is registered in `main.py:200-205`, but the screen itself guards neither. (Contrast: `services.storage` line 82 and `services.ads` line 157 ARE guarded.) | Guard before use, e.g. `if services.clipboard is None: show_snack(page, "Clipboard unavailable"); return` — or disable the button when the service is absent. `run_task` itself is fine here: `ft.Clipboard.set` and `ft.UrlLauncher.launch_url` are both `async def` (coroutine functions), satisfying `page.py:849` (`raise TypeError("handler must be a coroutine function")` otherwise). Minimal repro: `class S: clipboard=None; S().clipboard.set` -> `AttributeError: 'NoneType' object has no attribute 'set'`. |
| WRONG | `settings_screen.py:203` | `on_change=lambda e: _update_theme(next(iter(e.control.selected)))` assumes `selected` is non-empty. With the current single-select + `allow_empty_selection=False` (default) it cannot empty via tap, but after the CRASH-1 fix the handler reads server state; a defensive `if not e.control.selected: return` costs one line. The event field itself is correct: `Event` has `{name, data, control}` (`control_event.py`), and reading `e.control.selected` is the documented pattern (Dart reports selection via `data`, the control prop is the synced equivalent). | Add empty guard; keep `e.control.selected` (valid). |
| WRONG | `settings_screen.py:63` | `ft.use_effect(lambda: page.run_task(_load_engine_counts), [])` returns the `Future` from `run_task` as the effect's return value. The scheduler (`session.py:729-730`: `res = hook.setup(); if callable(res): hook.cleanup = res`) only treats *callable* returns as cleanup — a `Future` is not callable, so this is benign today, but it is one refactor away from a stored-cleanup bug. | `ft.use_effect(lambda: (page.run_task(_load_engine_counts), None)[1], [])` or a `def` body that returns `None`. |
| SMELL | `settings_screen.py:85-91`, `156-158` | `_do_clear_cache` and `_open_activity_terminal`/`_open_engine_inspector` call `page.update()` / `show_snack` from sync tap handlers — correct in Flet 1.0 (sync handlers run on the UI thread; only the probe is offloaded via `asyncio.to_thread` + `run_task`, which is the right pattern). No change needed; noted because `page.update()` from inside a `run_task` coroutine (line 59) is also legal (thread-safe via `run_coroutine_threadsafe`) but redundant — the state setters already schedule a re-render. | No fix required. |
| SMELL | `settings_screen.py:232` | `format_bytes(cache_size)` — `cache_size` is `int` from `get_cache_size_bytes()` (sums `st_size`, `OSError`-guarded per file); `format_bytes` accepts `int \| float` and `float(None)` would raise, but no path here yields `None` (no `cache size None` state exists in `state.py`; `get_cache_size_bytes` always returns `int`). | No fix required; claim in the assignment brief about "cache size None" does not reproduce. |
| SMELL | `settings_screen.py:66-83` | `_update_theme` checklist: writes `state.set_setting("theme_mode", mode_str)` (whole-value, line 69) — correct; mirrors to `page.theme_mode` (lines 70-75); sets `state.theme_mode = page.theme_mode` (line 79); bumps `state.theme_revision += 1` (line 80); persists via guarded `services.storage.set` (lines 82-83). No in-place `state.settings[...] = ...` mutation anywhere in this file (only read at line 48). Matches the `main.toggle_theme` contract. | No fix required — all five checklist items pass. |

## Explicitly checked, no bug

1. **Constructor kwargs**: every `ft.X(...)` in the file exists on the installed
   dataclass — `ListView(spacing, expand)`, `Column(controls, spacing, scroll)`,
   `Row(controls, spacing, alignment)`, `Container(content, width, height,
   padding)`, `Icon(icon, size, color)` (positional icon is the first
   `__init__` param), `Text(value positional, size, weight, color,
   font_family, selectable)`, `TextButton("Copy" positional, on_click)`,
   `OutlinedButton("Clear" positional, icon, on_click)` (content/icon are the
   first `Button` params), `AlertDialog(title, content, actions)`,
   `SegmentedButton(selected, segments, on_change)`, `Segment(value, label)`,
   `ListTile(leading, title, subtitle, on_click)`, `Divider(height)`. No
   `Row`/`Column(padding=...)` anywhere. Verified via
   `inspect.signature(ft.X)` against the venv.
2. **Icons/enums**: all nine `ft.Icons.*_ROUNDED` members exist
   (`DARK_MODE_ROUNDED`, `LIGHT_MODE_ROUNDED`, `CLEANING_SERVICES_ROUNDED`,
   `DELETE_SWEEP_ROUNDED`, `TERMINAL_ROUNDED`, `INFO_OUTLINE_ROUNDED`,
   `SECURITY_ROUNDED`, `SYSTEM_UPDATE_ROUNDED`, `OPEN_IN_BROWSER_ROUNDED`);
   `FontWeight.W_600`, `MainAxisAlignment.SPACE_BETWEEN`, `ScrollMode.AUTO`,
   `ThemeMode.{DARK,LIGHT,SYSTEM}` all exist. No typos, no dummy-icon risk.
3. **Handlers/arity**: all tap handlers are sync zero-or-one-arg lambdas/defs —
   legal (Flet calls with zero or one event arg). `_load`/`_load_engine_counts`
   are `async def`, awaited via `page.run_task` — legal. No Switch/Dropdown/
   Slider on this screen, so no change-event field question arises. Dialogs use
   `page.show_dialog(AlertDialog(...))` / `page.pop_dialog()` — correct
   (`show_dialog(dialog: DialogControl)`, `AlertDialog` and `SnackBar` both
   subclass `DialogControl`).
4. **Hooks**: no conditional/after-return hooks (single `use_effect` at top
   level, deps `[]` = mount-only — correct). Probe failure path is
   try/except-guarded both times (lines 54-61 log-and-leave-subtitle-default;
   lines 124-129 snack-and-return before `show_dialog`) — render can never see
   a probe exception.
5. **Services**: `storage.get/set` exist (`storage_service.py:30,34`);
   `ads.show_privacy_options` exists (`ad_service.py:93`, internally
   None-guards `_consent_manager`); `ctrl.check_update` wired in
   `main.py:702`; `MemoryLogHandler.get_logs()` always returns a list
   (fallback `["No logs recorded yet."]`, `logger_handler.py:34-38`).
6. **Platform**: no `page.platform` use in this file (the brief's desktop-
   platform landmine does not apply here; `ad_service._is_mobile` already
   try/excepts platform detection).
