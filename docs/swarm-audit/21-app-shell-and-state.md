# App shell + state + plumbing — audit reference

## src/main.py (1000+ lines)

Flet APIs all exist in 1.0.3 (constructors, services list, run_task
TypeError on non-coroutine — true). Defects: D1 HIGH_VALUE set says
`join`, join enqueues `concat` (interstitial never fires) + dispatch
has no `else` (unknown ops marked `completed` doing nothing). D2
`_show_view_box` dead (no writer; AppShell publishes via
`controller.show_view`). D3 `_refresh_view` dead. D4 `toggle_pause_job`
mutates without publishing (Paused label stale). D5 queued-cancel may
leave ghost row (verify queue emits on_finished for pending). D6
ad-deferred nav no generation guard; double-tap double-enqueue. D7
`show_update_dialog` unguarded on None. D8 transfer dialog non-modal +
unthrottled updates. D9 PermissionHandler skipped forever if
`page.platform` briefly None. D10 wakelock/connectivity appended
without membership check (dupes on re-run). Hallucinations: H1
`_handleSystemPopRoute/_markViewAsPopped` + 1.0.1 cite (Dart internals,
unverifiable; installed is 1.0.3); H2 teardown-before-on_disconnect
(unobservable); H3 Sherlock basicConfig anecdote. Verified-true:
run_task TypeError, no page.launch_url, PermissionHandler guard,
show/pop_dialog semantics, page.render, services list-ness.
Fix: `else→failed` + `concat` in set; delete dead paths; publish after
pause/cancel; nav token + submit guard; dialog guards; modal+throttle;
platform retry; uniform guards.

## src/app_shell.py (292 lines)

All Flet APIs valid (NavigationBar/Badge/SafeArea/View/ValueKey/hooks/
icons/label-behavior — runtime-verified). Defects: D1 back/go_home flip
local only, never `state.active_view` (re-entry stuck — medium-high).
D2 badge built once, effect syncs only selected_index (frozen count).
D3 local `use_state("dashboard")` drops pre-mount nav. D4 unknown-view
fallback keeps tool chrome (no nav bar). D5 no tab clamp. D6 Jobs
selected icon identical (no visible change). D7 icon-wrap inconsistency
(nit). Hallucinations: H1 "badge re-renders on queue change" (plain fn,
no subscription — FALSE); H2 "stable identity" (badge toggles —
FALSE); H3 "never mutated post-hoc" (selected_index mutated below).
Cleared-true: SafeArea flags, unknown-reject, single-tab-source.
Fix: back/go_home through state-syncing helper (or branch from
`state.active_view`, killing D1+D3); job count in effect deps +
destination badge update; init from state; clamp; distinct icon.

## src/core/state.py

Observable usage correct (`@ft.observable` order, create/use_context,
provider mount, ~25 in-component call sites). Defects: D1 cover-first
ordering misclassifies real video (skip attached_pic when selecting).
D2 image tables gappy (tiff/avif/heic/ico/jpeg) + exact-match on
possibly comma-joined format_name (split+lowercase). D3 `Job.op`
docstring omits live `"record"` (type as Literal incl. record; clamp
progress). D4 no None guards (streams/duration). D5 nested-observable
gap real but misdocumented (ObservableList publishes on append —
whole-value NOT needed for list mutation; it IS needed because
in-`\u200b`Job writes notify Job not AppState — comment says the
opposite mechanism). Hallucinations: H1/H2 set_setting/theme comments
factually wrong (ObservableDict.__setitem__ publishes on 1.0.3;
verified `observable.py:197-201,377-379`) — keep the style, fix the
reason. Verified-true: decorator order, use_context subscription,
singleton-stale warning. Fix: document nested contract; Literal ops +
progress clamp; kind robustness; export ChapterInfo; singleton-per-process
caveat comment; MediaInfo immutable-or-observable decision.

## state/controller_ctx.py (48) / state/service_ctx.py (34)

controller: Flet APIs real. D1 go_home/back undeclared (test doubles
AttributeError). D2 show_view lone-Optional vs no-op lambdas (dead
_show_view_box parallel). D3 `Any` hides async fire-and-forget
(callers get unawaited tasks). D4 lambda defaults mask regressions.
D5 module-level mutable default (cross-session leak). D6 unguarded
hook (outside-component crash). Plus: toggle_pause no job_id (serial
only). Fix: declare fields; non-optional show_view + delete box;
honest types; recording stubs; frozen dataclass.
service: D1 shared mutable default (High). D2 silent None services
(High — fail far from cause; no provider helper). D3 `Any` lies to
checkers. D4 non-reactive (document locator-once). D5 hook-only, no
escape hatch for handlers/tasks. D6 mutable equatable dataclass. Fix:
fail-fast on default/None; Protocols/Optional; scope docs + accessor;
slots/frozen; provider helper.

## core/notify.py (55)

