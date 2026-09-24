# FFmpeg v1.0 Rewrite Plan — Consolidated from 51 Research Reports

> Historical execution plan from 2026-09-23. The listed P0/P1 findings were triaged during the v1.0.0 release work; current status is tracked by the code, tests, and release checklist.

Generated 2026-09-23. Sources: `docs/kiri-apps-comparison.md` (sibling-app parity audit) and
50 per-dependency API dossiers in `docs/dep-research/` — one per package installed in `.venv`,
each written from a full read of that package's installed source.

Baseline: 168/168 tests pass; `ruff check` 0 findings; `ruff format --check` FAILS (5 files).
So every bug below is a *runtime/API* bug the test suite does not currently catch.

---

## P0 — Correctness bugs (fix first; each is user-visible or leaks resources)

### Media engine (PyAV) — see `dep-research/av.md`
1. **Input container leak on failed output open** — output containers opened outside `try`:
   `src/services/engine_service.py:645-646, 885-886, 1032-1033, 1115-1116`.
   A failed second `av.open(..., "w")` leaks the input. Restructure to try/except with cleanup.
2. **`codecs_available` misused as encoder-support check** — it holds all 557 codec *names*,
   not what this build can *encode*: `engine_service.py:673, 896, 1126, 2066, 2179`.
   Use `CodecContext.supported_options` + `Codec.video_formats/audio_formats` (see av.md §Underused).
3. **`_cut_stream_copy` never calls `rescale_ts`** — `engine_service.py:1078-1086`.
   Stream-copy cuts will produce wrong timestamps on non-zero start times. Must rescale packet
   timestamps relative to the cut point.
4. **`_mjpeg_bytes` encodes without `open()`** — `engine_service.py:150-156`.
5. **Inconsistent packet filtering** — `dts is None` dropped in some paths, `size==0` in others.
6. **Non-remux outputs silently drop** container metadata, chapters, data streams, attachments.
7. **Implicit `av.stream`/`av.filter`/`av.codec` access via transitive imports** —
   `engine_service.py:517`. Import explicitly.
8. Probe docstring claims modes `'e'`/`'d'`, only `"r"`/`"w"` exist — `src/core/engine_probe.py:152-160`.
9. **Fail-open capability probing** — `engine_probe.py:299` reports capability on failure instead of absence.

### Playback / preview — see `dep-research/flet-audio.md`, `flet-video.md`
10. **Pause button unreachable**: `src/screens/result_screen.py:147` compares the `AudioState`
    enum to the string `"playing"` → `playing` never becomes True; `:311-323` dead.
    Also no COMPLETED handling (stale slider), `:148` re-renders the whole screen every position
    event (fights slider drags), no `on_error`, slider live before `on_loaded`, `audio_ref.current=None`
    race at `:109`, absolute-path `src` at `:145`, no duplicate `page.services` guard at `:155`.
11. **Stale video player across jobs**: `result_screen.py:128` never resets `video_ref.current`
    → consecutive jobs show the previous job's output. `:264` offers Original segment on
    single-item playlists → doomed `jump_to(1)`.
12. **Cut scrubber never rebuilds on file change** — `cut_screen.py:99-111` empty effect deps;
    `:103` default AdaptiveVideoControls cover the frame on a 160px scrubber (use `controls=None`).
13. Neither preview screen pauses playback when encodes start → CPU contention.

### Capture (camera / mic / permissions) — see `flet-camera.md`, `flet-audio-recorder.md`, `flet-permission-handler.md`
14. **Mic leak**: `capture_screen.py:160-161` `_cleanup` stops only the ticker — never
    `stop_recording`/`cancel_recording` nor camera `pause_preview` → camera controller leaked with
    stale `camera_inited_ref` (`:160-163`).
15. **Permission/state desync**: pause UI flips local flag at `:556` instead of `on_state_change`/`is_paused()`;
    `start_recording` success never verified with `is_recording()` (`:536-545`);
    recorder's `has_permission()` never called (`:495-504`); `stop_recording` return discarded in WAV branch (`:474`).
16. **Camera**: `initialize(cameras[0], HIGH, enable_audio=True)` at `:291` requests video-audio while
    `_prepare_camera` (`:273`) only ever requests CAMERA — silent video/OEM throws on MIC-denied;
    always `cameras[0]` (no BACK preference → possible silent selfie); hardcoded `ResolutionPreset.HIGH`
    with no fallback; `photo bytes` hardcoded `.jpg` (`:373`); no `is_taking_picture` guard (`:372`);
    fixed `height=300` preview ignoring `aspect_ratio` (`:677-683`).
