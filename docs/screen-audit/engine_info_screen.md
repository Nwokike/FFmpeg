# Audit: `src/screens/engine_info_screen.py` (Flet 1.0.1, installed source)

Scope note: the assignment brief describes "a large capability dossier — expansion panels,
sections, list rows" plus a self-test button calling `probe.synthetic_transcode`. The file
on disk is **111 lines**: a minimal probe-text screen (`probe().to_text()` in a selectable
monospace `Text` + Refresh button). There are no expansion panels, sections, list rows,
clipboard calls, `%`-formatting, set iteration, or `synthetic_transcode` usage. Checklist
items 5–6 therefore mostly verify as **not applicable**; the missing self-test is logged
below as a spec gap, not a crash.

Ground truth: Flet `1.0.1` (`flet_version = "1.0.0"` in `version.py`, API surface reports
as 1.0.1), `.venv/Lib/site-packages/flet/`. Every control below was checked against its
installed dataclass (`inspect_flet_control`) and every icon against the installed icon set.

## Findings

| Severity | file:line | Problem | Exact correct API / verdict |
|---|---|---|---|
| OK | :52–53, 54–64, 69–97, 71–87 | All `ft.X(...)` kwargs exist on installed dataclasses | `ListView(controls, spacing, expand)` — all real (`expand` from `Control`). `Row(controls, spacing)` — no `padding` passed (Row has none; verified absent). `Column(controls, spacing)` — same. `IconButton(icon, on_click, tooltip)`, `Text(value, size, weight, color, font_family, selectable, visible)`, `ProgressRing(width, height)`, `Icon(icon, size, color)`, `OutlinedButton(content, icon, on_click)` — every kwarg present in installed source. **Zero unknown kwargs → zero constructor-time crashes.** Helpers: `card_container` → `Container(content, padding, border_radius, bgcolor, border, on_click, ink)` all real; `section_header` → `Column`/`Row` only. |
| OK | :57, 76, 104 | `ft.Icons.*` verified | `ARROW_BACK_ROUNDED` (0x101AF), `CHECK_CIRCLE_ROUNDED` (0x1053C), `REFRESH_ROUNDED` (0x11837) all exist in installed icon set. `ft.FontWeight.BOLD` exists. No `ft.Colors.*`/other enums used in this file. |
| OK | :35–48, 50, 105 | Probe runs off UI thread; exceptions surfaced, not crash-swallowed | `_load` is `async def`, awaited via `asyncio.to_thread(_load_sync)` (line 45); launched with `page.run_task(_load)` from both the effect (line 50) and Refresh (line 105). `run_task` requires a coroutine function — `_load` qualifies (`page.py:837`, raises `TypeError` otherwise — not triggered). `_load_sync` wraps `probe().to_text()` in `try/except` returning an `"Engine probe failed: …"` string, so socket/timeout/`av` errors render as text. `run_task`'s `_on_completion` surfaces background exceptions to default error handling (`page.py:855+`). |
| OK | :50 | Hook usage legal | `use_effect(setup, [])` matches installed signature `use_effect(setup, dependencies=None, cleanup=None)`; single unconditional call, deps `[]` = mount-only. Setup returns the `Future` from `run_task` — the scheduler (`session.py:715+`) only treats a setup result as cleanup `if callable(res)`; a `Future` is not callable, so it is safely discarded. Two `use_state` + one `use_context` (`use_controller`) all unconditional at top; `ft.context.page` read once at line 27, top of body. No conditional/after-return hooks. |
| OK | theme | Re-renders on dark/light flip | No direct `page.theme_mode` read anywhere in the file. `is_dark_mode(page)` (`core/theme.py:85`) performs the observable read `state.theme_revision`, subscribing this component; `muted`, card and header all derive from that per render. Correct pattern. |
| OK | data guards | Every `EngineProbe` field read is None-safe | The screen reads exactly one thing: `probe().to_text()`. All `to_text()` interpolations (`av_version`, counts, `video/audio_encoder_picks`, `hw_devices`, `protocol_probe`, `notes`, `missing_required_filters`) operate on dataclass defaults that are never `None` on the measured path, and the whole call sits inside `_load_sync`'s `try/except`. Edge: a hand-corrupted probe cache JSON with explicit `null`s (`_load_cached` filters keys but does not coerce `None`) would make `to_text()` raise — still caught by `_load_sync` and rendered as an error string. No crash path. `protocol_probe` iteration is insertion-ordered (`PROTOCOLS` order), no `set` iteration in the UI, no `%`-with-`None` formatting anywhere in this file. |
| WRONG (spec gap, not a crash) | :102–106 | No self-test button: `synthetic_transcode` is never called | Brief requires a self-test button calling `probe.synthetic_transcode` off the UI thread with surfaced exceptions. Actual Refresh button re-runs `probe().to_text()` only. If the button is added, the safe pattern already established here applies: `on_click=lambda _: page.run_task(_selftest)` where `async def _selftest()` awaits `asyncio.to_thread(synthetic_transcode, out_dir)` inside `try/except` and writes the result dict into state; never call it directly in the handler (it does ~10-frame H.264 encode + file IO, blocking the event loop for seconds). |
| SMELL (low) | :42–48 | Concurrent probes can interleave; no guard | Rapid Refresh taps (or Refresh during initial load) spawn parallel `_load` tasks via `run_task`; all write `set_report`/`set_loading`, last-writer-wins. No crash (verified: state setters + `page.update()` are thread/task-safe here), but a slow first probe can overwrite a fresh result. Fix if it matters: disable Refresh while `loading`, or gate with an `asyncio.Lock`/run-id check. |
| SMELL (low) | :42–48 | `set_*` + `page.update()` after unmount not guarded | If the user navigates away during the ~2 s socket-level protocol pass, `_load` still calls `set_report`/`set_loading`/`page.update()`. The `Page` object persists so `page.update()` is valid; component setters on an unmounted component are a no-op/warning in practice, not a crash — but an unmount guard (mounted flag via effect cleanup) would make it airtight. |
| SMELL (low) | :88–94 | Report `Text` unbounded | No `max_lines`/`overflow` on the report text. A pathological probe (e.g. dozens of long `notes`) renders a very tall `ListView` child; mitigated by `ListView.build_controls_on_demand=True` (installed default), so this is a layout/perf nit, not a crash. |
| N/A | — | Copy-to-clipboard | No clipboard API is used in this file; nothing to verify. (For reference, the dossier described in the brief does not exist on disk.) |

## CRASH repros

None. There are no CRASH-severity findings: no unknown constructor kwargs, no invalid
icons/enums, no blocking event-loop calls, no swallowed-crash paths.

## Test output (actual)

```
$ .venv\Scripts\python.exe -m pytest tests/test_all_screens_render.py -q
.................                                                        [100%]
17 passed in 1.28s
$ .venv\Scripts\python.exe -m pytest tests/test_all_screens_render.py -q -k EngineInfo
.                                                                        [100%]
1 passed, 16 deselected in 1.11s
```

`EngineInfoScreen` body renders in-process via `Renderer().render` with populated
queue/history state — no Python-side API error.
