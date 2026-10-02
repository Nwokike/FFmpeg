# Roadmap — milestones to production standard

Agreed workflow: plan M(n) → approve → implement → back to plan mode
for M(n+1). Repeat until production standard.

Constraint on every milestone: `docs/why-ffmpeg-lite.md` — mobile
wheel is the capability floor. No milestone widens the surface beyond
what the probe verifies; utilization work stays inside the wheel.

## M1 — Stop the bleeding (deadlocks, data loss, consent)

Fix the P0s that destroy data, deadlock, crash, or mis-record consent:

- job_queue: notify-outside-lock, `start()` race, terminal-status
  reconciliation, shutdown join semantics.
- storage_paths: symlink-safe delete, subtree-aware `keep`, TEMP out
  of `clear_cache` (or `keep` hatch), honest `freed` accounting.
- media_io: registry path, `with_data` mobile picks, cancel-vs-error
  split.
- notify: no destructive pop, single reusable SnackBar, honest
  suppress contract.
- logger_handler: snapshot under lock.
- storage_service: dict validation, exception-safe write, no live refs.
- onboarding: Skip ≠ accept (separate skipped state), tappable consent
  row, responsive CTA + scroll guard.
- banner revoke path publishes `ads_ready`.

Exit: no known data-loss path, no deadlock path, consent truthful.
Tests for each.

## M2 — Engine truth (mux, probe, parse)

- `_mux_packet` (pts+dts clamp) on all four mux sites; separate
  pts/dts bases + clamp at 0; skip drain/flush on cancel.
- UnknownCodecError real path; fifo `except` widened; GIF two-pass
  (or bounded single-pass); rotation loop; crop even-align order;
  HLS double-GET + size cap documented.
- engine_probe: hwdevices real path, cache key includes FFmpeg build
  identity, honest ~5s cost comment, `mpeg4` last-resort fallback.
- command_parser: `-vn`/`-an`/`-sn` exact-match first, duplicate-flag
  policy, cut `copy=False` default + full encode-flag set, volume
  dB/linear math, fps rounding, timestamp validation, `NoReturn`
  refuse, input==output guard, GIF `end is not None`.
- main dispatch: `concat` in HIGH_VALUE set, `else` marks failed.

Exit: duplicate-DTS class dead on all paths; parser honors
no-silent-drop; probe tells the truth.

## M3 — Stuck states (navigation, buttons, badges)

- app_shell back/go_home drive `state.active_view`; badge recounts on
  queue change (effect deps + destination update); pre-mount nav
  survives; tab clamp; distinct Jobs selected icon.
- controller_ctx: declare `go_home/back`, non-optional `show_view`,
  honest async types, recording test doubles.
- service_ctx: fail-fast on missing provider, real types, hook-scope
  docs.
- Every screen's `is_processing` resets on settle (or derives from
  `active_job`); kind gates (audio/image where video assumed);
  container↔codec matrix before Start; unique temp names.
- history Undo whole-value + position + Clear-All undo + search-state
  hygiene. result flet-audio fallback. job_card None-status.
- back_stack: wire-or-delete decision + docstring de-hallucination.

Exit: no dead buttons, no stuck navigation, no silent failures.

## M4 — Honesty pass (comments, labels, docs)

- Rewrite every hallucinated comment in the master list (§Hallucinated
  comments) to match installed source.
- Op-label single source (`Join`/`Recording`/… everywhere); `%`
  clamp parity; pause derived from queue state, not strings.
- update_dialog None/{} hardening, modal feedback, responsive sizing.
- settings responsive dialogs, off-thread cache size, single-flight
  probe. terminal log cap + Enter-to-run + async probe. home grid
  `with_opacity`, `xxl` pin, single-banner comment. probe exclusions
  reset per file. streams unique names + honest badge. engine_info
  error state + derived header. changelog fallback chain.

Exit: words match behavior; no comment a new dev would trust and regret.

## M5 — Utilize the wheels (inside Lite limits)

Only capabilities the mobile wheel actually ships, probe-verified,
display-table-gated:

- av: device enumeration for capture names; `supported_codecs` /
  `default_*_codec` dropdown defaults; `frame_rates/formats` preflight;
  rotation write; `skip_frame`/threads fast preview; per-job native
  log capture; typed error cards; Disposition badges; keyframe seek.
- flet-video: `take_screenshot` verify; `on_load`-gated readiness;
  `VideoConfiguration` title (kill `flet-video` mixer label).
- flet-audio: balance/rate preview in Audio Studio; `on_loaded`
  indicator; LOOP toggle.
- recorder: input-device picker; DSP flags surfaced; encoder breadth
  where wheel supports.
- camera: torch, zoom range, front/back switch, orientation lock.
- permissions: PHOTOS/VIDEOS/AUDIO gates before save paths; fix
  Linux/macOS mic block.
- ads: `on_paid` logging, lifecycle events, privacy-options entry
  point in Settings.
- httpx: HLS retries + Range resume groundwork, HEAD preflight,
  shared pooled client, total deadlines.

Exit: every shipped wheel capability the Lite surface can use is
either exposed or recorded as intentionally deferred.

## M6 — Release hardening

- Version/hex/changelog single-sources + CI guards.
- AdMob live-ID verification, UMP form created in dashboard (user
  action), privacy re-consent path tested.
- Full manual matrix (every tool × media kind), device retest of the
  four phone failures + HLS URL + back behavior.
- Play Store AAB, listing assets, rollout plan.

Exit: production standard, uploaded.
