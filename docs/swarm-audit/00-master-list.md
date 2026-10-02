# Swarm audit — master defects / gaps / hallucinations

Source: 40+ subagent reports, all verified against installed `.venv`
(av 18.1.0, flet 1.0.3 stack, httpx 0.28.1, Python 3.14).
Report-only pass. No code changed.

Constraint (non-negotiable): `docs/why-ffmpeg-lite.md`. Mobile wheel
is the capability floor — no H.264/HEVC/VP9/AV1 encode, no MP3
encode, no HTTPS transport (httpx fetches, PyAV consumes bytes).
Probe-driven gates only.

---

## P0 — crashes, data loss, deadlocks, consent (fix first)

### Queue / threading

- `services/job_queue.py:107-113` — `enqueue` calls
  `_notify_finished` while holding `_lock`, the one path violating its
  own lock-release rule. Deadlocks if the callback re-enters the queue.
- `services/job_queue.py:97-103` — `start()` unlocked: two concurrent
  enqueues spawn two workers, breaks the serial guarantee.
- `services/job_queue.py:218-237` — runner/`on_started` exception
  leaves non-terminal status but still fires finished: ghost rows.
  No cancel reconciliation (a running job whose runner ignores
  `cancel_evt` is never forced to `cancelled`).
- `services/job_queue.py:126-140` — `shutdown` async (no join),
  overwrites terminal message with `Cancelling...`, later `start()`
  can double-run workers.
- `core/logger_handler.py:34-38` — `get_logs()` iterates the live
  `deque` unlocked: `RuntimeError: deque mutated during iteration`
  when opening Activity Terminal under load.

### Storage / media IO (data loss)

- `core/storage_paths.py:78-79,111-112,145-146` — `is_dir()` follows
  symlinks, `rmtree` deletes link-target contents. Outside-tree delete.
- `core/storage_paths.py:134-137` — `prune_temp_outputs_keep`
  exact-string match only: nested keep paths unprotected, prune can
  delete the recording it promises to keep.
- `core/storage_paths.py:71-75` — `clear_cache()` purges TEMP
  (in-flight outputs) with no `keep` hatch; Settings clear during a
  job destroys unsaved results. Also D3: `freed` pre-snapshotted,
  over-reports on partial failure.
- `services/media_io.py:79-94` — `selected.bytes` branch dead
  (`with_data=False` always): mobile content-URI picks always return
  None. Picker looks broken on Android/iOS.
- `services/media_io.py:163-189` — user-cancel falls through to the
  Downloads copy. Cancel still writes a file.
- `services/media_io.py:71-74` — manual `page.services.append`
  bypasses `ServiceRegistry` (no client notify). Post-flush services
  may never mount.
- `services/storage_service.py:61-66` — non-dict JSON bricks the
  service; `set()` with a non-serializable value kills the timer
  thread (`TypeError` uncaught); `get()` returns a live mutable ref.

### Engine

- `services/engine_service.py:270` —
  `getattr(av.codec,"UnknownCodecError")` always misses; real path is
  `av.codec.codec.UnknownCodecError`. Friendly message never fires.
- `services/engine_service.py:1046` — `_mux_packet` clamps `dts` only,
  and only `convert()` has it. `compress` (:1342),
  `_cut_reencode` (:1616), `_concat_reencode` (:2669) mux raw: the
  `12800>=12800` EINVAL still crashes those paths. Must clamp pts+dts
  on all four paths.
- `services/engine_service.py:1502,3471` — stream-copy/record
  zero-basing uses one base for pts+dts; B-frame delay goes negative
  after rebase. Track `base_pts`/`base_dts` separately, clamp at 0.
- `core/engine_probe.py:411-413` —
  `getattr(av.codec,"hwdevices_available")` is always None; real path
  `av.codec.hwaccel.hwdevices_available` returns 6 backends here.
  Engine Info permanently reports `hw devices: none`.
