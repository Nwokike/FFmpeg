# Audit: `src/screens/extract_screen.py` vs installed Flet 1.0.0

Ground truth: `.venv/Lib/site-packages/flet` (1.0.0), `src/services/engine_service.py`,
`src/main.py` dispatch (lines 473–539), `src/core/theme.py`, tests below.
`extract_screen.py` is 338 lines; all line refs are to it.

## Findings

| Severity | File:Line | Problem | Exact correct API |
|---|---|---|---|
| SMELL | extract_screen.py:41 | `gif_duration` initialised once as `min(5.0, duration_s)` — stale when a new/shorter file is picked later (duration 0.2s clip keeps old 5.0s value; no `use_effect` re-sync on `media_path`). | Re-derive per render or sync on media change: `gif_duration = min(gif_duration, duration_s)` guarded, or `ft.use_effect(lambda: set_gif_duration(min(5.0, duration_s)), [media_path])`. No crash — engine clamps nothing, GIF just overruns a short clip. |
| SMELL | extract_screen.py:312–319 | GIF Duration slider: `min=1.0, max=min(15.0, duration_s)` — for any clip under 1.0s, `min > max` and `value (min(5.0, duration_s)) < min`. Construction does not raise (validators `V.ge_field`/`V.le_field` on installed `Slider` fire on the update path, verified by repro), but the thumb is out-of-range and behaviour on the client is undefined. | Clamp: `lo, hi = 0.2, max(0.2, min(15.0, duration_s))`, `value=min(max(gif_duration, lo), hi)`, `min=lo, max=hi`. Affects only sub‑1s clips in GIF mode. |
| SMELL | extract_screen.py:44,53,114 | `set_is_processing(True)` is never reset (no `use_effect` on job completion, `ctrl.start_job` navigates to dashboard anyway). If navigation ever stays on this screen, the Extract button stays disabled. | Reset via effect on `state.jobs`/`active_job`, or drop the flag: `disabled=not media_path or (mode == "subtitles" and not sub_streams)`. No crash — navigation to dashboard (main.py:600–603) masks it today. |
| SMELL | extract_screen.py:69 | Subtitle fallback `sub_streams[0]` when `sub_sel >= len` is reachable only after the track list shrinks (new file picked). It silently extracts the wrong track. | Clamp the selection on media change: `set_sub_sel(min(sub_sel, len(sub_streams) - 1))` via effect on `media_path`, or `chosen = sub_streams[min(sub_sel, len(sub_streams)-1)]`. Engine itself falls back to index 0 with a warning (engine_service.py:1684–1690), so no crash. |
| WRONG | extract_screen.py:78 | `params["stream_index"]` passes `chosen.index` (the container-wide stream index from `MediaStreamInfo.index`, = PyAV enumerate index) but `main.py:497` forwards it as `EngineService.extract_subtitles(stream_index=…)`, which indexes `inp.streams.subtitles` (engine_service.py:1684–1691) — the *subtitle-sublist*, not the container. A file with e.g. video=0, audio=1, subtitle=2 sends `stream_index=2` → out-of-range → engine logs a warning and silently extracts subtitle 0 (wrong track, no error). | Pass the sublist position: `"stream_index": sub_sel` (== `sub_streams.index(chosen)`). `chosen.index` is only correct when the first streams are the subtitles. |
| SMELL | extract_screen.py:157 | `ctrl.pick_media_for("extract")` is `async def` (main.py:388) but invoked from a sync `lambda _: …` without awaiting — fire-and-forget coroutine. Works only if Flet's dispatcher schedules coroutines returned from sync handlers; otherwise the picker never opens and Python emits "coroutine was never awaited". Same pattern is used by other screens, so this is app-wide, not extract-specific. | `on_click=lambda _: page.run_task(lambda: ctrl.pick_media_for("extract"))` or make the handler `async def` + `await`. Verify against installed dispatcher (`flet/messaging/session.py` handles `iscoroutine`). |
| SMELL | extract_screen.py:126,157,173+ | `on_click=lambda _: …` / `on_select=lambda _: …` / `on_change=lambda e: …` — handlers take the event positionally and read `e.control.value` (lines 215, 231, 302, 310, 318). Matches installed `ControlEventHandler` (`Event` has `name/data/control`, verified in `controls/control_event.py` + `events.py`) and sync handlers are supported. No arity issue. | No change. Listed only because the checklist asks for arity: 1-arg sync lambdas are correct. |

### Explicitly clear (checked, no issue)