APIs verified (SnackBar DialogControl + fields; show raises only on
same-instance `==`; pop returns topmost-or-None; dataclass value-eq +
identity-hash trap real). Defects: D1 wrong mental model (except
near-dead when needed). D2 value-equality collides identical re-toasts
(spurious RuntimeError). D3 except path pops user's real dialog then
drops toast (docstring "never pops" FALSE — double loss). D4 unbounded
stack growth (no reuse). D5-D7 minor (retry inside blanket catcher;
no duration validation; post-construction action assign). Fix: no
exception-driving, no popping; one SnackBar per Page; suppress→bool
return; explicit Duration; constructor action; honest docstring;
FLOATING/persist UX.

## core/back_stack.py (158; DEAD — nothing imports it)

main uses competing `can_pop=False` strategy. D2 integration docstring
false. D3 1.0.1 cites stale. D4 Router model backwards (matches
page.route, wipes suffix; "still matches" rationale wrong). D5 re-key
breaks `e.view` lookup. D6 no flush + underlay poppable. D7 /blank
collision. D8 drops tuple/single-View. D9 unused page param. D10 stale
activity cache + hardcoded package + jnius absent. D11 view_pop scope
overstatement (documented for AppBar back; system-back delivery is
Dart behavior). H1-H5 Dart claims absent from venv
(_handleSystemPopRoute/_markViewAsPopped/ValueKey(route)/scheduler-race/
KTV chain). Verified: unwrap path, View signature, update loop,
Router one-view-per-level (not per-route). Fix: FIRST decide — wire
into main or delete + tests. Then de-hallucinate, flush/can_pop/
collision/single-View/background-cache fixes.

## core/theme.py (151)

All APIs pass (Theme/ColorScheme 29 kwargs/NavigationBarTheme/TextStyle/
ThemeMode/Brightness/context.page/platform_brightness-Optional). D1
unknown→dark vs →light inconsistent paths. D2 never reads
`page.theme_mode` (dual-write drift; page is what Flutter renders).
D3 None-brightness silently light (startup flash, self-heals via
revision bump). D4 None-fallback unreachable from eager caller
(context.page raises before helper try). D5 seed+scheme redundant.
No hallucinations (Sherlock allusion not an API claim). Fix: read
page.theme_mode first; consistent unknown default; narrow except;
typed signature; document/drop seed; call-site passes None; cache
Theme singletons.

## core/constants.py (90) / core/assets.py (27)

constants: no ship-blockers; versions/URLs/AdMob-prod all consistent
(1.0.0/1, origin+main+version.json, sample test IDs, prod App ID
byte-identical incl. pyproject:89, CI guard passes). D1 deep-link
comment names wrong block (top-level ignored for APKs). D2 prod comment
describes empty norm (all filled, USE_TEST_IDS=False). D3
import-time pyproject walk fragile on-device (missing→walk+warn+defaults;
bake at build or degrade to debug). D4 hex case drift. D5 unvalidated
int cast inside broad except. Boilerplate house-cites unprovable.
Fix: comment corrections; bake-or-quiet; lowercase normalize;
Final/__all__; colocate limits/timeouts.
assets: zero ft imports; implied bytes contract verified real
(src bytes + color/SRC_IN + assets_dir). D1 no packaged fallback
(importlib.resources/MEIPASS/Flutter lookup — FileNotFoundError on
first on-device paint). D2 CWD candidates mask D1 in dev. D3
traversal/absolute escape (low today — hardcoded callers). D4 opaque
error (no candidates/cwd). D5 stale-bytes/unbounded cache (fine at 4KB
SVG, hazardous reused). Docstring "packaged apps" unproven. Fix:
bundle-safe resolution first; allowlist name; candidates in error;
soften docstring; cache control; drop-or-use icon_white.svg.

## core/changelog.py (30) / core/logger_handler.py (44)

changelog: correct today (1.0.0↔APP_VERSION, claims check out incl.
FFmpeg 8, LUFS presets, two-pass, soxr, crossfade, HLS/DASH, denoise,
capture). D1 new-title/old-notes skew. D2 "latest" fallback is
installed. D3 no normalization (v-prefix/space). D4 value-import of
reassigned constant. Fix: version→APP_VERSION→max→placeholder; strip/
lower/v-drop; lazy bind; CI guard for new versions.
logger: D1 unsynchronized deque iteration (real crash under load —
snapshot under handler lock). D2 double timestamp/level (formatter +
prefix). D3 4-char truncation (DEBU/ERRO). D4 second construction
orphans instance. D5 strings-only (no filter future). DST comment
accurate; maxlen honored. Fix: lock snapshot; message-only formatter
or structured tuples; full level names; limit param; instance guard.

## Router lesson (archived M3.5 — module deleted)

`src/core/back_stack.py` (deleted) kept a `/blank` underlay + `?back=` re-key
strategy from the Router era. It contradicted the single-view design three
ways: it grew `page.views` to length 2 (the shell's length-1-forever
invariant), its re-key broke `ACTIVE_VIEWS` exact-match gating, and its Dart
`page.dart` claims (`_handleSystemPopRoute`, `ValueKey(route)` keying) were
unverifiable from the published Python package. System-back stays on
`views[0].can_pop = False` + `on_view_pop` → in-app navigation. If a future
multi-view Router ever returns, re-derive the back contract from the
installed Flet source first — do not resurrect this file from memory.
