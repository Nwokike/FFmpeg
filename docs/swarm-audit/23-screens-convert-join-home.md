# Screens: convert / join / home + compress / extract / filters — audit reference

## convert_screen.py

Flet APIs all real (component/context/hooks, Chip mutual-exclusion,
Dropdown+Option, Slider, disabled, Row wrap, icons). D1 audio codec
hardcoded `aac` (setter discarded; AAC-in-.mp3 mismatch; no MP3/FLAC/
Opus picker though probe+aliases support them). D2 probe gate checks
video picks for EVERYTHING (audio-only job gated on video encoders;
video-encoders-present-but-no-AAC enables then fails late). D3 image
kind has no encode path (png/gif/webp hidden; whole codec section
hidden; JPG→PNG runs hidden libx264 default). D4 hidden video params
still sent for audio/image (still re-encoded with hidden codec/CRF/
scale). D5 width-only scale distorts (1920×2160 squish; 854 assumes
16:9; portrait breaks — derive both dims from aspect). D6 no
container↔codec check (vp9+mp4, prores+webm, aac+.mp3 fail post-encode).
D7 is_processing never reset (Start dead after one tap). D8 strict-key
filter hides aliased encoders (h264-only wheel hides H.264 chip; use
can_encode/resolve). D9 clamps never written back (stale state resurrects
on kind-switch). D10 sync stat() per render (info.file_size_bytes exists).
Hallucinations: Android-LGPL/H.264-log claims plausible but no
phone evidence in repo (desktop wheel: all 13 W-OK); "can copy media"
false affordance (no stream-copy path); universal CRF label vacuous for
lossless. No hallucinated Flet API. Fix: kind-aware gating + audio picker;
pair matrix; aspect-correct scale; lifecycle wiring (reset + progress +
cancel); alias-aware list; write clamps back; omit irrelevant params;
per-codec quality UI; info size; honest fallback copy.

## join_screen.py

Flet APIs all pass (component/context/state/effect/run_task/ListView/Row/
IconButton/Text/Chip/FilledButton/icons/Container/Column — verified).
D1 filter gate bypassed while/after load fails (avail falsy → None →
crossfade allowed; engine silently degrades to cut). D2 one gate for two
fade lengths (0.5-pass/1.0-fail both enabled → snack dead-end). D3 probe
failures silent (misleading "add one more"). D4 no kind filter
(images/audio-only enter video join; still dur≈0; re-encode sizes from
first.video_stream fallback 640×360). D5 double-submit + second-resolution
`joined_<ts>` collision (busy untouched, no navigate/feedback). No defect:
8-cap, fps>2.0 gate mirrors engine, resolution/audio/duration mirror,
mkv→matroska matches dispatch. No hallucinations (blend-window/app-wide-
media/lossless-vs-reencode/tail-head-blend all real; "no drag API" is
design rationale — Draggable exists, unused). Fix: avail=None→gate closed
+ failure note; per-fade gating; failure count snack; kind reject/warn via
MediaInfo.kind; busy+uuid names; concurrent probes; keyed rows; pure
_crossfade_reason helper shared with engine.

## home_screen.py

APIs verified (component/context, col ResponsiveNumber,
ResponsiveRow 12/breakpoints XS0/SM576/MD768/LG992/XL1200/XXL1400,
Column tight, Text max_lines, 12 icons incl. TRANSFORM/COMPRESS/
CELL_TOWER/MERGE_TYPE/AUTO_AWESOME_MOTION — all in icons.json; routing
matches main capabilities + ACTIVE_VIEWS; history[:3] newest-first).
D1 stale two-banner comment (one BannerAdView exists). D2 collapsed banner
keeps Column spacing (phantom ~16px gap when ads off). D3 `f"{color}22"`
alpha assumes #RRGGBBAA (venv documents with_opacity — hex-suffix
unverified; same pattern probe_screen:206,242). D4 "1-2-3-4-6" math, never
5; no xxl pin (≥1400 falls back implicitly). D5 11 tiles orphan last row
(3-col→2, 4-col→3, 6-col→5). H1-H3: "5-6"/chunk-history/inset story —
breakpoint px verified, rest app-history-as-framework-fact. Fix: pin xxl;
gate banner insert; with_opacity(0.13); single-slot comment; 12th tile or
spanning engine_info; distinct Audio Studio accent; tile tooltips + min-height.

## compress_screen.py (207 lines)