- `services/command_parser.py` — `-vn` misparsed as `-v n`
  (:49,298-306,493, dead `drop_video`); cut defaults
  `stream_copy=True` (ffmpeg re-encodes by default, :430-434);
  `-af volume` linear-vs-dB conflated (`1.5`→`2%` ≈ mute, :246-247);
  `fps` truncation 29.97→29 (:183,386); `nan/inf`/negative timestamps
  accepted (:127-145); `-vf atempo` accepted in video chain (:203-207);
  transpose 0/1 collapsed (:194-196); GIF `end=0.0` falsy fallback
  (:552-553); no `input == output` guard (:336-339).

### Navigation / state / consent

- `src/main.py:799,695-727` — `HIGH_VALUE_JOB_OPS` says `"join"` but
  join enqueues `op="concat"`: interstitial never fires for joins.
  Worse, dispatch has no `else`: unknown ops are marked `completed`
  having done zero work.
- `src/app_shell.py:206-208` — `controller.back/go_home` flip local
  `use_state` only, never `state.active_view`. Next
  `navigate("convert")` hits the same-branch no-op: user stuck unable
  to re-enter a tool.
- `src/app_shell.py:232-246` — jobs badge built once, effect syncs
  only `selected_index`; queue changes never update the badge.
- `screens/capture_screen.py:216,184-214` — unmount cleanup wiped by
  the first re-render (`use_effect` overwrites `hook.cleanup`);
  mic/camera keep recording after leaving the screen. Plus :991,428
  init flag in a ref (buttons stuck disabled); :234 vs 480,486 two
  effects below the early return (hook-count differs by branch).
- `screens/history_screen.py:75 + main.py:845-849` — `restore_job`
  in-place `insert(0)`: Undo persists to disk but never re-renders.
  Always inserts at 0 (order loss); Clear All has no Undo (up to 50
  records gone).
- `screens/onboarding_screen.py:105 + main.py:431-433` — Skip persists
  `terms_accepted`: a user who never saw the checkbox is stored as
  consented. Legal defect; back is swallowed during onboarding so
  Skip/accept are the only exits.
- `components/job_card.py:138` — `job.status.upper()` crashes on
  None-status history.
- `screens/result_screen.py:38-43,74,165` — `except ImportError` sets
  the flag but `AudioState.STOPPED` is referenced unconditionally:
  install without flet-audio crashes Results even for video jobs.
- `state/controller_ctx.py:15-37` — `go_home/back` monkey-patched by
  app_shell, not declared: every bare `ControllerMethods()` test
  double raises `AttributeError`.
- `state/service_ctx.py:26,15-23` — module-level `Services()`
  shared mutable default; all fields `Any=None` with no fail-fast.
- `core/notify.py:37-50` — `show_dialog` raises only on same-instance
  equality (dataclass value-`__eq__`), not when another dialog is open.
  Handler near-dead when needed, live on identical re-toasts; on that
  path it `pop_dialog()`s the user's real AlertDialog then drops the
  toast. Double loss.

---

## P1 — wrong behavior, wasted work, misleading UI

