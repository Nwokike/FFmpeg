# Terminal Screen Audit — `src/screens/terminal_screen.py`

Ground truth: installed Flet 1.0 at `.venv/Lib/site-packages/flet/` (dataclass
sources + runtime `__dataclass_fields__` checks). Tests run with
`.venv/Scripts/python.exe -m pytest tests/test_command_parser.py tests/test_tab_crashes.py -q`.

## Result: no render crash reproduced

- Empty-state `Renderer` render of `TerminalScreen` (via `PYTHONPATH=src`,
  `ServiceCtx`/`ControllerMethodsCtx` wrapper): **OK**.
- Row/Column take no `padding` anywhere in this file: **pass** (no occurrences).
- `ft.Icons.*` (7 used): all `hasattr` True —
  `ARROW_BACK_ROUNDED`, `TERMINAL_ROUNDED`, `HELP_OUTLINE_ROUNDED`,
  `PLAY_ARROW_ROUNDED`, `RULE_ROUNDED`, `LOCK_ROUNDED`, `HISTORY_ROUNDED`.
- `ft.Colors.with_opacity(0.15, PRIMARY)` (line 176): **correct** — installed
  signature is `with_opacity(opacity, color)`, runtime returns `'#3C8038,0.15'`.
  (Earlier `dir()` confusion was Enum-method lookup noise; direct call confirms.)
- Enums `ft.FontWeight.BOLD / W_600`, `ft.ScrollMode.AUTO`,
  `ft.CrossAxisAlignment.CENTER`: all exist.

## Findings

| Severity | File:line | Problem | Exact correct API |
|---|---|---|---|
| WRONG (high) | `terminal_screen.py:177` | `ft.RoundedRectangleBorder(RADIUS_MD)` passes `12` positionally, which binds to `side`, not `radius`. Installed source: `RoundedRectangleBorder(OutlinedBorder)` with `radius: BorderRadiusValue = 0`, `side` inherited first. Repro below. Sibling files (`brand_header.py:51`, `update_dialog.py:100`) use the keyword form. Renderer did NOT crash on empty state, so this is a silent mis-shape / serialization hazard, not a confirmed render crash. | `ft.RoundedRectangleBorder(radius=RADIUS_MD)` |
| SMELL | `terminal_screen.py:198-204` | `ft.TextField` has no `on_submit`, no `autofocus`, no `KeyboardListener`/`on_key` anywhere in the file. Constructor kwargs used (`value`, `on_change`, `hint_text`, `dense`, `expand`) all verified present in `TextField.__dataclass_fields__`, and `on_change` arity (`e.control.value`) is correct — but keyboard Enter does nothing; user must click Run. There is no key-event class/field to verify (no handler exists). | Add `on_submit=_submit` (arity `(_=None)` already compatible) and consider `autofocus=True`. |
| SMELL | `terminal_screen.py:84-88` | `services.engine.probe(src)` has no `None` guard (`Services.engine` defaults to `None`). Currently survives only because the `except Exception` catches the resulting `AttributeError` and renders `probe failed: 'NoneType'…`, which is cryptic. | `engine = services.engine; if engine is None: entry.append(("err", "engine not ready")); else: probe…` |
| SMELL (low) | `terminal_screen.py:106-107` | `_confirm` dereferences `pending` (`plan.op`) with no `None` check. Unreachable via UI (buttons only render when `pending is not None`), but a double-click before re-render unmounts could fire with `pending=None` → `AttributeError`. | `if pending is None: return` guard at top of `_confirm`. |
| SMELL | `terminal_screen.py:249-262` | Output `ListView` renders **all** lines as `ft.Text` children every render, unbounded, with no `build_controls_on_demand`/cap. `spacing`, `auto_scroll`, `controls` props are valid; `font_family="Roboto Mono"` falls back silently if unbundled. Long sessions degrade linearly. | Cap lines (e.g. last 500) or paginate; optional `build_controls_on_demand`. |
| SMELL (minor) | `terminal_screen.py:95,101,104` | `set_lines(lines + …)` / `set_history(…history…)` close over stale `lines`/`history`; rapid double-submit can drop a line. History lambda `lambda _, c=cmd:` binding is correct (no late-binding bug). | Functional update if the hooks API supports it, else disable Run while handling. |
| OK | `terminal_screen.py:44` | Theme: `is_dark = is_dark_mode(page)` reads `state.theme_revision` observable → subscribes component; `state.theme_mode` is the single truth with `page.platform_brightness` fallback for SYSTEM. No direct `page.theme_mode` reads; all render paths derive from `is_dark`. | No change. |
| OK | engine path | Screen never calls `EngineService.record(...)` directly — it enqueues `Job(op=plan.op, …)` via `ctrl.start_job`, matching the `Job` dataclass. `record` real signature verified: `(input_url, output_path, container_format=None, duration_s=None, on_progress=None, cancel_event=None)`; dispatcher (`main.py:503`) passes `container_format=p.get("format")`. Parser never emits `op="record"`, so no inference gap here. `concat` container inference (`out_ext or "mp4"`) matches `engine.concat(container_format)` dispatch. All 7 parser ops covered by dispatcher. | No change. |
| OK | `page.run_task` | Screen makes zero `page.run_task` calls. | N/A — no violation. |

## Repro (WRONG item, line 177)

```python
import flet as ft

b_bad = ft.RoundedRectangleBorder(12)  # what the screen does
b_good = ft.RoundedRectangleBorder(radius=12)  # correct
print(b_bad)  # RoundedRectangleBorder(side=12, radius=0)   <- 12 lands in side
print(b_good)  # RoundedRectangleBorder(side=None, radius=12)
```

## Test output (actual)

```
............................  [100%]
28 passed in 1.09s
```

`tests/test_command_parser.py` + `tests/test_tab_crashes.py`, run via
`.venv/Scripts/python.exe -m pytest tests/test_command_parser.py tests/test_tab_crashes.py -q`.
