# Components — audit reference

## banner_ad.py (40 lines)

APIs pass (component/Control/Container/Row/CENTER/use_app_state/
use_services — no direct flet_ads use; signatures valid). D1 dead `_ =
ads_ready` read (use_context subscribes whole-AppState already;
implies field-tracking that doesn't exist; every AppState write
re-renders all slots). D2 `height==0` eligibility sniff (duplicates
service logic; breaks on adaptive/None height; masks contract change).
D3 default `slot="default"` invites double-mount steal (cached instance
per slot; second parent steals; current 3 slots safe; no keying). D4
revoke path never publishes (show_privacy_options updates flag, not
ads_ready — withdrawing consent leaves banners mounted: privacy risk;
gather publishes, revoke doesn't). D5 unchecked `services.ads` duck-type
(Any=None; AttributeError inside render kills page). D6 centering on
implicit Row width (host_expanded semantics; fragile). D7 no boundary
for deferred FletUnsupportedPlatformException (construction wrapped,
before_update raise at render time not — misdetect blanks screen).
Hallucinations: H1 "responsive fallback" (fixed 320×50); H2 "observable
read → re-render" (object granularity); H3 Sherlock-file attributions
(no such module in repo — rationale real, attribution uncheckable).
Fix: explicit `is_banner_ready`/None contract; publish on revoke;
required slot + key; getattr guard + platform-exception boundary;
pinned centering; honest comments + docstring.

## job_card.py (233 lines)

APIs all pass (component/Control/IconButton 12 icons verified/Icon/Row/
Column/Text/weights/overflow/SPACE_BETWEEN/ProgressBar 0–1/card_container/
status_badge/use_controller/format_bytes/Job ops incl. remux/concat/
extract_subtitles/record confirmed in main). D1 `job.status.upper()`
on None (High — guards op/paths/progress but not status; persisted
history delivers None). D2 `Text(job.status_message)` no None guard
(renders "None"/encode-fail; L208 gates correctly). D3 `%` unclamped vs
clamped bar (150%/−X% divergence + float() inconsistency). D4 pause from
`"Paused"` string (reword/localize/Cancelling... silently flips icon).
D5 pause global not per-card (every card hits queue.current; cancel
correctly scoped by id). D6 share/save coroutine lambda (async impls,
plain lambda — auto-await assumed; result_screen same pattern; needs
runtime confirm). D7 cancelled/failed dead-ends (generic gray, no
retry/delete despite ctrl.retry/delete existing). D8 card on_click wraps
inner IconButtons (Share/Save may also fire _card_clicked → yank to
result mid-sheet — needs bubbling confirm). D9 pause live during
"Cancelling..." (is_running still true; races cancel). No hallucinations.
Fix: `(status or "unknown").upper()` + `(message or "")`; single clamped
helper; queue-derived is_paused + per-id toggle + hide-while-cancelling;
awaited share/save; explicit cancelled/failed branches; bubbling verify;
centralize op map (join alias, noun casing); either-size info; hoist import.

## jobs_banner.py (95-96 lines)

APIs pass (component/Container/Padding/Margin/Column/Row/ProgressRing-Bar
(value None = indeterminate — blessed)/Text/weights/icons/IconButton/
Padding/Margin symmetric/use_app_state/use_controller/observable args —
auto-subscribe verified component.py:234-248; TextOverflow shared with
job_card). D1 percent unguarded vs guarded bar (None crash + >100%
divergence). D2 `op.title()` mangles (Extract_Audio/Concat-vs-Join/
Record-vs-Recording; None-unsafe; canonical map in job_card:37-50 +
result:306 disagrees). D3 wrong filename for concat (first-path only)
+ record (Path(url).name junk). D4 paused/cancelling by magic string
(progress drain overwrites Paused; Cancelling still offers Pause+Cancel —
double-action in teardown; is_running stays true, correct, buttons lie).
D5 record forced indeterminate even when bounded (duration_s offered +
plumbed + engine on_progress — percentage knowable, hidden behind REC).
D6 no navigation (only job UI on tool screens — app_shell:109 — yet
strip + "+N queued" untappable; dead end). D7 cancel binds render-time
id vs pause acts on current (asymmetric on rollover; negligible — rebuilds
each publish). D8 queued assumes active∈jobs (structural not queue-read;
JobQueue.active/queued exist). Hallucination: H1 "live streams have no
total" overgeneralizes (bounded records have totals — D5's comment).
Fix: shared op map (kills drift); tappable banner → Jobs tab + phase
sub-text; explicit paused/cancelling flags (no more strings); clamped
percent + determinate-when-bounded; concat-aware/record-aware names;
theme hexes into constants; queue-derived count; elapsed-REC polish.

## brand_header.py (121 lines)

APIs verified (component/context.page/create/use_context/observable 7
icons incl. LIGHT/DARK/AUTO/SETTINGS/Image bytes+color+SRC_IN/CONTAIN/
Filled/TextButton+ButtonStyle+RMI(999 valid)/Colors/IconButton/Row/
CrossAxis/COLUMN/Text/Container/Padding/ThemeMode/is_dark_mode contract;
SRC-IN docstring accurate). D1 unguarded `ft.context.page` (raises outside
context; theme.py wraps, header doesn't). D2 theme icons ≠ cycle
(DARK→LIGHT icon right; LIGHT shows dark but next is SYSTEM; SYSTEM shows
auto = current not next DARK; tooltip promises cycle). D3 magic tab index
2 (comment-only 0/1/2 mapping). D4 no narrow overflow guard (brand + icon +
version/update + 2 buttons overflow 320–360dp; title never yields). D5
redundant observable read (line 45 subscribes already). D6 magic 999
(RADIUS_FULL exists). D7 "Update" hides version (v… opens dialog that
handles None — tooltip overpromises). No hallucinations. Fix: next-mode
icons + dynamic tooltip; try/except page; ellipsis/expand/responsive;
named index + RADIUS_FULL; version label; drop line 36.

## empty_state.py (38 lines)

APIs all valid (Container+Padding(int valid)+alignment — margin via
LayoutControl; Column alignments; Icon positional; Text props;
Alignment/Margin/Control/IconData exports). D1 not centered (no expand/
size; Column-list parent shrink-wraps; alignment no-op — "Centered"
broken on tall windows). D2 inner Column contradictory (tight=False
expand vs shrink parent; missing tight=True + outer expand). D3 title
START vs subtitle CENTER on wrap. D4 double gap (spacing 8 + margin-top
8 = 16 vs 8 rhythm). D5 positional Margin + wrapper node (readability).
D6 `is_dark=True` default (future omission → dark-on-light). No
hallucinations. Fix: expand+tight contract OR rename + drop alignment;
title CENTER; single gap source; Margin.only; required is_dark (or
None→resolve); max-width for long subtitles (capture:250 stretches
desktop).

## offline_banner.py (33 lines)

APIs live-verified (Container/Row/Icon/Text/weight/CENTER/Padding/
ACCENT_AMBER/FONT_SM/SPACE_*; Text overflow CLIP + wrap defaults). D1 not
full-width (no width/expand; Column children content-sized; CENTER no-op;
"_shell_body full-width" promise broken — sibling uses expand). D2 bool
arg snapshot-fragile (updates only via subscribed caller app_shell:108;
`state.py:229-233` warns; signature invites misuse). D3 redundant
height=0+width=0+visible=False (visible=False suffices; branch identity
churn). D4 hardcoded #000000 ×2 (bypass ACCENT_AMBER-adjacent theme).
D5 size=16 dupes ICON_SM (imports neighbors, not it). D6 long label, no
expand/align (awkward 320dp wrap). No hallucinations. Fix: width inf/
expand; @ft.component reading use_app_state internally; single container
+ visible toggle (+animate); theme literals; ICON_SM; Text expand+CENTER;
semantics label.

## update_dialog.py (101 lines)

APIs resolve (AlertDialog modal/title/content/actions/alignment/shape;
Markdown+ExtensionSet+on_tap_link; Filled/TextButton; Column+scroll;
Text weight; Container; END alignment; RADIUS_LG; pop_dialog; run_task
coroutine rule; platform.is_mobile; UrlLauncher async; notes_for/
APP_*/URLs/snack/tokens). No hallucinated API; `page.launch_url`
absence TRUE. D1 falsy-dict + None payload (`{}`→is_update yet None-
branch; None release_notes/title crash Markdown/Text; upstream keys
unvalidated). D2 non-str link (`urlsplit(123)` AttributeError uncaught;
e.data Any; need isinstance + (ValueError,AttributeError,TypeError)).
D3 fire-and-forget run_task (closed-loop RuntimeError; discarded Future
→ silent launch failure). D4 blocked feedback suppressed (notify guard
won't show snack over open AlertDialog — tap looks dead). D5 generic
pop_dialog (may close wrong stacked dialog — capture instance). D6
modal≠mandatory (outside-tap only; dismiss/back bypass). D7 fixed
400×300 overflows 360px phones + action clipping. Fix: isinstance-guard
+ widened except + run_task try; `is not None` + `or`-defaults + str();
inline dialog error (not snack); instance close; true mandatory (re-show/
document advisory); responsive + scrollable; typed service +
can_launch_url; allowlist decision (ffmpeg.org/flet.dev/image-URL
tracking-pixel vector noted).
