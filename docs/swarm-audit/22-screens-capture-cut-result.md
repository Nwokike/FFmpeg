# Screens: capture / cut / result — audit reference

## capture_screen.py

APIs verified (Camera/PermissionHandler/AudioRecorder methods+enums,
detect_video_extension, run_task/dialogs, page-RuntimeError, hooks).
D1 unmount teardown wiped by first re-render (use_effect overwrites
cleanup; `[]` skipped on re-run) — mic/camera keep recording after
leave. D2 init flag in ref (buttons stuck disabled; equality-bail in
_on_camera_state schedules nothing). D3 hooks below early return
(count differs by branch) + not-mounted branch leaves stale
camera_ready=True ("Starting camera…" forever). D4 meter dead
(on_stream never wired; handler/RMS/WAV/chunk cap inert; bar permanent
0). D5 blocking write_bytes (100s MB video on loop thread) + unguarded
stat() in render (FileNotFoundError). D6 RESTRICTED→Settings wrong
(OS-forbidden). D7 stale camera_ready across mic trips + silent
busy-tap. D8 video-pause stale closure, no optimistic UI. Hallucinations:
PCM16-streaming constraint inapplicable (never streams); meter-needs-WAV
false; "hook order identical" false; permission docstring half-wrong;
task-cancelling-denial unverified. Verified-true: page-RuntimeError,
desktop camera guard, detect_video_extension. Fix: explicit cleanup
(on_unmounted), state-mirrored cam_live, hooks above branch, meter
story decided (stream PCM16 OR delete), to_thread IO + exists guard,
restricted≠permanentDenied copy, busy feedback + optimistic pause.

## cut_screen.py

APIs valid (Video playlist/autoplay/controls-None/filter_quality/
on_error; seek/stop/pause async; RangeSlider server validators make
clamp load-bearing; Chip.on_select internal toggle fights controlled
selected; page-RuntimeError + _invoke_method re-check real). D1 fake
60s duration (UI prints 01:00, thumbs/job use it — need unknown state +
disabled Cut). D2 shrink-only clamp (longer-file keeps narrow window;
shrink can stack thumbs zero-length; 0.05 invariant unenforced). D3
preview never play()s (unstarted mpv → black seeks; need on_load play→
pause or play-on-first-scrub). D4 leading-edge throttle drops final seek
+ only seeks start thumb (need on_change_end). D5 strip no generation
guard (slow old file overwrites new) + deps miss post-probe duration.
D6 divisions=100 defeats 0.05 guard + sub-second claim false (need
continuous + on_change_end). D7 scrub-mount failure spins forever (need
error flag). D8 cleanup nulls ref (no render; comment overclaims).
D9 controlled Chip+on_select flicker (use on_click for mode chips). D10
fire-and-forget pause vs encode ordering claim + exists-then-stat
TOCTOU ×3. Hallucinations: "Dart range throw" (Python V.le_field
ValueError); "one frame" (async tasks, no frame guarantee); CPU-cover
story. Verified-true: keyframe snap, mount-guard, empty-deps staleness.
Fix: prime preview; continuous+change_end; generation-guarded strip +
duration dep; reset window on file change; unknown-duration state;
on_click chips; error state; stat try/except; trailing debounce.

## result_screen.py

APIs verified (SegmentedButton defaults/validation; jump_to IndexError +
negative normalize; Video/VideoMedia/filter_quality; Audio
play/pause/resume/release/seek/get_*; AudioState/ReleaseMode-STOP
semantics; Slider validation; hooks/run_task coroutine rule; page-
RuntimeError; services list ops). Defects: D1 ImportError fallback
broken (AudioState referenced unconditionally — no-audio install
crashes video results). D2 dead-duplicate Video branches (length
distinction undescribed). D3 cleanup run_task calls unguarded
(shutdown/navigate race). D4 service removal may never sync (no update;
dataclass `in` not identity). D5 effect keyed job.id only (same-id
retry shows stale preview). D6 per-tick set_pos_ms (render storm +
gesture risk). D7 absolute audio src (desktop ok; web/mobile asset-tree
risk; no on_loaded fallback). Cleared: empty-selection triple-guarded;
jump_to(1) hidden+caught; Path guard order; COMPLETED→play matches STOP.
Hallucinations: H1 Dart empty-selected on re-tap (contradicts
segmented_button.py:96-98; next(iter,default) can't StopIteration); H2
"SegmentedButton guards jump_to" (file's own guard); H3 "hardware-
accelerated preview" puff (inherits default, platform-dependent).
Verified-true: mount-guard, True→True no-op, enum/COMPLETED notes.
Fix: collapse branches; AudioState sentinels; harden run_task; effect
deps +output/input; identity removal + update; thumb-only-on-end;
explicit allow_empty_selection + check-mark decision; video height
bound; reset audio UI on release; dedupe stat; audio on_error fallback.