APIs + job contract pass (component/hooks/ListView/Row/Column/Text/Icon/
IconButton/Outlined/Filled/Chip/Slider/ProgressRing/icons; card/section/
snack/Job/probe-gate/preset sanity; engine hardcodes fast → no picker
correct; param name matches dispatch→engine). D1 incomplete probe gate
(claims Convert parity; no encoder-empty card → fails late in
_pick_video_encoder). D2 no kind guard (audio→audio-only .mp4 or error;
image→1s bitrate on single frame). D3 ≈kbps shows total incl. audio+
container (15–20% off at small sizes) + 10.0s vs engine max(1.0) fallback
mismatch + engine re-probes (stale info lies). D4 MiB vs decimal quotas
(+4.9% over strict; 0.92 headroom covers — document). D5 int() truncation
collision (16.0+16.9 same name). D6 divisions=78 → 1.0 steps, round(…,1)
dead. D7 empty-state readout (0 B • 10.0s; Convert omits). Hallucinations:
H1 "first verified encoder" FALSE (tries libx264→h264 then raises, never
walks picks — mpeg4-only build fails); H2 "gated like Convert" overstated;
H3 "maintain sharp visual clarity" puff (only downscales; low-bitrate
softer by definition). Fix: mirror encoder-empty guard; kind branch;
engine-matching estimate (video+audio split, max(1.0), hide when None);
uuid names; divisions=780; honest footnote (8% headroom, 720p/480p
thresholds, H.264/AAC fast, MiB note); respect-or-remove preset setting.

## extract_screen.py

Flet APIs all real (component/hooks/context/page; Chip/Slider/ListView/
Filled/Outlined/IconButton/Row/Column/Text/icons/weights/align/overflow;
can_encode gate matches engine map — all 7 True here; SUBLIST + palette
comments match engine). D1 is_processing never reset (one-shot button).
D2 GIF max<min for sub-1s media (0.5<1.0, clamp only lowers — silent
broken slider; constructor doesn't raise, tested). D3 empty-encoder case
submits doomed job (no disabled clause). D4 frame dir reused, stale frames
mix. D5 repeat audio/GIF outputs clobber (no job-id). D6 stale sub_sel
UI-silent (engine substitutes track 0). D7 bitrate slider for lossless
(engine ignores only pcm_s16le; FLAC forced). D8 32kbps steps + int()
truncation. D9 GIF height uncapped (1080-wide portrait → ~1920 tall).
D10 Job.op docstring omits extract_subtitles. D11 sync stat() ×4 per build.
Hallucination: H1 Slider-raises claim tested FALSE on 1.0.3 (renders
broken, no raise) — keep clamp as hygiene. Verified-true: SUBLIST,
palette graph, Android-LGPL-MP3 consistent (host-unverifiable). Fix:
reset via active_job effect; triple clamp lo/hi/value; disabled +
empty-state; uuid names + fresh dirs; sub_sel effect clamp; hide bitrate
for wav/flac + divisions=14 + round(); height cap/warn; memoize stat.

## filters_screen.py

All Flet + engine contracts verified (component/context/hooks/run_task;
Chip⊕Click invariant; Slider/Row/Column/ListView/Text/IconButton/Buttons;
FilePicker IMAGE + FilePickerFile; icons/weights/overflow/align; Job
op=convert + all param keys match _build_* gates; WM positions + crop
aspects + transpose map match; "eq compiled out" TRUE here — eq=False
live). D1 is_processing set-never-cleared (stuck if stat/tempdir/start
raises). D2 exists()→stat() race in render + submit (FileNotFoundError
takes screen or wedges button). D3 avail-load failure → silent no-ops
(engine drops missing node, full render, zero effect, no warning —
docstring "degrades to a note" holds only on successful enumerate). D4
optimistic render flickers EQ block every visit (deterministic here). D5
non-video gate over-blocks images (crop/scale/EQ/sharpen are frame ops
convert could apply to stills; audio exclusion correct). D6 deterministic
`{stem}_filtered{ext}` collision (shared with convert — fix once in
helper). D7 fragile scale mapping (future value → silent 720p). No
hallucinations. Fix: tri-state avail (None=loading skeleton; fail=conservative
gate + banner); finally-reset + submit-error snack; prune gated-off params
before Job; name active denoise backend in subtitle; memoize stat;
unique names; split image gate (offer frame ops via convert).