- `core/state.py:94-118` — `video_stream` returns the first video even
  if `attached_pic` sorts first. Plus image-table gaps
  (tiff/avif/heic/ico/jpeg codec), comma-joined `format_name` never
  split. Plus stale docs: `set_setting` "never published" is false on
  1.0.3 (`ObservableDict` publishes); the real nested rule (Job-in-list
  writes don't notify AppState) is undocumented.
- `screens/cut_screen.py` — preview never `play()`s (black seeks);
  fake 60s duration feeds slider/thumbs/job; `divisions=100` defeats
  the 0.05s guard; leading-edge throttle drops the final seek;
  thumbnail strip has no generation guard.
- `screens/convert_screen.py` — audio codec hardcoded `aac`; audio
  jobs gated on video picks; image kind has no still-encoder path;
  hidden video params sent for audio/image; width-only scale distorts
  aspect; no container↔codec matrix; `is_processing` never reset.
- `screens/compress_screen.py` — probe gate weaker than claimed; no
  kind guard; `≈kbps` shows total not video split; MiB vs decimal MB;
  `int(target_mb)` output collision.
- `screens/extract_screen.py` — `is_processing` never reset; GIF
  slider `max<min` for sub-1s clips; empty-encoder case submits a
  doomed job; frame dir reused with stale frames; repeat outputs
  clobber.
- `screens/filters_screen.py` — avail-load failure degrades to silent
  no-ops; optimistic render flickers EQ every visit; non-video gate
  over-blocks images.
- `screens/audio_screen.py` — process button dead after one tap, no
  navigation/feedback, no-audio source not gated, loudness can't turn
  off (every job pays two-pass), hardcoded 256k wrong for lossless.
- `screens/join_screen.py` — filter-load failure opens the crossfade
  gate; one gate for two fade lengths; probe failures silent; no kind
  filter; double-submit + second-resolution collision.
- `screens/probe_screen.py` — `excluded` survives file swaps; switch
  no-op for data/attachment; `NonexNone`/`None Hz` cards; `0 kbps`.
- `screens/streams_screen.py` — `stream_<ts>` collision; badge
  overclaims HLS; no post-start guard.
- `screens/engine_info_screen.py` — placeholder never visible; failure
  reports green CHECK; redundant `page.update()`; no in-flight guard;
  hardcoded `FFmpeg 8` header.
- `screens/settings_screen.py` — sync FS walk per render, `freed`
  over-reports; fixed 500×350 dialogs overflow phones; no
  single-flight.
- `screens/terminal_screen.py` — unbounded log + rebuild per keystroke;
  stale-closure setters; `_confirm` None-guard missing; no
  Enter-to-submit; sync probe on UI thread; `is_dark` never forwarded.
- `screens/home_screen.py` — `f"{color}22"` alpha unverified (use
  `with_opacity`); "5-6 cols" overclaim (math gives 1-2-3-4-6);
  11 tiles orphan last row; stale two-banner comment.
- `components/banner_ad.py` — `_ = ads_ready` registers nothing;
  eligibility from `height==0`; default `slot="default"` invites
  double-mount steal; revoke path never publishes `ads_ready`
  (privacy risk).
- `components/jobs_banner.py` + `job_card.py` — `op.title()` mangles
  (`Extract_Audio`, `Concat` vs `Join`); concat/record filenames wrong;
  `%` unclamped vs clamped bar; pause from magic `"Paused"` string;
  share/save coroutine lambda; card-wide `on_click` wraps buttons.
- `components/update_dialog.py` — `{}` vs None + `None` notes crash;
  non-str link uncaught; fire-and-forget launch; blocked-link snack
  suppressed; generic `pop_dialog()`; fixed 400×300 overflows phones.
- `components/offline_banner.py` — no width/expand (not full-width);
  plain-bool arg (snapshot-fragile).
- `components/brand_header.py` — unguarded `ft.context.page`; theme
  icons don't match the cycle; no narrow-screen guard.
- `components/empty_state.py` — not actually centered; align mismatch;
  double gap.
- `core/back_stack.py` — dead module (nothing imports it).
  Docstring integration claim false; `restore_top_view` suffix
  irrelevant and breaks `e.view`; underlay left `can_pop=True`;
  `/blank` collision; jnius absent. Wire-or-delete.
- `core/theme.py` — unknown maps dark in one path, light in another;
  helper never reads `page.theme_mode`; `platform_brightness=None`
  silently light.
- `core/constants.py` — deep-link comment names the wrong block;
  prod-ID comment stale; import-time FS walk fragile; hex case drift.
- `core/assets.py` — no packaged-app fallback; CWD candidates mask it;
  unsanitized `name`; opaque error.
- `core/styles.py` — `#FFFFFF` vs `KIRI_LIGHT_BG`; badge defaults
  unreadable dark; `is_dark=True` defaults; "pill" radius 8.
- `services/ad_service.py` — cooldown stamped before `show()`;
  `show_privacy_options` never publishes; banner has no `on_error`
  (permanent 50px blank); `_on_error` closure reads `ad` before bound;
  `_handle_close` starves preload; no offline guard; Android test IDs
  on iOS.
- `services/update_service.py` — no total deadline (~30s worst); shared
  transport reused after close; None conflates offline/error/up-to-date;
  no schema validation; `v`-prefix never matches; 403 misclassified.
- `core/changelog.py` — new-title/old-notes skew; fallback is
  installed not latest.
- `state/controller_ctx.py` — `show_view` lone-Optional; `Any` hides
  async; lambda defaults mask regressions; module-level mutable
  default.

---

## Utilization gaps (wheels expose, app ignores)

See `10-dependencies-*.md` per package. Headlines:

- **av**: device enumeration, custom-IO open, muxer/codec-driven
  dropdown defaults, encoder capability validation, HW *encode*,
  ndarray frame access, rotation write, GOP/quality/thread knobs,
  `encode_lazy`, filter help + live retune, FIFO sizing, packet
  sidedata (HDR/3D), motion-vector/QP viz, subtitle encode,
  demux-level discard, subtitle/attachment pickers, keyframe-accurate
  seek, `Container.Flags`, exact `AVRational` math, per-job native
  logs, typed `error` subclasses, full `Disposition` badges, chapter
  authoring.
- **flet-video**: explicit controls, subtitle tracks, volume/rate/pitch,
  fullscreen, playlist modes, transport queries, `take_screenshot`,
  player `configuration` (title still `flet-video` in mixer).
- **flet-audio**: balance, playback_rate, volume, `on_loaded`,
  `on_seek_complete`, pull APIs, play-from-offset, LOOP/RELEASE,
  PAUSED/STOPPED/DISPOSED branches.
- **recorder**: input-device picker, `on_stream` wiring (meter dead),
  PCM16 path, upload path, state events, 6 unused encoders, DSP flags,
  Android/iOS source options.
- **camera**: overlay slot, image-stream, flash/torch, zoom, exposure,
  focus, front/back switch, orientation lock, bitrate/fps caps,
  resolution presets, preview-size sizing, busy flags.
- **permissions**: 38/40 unused — PHOTOS/VIDEOS/AUDIO/STORAGE/
  MANAGE_EXTERNAL_STORAGE/MEDIA_LIBRARY missing (save-to-gallery will
  hit OS denials); Linux/macOS mic hard-blocked.
- **ads SDK**: no RewardedAd in 1.0.3; NativeAd unexported/unused;
  `on_paid`, lifecycle events, `AdRequest` targeting, consent params,
  `show_privacy_options` has zero call sites.
- **httpx**: no Range resume, pooled-vs-fresh client asymmetry, no HEAD
  preflight (double-GET), HLS `retries=0`, unbounded write/pool
  timeouts, no proxy/auth.
- **transitives**: msgpack (keep JSON, don't promote), oauthlib idle
  (can't prune), repath dormant (deep-link parsing is the one use),
  anyio ready for async HLS, certifi fresh (confirm packaged cacert).

## Hallucinated comments (fix the words, they mislead future fixes)

- `state.py` dict-mutation "never published" (false on 1.0.3).
- `app_shell.py` badge re-render / stable identity / "never mutated".
- `main.py` Dart `_handleSystemPopRoute`/`_markViewAsPopped` (1.0.1
  cites, unverifiable), teardown ordering, Sherlock anecdote.
- `back_stack.py` header + Router model (backwards).
- `notify.py` "never pops a real dialog".
- `banner_ad.py` "responsive", "observable read", Sherlock attributions.
- `result_screen.py` Dart empty-`selected`, "SegmentedButton guards".
- `capture_screen.py` PCM16/meter/hook-order/RESTRICTED claims.
- `cut_screen.py` Dart-throw layer, "one frame", CPU-cover story.
- `extract_screen.py` Slider-raises claim (tested false).
- `convert_screen.py` "can copy" affordance; universal CRF label.
- `audio_screen.py` "EBU R128" for −14/−16.
- `command_parser.py` `-sslide`, `-vf crop/atempo` help lines.
- `home_screen.py` "5-6 cols", second banner, inset story.
- `engine_probe.py` "~2s" (measured 5.25s), stale file cites.
- `compress_screen.py` fallback/gate/sharpness claims.
- `constants.py` house-pattern/version cites.
