# Screen audit — `src/screens/streams_screen.py` (Flet 1.0.1)

Date: 2026-09-23 · App code NOT modified (read-only audit).
Ground truth: `.venv/Lib/site-packages/flet/` (flet 1.0.1), `src/core/state.py`,
`src/core/engine_probe.py`, `src/services/engine_service.py`, `src/main.py`.

> Scope note: this file is a **stream recorder** (enqueues `op="record"` jobs).
> It never touches `MediaInfo`/`MediaStreamInfo`, `EngineService.probe`/`remux`,
> checkboxes, lists, or expansion panels — checklist items (5) and (6) are
> N/A here (the `record` wiring is verified instead). No `bitrate=None` /
> `disposition` / chapters / attachment-stream landmines are reachable.

## Verdict

One **CRASH** bug (`Chip(avatar=…)`), currently invisible to the test suite
because the render harness never executes screen bodies (see finding 2).
Everything else verifies clean against installed source.

## Findings

| # | Severity | File:line | Problem | Exact correct API |
|---|----------|-----------|---------|-------------------|
| 1 | CRASH | `streams_screen.py:87-94` | `ft.Chip(..., avatar=...)` — `Chip` has **no** `avatar` property in flet 1.0.1 (71 props verified via `flet/controls/material/chip.py`; direct repro raises `TypeError: Chip.__init__() got an unexpected keyword argument 'avatar'`). Fires the moment `_proto_chip()` runs on-device, i.e. every visit to the Streams tab. | `leading=` (the documented slot for an Icon): `ft.Chip(label=..., leading=ft.Icon(ft.Icons.CELL_TOWER_ROUNDED, size=16, color=color))` — matches the class docstring example `ft.Chip(label="Explore topics", leading=ft.Icon(...))`. |
| 2 | WRONG (test harness) | `tests/test_all_screens_render.py:86-89` | The "body-executing render pass" does **not** execute bodies. `Renderer.render(root_fn)` just calls `root_fn`, and each `@component` call goes through `render_component()` (`flet/components/component.py:476`), which returns a frozen `Component` wrapper **without calling `fn`**. Bodies only run in `Component.update()/before_update()` behind a mounted session. Proven: rendering `StreamsScreen` in-process returns fine despite finding 1. So the suite cannot catch any Python-side API error in any screen body, contrary to the module docstring. | Execute bodies in-process: call the unwrapped impl (`StreamsScreen.__component_impl__`) inside a renderer/context frame with stub `page` + controller, or drive `Component.before_update()` on a mounted fake session. Until then, treat this file's "26 passed" as import-level only. |
| 3 | SMELL | `streams_screen.py:74` | `ft.use_effect(lambda: page.run_task(_load_protocols), [])` returns the `concurrent.futures.Future` from `run_task` as the setup result. Harmless today (scheduler in `flet/messaging/session.py:718-731` only adopts the result `if callable(res)`), but one refactor away from a cleanup-type bug, and non-idiomatic — siblings do the same, so fix everywhere or nowhere. | `ft.use_effect(lambda: page.run_task(_load_protocols) or None, [])`, or better `async def _setup(): await _load_protocols()` + `ft.use_effect(_setup, [])` (scheduler awaits coroutine setups natively). |
| 4 | SMELL (latent, out of scope but on this screen's path) | `core/engine_probe.py:294` | `_probe_protocol` catches `av.error.ProtocolNotFound`, which **does not exist** on the installed av (`hasattr → False`; the real name is `av.error.ProtocolNotFoundError`, as used correctly in `engine_service.py:record`). Only the string fallback (`"protocol not found"` in `str(exc)`) saves it. This is the function the Streams badge calls twice per visit. | `except av.error.ProtocolNotFoundError:` (or `getattr(av.error, "ProtocolNotFound", av.error.ProtocolNotFoundError)` for cross-wheel safety). |
| 5 | OK (info) | `streams_screen.py:199-205` | `ft.FilledButton("Start Recording", icon=..., height=48, disabled=..., on_click=...)` — all verified: positional `content: str \| Control`, `icon` on `Button`, `height` on `LayoutControl`, `disabled` on `Control`. `disabled=not url_ok` correctly gates recording. | — |
| 6 | OK (info) | `streams_screen.py:136-143` | `TextField(value, label, hint_text, prefix_icon, dense, on_change)` — every kwarg exists in `flet/controls/material/textfield.py`; `prefix_icon: IconData \| Control` accepts the `LINK_ROUNDED` IconData directly. | — |
| 7 | OK (info) | `streams_screen.py:148-167` | Selectable `Chip(label, selected, on_select)` usage is correct; `on_select`/`on_click` are mutually exclusive (validation rule) and only `on_select` is passed. `lambda _, f=ext: ...` correctly captures the loop var and accepts the 1-arg `Event[Chip]`. Non-selectable badge chip (after finding-1 fix) takes neither handler, which is legal. | — |
| 8 | OK (info) | handlers/events | `Event` fields are `(name, data, control)` — `e.control.value` (line 142) is valid. `_start(_)` 1-arg `on_click` valid (0-or-1-arg handlers). `_load_protocols` is a genuine coroutine; `asyncio.to_thread(_check_protocols_sync)` keeps socket probes off the UI thread; exceptions inside are caught per-scheme. | — |
| 9 | OK (info) | icons / enums / hooks | All four icons exist in installed `icons.json`: `CELL_TOWER_ROUNDED`, `FIBER_MANUAL_RECORD_ROUNDED`, `ARROW_BACK_ROUNDED`, `LINK_ROUNDED`. `FontWeight.BOLD` / `W_600` exist (`flet/controls/types.py`). `ft.component`, `ft.use_state`, `ft.use_effect`, `ft.context.page`, `Page.run_task(handler)` all verified present with matching signatures. `Row(wrap)`, `ListView(spacing, expand)`, `Column(spacing)` all exist. | — |
| 10 | OK (info) | engine wiring | `Job(op="record", input_path=url, output_path=temp/stream_<ts>.<ext>, params={url, format, duration_s})` matches the `main.py:503` dispatch exactly (`input_url=p.get("url", job.input_path)`, `container_format=p.get("format")`, `duration_s=p.get("duration_s")`), and `EngineService.record(input_url, output_path, container_format, duration_s, on_progress, cancel_event)` accepts all of them. `_FORMATS` maps `ts→mpegts`, `mkv→matroska`, `mp4→None` (infer) — all valid libavformat muxer names. | — |
| 11 | OK (info) | theme re-render | `is_dark = is_dark_mode(page)` reads the `state.theme_revision` observable (`core/theme.py:96`), subscribing the component — theme flips re-render this screen; no stale-hex path (all colors resolve per-render). | — |

Note: `verify_flet_code` emitted `enum-value` noise (`'#fff' is not a valid Colors`)
against plain hex strings — false positive; color props are typed
`str | Colors | ...` (`ColorValue`), so hex literals like `PRIMARY = "#3C8038"`
are valid. Its `bad-kwarg` hit on `Chip.avatar` is real and matches finding 1.

## Test output

`.venv\Scripts\python.exe -m pytest tests/test_all_screens_render.py tests/test_remux_dossier.py -q`
→ **26 passed in 10.26s**. (Caveat: per finding 2, the 17 render tests do not
execute screen bodies, so they pass with finding 1 present.)
