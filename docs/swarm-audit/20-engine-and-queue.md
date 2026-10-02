# Engine + queue + storage — audit reference

## services/engine_service.py (~3531 lines; sole engine)

av API verdict: essentially clean (`timeout/hwaccel` open, Codec w-mode,
`supported_options.private`, Graph add/buffer/link/configure/push/pull,
AudioFifo, Resampler, `rescale_ts(AVRational)`, decode2,
`add_stream_from_template(opaque=True)`, `start_encoding()`, BSF
filter, chapters, `search_timestamp`, VideoFrame save/reformat,
`HWAccel(allow_software_fallback)`, disposition int setter — all correct;
`add_buffer(template=VideoFrame)` works by duck-typing).
Findings: P0-1 `getattr(av.codec,"UnknownCodecError")` always misses
(real: `av.codec.codec.UnknownCodecError`, ValueError subclass) —
friendly branch dead. P0-2 `_mux_packet` clamps dts-only, convert-only;
compress/_cut_reencode/_concat_reencode mux raw (EINVAL class alive
there); with bf=0 should clamp pts+dts. P1-1 stream-copy/record
single-base rebase goes negative on B-delay (split bases, clamp 0;
_cut_stream_copy has no clamp). P1-2 cancel still drains+flushes (skip
when cancelled; thumbnail/keyframe paths ignore pause/cancel entirely).
P1-3 GIF single-pass palettegen buffers ~900 frames unbounded (two-pass
or periodic pull). P1-4 probe rotation `break` outside `if _frames`
(first-packet decoder delay → rotation 0). P1-5 HLS double-GET + whole
stream to one `.dat` temp (no size cap; multi-GB VOD fills disk).
P2-1 fifo fallback catches (TypeError,ValueError) but mismatch raises
FFmpegError — fallback never triggers. P2-2 `_crop_dims` even-align
undone by `min()` (odd width into crop filter → yuv420p error).
P2-3 `finally: out.close()` can mask root traceback (suppress/log like
record() does). P2-4 `_push_pull` single-pull loses delayed audio
(atempo buffering → mid-stream gaps). Load-bearing comments mostly
TRUE (loudnorm NULL-container, rescale_ts AVRational, template metadata
gap, mp4toannexb manual BSF, subtitle units, fps gates); stale: the
UnknownCodecError ValueError note (lookup, not class, is wrong).
Fix: one `_mux_packet` (pts+dts) on every `out.mux(enc_pkt)`; split
bases; skip drains on cancel; rotation loop; even-after-min; GIF
two-pass; broaden fifo except; suppress close(); pause hooks on
thumbnail/keyframe.

## core/engine_probe.py

Empirical (Windows wheel): 557 codecs / 468 filters / 414 formats /
49 BSFs; all REQUIRED_FILTERS present; drawtext/subtitles/ass absent
(OPTIONAL, all 3); every PREFERRED encoder w-mode except libvorbis
(dead entry). Findings: D1 `hwdevices_available` on wrong object
(`av.codec` lacks re-export; real `av.codec.hwaccel...` returns 6
backends; app reports none — highest severity in file). D2 probe cost
~5.25s sequential, comment says ~2s; first `can_encode()` pays it.
D3 cache keyed on `av.__version__` only (FFmpeg rebuild invisible →
stale forever). D4 `hls_ok` codecs clause dead. D5 libvorbis dead;
mp3 double-entry harmless. D6 `_find_attr` fallback imports
non-modules. D7 counts read as totals (preferred-only). D8
`synthetic_transcode` falls back `h264` not `mpeg4` (thesis
contradiction). Confirmed-true: REQUIRED/ogg/mode-w/Capture/
ProtocolNotFoundError-only/forms/hwconfigs/private-options access.
Disproven: ~2s, `codec.py:369/filter.py:67` cites. Unverifiable here:
Mobile Forge LGPL set (defensively ordered regardless).

## services/job_queue.py (243 lines)

