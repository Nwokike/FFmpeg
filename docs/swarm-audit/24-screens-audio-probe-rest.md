# Screens: audio / probe / streams / engine_info / history / settings / onboarding / terminal — audit reference

## audio_screen.py (202 lines)

Params vs engine MATCH (format/bitrate/lufs/channels/rate → extract_audio
via main:656-667; can_encode filter matches AUDIO_FORMAT_ENCODERS). Flet
APIs all real. D1 process button permanently dead after one tap (no reset —
High). D2 no feedback/navigation after enqueue (job runs invisibly —
High). D3 no-audio/image source not gated (engine ValueError in
background — Medium). D4 loudness can't turn off (every job pays two-pass
+ requires loudnorm; missing filter degrades silently while UI promises
calibrated mastering — Medium). D5 hardcoded 256k (ignored for wav,
misleading for flac, excessive for opus; diverges from engine default 192
and settings default — Medium). D6 empty-encoder edge submits doomed job
(Low). D7 temp collision/overwrite (Low). D8 stale audio_format state
(diverges when m4a unencodable; ignores settings default — Low).
Hallucinations: H1 "EBU R128" for YouTube −14/Podcast −16 overclaim
(R128 = −23+TP+LRA; engine passes only i=; no R128 delivery). H2 none
(API-clean; LGPL-MP3 consistent). Fix: settle-reset + navigate + toast;
kind/audio-presence gate; Loudness Off + per-codec bitrates; honor
settings default + channels auto; unique names + empty-state; run_spacing
+ measured-LUFS affordance + missing-filter surfacing.

## probe_screen.py (446 lines)