17. **open_app_settings bool ignored** — `capture_screen.py:210` (dead tap, no feedback);
    `:198` hardcodes rationale names; `:268` early-return strands `camera_ready=False` silently.
18. `on_camera_state` reads 3 of 21 event fields (`:257-265`) — trust `CameraStateEvent`.
19. `rec.on_stream` reassigned per take, never reset on start-failure (`:518-526`).

### Ads / consent — see `flet-ads.md`
20. **Consent/load race**: `main.py:712-713` runs `gather_consent` and `preload_interstitial` as
    independent tasks → first ad request fires before consent resolves.
21. **Fail-open consent**: `ad_service.py:46` `_can_request_ads=True` default → serves pre-consent
    ads on EEA first launch. Default `False`, gate all loads on `can_request_ads()`.
22. **Interstitial show-before-load race**: `ad_service.py:143-202` awaits `ad.show()` with no
    ready-flag/backoff.
23. Banner rebuilt **per render** (`banner_ad.py:17` → `ad_service.py:101-116`) → request spam; cache it.
24. Fixed 320×50 banner (`:109-110`) ignores tablets.
25. **Release blocker**: test AdMob IDs live — `ad_service.py:39`, `constants.py:61-63`,
    `pyproject.toml:68`; **and `tools/admob.py` swap-ids is broken** by `_sub` vs `_subst` NameError
    (+ dead `is_test` var, non-atomic writes). Fix the tool before the swap.
26. Zero `flet_ads` test coverage.

### Networking / update — see `httpx.md`, `httpcore.md`, `packaging.md`
27. **Effective timeout is ~16s, not 4s** — `AsyncClient(timeout=4.0)` (`update_service.py:22`)
    fans into 4 per-phase budgets (connect/read/write/pool). Use `httpx.Timeout(4.0, connect=3.0, pool=2.0)`.
28. New client per check → pooling never engages, cold handshake every time, `retries=0`.
    Mount `AsyncHTTPTransport(retries=2)`, share one client, close in connectivity handler (`main.py:226`).
29. `==200` instead of 2xx/`raise_for_status` (`:24`); blanket `except Exception` (`:32`) conflates
    offline with up-to-date — split `TimeoutException`/`NetworkError` from parse errors.
30. **Version-only releases missed** — only `int(remote_build) > BUILD_NUMBER` compared (`:27`);
    manifest `"version"` never compared. Add `Version(remote) > Version(APP_VERSION)` gate +
    `InvalidVersion` validation (packaging.md §Underused).
31. **Unvalidated URL launches** — `update_dialog.py:42,66` open any URL from remote markdown;
    `:39-42` silently no-ops when `url_launcher` is None. Port voicelm's `safe_launch_url` allowlist
    (mdurl/`urllib.parse` normalization + hostname allowlist).

### State / UI shell — see `flet.md`, `msgpack.md`
32. **Dead context surface**: `AppStateCtx` created at `core/state.py:160` but never
    provided/consumed — wire or delete.
33. **Possible missed observable notification**: dict-item state write at `main.py:~292`
    may bypass `@ft.observable` change detection.
34. Every `ft.View` inherits `padding=Padding.all(10)` (view.py:119) and `app_shell.py:141-180`
    never overrides → 10px gutter stacked over `page.padding = 0`.
35. Unversioned terms acceptance — `main.py:379` (bump version key so T&C updates re-prompt).
36. Swallowed **storage-full** errors — `media_io.py:51, 71, 114, 148` (the one failure users hit mid-job).
37. Naive `datetime.fromtimestamp()` in Activity Terminal — `logger_handler.py:22` (DST-ambiguous;
    use `tz=timezone.utc` when display lands).
38. No pre-flight **free-space check** in the job runner (sibling-app gap).

### Build config — silent key drops verified against flet-cli source — see `flet-cli.md`
39. `[tool.flet.android] min_sdk_version = 24` — **never read** (zero hits in flet-cli). The ABI-24
    floor for `av` wheels is NOT being enforced as documented.
