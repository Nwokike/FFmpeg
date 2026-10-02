# Swarm audit — reference index

Full-file + per-dependency audit of FFmpeg Lite, run against installed
`.venv` (av 18.1.0, flet 1.0.3 stack, httpx 0.28.1, Python 3.14).
Report-only pass: no code changed. Every finding cites `file:line`
verified against installed source, not docs.

## The constraint everything obeys

`docs/why-ffmpeg-lite.md` — the Flet mobile wheel (`av` +
`flet-libffmpeg` from pypi.flet.dev) has no H.264 / HEVC / VP9 / AV1
encoders, no MP3 encoding, and no HTTPS transport (app fetches via
`httpx` and hands bytes to PyAV). Mobile is the capability floor:
desktop exposes the same surface so projects behave consistently.
Every feature is probe-driven (`src/core/engine_probe.py`) — never
show a control the runtime probe says the engine cannot support, and
never assume a probe-verified capability is automatically visible
(it must also be in the screen's display table).

## Documents

- `00-master-list.md` — consolidated defects (P0/P1), utilization
  gaps, hallucinated comments. Start here.
- `30-roadmap-milestones.md` — M1–M6 phases + the plan-mode workflow.
- Dependencies (the wheels we ship on):
  - `10-dependencies-av.md` — av 18.1.0 surface / used / unused.
  - `11-dependencies-flet-core.md` — flet 1.0.3 core surface / unused.
  - `12-dependencies-flet-video.md` — flet-video player API / unused.
  - `13-dependencies-flet-audio.md` — flet-audio player API / unused.
  - `14-dependencies-flet-audio-recorder.md` — recorder API / unused.
  - `15-dependencies-flet-camera.md` — camera API / unused.
  - `16-dependencies-permission-handler.md` — 40 permissions / used 2.
  - `17-dependencies-flet-ads-sdk.md` — ads SDK surface / unused.
  - `18-dependencies-httpx.md` — httpx + what the app uses / misses.
  - `19-dependencies-transitives.md` — msgpack, oauthlib, repath,
    anyio/httpcore/h11/certifi/idna.
- Code areas:
  - `20-engine-and-queue.md` — engine_service, engine_probe,
    job_queue, command_parser, storage paths/services.
  - `21-app-shell-and-state.md` — main, app_shell, state,
    controller/service ctx, notify, back_stack, theme, constants,
    assets, changelog, logger.
  - `22-screens-capture-cut-result.md` — capture, cut, result.
  - `23-screens-convert-join-home.md` — convert, join, home,
    compress, extract, filters.
  - `24-screens-audio-probe-rest.md` — audio, probe, streams,
    engine_info, history, settings, onboarding, terminal.
  - `25-components.md` — banner_ad, job_card, jobs_banner,
    brand_header, empty_state, offline_banner, update_dialog.

## Workflow (agreed)

Plan mode per milestone: plan M(n) → approve → implement → back to
plan mode for M(n+1). Repeat until production standard.
