# Probe screen audit — `src/screens/probe_screen.py` (Flet 1.0.0)

Ground truth: `.venv/Lib/site-packages/flet` (1.0.0). All `ft.*` signatures checked via
`inspect.signature` on the installed dataclasses; icons checked against `ft.Icons`;
`EngineService.probe`/`remux` read from `src/services/engine_service.py`;
`MediaInfo`/`MediaStreamInfo`/`ChapterInfo` from `src/core/state.py`.
Tests run: `.venv/Scripts/python.exe -m pytest tests/test_remux_dossier.py tests/test_all_screens_render.py -q` → **26 passed in 12.43s**.

## Verdict: no constructor crashes, no dead paths. All findings are SMELL/INFO.

## Findings

| Severity | File:line | Problem | Correct API / note |
|---|---|---|---|
| PASS | probe_screen.py:102-140, 276-431 | `ft.ListView(controls, spacing, expand)` — all kwargs exist on installed `ListView`. | Verified against installed signature; `padding` also exists on `ListView` but is unused here. |
| PASS | probe_screen.py (all `ft.Row`/`ft.Column`) | No `padding` passed to any `Row`/`Column` (they take none). `padding=` appears only on `card_container` → `ft.Container`, where it is valid. `wrap`/`tight`/`spacing`/`alignment`/`horizontal_alignment` all exist. | `Row` has `wrap` and `tight`; status_badge's `tight=True` (styles.py:87) is valid. |
| PASS | probe_screen.py (buttons/text/switch/icon) | `FilledButton(content, icon, height, expand, disabled, on_click)`, `OutlinedButton(content, icon, height, on_click)`, `Text(selectable, max_lines, overflow, expand, font_family)`, `Switch(value, tooltip, on_change)`, `Icon(icon, size, color)`, `IconButton(icon, on_click, tooltip)`, `Container(expand, content)` — every kwarg exists. `height` is on the shared button/layout base. | `ft.Icon` takes `icon` positionally (lines 116, 215 do so — correct). |
| PASS | probe_screen.py:107,116,127,159,171,179,281,364,406,414,424 | All 10 `ft.Icons.*` exist: `ARROW_BACK_ROUNDED`, `ANALYTICS_OUTLINED`, `FILE_OPEN_ROUNDED`, `VIDEOCAM_OUTLINED`, `AUDIOTRACK_OUTLINED`, `SUBTITLES_OUTLINED`, `CONTENT_COPY_ROUNDED`, `SHARE_ROUNDED`, `TRANSFORM_ROUNDED`, `FLAG_ROUNDED`. `FontWeight.BOLD`/`W_600`, `TextOverflow.ELLIPSIS`, `CrossAxisAlignment.CENTER`, `MainAxisAlignment.SPACE_BETWEEN` all exist. | Checked with `hasattr` on installed 1.0.0. |
| PASS | probe_screen.py:96-101 | Hooks discipline correct: single `ft.use_state([])` (line 96) runs unconditionally before the empty-state early return (line 101). No conditional/after-return hooks. No `use_effect` in this screen — there is no probe effect to wire; probing is delegated to `ctrl.pick_media_for("probe")`. | No effect-deps issue exists here by construction. |
| PASS | probe_screen.py:92 | Theme: `is_dark = is_dark_mode(page)` reads the `state.theme_revision` observable (`core/theme.py:96`), subscribing the component so it re-renders on dark/light flip. No direct `page.theme_mode` reads anywhere in this file. | Correct per the CollabShell pattern documented in `core/theme.py:85-102`. |
| PASS | probe_screen.py:128,207,248,264,288,404,412,416,426 | Handler arity/async all match: sync `lambda _:` / `def _start_remux(_)` for `on_click` (accepts 0-or-1-arg); `on_change=lambda _e, i=s.index: ...` for `Switch` (accepts 0-or-1-arg); `async def _share_report()` with zero args launched via `page.run_task(_share_report)` — matches `run_task(handler, *args)` (handler passed un-called, correct). `services.media_io.share_file(str)` awaited, returns `bool` — matches `media_io.py:151`. | `Share.share_files(files, *, text=...)` / `ShareFile.from_path` confirmed on installed service. |
| PASS | probe_screen.py:249-262 → main.py:522-529 | Remux wiring is end-to-end correct: screen builds `Job(op="remux", params={"drop": [...]})`; `main.py:522` dispatches `engine.remux(input_path, output_path, drop_indices=p.get("drop", []))` — key matches. All-excluded guard (line 249 + `disabled=` line 409) prevents the engine's `ValueError("Nothing to keep")`. | `EngineService.remux(input_path, output_path, drop_indices=None, ...)` signature confirmed. |
| INFO | probe_screen.py — | This file never calls `EngineService.probe` directly; media selection flows through `ctrl.pick_media_for("probe")` → controller. So there is no probe-signature call site to mismatch here. Real signature is `probe(file_path: str) -> MediaInfo` (engine_service.py:489). | Nothing to fix in this file. |
| SMELL (low) | probe_screen.py:178-183, 221 | `data`/`attachment` streams fall into the `else` (subtitle-styled) branch: label reads `DATA`/`ATTACHMENT` via `s.stream_type.upper()` but the icon is always `SUBTITLES_OUTLINED` and props show subtitle-oriented `Language` rows. Cosmetic mislabel, not a crash. | Consider an explicit `elif s.stream_type in ("subtitle",)` plus a generic fallback icon (e.g. `ATTACH_FILE_OUTLINED`) for unknown types. |
| SMELL (low) | probe_screen.py:75-76, 185-199 | Disposition rendering iterates dict **keys** (`"/".join(s.disposition)`, `for flag in s.disposition`), which is correct only under the engine's True-only contract (engine_service.py:537-545 stores only set flags). A dict containing `False` values would render disabled flags as active. | Either filter truthy (`[k for k, v in s.disposition.items() if v]`) or document the True-only invariant on `MediaStreamInfo.disposition`. |
| SMELL (low) | probe_screen.py:58, 330 | `info.bitrate // 1000` assumes non-`None` `int`. Safe today (engine defaults `bitrate = 0`, `MediaInfo.bitrate: int`), but a `None` bitrate would `TypeError`. Same for `s.codec_name.upper()` (line 226) — safe today (`"unknown"` fallback) but yields an empty badge for `codec_name=""`. | Defensive: `(info.bitrate or 0) // 1000`, `(s.codec_name or "?").upper()`. |
| SMELL (low) | probe_screen.py:54-61, 77-81 | `build_media_report` interpolates unescaped user data (`file_name`, metadata keys/values, chapter titles, codec names) into markdown. No in-app `ft.Markdown` renders it (report is written to `.md` and shared externally), so impact is limited to external viewers mis-rendering `#`, backticks, etc. | Escape or strip markdown metacharacters if the dossier is ever rendered in-app. |
| INFO | core/state.py:91 | `Job.op` doc-comment omits `"remux"` (and `"join"`), though `op="remux"` dispatches correctly in `main.py:522`. Stale comment only. | Add `"remux"` to the comment. |