Correct: FIFO pop(0) under lock, cancel-pending removes under lock +
notifies after, shutdown snapshots under lock, finally pops cancel map
+ notifies outside. Defects: D1 `enqueue`-after-shutdown notifies
holding `_lock` (deadlock). D2 `start()` unlocked (two workers). D3
runner/`on_started` exception → non-terminal status + finished fired
(ghost row); on_started failure mis-logged, runner skipped. D4 no
cancel reconciliation for running jobs (ignoring runner never forced
cancelled). D5 shutdown async + message overwrite + restart duplicates.
D6 `_current` unsynchronised + pop-to-assign gap (shutdown can miss).
D7 `_shutdown` unlocked reads. D8 Event+0.5s poll lost-signal class.
D9 inconsistent Job mutation (direct vs `_set_worker_field`). D10 dead
`Path.parent` branch. Fix: lock start/shutdown/current; generation
counter + join; terminal-status reconcile in finally; notify outside
lock; Condition instead of poll; consistent worker-field writes.

## services/command_parser.py (521 lines)

D1 `-vn`→`-v n` (dead drop_video). D2 duplicates last-wins silently
(-ss×2, -vf×2, -af×2). D3 multi-`-i` concat drops all shaping/time
flags. D4 cut `stream_copy=True` default (ffmpeg re-encodes) + narrow
encode detection (-r/-s/-c* /-b/-ar/-ac/-af don't clear copy). D5 `-vf
atempo` accepted. D6 volume math wrong (linear/dB/% conflated +
char-set rstrip). D7 transpose 0/1 collapsed. D8 fps truncation. D9
extraction/subtitle ignore time range (full track instead). D10 GIF
`end=0.0` falsy + 5s clip + dropped shaping. D11 shaping guard misses
scale_height/crf/preset/codec/denoise/sharpen/eq. D12 remux misses
`-c:v/-c:a copy`; `-c aac` mis-mapped to video. D13 nan/inf/negative
timestamps. D14 `_refuse->None` + bare-raise/AssertionError idiom bugs.
D15 no input==output guard. D16 tokenizer drops `""` + no escapes.
Hallucinations: `-sslide` flag; unverifiable downstream op/param names
(single-file); help lists `-vf crop/atempo` code refuses/misplaces;
`-b:v` validated-then-discarded. Fix order: -vn exact-match; dup
policy; concat refuse-or-plumb; copy default False + full encode set;
volume/fps/transpose math; timestamp hardening + NoReturn; GIF
`is not None`; guards; help truth.

## storage: storage_paths.py / storage_service.py

paths: D1 symlink-following rmtree (outside-tree delete, ×3 sites).
D2 keep exact-match (nested keeps unprotected — prune deletes what it
promises). D3 `freed` pre-snapshotted (lies on partial failure); prune
under-reports inversely. D4 `clear_cache` purges in-flight TEMP, no
keep. D5 cache+TEMP overlap double-count/sweep. D6 size getters mkdir
side effect. D7 truncated write permanently reused (non-atomic +
exists-check + no revalidation). D8 top-level-only prune (nested new
in old dir over-deleted; old in new dir leaks — the 2.2GB class
survives job subdirs). D9 mkdir OSError uncaught; silent `~/.ffmpeg`
fallback. D10 32-bit cache key + unbounded filename (collisions at
scale; 255-byte crash). D11 NaN/negative max_age deletes everything.
D12 symlink size miscount + inconsistent OSError handling. D13
format_bytes negative/inf/nan/PB-cap. H1 2.2GB anecdote in docstring;
H2 FLET_APP_STORAGE_* names unverified; H3 unenforceable safety
contract. Fix: is_symlink/unlink; subtree-aware keep; per-item
accounting; split cache vs temp clearing; resolve-vs-ensure getters;
atomic writes + ≥16-hex keys + name truncation; recursive age prune;
input validation + loud fallback.
service: non-dict JSON bricks; TypeError kills timer thread; lock held
across fsync I/O; live mutable refs; no dir fsync; 1s loss window, no
atexit. Fix: validate dict; catch (OSError,TypeError,ValueError);
snapshot-then-write; deepcopy; atexit flush.

## services/update_service.py

No total deadline (~30s worst: phases × retries); shared transport
reused after close; None conflates offline/error/up-to-date; no
manifest schema validation (KeyError downstream); `v`-prefix never
matches; 403 misclassified as expected-missing. Fix: 10s wait_for;
per-client transport; tri-state result; key validation; strip v;
403→warning. Pooled AsyncClient + 4-phase timeout + retries=2 already
right.
