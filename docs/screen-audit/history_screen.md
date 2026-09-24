# Screen audit — `src/screens/history_screen.py`

Date: 2026-09-23 · Flet 1.0.0 (installed source in `.venv/Lib/site-packages/flet/`)

## Verdict

No bad `ft.X(...)` kwarg in this file — every constructor arg was checked against the
installed dataclass fields and all exist (Row has no `padding`; the file already puts it
on `Container`, lines 86/96). All `ft.Icons.*` members exist. Hooks, theme subscription,
and controller signatures all check out. **The crash is data-dependent, not structural:**
it fires only when the user types in the search box (or swipes-to-delete) on history
entries whose `input_path` / `output_path` / `op` is `None`. The render suite stays green
because its fixture uses `""` paths and never types a query (`search_query` starts `""`,
so the filter expression never executes in tests).

## Findings

| # | Sev | Location | Problem | Correct API / fix |
|---|-----|----------|---------|-------------------|
| 1 | CRASH | `history_screen.py:29-39` | Filter does `Path(j.input_path).name` and `j.op.lower()`. `Path(None)` raises `TypeError: argument should be a str or an os.PathLike object…`, `None.lower()` raises `AttributeError`. Fires the moment the user types one character with a `None`-path/None-op entry in history (search box only renders when `len(history) > 2`, so ≥3 items + 1 keystroke). | Coerce before use: `(j.input_path or "")`, `(j.op or "")`, `(j.output_path or "")`, i.e. `Path(j.input_path or "").name.lower()`. `Path("")` → `""`, safe. |
| 2 | CRASH | `history_screen.py:67` | Swipe-delete builds the Undo snack text with `Path(job.output_path).name`. Same `TypeError` when `output_path` is `None`. (`show_snack` itself never raises — the f-string arg evaluates first.) | `Path(job.output_path or "").name or (job.op or "job")`. Installed `show_snack(page, message, *, bgcolor, duration_ms, action)` signature already matches. |
| 3 | CRASH (latent) | `components/job_card.py:172` via this screen | `if job.original_size_bytes > 0` raises `TypeError` when sizes are `None` (explicit JSON `null`, see #5). Reachable: any `completed` history card. | `(job.original_size_bytes or 0) > 0 and (job.output_size_bytes or 0) > 0`. `format_bytes(int\|float)` in `storage_paths.py` otherwise fine. |
| 4 | CRASH (latent) | `components/job_card.py:157` via "Now Processing" | `max(0.0, min(job.progress, 1.0))` raises `TypeError` if `progress` is `None`. | Clamp `(job.progress or 0.0)`. `ft.ProgressBar(value, color, bgcolor)` fields verified present. |
| 5 | WRONG | `main.py:296-311` (restore) | `d.get("input_path", "")` returns `None` (not `""`) when stored JSON has explicit `null` — this manufactures the `None` Jobs that detonate #1/#2. Missing ids become `id=""` → duplicate `ValueKey('')` on every `Dismissible` (history_screen.py:77). Restore also drops `progress/status_message/error_message/finished_at`. | `d.get("input_path") or ""` (same for `output_path`, `op`), `d.get("id") or <new uuid>`, persist/restore the dropped fields. `ft.ValueKey(value)` positional is correct per installed `keys.py`. |
| 6 | SMELL | `history_screen.py:129` | Search box gated on `len(history_items) > 2` while the comment says "if there are history items" — 1–2 items get no search. | Gate on `if history_items` (or `> 0`) to match intent. |
| 7 | SMELL | `history_screen.py:76-102` | `Dismissible` has `on_dismiss` but no `on_confirm_dismiss`; an accidental swipe deletes immediately, Undo lives only 5 s in the snack. | Either keep + document, or add `on_confirm_dismiss` → `confirm_dismiss(bool)` per installed `dismissible.py`. `key/background/secondary_background/on_dismiss` kwargs all verified present. |

## Explicitly checked — PASS

- **Constructors:** `AlertDialog(title/content/actions/actions_alignment)`, `TextButton/FilledButton/OutlinedButton(content positional str, icon, bgcolor, on_click)`, `TextField(value/hint_text/prefix_icon/dense/on_change)`, `Container(padding/bgcolor/border_radius/alignment/height)`, `Row/Column(controls/spacing/alignment/scroll/expand)`, `Icon(icon/color/size)`, `Dismissible(key/content/background/secondary_background/on_dismiss)`, `SnackBarAction(label/on_click)`, `ft.Padding.only(left=/right=)`, `ft.Margin` — every kwarg exists on the installed dataclass; `Row` correctly has **no** `padding` field.
- **Icons:** `DELETE_OUTLINE_ROUNDED`, `DELETE_SWEEP_ROUNDED`, `SEARCH_ROUNDED`, `HISTORY_ROUNDED` all present (`hasattr(ft.Icons, …)` True). `ft.Alignment.CENTER_LEFT/RIGHT`, `ScrollMode.AUTO`, `TextOverflow.ELLIPSIS`, `FontWeight.BOLD/W_500/W_600`, `MainAxisAlignment.*`, `Colors.WHITE` all present.
- **Events:** `on_change=lambda e: set_search_query(e.control.value)` — `Event.control` field exists, `TextField.value` exists; 1-arg handler accepted. `on_click`/`on_dismiss` accept zero-arg or event-arg callables per installed signatures, so `_(_)`, `lambda _: …` are fine.
- **Hooks:** single unconditional `ft.use_state("")` (line 26) + `use_controller()` → `use_context` (no conditional/after-return hooks). `ft.component`, `ft.context.page`, `create_context` all exist.
- **Controller:** `delete_job(str)→None`, `restore_job(Job)→None`, `clear_history()→None`, `select_tab(int)→None` in `main.py:374,623,628,634` match all call sites; all sync (called sync — correct).
- **Theme:** `is_dark_mode(page)` called on every render (line 24); it reads observable `state.theme_revision`. Zero direct `page.theme_mode` reads in this file (grep-confirmed).

## Minimal repros (throwaway scripts, removed after run)

```python
# CRASH-1 — filter, history_screen.py:29-39 logic verbatim:
Job(op="convert", input_path=None, output_path=None, status="completed")
# with search_query="x" → TypeError: … not 'NoneType'
# CRASH-2 — history_screen.py:67 verbatim:
Path(None).name  # → TypeError
```

## Actual test output

- `.venv\Scripts\python.exe -m pytest tests/test_all_screens_render.py -q` → **17 passed in ~9s** (HistoryScreen included; fixture uses `""` paths, empty query — crash paths not exercised).
- `.venv\Scripts\python.exe -m pytest tests/test_routes.py -q` → **5 passed**.
- Adversarial probes: 7/7 full-tree renders with `search_query=""` passed (expected — filter/dismiss code only runs on user input); direct evaluation of the filter and dismiss expressions with `None` inputs crashed as above.