## Edge-case repro (report builder — all pass, no crash)

```python
import sys

sys.path.insert(0, "src")
from core.state import MediaInfo, MediaStreamInfo
from screens.probe_screen import build_media_report

base = dict(
    file_path="/x/f.mp4",
    file_name="f.mp4",
    file_size_bytes=1000,
    duration_s=0.0,
    bitrate=0,
    format_name="mp4",
    format_long_name="MP4",
)
build_media_report(MediaInfo(**base, streams=[], metadata={}, chapters=[]))  # empty
build_media_report(
    MediaInfo(
        **base,
        streams=[
            MediaStreamInfo(
                index=0,
                stream_type="video",
                codec_name="h264",
                width=0,
                height=0,
                fps=None,
                pix_fmt=None,
            )
        ],
    )
)  # zero dims
build_media_report(
    MediaInfo(**base, streams=[MediaStreamInfo(index=0, stream_type="data", codec_name="")])
)  # data stream
build_media_report(MediaInfo(**base, chapters=None))  # chapters=None
build_media_report(
    MediaInfo(
        **base,
        streams=[
            MediaStreamInfo(
                index=0,
                stream_type="audio",
                codec_name="aac",
                bitrate=None,
                sample_rate=None,
                channels=None,
                disposition={},
            )
        ],
    )
)  # Nones
# Result: all OK — falsy guards (`if s.width`, `if s.fps`, `if s.disposition`,
# `if info.chapters`, `if info.metadata`) skip every degenerate field.
```

Note: `MediaInfo.chapters` is typed `list` but `None` is tolerated by the builder's truthiness
check; `_fmt_ct` clamps negatives via `max(0, ...)`; no division-by-zero (only `// 1000` by a
constant); `_share_report`'s `write_text` is inside try/except → snackbar, and
`share_file` re-checks existence before invoking the native sheet.
