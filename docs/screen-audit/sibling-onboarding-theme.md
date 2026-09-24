# Sibling audit: onboarding-completion + theme-switching patterns

Scope: verify ffmpeg's two candidate fixes against the house pattern used by the
seven sibling apps. Repos at `<workspace>\`.
No app code was modified; only this report was written.

ffmpeg fixes under review (all already applied):
- F1 — `finish_onboarding` re-invokes `page.render_views` after the terms flip
  (`ffmpeg/src/main.py:379-386`, mount fn `ffmpeg/src/main.py:736-749`).
- F2 — `is_dark_mode` reads the observable `state.theme_revision`
  (`ffmpeg/src/core/theme.py:85-102`); Settings picker mirrors the header
  toggle's observable writes (`ffmpeg/src/screens/settings_screen.py:65-83`).

---

## 1. Onboarding flow per app

### ffmpeg (fixed)
- Terms live in storage key `"terms_accepted"` compared against `TERMS_VERSION`:
  `src/main.py:280` — `state.has_accepted_terms = storage.get("terms_accepted") == TERMS_VERSION`.
- Accept handler `finish_onboarding`, `src/main.py:379-386`: sets
  `state.has_accepted_terms = True`, persists, **then calls `_mount_ui()` again**.
  Both the last-slide "Get Started" (`src/screens/onboarding_screen.py:57-60`,
  `_next` → `ctrl.finish_onboarding()`) and "Skip"
  (`src/screens/onboarding_screen.py:102`) funnel into it.
- Root swap: `ft.Router(..., manage_views=True)` mounted once via
  `page.render_views(...)` (`src/main.py:739`, boot call `src/main.py:749`).
  The gate lives **inside** each route view (`_onboarding_gate`,
  `src/app_shell.py:127-138`, read at `src/app_shell.py:136`), because — per the
  comment at `src/app_shell.py:130-134` and `src/main.py:382-385` — the
  `render_views` output list is established at boot (one-shot
  `page.views = Renderer().render(component)`), so the observable flip alone
  left the boot-time onboarding view mounted.
- **ffmpeg is the ONLY app that invokes its mount function more than once.**

### ktv-player — single-root conditional, mount once
- Storage keys `"user_country"` + `"accepted_terms"`:
  `ktv-player/src/screens/onboarding_screen.py:43-44`, restored at
  `ktv-player/src/main.py:125-128`.
- Submit handler `_on_submit` (`onboarding_screen.py:113-122`) calls
  `_persist_terms_and_country` (`onboarding_screen.py:34-47`), which writes the
  DB keys **and** flips `state.has_accepted_terms = True` /
  `state.is_first_launch = False` (`onboarding_screen.py:45-47`). Skip path
  (`_on_skip`, `onboarding_screen.py:110-111`) does the same via
  `_persist_offline_defaults`. The `on_complete` callback is a no-op
  (`app_shell.py:37-38`) — no remount, no navigation call.
- Root swap: one `AppShell` component with `if _should_show_onboarding(state)`
  (`app_shell.py:27-29`, branch `app_shell.py:98-103`). Mounted exactly once:
  `self.page.render(...)` (`main.py:192`).
- Chrome sync via `use_effect` deps
  `[selected_tab, state.has_accepted_terms, search_mode]` (`app_shell.py:94-96`).

### Sherlock — single-root conditional, mount once (KTV mirror)
- Storage key `"sherlock_onboarding_done"` (`core/constants.py:23`), restored at
  `src/main.py:507-509`.
- Handler `set_onboarding_done` (`src/main.py:1072-1082`): flips
  `state.has_accepted_terms = True` + `state.is_first_launch = False`,
  persists + flushes. No remount, no `page.go()`.
- Root swap: `if _should_show_onboarding(state)` (`app_shell.py:28-30`, branch
  `app_shell.py:1096-1097`). Mounted once: `self.page.render(...)`
  (`main.py:338`). Chrome re-syncs via `use_effect` deps including
  `state.has_accepted_terms, state.theme_mode` (`app_shell.py:1080-1088`).

### CollabShell — single-root conditional, mount once
- Storage key `"colab_onboarding_done"` (`core/constants.py:17`).
- Handler `_on_get_started` (`screens/onboarding/__init__.py:~100-105`):
  `state.onboarding_done = True`, `await storage.set(...)`, `page.update()`.
  No remount.
- Root swap: `if not state.onboarding_done or not state.is_authenticated`
  (`app_shell.py:184-187`). Mounted once: `page.render(...)` (`main.py:445`).

### DDGS — single-root conditional, mount once
- Storage key `"onboarding_done"` (`core/constants.py:8`).
- Handler `_finish` (`screens/onboarding_screen.py:162-164`):
  `await controller.save_async("onboarding_done", True)` then
  `state.has_accepted_terms = True`. No remount. (Skip: `_on_skip` runs the
  same `_finish`, `onboarding_screen.py:158-160`.)
- Root swap: `if not state.has_accepted_terms` (`app_shell.py:85-86`).
  Mounted once: `self.page.render(...)` (`app_controller.py:129`).
  Nav-bar sync `use_effect` deps
  `[state.selected_tab, state.has_accepted_terms, state.search_active]`
  (`app_shell.py:81`).

### voicelm — Router + render_views like ffmpeg, but swap via subscription, mount once
- Storage key `"onboarding_done"` (`core/constants.py:49`).
- Handler is in the screen itself (`screens/onboarding_screen.py:66-80`):
  `_go_next`/`_skip` flip **`state_.has_accepted_terms = True` via the
  context-subscribed state FIRST**, then call `controller.finish_onboarding()`,
  which only persists + flushes (`main.py:327-331`) — deliberately no state
  write there.
- Root swap: `ft.Router(ROUTES, manage_views=True)` through a single
  `page.render_views(...)` (`main.py:361`, never re-invoked). Every route
  component subscribes: `RootRoute` does `state_ = ft.use_context(AppStateCtx)`
  (`app_shell.py:359-362`); History/Settings/Recorder/Voiceover routes do the
  same (`app_shell.py:360-361` and siblings). The comment at
  `app_shell.py:353-358` documents the exact bug ffmpeg had: reading the
  module-global directly left "zero subscribers owning the visible View — Get
  Started persisted the flag but nothing changed on screen", while
  "Sherlock/DDGS avoid this by branching inside a context-subscribed AppShell;
  under Router we subscribe at the route component instead."
- **Closest architectural sibling to ffmpeg, and it does NOT re-invoke mount.**

### spaninsight — single-root conditional, mount once
- Storage key `"spaninsight_onboarding_done"` (`core/constants.py:56`).
- Handler `on_next` (`screens/onboarding/__init__.py:143-151`):
  `state.onboarding_done = True`, persist, `page.update()` (`:147-151`).
- Root swap: `elif not state.onboarding_done or not state.is_authenticated`
  (`app_shell.py:351-354`). Mounted once: `page.render(...)` (`main.py:158`).

### lm-router — single-root conditional, mount once (+ explicit update)
- Settings flags `onboarding_done` / `terms_accepted`
  (`core/settings.py:83`, restored `main.py:57-58`).
- Screen `_finish` (`screens/onboarding_screen.py:124-133`) flips
  `app_state.onboarding_done/terms_accepted` in the tap, then
  `controller.finish_onboarding()` (`main.py:785-798`) re-flips, persists, sets
  `state.selected_tab = 0`, and calls `page.update()` (`main.py:793-797`).
  Its comment cites ffmpeg: "the controller then persists it and forces
  page.update (ffmpeg pattern)."
- Root swap: `if not state.onboarding_done` (`app_shell.py:20-21`). Mounted
  once: `page.render(...)` (`main.py:833-835`).

### Onboarding house pattern
Single-root conditional branch on an observable flag; the Accept handler flips
the observable (+ persist + `page.update()`); **the mount function is called
exactly once in every sibling**. Zero siblings re-invoke `render`/`render_views`
after the terms flip, zero call `page.go()` for it.

---

## 2. Theme flow per app

### ffmpeg (fixed)
- Header toggle `toggle_theme` (`src/main.py:666-683`): `page.theme_mode = …`,
  `state.set_setting("theme_mode", mode_str)` (whole-value, `core/state.py:158-165`),
  `state.theme_mode = new_mode`, `state.theme_revision += 1`, persist,
  `page.update()`.
- Settings picker `_update_theme` (`screens/settings_screen.py:65-83`) mirrors it
  exactly: whole-value `set_setting` (`:69`), `page.theme_mode` (`:70-75`),
  `state.theme_mode = page.theme_mode` (`:79`),
  `state.theme_revision += 1` (`:80`), `page.update()` (`:81`).
- Readers: `is_dark_mode` (`core/theme.py:85-102`) subscribes via
  `_ = state.theme_revision` (`:96`), prefers `state.theme_mode` (`:97-100`),
  falls back to `page.platform_brightness` for SYSTEM (`:102`) — correctly
  against `ft.Brightness.DARK`.
- SYSTEM brightness flips bump the revision too
  (`src/main.py:177-183`). Boot seeds the observable (`src/main.py:290-291`).
- Header icon itself reads `page.theme_mode` (`components/brand_header.py:36-40`)
  but re-renders because its parent `_shell_body` calls `is_dark_mode`
  (`app_shell.py:56`), subscribing the dashboard view — same indirect pattern
  as Sherlock's header.

### ktv-player — the outlier: no observable at all
- One shared util `toggle_theme` (`utils/theme_utils.py:13-20`): flips
  `page.theme_mode`, `page.update()`, persists to DB async. Writes **no**
  observable (zero `state.theme_mode =` writes repo-wide).
- Header (`components/header.py:47-53`) and Settings (`screens/settings_screen.py:
  219-234,302`) both call that same util plus a **local** `use_state` setter for
  their own icon/switch. Readers (`core/theme.py:42-50`) check `page.theme_mode`
  + `platform_brightness` directly each render. Works because every toggle ends
  in `page.update()` and nothing caches the derived value.

### Sherlock — both pickers write the same observable
- Header `_cycle_theme` (`components/app_header.py:~107-145`): `page.theme_mode`,
  `state.theme_mode = new_mode`, `state.progress_version += 1` (generic revision
  counter as the re-render kicker), async persist, `page.update()`.
- Settings `_on_theme_change` (`screens/settings_screen.py:173-189`):
  `page.theme_mode = new_mode` (`:181`) + `state.theme_mode = new_mode` (`:182`),
  persist, `page.update()`. **Same observable as the header** — the exact
  property ffmpeg's fix restores.
- `is_dark_mode(page)` (`core/theme.py:119-131`) is a pure function of
  `page.theme_mode`/`platform_brightness`; reactivity comes from the AppShell
  `use_effect` deps (`app_shell.py:1080-1088`).

### CollabShell — the pattern ffmpeg copies (revision counter included)
- Toggle `_toggle_theme` (`main.py:401-418`): `page.theme_mode`,
  `state.theme_mode = page.theme_mode` (`:408`), persist, `page.update()` —
  **no revision bump on toggle**.
- Settings `_select` (`screens/settings/preferences_section.py:19-23`): identical
  pair of writes. Same observable both paths.
- Readers subscribe to **both** `state.theme_mode` and `state.theme_revision`
  (`core/theme.py:92-93`); the revision is bumped **only** on
  platform-brightness change (`main.py:203-210`). State fields at
  `core/state.py:37-38`.

### DDGS — single-funnel save both pickers share
- Home toggle (`screens/home_screen.py:403-412`) and Settings
  (`screens/settings_screen.py:45-46` → `_set("theme", …)`) converge on
  `controller.save("theme", …)` (`app_controller.py:269,304-305`), which sets
  **both** `page.theme_mode` and `state.theme_mode` and persists. No revision
  counter; readers check `page.theme_mode` (`home_screen.py:364-365`,
  `settings_screen.py:38-43`).

### voicelm — single-funnel controller method
- `toggle_theme` (`main.py:261-278`): `page.theme_mode`,
  `state.theme_mode = page.theme_mode` (`:275`), persist + flush. Header
  (`app_shell.py:109-112`) cycles with no arg; Settings pills
  (`screens/settings_screen.py:361,398`) call the **same**
  `controller.toggle_theme` with a mode. `is_dark_mode` reads page only
  (`core/theme.py:58-70`); header icon reads context-subscribed
  `state_.theme_mode` (`app_shell.py:109`).

### spaninsight — both pickers write the same observable
- Toggle `_toggle_theme` (`main.py:214-231`) and Settings `on_theme_changed`
  (`screens/settings/__init__.py:68-78`, cards in
  `screens/settings/appearance_section.py`): both do `page.theme_mode` +
  `state.theme_mode = page.theme_mode` + persist + `page.update()`. No revision
  counter.

### lm-router — single-funnel, string-typed mode
- `_set_theme` (`main.py:268-272`): `state.theme_mode = mode` (string),
  `page.theme_mode`, settings save. Header (`components/app_header.py:36`) and
  Settings (`screens/settings_screen.py:61`) both call `methods.set_theme`.
- Aside (sibling bug, NOT ffmpeg's): `is_dark_mode(page, theme_mode)`
  (`core/theme.py:20+`) compares `page.platform_brightness == ft.ThemeMode.DARK`
  in its SYSTEM branch — `ThemeMode` vs `Brightness` is always False, so SYSTEM
  never resolves dark. ffmpeg's `core/theme.py:102` gets this right.

### Theme house pattern
6 of 7 siblings write the **same** `state.theme_mode` observable from both the
header toggle and the settings picker (always paired with `page.theme_mode` +
persist + `page.update()`); ktv-player instead shares one util that touches only
`page.theme_mode` + `page.update()`. Only CollabShell has a dedicated
`theme_revision`, bumped on brightness change; Sherlock bumps a generic
`progress_version` in the header toggle.

---

## 3. flet-1.0 mechanisms that make the swaps instant
- `@ft.observable` whole-value writes (`ffmpeg/core/state.py:158-165`,
  CollabShell/DDGS/Sherlock equivalents): in-place dict mutation never reaches
  `__setattr__`, so subscribers never fire — the root cause of ffmpeg's
  stale-until-next-interaction theme bug.
- Observable reads inside a rendered component subscribe it
  (ffmpeg `core/theme.py:96`, CollabShell `core/theme.py:92-93`); voicelm shows
  the Router variant must subscribe via `ft.use_context(AppStateCtx)` in each
  route component (`voicelm/app_shell.py:353-362`).
- `page.platform_brightness` resolves SYSTEM mode (all apps); only
  ffmpeg + CollabShell pair it with a revision bump so OS sunset flips repaint
  without interaction.
- Mount shape splits the family: `page.render` + single-root conditional
  (ktv/Sherlock/CollabShell/DDGS/spaninsight/lm-router) vs
  `page.render_views` + `ft.Router(manage_views=True)` (ffmpeg, voicelm).

---

## (a) VERDICT
- **Theme fix: YES, matches the house pattern — it is CollabShell exactly,
  plus a harmless superset.** Both pickers now write the same
  `state.theme_mode` observable whole-value (main toggle
  `ffmpeg/src/main.py:680`, Settings picker
  `ffmpeg/src/screens/settings_screen.py:79`), readers subscribe via
  `theme_revision` (`ffmpeg/src/core/theme.py:96`), brightness flips bump it
  (`ffmpeg/src/main.py:180`). Bumping the revision on manual toggle too (where
  CollabShell does not) only re-renders once more; no downside found.
- **Onboarding fix: works, but it is NOT the house pattern — it is unique to
  ffmpeg.** Every sibling mounts once and swaps on the observable flip; only
  ffmpeg re-invokes its mount fn. The re-invoke is defensible given
  `render_views` one-shot semantics (`ffmpeg/src/main.py:382-385`), but voicelm
  proves the same Router + `render_views` + `manage_views=True` stack swaps
  instantly with per-route `use_context` subscriptions and a single mount
  (`voicelm/src/app_shell.py:353-362`, `voicelm/src/main.py:361`).

## (b) Remaining gaps (no code changed)
1. **Divergent mount-twice onboarding (architectural).** If the team wants
   strict house conformity, replace the `_mount_ui()` re-invoke in
   `ffmpeg/src/main.py:379-386` with voicelm-style subscriptions: read the
   terms flag through a context-subscribed handle inside each route component
   (`_dashboard_view` at `ffmpeg/src/app_shell.py:141-164`, `_route_view` at
   `ffmpeg/src/app_shell.py:174-184`) instead of the module-global
   `state.has_accepted_terms` (`ffmpeg/src/app_shell.py:136,177`), keeping the
   single boot-time `page.render_views` (`ffmpeg/src/main.py:739`). Until then,
   at minimum regression-test that the second `render_views` after "Get
   Started" preserves `page.route`/back-stack (no duplicate root view).
2. **No per-picker divergence remains** — verified the Settings picker
   (`ffmpeg/src/screens/settings_screen.py:65-83`) mirrors the toggle
   (`ffmpeg/src/main.py:666-683`) write-for-write. Nothing to change.
3. **Informational only:** `lm-router/src/core/theme.py:20+` SYSTEM branch
   compares against `ft.ThemeMode.DARK` instead of `ft.Brightness.DARK`;
   ffmpeg already does this correctly (`ffmpeg/src/core/theme.py:102`). No
   ffmpeg change needed.