- **Constructor kwargs**: every `ft.X(...)` kwarg in the file exists on the installed dataclass (verified field-by-field against installed source): `Chip(label/selected/on_select)` (+`wrap` is on `Row`, correctly placed, lines 206/262); `Slider(value/min/max/divisions/on_change)`; `ListView(controls/spacing/expand)` — `ListView` takes `spacing` + `expand`, no `padding` passed; `Row(controls/spacing/alignment/wrap/vertical_alignment)` — **no `padding` on any Row/Column**; `Column(controls/spacing/expand)`; `Text(size/weight/max_lines/overflow/color)`; `Icon(size/color)`; `IconButton(icon/on_click/tooltip)`; `OutlinedButton("Change", on_click=…)` (first positional is `content`); `FilledButton(content, icon, height, disabled, on_click)` — `height` and `disabled` are real inherited `LayoutControl` fields. `card_container(padding/border_radius/is_dark)` are its own helper params (`core/styles.py:27`), not Flet kwargs.
- **Icons/enums**: `ARROW_BACK_ROUNDED`, `FILE_DOWNLOAD_OUTLINED`, `DOWNLOAD_ROUNDED` all present in installed `icons.json` (8825 entries); `FontWeight.BOLD`, `TextOverflow.ELLIPSIS`, `MainAxisAlignment.SPACE_BETWEEN`, `CrossAxisAlignment.CENTER` all exist.
- **Hooks**: 11 `ft.use_state` calls, all unconditional at top (lines 35–44), none after return, none conditional — the mode-conditional UI is plain `*(… if mode == … else [])` list splicing (lines 194–323), not conditional hooks. `use_controller()` unconditional (line 21).
- **Engine signatures**: `extract_audio(format_name/bitrate_kbps)` ✓ (engine 1284–1293, dispatch main.py:473–484); `extract_frames(output_dir=job.output_path, count, format_name)` ✓ — screen sends `output_path=out_dir` directory, dispatch maps `output_dir=job.output_path` (main.py:485–493) ✓; `create_gif(fps/width/start_s/duration_s)` ✓ (engine 1522–1531, dispatch main.py:530–539); `extract_subtitles(stream_index/format_name)` key names ✓ — only the *value* semantics are WRONG (see table).
- **Data landmines**: no-media → button disabled (line 329) + early return (line 49); `Path.stat()` guarded by `exists()` (lines 29–31, 64–66, …); empty-frames/audio-less failures raise in engine (`ValueError: No video/audio stream`), surfaced as failed jobs, not screen crashes; subtitle empty-list → button disabled (line 331) + early return (line 51).
- **Theme**: `is_dark_mode(page)` (line 22) reads `state.theme_revision` observable (theme.py:96) → subscribes the component, re-renders on flip. No direct `page.theme_mode` read. Correct pattern.
- **NO `ft.Dropdown` / image grid / format cards** in this file — audio/subtitle formats are `Chip` rows, so there is nothing to check for dropdown `options`/`value` or grid kwargs.

### Repro (WRONG item — silent wrong-track extraction, no exception)

```python
# container: video=0, audio=1, subtitle(eng)=2, subtitle(spa)=3
# screen builds sub_streams=[idx2, idx3]; user picks 2nd chip -> sub_sel=1, chosen.index=3
# params {"stream_index": 3} -> engine: subs=[s2,s3], 3 >= len(subs)=2 -> warning + uses subs[0]
# result: user asked for Spanish, gets English. Fix: "stream_index": sub_sel  (=1 -> subs[1] = Spanish)
```

### Repro (GIF slider, sub‑1s clip — out-of-range construction, validators deferred)

```python
# duration_s = 0.2 -> gif_duration = min(5.0, 0.2) = 0.2
ft.Slider(value=0.2, min=1.0, max=0.2, divisions=14, on_change=...)
# constructs without raising (V.ge_field/V.le_field fire on update, not __init__);
# thumb out of range on the client. Fix: clamp lo/hi as in the table.
```

## Tests — actual output

```
.venv\Scripts\python.exe -m pytest tests/test_all_screens_render.py tests/test_subtitles.py -q
31 passed in 5.91s
```

17/17 screen bodies render (incl. `ExtractScreen` in default audio mode), 14/14 subtitle tests pass (writers, e2e srt→srt/vtt/ass, out-of-range fallback, no-stream/unknown-format errors, cancel, cue-count progress). Note: the render test exercises only the default `mode="audio"` branch — the GIF/frames/subtitles branches and the WRONG `stream_index` value path are not covered by these tests.