40. `[tool.flet.android.manifest_application] usesCleartextTraffic` — **unknown key**; only
    permission/feature/meta_data/provider merges exist. `http://` capture may be broken as configured.
41. `[tool.flet.app.boot_screen] startup_message` — ignored; only top-level `tool.flet.boot_screen` merges.
42. Global `[tool.flet.deep_linking]` — does not apply to Android; needs `android.deep_linking.*`.
43. Relative `signing.key_store` consumed raw (`build_base.py:2970`) — fragile path.
44. `cleanup.app = true` redundant with `app_files`; `x86_64` in target_arch ships emulator-only split;
    `icon.svg` dropped with warning (SVG never becomes a launcher icon).

---

## P1 — Release discipline (from `kiri-apps-comparison.md`)
- [ ] Commit + tag `v1.0.0` (30+ files uncommitted, no tags).
- [ ] Swap production AdMob IDs (blocked on #25 `tools/admob.py` fix); CI guard will fail tags until done.
- [ ] LICENSE file (only ktv-player & spaninsight have one; ffmpeg lacks it).
- [ ] Screenshots gallery (empty `screenshots/`; shipped siblings embed 8–15 images).
- [ ] URL allowlist + security test (#31).
- [ ] Disk-persisted crash reporter (ktv-player pattern) — field crashes currently vanish.
- [ ] 16 KB ELF-alignment check on the AAB (PyAV native libs; top Play-rejection risk).
- [ ] Record/pin PyAV-FFmpeg build identity (lm-router sha256-pin pattern).
- [ ] Delete prototype leftovers: `spike.py`, `src/ui-spike/`, `deps-tree.txt`, `pinned-deps.txt` refs.
- [ ] CI: add `ruff format` green (#45), `--junit-xml`, `--strict-markers` + registered markers.

## P1 — Test suite hardening (from `pytest.md`, `ruff.md`)
- `ruff format` the 5 failing files: `app_shell.py`, `main.py`, `terminal_screen.py`,
  `command_parser.py`, `tests/test_command_parser.py` — then keep the CI gate.
- Collapse duplicated assert-tables with `@pytest.mark.parametrize` (capture helpers, previews,
  subtitles, container variants).
- Register markers (`slow`, `engine`, `needs_network`) + `--strict-markers`;
  `filterwarnings = ["error::DeprecationWarning"]`.
- Migrate `tempfile` → `tmp_path` (`test_engine.py:23`, `test_storage.py:11`); `pytest.approx(abs=…)`.
- Reduce private-API coupling: `test_routes.py:10,12,32-54` (`_match_routes`/`_normalize_path`/`_ROUTES`)
  — test via public route changes instead.
- Unify two divergent `_isolated_state` fixtures (`test_all_screens_render.py:61` vs `test_tab_crashes.py:30`),
  three `_render` copies, four clip builders.
- Replace `pytest.raises(Exception)` (`test_concat.py:112`) with specific types.
- Add missing coverage: flet-ads consent flow, camera/recorder state machine, icon-name existence test
  (flet's `Icons` mints silent dummies on typos — `icons.py:15-22`).

---

## P2 — Adopt the installed-but-underused APIs (the "use everything" mandate)

Each row is backed by a full dossier in `dep-research/`.

| Area | Adopt for v1 | Report |
|---|---|---|
| Flet core | `ft.use_dialog()` (replace imperative dialogs in main.py/notify.py), `Control.badge` (delete hand-rolled Stack badge in app_shell), `ft.SharedPreferences` (settings/theme/terms), `ft.HapticFeedback`, `ft.RangeSlider` (Cut start/end), `ReorderableListView` (Join queue), `use_memo`/`use_callback`, `on_mounted`/`on_unmounted` (terminal/connectivity), route `loader=` + `use_route_loader_data()` (PyAV probe off click path), `ft.Tester`/`Finder` widget tests | `flet.md` |
| PyAV | `supported_options` pre-validation, `HWAccel` (wheel ships cuda/qsv/dxnv/d3d11va/amf), open/read timeouts on every `av.open`, output `metadata`+`set_chapters`, `StreamContainer.best`/filtered demux, `AudioFifo` for AAC, reusable `VideoReformatter`, `av.logging` VERBOSE capture, bitstream filters, `add_mux/data/attachment_stream`, subtitle encode | `av.md` |
| flet-ads | `ConsentManager.request_consent_info_update` → `load_and_show_consent_form_if_required` → `can_request_ads()` as the single gate; `get_privacy_options_requirement_status`/`show_privacy_options_form` (GDPR persistent entry); `NativeAd`+template in job list; `AdRequest(keywords, non_personalized_ads)`; lifecycle + `on_paid` telemetry; `ConsentDebugSettings` EEA simulation | `flet-ads.md` |
| flet-audio | `on_state_change`/`AudioState` driving transport UI, `play(position)` for cut-point preview, `seek`+`on_seek_complete`, `on_loaded` gating, `get_duration`/`get_current_position`, `volume`, `playback_rate`, `ReleaseMode.LOOP`, `bytes` src for temp-free previews, dual-instance A/B | `flet-audio.md` |
| flet-audio-recorder | `has_permission()` before every start, `on_state_change`, `cancel_recording` (Discard-take + unmount cleanup), `is_recording`/`is_paused` re-sync, `get_input_devices`+config, `suppress_noise`/`cancel_echo`/`auto_gain`, `on_upload`, Android `VOICE_RECOGNITION` source, `is_supported_encoder` probes (FLAC) | `flet-audio-recorder.md` |
| flet-camera | `set_description`+`CameraLensDirection` front/back toggle, per-mode `initialize(enable_audio=…)`, `set_flash_mode(TORCH)`, zoom clamped by min/max, `CameraStateEvent` as single source of truth, `pause_preview`/`resume_preview`, `ResolutionPreset` w/ lower-preset retry, `fps`/`video_bitrate`, `supports_image_streaming`, `content` overlay + `aspect_ratio` | `flet-camera.md` |
| flet-permission-handler | `get_status` before each capture, `open_app_settings` (honor bool, show feedback), CAMERA+MIC together for video, `NOTIFICATION` for job/update alerts, `PHOTOS_ADD_ONLY` (iOS), `AUDIO`/`VIDEOS` instead of STORAGE (Android 13+), treat `LIMITED` as usable, `RESTRICTED`/`PERMANENTLY_DENIED` → settings, permission dashboard in Settings screen | `flet-permission-handler.md` |
| flet-video | `controls=None` chromeless scrubber, `on_load` gating, `take_screenshot(format="image/png")` poster frames (only thumbnail API!), `playback_rate` frame-check, `PlaylistMode`, `on_track_change`↔segment sync, `VideoConfiguration(mpv low-latency)`, subtitle track preview, programmatic fullscreen | `flet-video.md` |
| flet-cli | `android.split_per_abi`, `permissions=["camera","microphone"]` (iOS plist+macOS entitlements for free), `android.extract_packages` (zipimport `__file__` risk for av/httpx), `proguard_rules` keep lines for flet-video, `cleanup.package_files` globs, `--exclude`/`app.exclude` (drop `ui-spike` at source), `flutter.build_args`, `flet doctor/test` in CI, `$FLET_ANDROID_SIGNING_*` secrets pattern; FIX the four ignored keys (#39-42) | `flet-cli.md` |
| httpx/httpcore | shared `AsyncClient`, `AsyncHTTPTransport(retries=2)`, split `Timeout`, exception taxonomy split, gate on `state.is_online` | `httpcore.md` |
| anyio | `move_on_after`/`fail_after` around engine ops, `CapacityLimiter` bounding phone-side PyAV, `to_thread.run_sync(abandon_on_cancel=True, limiter=…)` replacing bare `asyncio.to_thread` (5 sites: `main.py:392`, `cut_screen.py:116-117`, `join_screen.py:123`, `settings_screen.py:55,118`), `create_memory_object_stream` progress channels, `BlockingPortal` for threaded JobQueue, stop swallowing `CancelledError` (`capture_screen.py:327`), replace 500ms `threading.Event` polling (`job_queue.py:162,167`) | `anyio.md` |
| charset | **Standardize on `charset-normalizer`** (not chardet): route subtitle sidecar reads, attachment bytes (`engine_service.py:1642, 1699`), probe caches through `from_bytes().best()`; show detected encoding in Extract screen; one-tap `output()` normalization. Add `charset-normalizer>=3,<4` to runtime deps when adopted. | `charset-normalizer.md`, `chardet.md` |
| Filenames | one `safe_output_name()` = `slugify(stem, separator="_", max_length=80, word_boundary, save_order)` + reserved-name guard + `text_unidecode` fallback (CJK→readings, strip/collapse whitespace, generic stem when blank) — replace raw `Path(...).stem` interpolation at 6+ build sites (audio/extract/probe/cut/compress/capture screens) | `python-slugify.md`, `text-unidecode.md` |
| Time | `arrow` `humanize()` for history relative times, `format('YYYYMMDD-HHmmss')` stamps replacing `int(time.time())` collisions; dateutil `rrule` when recurrence lands; **promote `tzdata` to runtime deps the moment any local-time display ships** (dev-only today → `ZoneInfoNotFoundError` in release) | `arrow.md`, `python-dateutil.md`, `tzdata.md` |
| Images | Pillow `ImageOps.exif_transpose` before display, `Image.frombuffer` → `thumbnail` → WebP/JPEG posters, Convert-screen rotate/normalize/WebP; promote Pillow to direct dep if runtime use lands | `pillow.md` |
| Types (stdlib on 3.14) | `Literal` job states on `state.py:96` + `assert_never` in job_card dispatch; `TypedDict UpdateManifest` replacing `dict[str, Any]` in `update_service.py:19`; narrow `Protocol`s replacing the 9 `Any` fields in `state/service_ctx.py:11-24`; `ParamSpec` for `run_task` | `typing_extensions.md` |
| Tooling (dev-only) | rich: `RichHandler` logging (replace hand-rolled `main.py:47-99`), `traceback.install(show_locals=True)` crash reports, `Progress` bars for engine jobs, syntax-colored Activity Terminal; pygments tokens → `TextSpan`s (no ffmpeg lexer — use `BashLexer`/`JsonLexer`); click: `CliRunner` tests for `tools/` (would have caught the admob NameError), `batch`/`doctor` CLI surface; jinja2: command-preview templates, changelog generator, HTML dossier export, screen/test scaffolder | `rich.md`, `pygments.md`, `click.md`, `jinja2.md` |
| qrcode | About/Share QR (`ffmpeg://app` deep link), desktop↔mobile pairing codes, branded `StyledPilImage` at EC level H | `qrcode.md` |
| pluggy (optional) | job-lifecycle hook bus (`on_job_start`/`on_progress`/`on_job_done`) for future filter/export/notifier plugins — warranted but deferrable past v1 | `pluggy.md` |

## P3 — Documented as intentionally-transitive (no action / do not adopt)
- **six** — inert on py3.14; keep (flet→repath and dateutil need it). Never import in app code.
- **oauthlib** — flet's `page.login()` backend; app has no login. Keep, don't pin.
- **requests/urllib3** — cookiecutter chain only. **httpx-only policy**: never add sync HTTP to mobile code.
- **chardet** — superseded by charset-normalizer; leave dev-transitive.
- **binaryornot** — unmaintained; prefer `charset_normalizer.is_binary()` if ever needed.
- **colorama** — pytest/qrcode Windows shims; use rich/click for tooling output; never wrap streams in conftest.
- **iniconfig** — pytest legacy-ini plumbing; this repo uses TOML. Keep untracked.
- **h11/idna/certifi/mdurl/markupsafe** — correctly-bounded internals of the HTTP/markdown stacks;
  certifi posture verified clean (zero `verify=False` anywhere).
- **watchdog** — `flet run` hot-reload only; **desktop-only** if ever adopted (Android SAF/Web emit no events).
- **repath** — flet's route matcher (Express-style `TemplateRoute`); relevant only if parameterized
  routes like `/job/:job_id` are added. Note: `repath.match()` ignores caller flags (latent upstream bug).

---

## Suggested execution order for the rewrite
1. **Engine P0** (#1-9) — data-integrity bugs; add regression tests per fix.
2. **Playback + capture P0** (#10-19) — state-machine fixes against the events the plugins expose.
3. **Consent/ads + update P0** (#20-31) — release blockers (test IDs, admob tool, allowlist, timeout).
4. **State/UI + build config P0** (#32-44) — flet-cli key fixes verified by grepping flet-cli source.
5. **P1 release checklist** — LICENSE, screenshots, crash reporter, ELF check, commit/tag.
6. **P1 tests/CI** — format gate, parametrize, markers.
7. **P2 adoptions** — one row at a time, each landing with tests; promote undeclared runtime deps
   (charset-normalizer, and pillow/arrow/rich/click if adopted) to `pyproject.toml`.