Flet APIs all verified 1.0.3 (component/Control/context/state/ListView/Row/
Column/Icon/IconButton/Text/Filled/Outlined/Switch/Container/icons/weights/
overflow/align/run_task-async/page.services/share; Job op=remux matches
main:705-712; build_media_report unit-tested — docstring true). D1 excluded
survives file swaps (raw indices; track 1 of B starts off — Medium; reset
on media change). D2 switch no-op for data/attachment (remux only copies
video/audio/subtitle — misleading control). D3 `NonexNone`/`None Hz`/`None
(…)` cards (report guards, UI doesn't). D4 `0 kbps` for unknown bitrate
(render Unknown; BITRATE stat too). D5 save enabled with zero streams
(tappable, silently returns). D6 stale/empty _start_remux silent return.
D7 disposition iterated as list but typed dict (works — probe stores only
True flags; one False entry renders unset flag; filter truthy). No
hallucinations. Fix: reset excluded per file; hide/footnote switch on
data/attachment; Unknown for bitrate/duration; first-token format badge;
complete disposition labels (dub/karaoke/still_image/timed_thumbnails…);
light badge contrast; share/remux double-tap guard; uuid temp names;
unify duration formatting (_fmt_ct).

## streams_screen.py (227 lines)

APIs all pass incl. `[]`-mount semantics, Chip avatar note accurate,
run_task coroutine rule, op=record dispatch, record(duration None),
_probe_protocol present-on-error, controller methods. D1 `stream_<ts>`
second-resolution collision (silent overwrite). D2 badge overclaims
HTTP/HTTPS/HLS (only http/https probed; HLS is a demuxer per probe:161).
D3 no post-start guard/feedback (double-tap duplicate records). D4 probe
Future unobserved (raise → "Checking…" forever). No hallucinations
(avatar comment true; record-op/record-doc/probe-first claims match
engine). Fix: uuid names + debounce; honest badge or real HLS/DASH probe;
inline start_job error; on_submit Enter; public probe import; gate Start
on missing + tooltip; temp hygiene (discard-cleanup offer).

## engine_info_screen.py (113 lines)

All Flet APIs real. D1 placeholder never visible (`report or …` +
`visible=bool(report)` → blank during ~2s probe). D2 failure reports
green CHECK + "ready" (error text as normal report). D3 redundant
page.update() after set_state (double-patch). D4 no in-flight/unmount
guard (concurrent probes race cache; set_state on dead component; effect
returns Future unintentionally). D5 hardcoded `FFmpeg 8` header (probe
measures dynamically). D6 display gap (to_text omits counts/sets/configs/
options/formats/props — docstring overpromises). D7 refresh never disabled
(spam amplifies D4). No hallucinations. Fix: always-visible report +
error state; drop manual update; generation guard + disabled refresh;
derived header; encoder/h264/mpeg4/hls/dash/network badges + expandable
sets; FONT_SM token; ListView padding.

## history_screen.py (186 lines)

Flet APIs all pass (component/state/context, Dismissible+ValueKey,
AlertDialog+Buttons, TextField, Column/Row/Container/Padding/Alignment,
icons, SnackBarAction, show/pop_dialog; Row-no-padding comment CORRECT;
None-guards match restore defaults + job_card). D1 Undo invisible
(restore in-place insert → persists, never re-renders — High). D2 wrong
position (always 0 — order loss). D3 Clear-All unrecoverable (≤50 records,
no snapshot/snack — High, inconsistent with swipe-undo). D4 stale search
filter after clear ("No History Found", no CTA). D5 zero-result no recovery
(subtitle lies when tasks exist but filtered; no Clear-search). D6
controlled field cursor-jump per keystroke (whole rebuild, no debounce).
D7 `>2` threshold arbitrary + None-crash. D8 lone pending mislabeled
"1 running". D9 header excludes queue from "total". D10 ValueKey assumes
unique ids (double-Undo duplicates → same-key diffing). D11 second swipe
kills first Undo (no trash stack). D12 pop_dialog may pop wrong dialog
(main:879-884 identity pattern omitted). No hallucinations. Fix: whole-value
restore + index capture + exists-guard; snapshot Clear-All + UNDO + query
reset; Clear-search action + honest subtitle; field whenever non-empty +
strip + suffix-clear + debounce; running-vs-queued labels; combined counts;
full uuid (or id+created key); explicit HORIZONTAL + trash stack.

## settings_screen.py

All flet symbols real (SegmentedButton/Switch/AlertDialog/ListTile/
OutlinedButton/dialogs/run_task/Clipboard/UrlLauncher/Image/Container/
icons/BlendMode/Colors/ThemeMode/ScrollMode/Text/Column; AppState/
storage/clipboard/launcher/snack/probe/styles/BannerAd/assets/
show_update_dialog all match). D1 hardcoded "PyAV 18" (+`FFmpeg 8` —
derive from av.__version__/library_versions). D2 sync FS walk per render
+ freed pre-snapshot (jank + over-report). D3 fixed 500×350 dialogs
overflow 360dp phones. D4 no single-flight (stacked dialogs, concurrent
probes). D5 unsanitized theme_mode (corrupt → no selection + nonsense).
D6 redundant update + unmount race. D7 empty-logs blank + silent last-100
truncation. D8 copy no feedback, failures silent. No hallucinations. Fix:
off-thread size + skeleton; responsive dialogs + empty/truncation states;
single-flight + debounce; centralize theme apply + sanitizer; SUCCESS
snacks + launch exceptions; dynamic versions; lazy/factory size +
post-size from clear.

## onboarding_screen.py (191 lines)

No hallucinated Flet API (component/key, state/context, icons,
DragEndEvent.primary_velocity, Container/Animation/EASE_OUT, Image
bytes+color+SRC_IN, Icon/Column/Row/Text/Buttons/Checkbox/
GestureDetector/Padding/Alignment/TextAlign/Weight/ValueKey — all
confirmed). D1 Skip records acceptance without consent (High — legal;
Skip on slide 1/2 persists terms_accepted="1"; back swallowed so
Skip/accept only exits). D2 consent text not tappable (split Row
bypasses Checkbox label= hit-target; no actual terms content/link).
D3 fixed 320 CTA + 32 padding = 352dp min (overflows 320–360 phones).
D4 no scroll guard (large-font/small-height/landscape overflow —
first-run screen). D5 swipe dead-zone (<200px/s nothing; no tap/dots
nav; display-only dots). D6 dead tuple field ("icon.svg" never used;
invites path-"fix" breaking packaged resolution). D7 dot animation
likely never interpolates (fresh identities per render → snap). D8
silent no-op on test doubles. D9 SRC_IN tint assumes monochrome mask
(confirmed single-path #3c8038 fill — technique correct; keep tied to
asset). Fix: Skip≠accept (distinct skipped state); Checkbox(label=) +
real terms link; responsive CTA + scrollable deck; tappable dots + back
affordance + forgiving swipe; keyed dots; explicit slide type; semantics.

## terminal_screen.py (288 lines)

APIs all pass (component/state, Column/Row/Container/Text/Icon/IconButton/
ScrollMode.AUTO/weights/with_opacity(0.15,PRIMARY)-order-correct/
ButtonStyle+RoundedRectangleBorder/TextButton+icon/TextField+on_submit-
exists/ListView+auto_scroll/icons/imports/Job/navigate/probe/summary).
D1 unbounded log + full rebuild per keystroke (O(N) jank, memory).
D2 stale-closure setters (lost lines/history — use updater fns). D3
_confirm no None-guard (double-tap → AttributeError or duplicate jobs).
D4 nested scrollers + 1s auto-scroll animation (log scrolls away; lag;
no jump-to-end). D5 no Enter-to-submit (on_submit+autofocus exist,
unused). D6 sync blocking probe on UI thread + fragile `-i` regex
(single-quotes/multi-input/Windows-spaces missed; `"-ss" in cmd`
substring; None-engine misleading error + double error lines). D7 is_dark
never forwarded (light mode gets dark cards + dark log pane). D8 help
spams log; no timestamp/level prefix (color-only; hurts copy-paste). D9
history buttons raw long commands (overflow, no tooltip/key). No
hallucinations (shape comment true; Roboto Mono fallback not a claim).
Fix: cap 200–500 + Clear + on_demand; functional updaters + confirm
guard + in-flight disable; on_submit/autofocus; outer scroll None +
expand pane + animation 0 + jump-to-end; tokenizer reuse + off-thread
probe + engine-missing distinction; forward is_dark; prefixed/
timestamped/copyable log + dedup help; truncated history + tooltip + key.
