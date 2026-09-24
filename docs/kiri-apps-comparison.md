# Kiri Apps Comparison — FFmpeg v1.0 Release Audit

> Historical audit snapshot from 2026-09-23. Findings were triaged during the v1.0.0 release work; use the current code, lockfile, tests, and release checklist as the source of truth.

Date: 2026-09-23. Auditor: static comparison only (tests already green at 168/168; no test runs).
Scope: `ffmpeg/` vs siblings `CollabShell`, `DDGS`, `Sherlock`, `kiri-router`, `ktv-player`, `lm-router`, `spaninsight`, `voicelm`.

---

## 1. Per-app inventory

### CollabShell — Notebook + TTY client for Google Colab (v2.1.2, build 12)
- Stack: Flet ≥1.0.1, `flet-terminal`, `google-colab-cli` (pins `jupyter-kernel-client<1.0`), rich, httpx.
- Shape: `app_shell.py`, `core/` (changelog, constants, notifications, shortcuts, state, styles, theme, tokens), `hooks/use_keyboard_shortcuts`, `screens/` (files, history, home, onboarding/slides, session, settings in 9 section files), `services/colab/` (auth, execution, files_ops, logs, session_ops, terminal_client, vm_ops), `state/service_ctx.py`.
- Release discipline: version.json (full release-notes feed) + `tests/services/test_version_sync.py` born from a real incident — build 11 shipped with `core.constants` stuck at 10, causing a phantom "update available" loop. Guard enforces a **one-sided invariant: feed build ≤ APP_BUILD_NUMBER** (feed is held back until a build is published). Has `scripts/check_elf_alignment.py` (gates Play's 16 KB page-size rule in CI) because pyzmq's x86_64 wheel broke it — target_arch drops x86_64, keeps armeabi-v7a.
- What's good: incident-driven guards, shortcuts help, offline_flow, crash-safe terminal, 10 screenshots embedded in README download table.

### DDGS — privacy metasearch across 14 engines (v1.2.1, build 4)
- Stack: Flet ≥1.0.1, `ddgs`, `flet-ads`, httpx. Smallest app.
- Shape: `app_controller.py` + `app_shell.py`, `contexts/` (app_state_ctx, controller_ctx — React-style context instead of `state/`), `hooks/use_debounce|use_search`, `screens/` (6: home, results, history, settings, onboarding, content_reader), `services/` incl. `services/youtube/` (innertube client, cipher solver, format parser).
- Release discipline: weakest — **no `tests/` directory at all**, no changelog.py, version.json release_notes is a stub ("You're up to date on v1.2.1!"). Still ships update_service + update_dialog + offline_banner + settings sections.
- What's good: contexts pattern, YouTube resolver depth, 10 screenshots in README. Lesson for ffmpeg: don't ship stub release notes.

### Sherlock — OSINT username/email hunter, 3,300+ networks (v2.1.0, build 11)
- Stack: Flet ≥1.0.1, maigret, holehe-v2, socid-extractor.
- Shape: `app_shell.py`, `core/` (changelog, notify, geo_utils, logger_handler), `screens/` (home, results, history, settings, onboarding, sites), `services/` (ad, cache 6-layer, email, enrich, graph, report, sherlock, storage, update), `state/`.
- Release discipline: 25 test files incl. `test_update_service`, `test_offline`, `test_history_order`, `test_screens_audit_polish`; rich version.json notes; `core/notify.py` is the house `show_snack` origin (wraps `page.show_dialog`, pops only SnackBars, never real dialogs).
- What's good: performance-cache story, dossier exports (PDF/XMind/CSV), process-kill cancel, notify helper every other app copied.

### kiri-router — OpenAI-compatible free-LLM gateway (v1.0.0, Node + Cloudflare Worker)
- Stack: plain Node ESM + Wrangler; zero-dependency local proxy (Python or Node). Only non-Flet sibling.
- Shape: `src/` (worker, routes, aggregate, convert, discovery, http, upstream, generated, version), `scripts-content/`, `ui/`, `tools/bundle-scripts.js`, `tests/` (node:test + one pytest).
- Release discipline: `ci.yml` with bundle-freshness check + node tests + python runtime tests. No version.json (server-side, no OTA needed), no screenshots, no LICENSE.
- What's good: dual-tier (cloud Worker + local console), auto-rebuilt generated assets gated in CI. Mostly irrelevant to ffmpeg except the CI pattern of testing generated artifacts.

### ktv-player — IPTV + local media player (v2.1.0, build 18, most mature)
- Stack: Flet 0.86.5 (pre-1.0), flet-video, flet-permission-handler, pyjnius, httpx[http2].
- Shape: biggest suite — `core/` incl. **crash_reporter.py** (disk-persisted, rotated crash logs), `app_loader.py`, `deeplink.py`, `url_validator.py`; `components/player/` (controls/handlers/immersive_player); `services/` (hls_proxy, liveliness x2, pip_service, permission_service, youtube_resolver…); 48 test files incl. `test_deep_link_pip_fixes`, `test_liveliness_offline`, `test_offline_flow`, `test_notifications`.
- Release discipline: **has LICENSE** (proprietary Kiri Research Labs), deep-link scheme `ktv://play`, PiP, auto-resume with checkpoints, rebuilt retry system ("never a dead-end overlay"), Uptodown distribution, 8 screenshots in README.
- What's good: the bar for playback-adjacent robustness — crash persistence, offline liveliness, retry UX. Closest cousin to ffmpeg's media work.

### lm-router — on-device LLM chat via local gateway (v0.1.0, build 1, pre-release)
- Stack: Flet ≥1.0.0, kani[mcp,openai]. Closest template to ffmpeg (both Flet 1.0, both bundle an engine).
- Shape: `core/` (settings, secrets, storage), `screens/` (chat, history, onboarding, server, settings), `services/` (agent, engine, history, http, mcp, search, tokenizer, update_service), `assets/engine/run.py` (pinned binary), `scripts/fetch_engine.py`.
- Release discipline: **engine pinning** — `version.json` carries `engine_version` + `engine_sha256`, refreshed by script, asserted by `test_version_sync.py` (pyproject ↔ version.json ↔ constants). Only 5 tests. Still on Google TEST AdMob IDs ("swap at Play release"). README screenshots section is a placeholder ("added after the UI is built").
- What's good: the engine-honesty pattern (pinned, hashed, hash-verified bundle) ffmpeg should copy for its PyAV/FFmpeg build.

### spaninsight — Colab-backed data intelligence (v2.0.0, build 7)
- Stack: Flet 0.86.5, google-colab-cli, flet-charts, flet-audio-recorder, orjson.
- Shape: largest — `screens/` in 7 groups (analysis: 18 files, files, forms, home, onboarding, projects, reports, settings), `services/ai/` + `services/colab/`, `tools/audit_call_kwargs.py`, `audit_ft_kwargs.py` (Flet-API misuse auditors!).
- Release discipline: **has LICENSE**, 15 test files, `connectivity_monitor`, credit service. Notably **no version.json** (no OTA channel at all) — ffmpeg is ahead here.
- What's good: audit tooling for Flet kwargs, report/form builders, live-share links. The `audit_ft_kwargs.py` idea is directly reusable.

### voicelm — free voice studio (version.json 0.1.0 / pyproject 1.0.0 — deliberately split)
- Stack: Flet ≥1.0.0, gRPC (NVIDIA BNR/StudioVoice/Magpie via Kiri Gateway leases), soundfile/soxr/numpy DSP.
- Shape: `core/` (changelog, utils with **is_safe_url/safe_launch_url/open_dialog/close_dialog**, wakelock, storage_paths), `screens/` (recorder, studio, voiceover, result, history, settings, onboarding), `services/` (11 incl. gateway_client, bnr_service, credit_service), `state/service_ctx.py`, `tools/` with **compare_kiri_apps.py / audit_kiri_apps_features.py / generate_kiri_comparison_report.py** (a prior cross-app audit — this report is its successor).
- Release discipline: strongest self-audit — `test_audit.py`, `test_ci_workflow.py`, `test_security.py`, `test_remediation.py`, `test_version_sync.py` (constants ↔ version.json; pyproject deliberately excluded, unified at ship via `tools/voicelm_cli release --set`). CI quality gate (ruff + pytest + asset gate) blocks every build path. **URL allowlist**: every outbound link funnels through `safe_launch_url` so a hostile version.json can't open arbitrary URLs. **No screenshots/**, no LICENSE.
- What's good: security choke point, dialog helpers with declarative-host fallback, CI-that-tests-itself. The single best release-discipline template.

---

## 2. Parity matrix (ffmpeg vs siblings)

| Area | ffmpeg status | Siblings ahead / notes |
|---|---|---|
| Onboarding | ✅ 3-slide `onboarding_screen.py`, Skip, terms gate (`terms_accepted` persisted), theme/hydration in `main.py` | At parity (CollabShell/Sherlock/ktv/voicelm same shape) |
| Settings | ✅ Strong: About w/ version+build + tap-to-check-update, theme, cache clear, activity terminal (MemoryLogHandler), engine inspector, ad privacy | Matches DDGS section pattern; ktv adds logs + data sections — ffmpeg covered via terminal |
| History | ✅ `history_screen.py` + persistent jobs (50 cap), Dismissible delete **with Undo** | At/above parity (Sherlock tests history order; ffmpeg has `test_tab_crashes`) |
| Update service | ⚠️ Present but thinnest in house: `UpdateService.check_for_updates` compares `BUILD_NUMBER` only, no `UpdateInfo` dataclass, no mandatory/install-path handling | CollabShell/DDGS/Sherlock/ktv all use a dataclass + browser-based delivery notes; ffmpeg works but is the least structured |
| version.json sync | ✅ Strongest guard: pyproject ↔ version.json ↔ changelog ↔ constants (`test_version_sync.py`) | Beats voicelm (excludes pyproject) and CollabShell (one-sided feed rule — ffmpeg should confirm its guard handles the held-back-feed case) |
| Ads | ⚠️ `AdService` + `banner_ad.py` + UMP consent + interstitial-on-result-exit + `tools/admob.py` swap tooling, **but still on Google TEST IDs** (`USE_TEST_IDS=True`, PROD IDs empty) | Shipped siblings (CollabShell/DDGS/Sherlock/ktv) carry production App IDs; lm-router also still on test IDs. CI AdMob guard exists — release-blocked until swap |
| Notifications | ✅ `core/notify.py` mirrors Sherlock's never-raising `show_snack` (verified: `show_dialog`/`pop_dialog` exist on Flet 1.0 `base_page.py`; `DurationValue=Union[Duration,int]` so `duration_ms:int` is legal) | At parity |
| Changelog | ✅ `core/changelog.py` + `notes_for()` fallback, surfaced in update dialog | Ahead of DDGS/lm-router (none); at parity with rest |
| LICENSE | ❌ **Missing** | Only ktv-player + spaninsight have it (proprietary Kiri text). 6 of 8 siblings also lack it — but store submission wants it |
| Screenshots | ❌ **`screenshots/` empty, no README Screenshots section** | CollabShell 15, DDGS 11, spaninsight 11, Sherlock 8, ktv 8 files, all embedded in READMEs. voicelm/lm-router/kiri-router also zero — ffmpeg joins the worst group |
| CI gates | ✅ `build-all.yml`: quality job (Ruff, Ruff format, Tests, AdMob release-ID guard) with `needs:[quality]`; split APK/AAB/Win/Linux packaging | Matches house; voicelm adds asset gate + self-testing workflow (`test_ci_workflow.py`) which ffmpeg lacks |
| Test coverage | ✅ 21 files / 168 passing: screens render, engine params, queue, pause, remux/dossier, version sync | Above DDGS (none), CollabShell (5), lm-router (5); below ktv (48). Missing: CI-workflow self-test, security/URL test, audit test |
| Error handling | ✅ `page.on_error` + `_crash_hook` (thread excepthook) + `logger_handler`; no bare `except:` anywhere; all `except Exception:` blocks log | ktv goes further: **disk-persisted rotating crash logs** (`crash_reporter.py`) — ffmpeg crashes on-device leave no retrievable trace |
| State pattern | ✅ `@ft.observable` AppState + whole-value writes, `Services`/`controller_ctx` contexts | House has three dialects (ClassVar scalars voicelm, instance ktv, dataclass DDGS); ffmpeg's is the only Flet-1.0-observable one — fine, but one spot (see §4 bug 3) writes a dict item directly |
| Offline handling | ✅ `offline_banner.py` + `ft.Connectivity` monitor + `_refresh_online` in `main.py` | At parity (DDGS banner, CollabShell/ktv `offline_flow`, lm-router/spaninsight/voicelm `connectivity_monitor`) |
| Engine/probe honesty | ✅ `core/engine_probe.py` gates every filter on device capabilities; `engine_info_screen` shows capabilities | Best-in-house for honesty; lm-router goes further with **sha256-pinned engine bundle** in version.json — ffmpeg's `av>=18.1.0` floor is unpinned and unrecorded |

---

## 3. Gaps — things siblings have that ffmpeg lacks (all verified by reading)

1. **No LICENSE file.** `ktv-player/LICENSE` / `spaninsight/LICENSE` carry the proprietary Kiri text. Copy + adapt.
2. **Empty `screenshots/` + no README gallery.** Every shipped sibling embeds 8–15 screenshots; store listings and README quality both need them.
3. **Production AdMob IDs not set** (`constants.py`: `ADMOB_*_PROD = ""`, `USE_TEST_IDS=True`). CI guard will fail tag builds — correct behavior, but the swap + `tools/admob.py swap-ids --mode prod` run is an explicit release step.
4. **No URL allowlist.** voicelm's `is_safe_url`/`safe_launch_url` is the single choke point for outbound links. ffmpeg's `update_dialog.py:42` (`page.run_task(url_launcher.launch_url, url)`) and `:66` (`on_tap_link=_launch`) launch remote `version.json` markdown links unvalidated — a compromised feed = arbitrary URL open. Port the allowlist (hosts: `github.com`, `play.google.com`, `kiri.ng`…).
5. **No disk-persisted crash reporter.** ktv-player's `core/crash_reporter.py` (FLET_APP_STORAGE_DATA/crashes, rotation, MAX 10). ffmpeg's `_crash_hook` logs to memory only; field crashes are unrecoverable.
6. **No `open_dialog`/`close_dialog` helper.** voicelm abstracts the declarative `use_dialog` host with imperative fallback; ffmpeg calls `page.show_dialog` in 8+ places. Works today, brittle against shell refactors.
7. **No CI-workflow/audit/security self-tests.** voicelm has `test_ci_workflow.py`, `test_audit.py`, `test_security.py`; spaninsight has `audit_ft_kwargs.py`. ffmpeg's suite is feature-deep but never interrogates its own release machinery.
8. **No 16 KB ELF-alignment check.** CollabShell's `scripts/check_elf_alignment.py` gates Play's 64-bit page-size rule. ffmpeg bundles **PyAV + native FFmpeg `.so`s** and ships `arm64-v8a` + `x86_64` — the highest native-lib risk in the house — with no equivalent script. Run the check against the first AAB before any Play upload.
9. **No engine pin recorded.** lm-router records `engine_version` + `engine_sha256` in version.json and asserts them. ffmpeg should record the PyAV/FFmpeg build identity (at minimum log `av.__version__` + `av.library_versions()` into the dossier/engine screen and pin `av==` in pyproject).
10. **Prototype leftovers in tree:** root `spike.py`, `src/ui-spike/`, plus research artifacts `deps-tree.txt`, `pinned-deps.txt`. Siblings don't ship spikes. Delete or `.zcodeignore` before v1.
11. **30+ modified files uncommitted** (`git status --short`), **no git tags**. Nothing is releasable until the tree is committed and `v1.0.0` is tagged.
12. **voicelm-style prior art ignored:** `voicelm/tools/compare_kiri_apps.py` et al. already automate cross-app comparison — worth mining for a recurring audit job rather than one-off reports.

---

## 4. Code-quality signals in ffmpeg

- `git log --oneline` (7 commits): scaffold → full app → context fix + suite → observable rewrite/crash fixes → M1 blockers → M2 feature delivery. Coherent, but everything after M2 is uncommitted.
- `git status --short`: ~30 `M` entries spanning workflow, README, pyproject, shell, 10+ screens, services. Uncommitted release surface.
- `TODO|FIXME|XXX|HACK`: **zero hits**. `except:` bare: **zero**. `except Exception`: ~30 sites, all log (`logger.exception/warning`) — the M1 cleanup ("remove all except:pass") held.
- `deprecated`: zero hits. Flet 1.0 API usage verified against installed `flet-1.0.0`: `run_task` requires a coroutine function — all 20+ call sites pass coroutine fns/methods (`gather_consent`, `preload_interstitial`, `launch_url`, `clipboard.set`, `open_app_settings`, `_prepare_camera`, …). `show_dialog`/`pop_dialog` confirmed on `BasePage`. No API misuse found.
- **Suspected bugs / issues (file:line):**
  1. `src/components/update_dialog.py:36-42,66` — unvalidated URL launch from remote markdown (security, see gap 4). Also `_launch` silently drops when `url_launcher is None` with only a log — user taps "Download Update" and nothing happens on misconfigured platforms; surface a snack.
  2. `src/main.py:379-382` — `finish_onboarding` sets `terms_accepted` but there is no app-version stamp; after a v1.1 update users never re-see changed terms/changelog. Consider `terms_accepted_v<build>` or a "What's new" once-flag.
  3. `src/main.py:~292` — `state.settings["theme_mode"] = saved_theme` is a dict-item write next to whole-value `state.theme_mode = …`; if `settings` is observed, item mutation may not notify (the codebase's own comment at `core/state.py:140` warns about whole-value-only writes). Harmless today (theme_mode carries it) but a latent propagation bug — route all writes through whole-value assignment.
  4. `src/screens/capture_screen.py:250,347`, `src/services/media_io.py:51,71,114,148` — broad `except Exception` around permission/file flows correctly toasts, but swallows `CancelledError`/storage-full distinctions; at minimum log disk-space on media-io failures (encodes fail opaquely when storage fills).
  5. `src/core/engine_probe.py:299` — `except Exception: return "present"` (any unexpected error ⇒ protocol declared present). Fail-open probing contradicts the engine-honesty story; fail closed (`"missing"`/`"unknown"`) or re-raise.
  6. No storage-quota guard before encodes: `get_cache_size_bytes`/cache-clear exists in settings, but no pre-flight free-space check in the job runner — the most likely real-world encode failure mode.

---

## 5. Prioritized remaining-work checklist for v1

**Blockers (must close before any store/GitHub release):**
1. [ ] Commit the tree; tag `v1.0.0`. (30+ modified files, zero tags.)
2. [ ] Swap production AdMob IDs (`tools/admob.py swap-ids --mode prod` × constants/pyproject), confirm CI AdMob guard passes on the tag build.
3. [ ] Build all artifacts once from CI; run CollabShell-style 16 KB ELF check on the AAB/APKs (PyAV native libs = highest risk in house); install-test Android (arm64 + x86_64), Windows installer, Linux deb.
4. [ ] Port voicelm `is_safe_url`/`safe_launch_url` allowlist; route update-dialog + all markdown links through it; add `test_security.py`.
5. [ ] Take 8–10 screenshots (light/dark, phone), fill `screenshots/`, add README gallery (store listing needs them).
6. [ ] Add `LICENSE` (copy ktv-player/spaninsight proprietary text).
7. [ ] Delete `spike.py`, `src/ui-spike/`, `deps-tree.txt`, `pinned-deps.txt` (or exclude from packaging).

**Should-have (v1 quality bar):**
8. [ ] Port ktv `crash_reporter.py` (disk-persisted, rotated) and surface "view logs" from settings activity terminal.
9. [ ] Pin engine identity: `av==` in pyproject, record `av.library_versions()` in version.json/engine screen; assert in `test_version_sync.py`.
10. [ ] Pre-flight free-space check in job runner + storage-full error path (most likely field failure).
11. [ ] Add `test_ci_workflow.py` (voicelm pattern: assert quality-gate jobs, `needs:` wiring, AdMob guard, version defaults in `build-all.yml`).
12. [ ] Flip `engine_probe.py:299` fail-open → fail-closed; fix `state.settings` dict-item write to whole-value.

**Polish (v1.x):**
13. [ ] `open_dialog`/`close_dialog` helper (voicelm pattern) to de-risk future shell refactors.
14. [ ] Version-stamped terms / "What's new on update" once-flag.
15. [ ] Launch-failure feedback in update dialog when `url_launcher` is unavailable.
16. [ ] Mine `voicelm/tools/compare_kiri_apps.py` for a recurring house-wide audit job.
17. [ ] Deep-link (`ffmpeg://app/…`) end-to-end test on device (declared in pyproject, route templates in `app_shell.py:208`, ktv proves the pattern works).
