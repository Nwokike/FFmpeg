# Audit: `src/screens/onboarding_screen.py` (Flet 1.0.0)

Ground truth: project venv `<repo>\.venv\Lib\site-packages\flet\`
reports Flet **1.0.0** (`flet.__file__` inside that venv). The MCP `get_flet_version`
tool pointed at a *different* bundled copy (1.0.1, uv cache) — every row below was
re-verified by direct source read + runtime construction against the **project 1.0.0 venv**.
Tests: `22 passed in 0.78s`
(`tests/test_all_screens_render.py` + `tests/test_theme_and_onboarding.py`, `-q`).

## Findings table

| Sev | File:Line | Problem | Exact correct API (installed 1.0.0 source) |
|-----|-----------|---------|--------------------------------------------|
| OK | `onboarding_screen.py:29,35` | Suspected `ft.Icons` typos | **No typo.** Runtime: `hasattr(ft.Icons,'AUTO_AWESOME_ROUNDED') == True`, `hasattr(ft.Icons,'SHIELD_ROUNDED') == True`. `icons.py` builds members from `icons.json` with a `_missing_` fallback, so names resolve. |
| OK | `onboarding_screen.py:89` | `ft.Colors.WHITE` | **Exists.** Runtime `hasattr(ft.Colors,'WHITE') == True` (`flet/controls/colors.py`). |
| OK | `onboarding_screen.py:110` | `GestureDetector(on_horizontal_drag_end=…)` | **Exists.** `flet/controls/core/gesture_detector.py` declares `on_horizontal_drag_end: Optional[EventHandler[DragEndEvent["GestureDetector"]]]`. Constructed at runtime OK. |
| OK | `onboarding_screen.py:140` | `expand=True` on `GestureDetector` inside a `Column` | **Valid.** `expand` comes from `Control` (inherited by `GestureDetector` via `LayoutControl`), type `bool \| int \| None`. Runtime construction with `expand=True` inside `Column` passes. |
| OK | `onboarding_screen.py:62-63` | `_on_drag(e: ft.DragEndEvent)` type hint + `e.primary_velocity` | **Accurate.** `flet/controls/events.py:291` → `class DragEndEvent(Event)` with field `primary_velocity: Optional[float]` (`data_field "pv"`). The `Optional` guard (`is not None`) in the handler is exactly right. `ft.DragEndEvent` is exported (`hasattr == True`). |
| OK | `onboarding_screen.py:75` | `animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT)` on `Container` | **Valid.** `Container.animate: Optional[AnimationValue]`; `Animation.duration` accepts int as ms ("If provided as an integer, it is considered/assumed to be in milliseconds"), `AnimationCurve.EASE_OUT` exists (runtime-checked). Constructed OK at runtime. |
| OK | `onboarding_screen.py:138,178` | `ft.Padding.symmetric(vertical=…)` / `ft.Padding.only(bottom=…)` | **Valid.** `flet/controls/padding.py` defines `Padding.symmetric(*, vertical=0, horizontal=0)`, `Padding.only(...)`, `Padding.all(...)`. `Container.padding` accepts `int \| float \| Padding`. |
| OK | `onboarding_screen.py:150-155` | `Checkbox(value=…, on_change=lambda e: …e.control.value)` | **Valid.** `Checkbox.value: Optional[bool]`, `on_change: Optional[ControlEventHandler["Checkbox"]]`. Base `Event` (`flet/controls/events.py`) has a `control` field ("The control that emitted the event"), so `e.control.value` is the documented read-back pattern. |
| OK | `onboarding_screen.py:167-173` | `FilledButton("Get Started"/"Continue", on_click, disabled, height, width)` | **Valid.** `FilledButton` extends `Button`: positional `content: str \| Control`, inherited `disabled` (from `Control`), `height`/`width` (from `LayoutControl`), `on_click`. Runtime-constructed with `height=48, width=320, disabled=True` OK. |
| OK | `onboarding_screen.py:84-91` | `Image(src, width, height, fit, color, color_blend_mode)` | **Valid.** All six are declared on `Image` (`flet/controls/core/image.py`); `BoxFit.CONTAIN` and `BlendMode.SRC_IN` ("srcIn", `types.py:611`) verified. |
| OK | `onboarding_screen.py:120-131` | `Text(title, size, weight, text_align)` / `Text(description, size, color, text_align)` | **Valid.** `Text.value` positional, `size`, `weight=FontWeight.BOLD` (member of `FontWeight` enum, `types.py:165`), `text_align=TextAlign.CENTER`, `color`. |
| OK | `onboarding_screen.py:51-52` | Hooks | **Clean.** Two top-level `ft.use_state` calls before any return/branch — no conditional or after-return hooks. `use_controller()` is context read, not a hook-order hazard. |
| OK | `onboarding_screen.py:21-40` | `_SLIDES` mixed-type tuples | **Safe by construction.** Each tuple is `(str\|IconData, bool, str, str)`; `is_image` flag selects `ft.Image(icon_src)` (str branch) vs `ft.Icon(icon_src)` (IconData branch). Destructure `icon_src, is_image, title, description` matches arity 4 on all three rows. |
| INFO | `onboarding_screen.py:85` | `src=f"/{icon_src}"` → `"/icon.svg"` | **Correct, verified.** `src/assets/` contains `icon.svg` (plus `icon.png`, `icon_android.png`, `icon_white.svg`); `main.py:753-754` sets `assets_dir = <repo>/src/assets`, so `"/icon.svg"` resolves to that file. Note: SVG + `color`/`SRC_IN` tint works (Image docs list SVG as supported) — the multi-color brand SVG will render **monochrome** (white/dark-green) by design; if the full-color mark is ever wanted, drop the `color`/`color_blend_mode` args. No `error_content` fallback — a missing asset would render blank rather than crash; asset confirmed present so this is latent-only. |
| LOW | `onboarding_screen.py:96-187` | Small-screen overflow | **Latent, no crash.** Fixed hero size (`ICON_HERO*2.2` = ~106px + `SPACE_XL` padding), `width=320` button, and a non-scrollable `Column(SPACE_BETWEEN)` can squeeze the middle swipe area on short (<600dp) screens; `Text` uses default `overflow=CLIP` with no `max_lines`, so long descriptions clip rather than throw. Consider `scroll=ft.ScrollMode.AUTO` on the outer Column or replacing `width=320` with `expand=True` + horizontal padding if 320dp+ phones report crowding. Not a crash — layout only. |
| OK | Get Started handler chain | `"Get Started"` → `_next` → `ctrl.finish_onboarding` | **Correct end-to-end.** `ControllerMethods.finish_onboarding: Callable[[], None]` exists in `state/controller_ctx.py:27`; wired in `main.py:695` to the real `finish_onboarding()` (`main.py:379-386`), which persists `terms_accepted=TERMS_VERSION`, flips the `has_accepted_terms` observable, and re-invokes `_mount_ui()`. Checkbox gating is right: `disabled=is_last and not accepted_terms` — Continue/Skip are ungated on slides 1–2, Get Started is blocked until the box is ticked. **UX note (not a bug):** the terms row renders *only* on the last slide, and swiping/dragging back to slide 1 leaves `accepted_terms=True` in state — harmless, acceptance persists by design. |

**Zero missing kwargs. Zero icon/color/enum typos. Zero hook violations.**

## Post-onboarding swap: verify the fix

**Verdict: the `_mount_ui()` remount fix is sound — the bug it fixes is real, and the fix is the minimal correct mechanism.**

1. **Why the bug was real.** `Page.render_views` (`flet/controls/page.py:683-706`, installed source) is one-shot:
   `self.views = Renderer().render(component, *args, **kwargs)` followed by `self.__render()`
   (`update()` + `enable_components_mode()` + `start_updates_scheduler()`). The onboarding gate
   (`app_shell.py:127-138`, `_onboarding_gate()` returning an `ft.View` while
   `state.has_accepted_terms` is false) is evaluated *during* that render. Flipping the observable
   alone only schedules a reactive re-render of subscribed components — it does **not** rebuild
   `page.views`. So the old code (persist + flag flip, no remount) left the boot-time onboarding
   `View` mounted: pressing "Get Started" persisted acceptance but the user stayed on the deck.
2. **What the fix does.** `main.py:379-386` → `finish_onboarding()` persists, flips the observable,
   then calls `_mount_ui()` (`main.py:736-747`), which re-runs `page.render_views(...)` over the same
   `ServiceCtx → ControllerMethodsCtx → AppShell` tree. On the second pass `_onboarding_gate()`
   returns `None` (flag is now true), so `_dashboard_view()` builds the real dashboard `View` and
   `page.views` is **replaced** (`=` assignment, not append) — the user lands on Home immediately.
3. **Second-call safety (`__render` idempotency).** `__render` (`page.py:708-716`) calls
   `self.update()`, `context.enable_components_mode()`, `self.session.start_updates_scheduler()`.
   Re-invoking update + re-enabling components mode + restarting the batch scheduler is idempotent
   by construction (the scheduler start re-arms an already-running loop; no per-call registration
   accumulates in `render_views` itself). The closure captures the *same* `services`/`methods`
   objects, so no duplicate service instances are created on remount.
4. **No view-stack corruption.** At boot the app sits on the index route (`/`); `finish_onboarding`
   performs no `page.navigate`, so the route is unchanged and the Router (`manage_views=True`,
   `app_shell.py:214`) re-emits exactly one index-level `View` — now the dashboard instead of the
   gate. `page.route` still matches `/`; no stale back-stack entry, no duplicated views
   (assignment replaces the list). Deep-link routes re-evaluate their own `_onboarding_gate()`
   inside `_tool_view`, so they benefit from the same flip on next render.
5. **Residual risk (accepted, negligible).** A second `render_views` re-renders the whole tree —
   transient per-component `use_state` (e.g. selected tab, scroll position) resets to initial values.
   In practice the pre-acceptance tree contains only onboarding state, which is correctly discarded.
   Test pin: `tests/test_theme_and_onboarding.py:63-68`
   (`test_finish_onboarding_remounts_views`) asserts `_mount_ui()` is called inside the
   `finish_onboarding` handler — guards against regressing to the flag-flip-only version.

**Conclusion: keep the fix as-is. No further change recommended.**
