# Release runbook — FFmpeg Lite v1.0.0 → Play Store

How a release happens, in order. The tag is YOUR action; everything before
it is automated or documented below.

## 1. Version bump discipline (enforced by CI identity check)

Source of truth order:

1. `pyproject.toml`: `[project] version` + `[tool.flet] build_number`.
2. `src/core/constants.py`: auto-reads pyproject at import (`APP_VERSION`,
   `BUILD_NUMBER`) — no hand edit.
3. `version.json`: `version` + `build_number` must equal pyproject when
   synced, or sit strictly BEHIND it (held back = notice, ahead = fail).
   The update checker compares remote `build_number`/`version` against the
   installed build; a held-back manifest means "no update yet".

`src/core/changelog.py` needs a `CHANGELOG` key for the new version
(pinned by `test_changelog_has_entry_for_current_version`).

## 2. `mandatory` policy

`version.json → mandatory: true` hides the dialog Close button and sets
modal. Known limitation (do not oversell it): modal blocks outside-tap
only — back-button/dismiss paths can bypass, so `mandatory` is strong
guidance, not a hard block. Set true only for: broken-update recovery,
security fixes, data-loss bugs. Everything else ships `false`.

## 3. Pre-tag gates (all automatic on `v*` push)

- `ruff check` + `ruff format --check` + `pytest -m "not live"`.
- Version identity script (pyproject ↔ constants ↔ version.json).
- AdMob production guard: fails the tag on Google test IDs in
  `pyproject.toml` OR `src/core/constants.py`, or `USE_TEST_IDS=True`.
- AAB inspection step: asserts `minSdkVersion` ≥ 24 (av ABI floor),
  `versionCode` == build number, prod AdMob App ID in the merged
  manifest; records `usesCleartextTraffic` state. Fails on mismatch.

## 4. Artifacts

Tag builds produce: split APKs (`build/apk/`), Play AAB (`build/aab/` —
THE upload artifact), Windows installer, Linux tarball/deb/rpm. All
attached to the GitHub Release automatically.

## 5. UMP consent form (YOUR dashboard action — blocks EEA launch)

AdMob → Privacy & messaging → create a UMP consent form for app ID
`ca-app-pub-5679949845754640~8554716742` → republish. The app fail-closes
(no ads without consent) and logs the dashboard fix at error (code 3)
until the form exists. After creating it: EEA-retest per the matrix,
including Settings → Ad Privacy Choices (revoke path collapses banners
immediately).

## 6. Data safety + privacy + content rating (YOUR Play Console actions)

- Data safety: declare INTERNET (update check, stream fetch, ads),
  CAMERA + RECORD_AUDIO (in-app capture only), WAKE_LOCK. No broad
  storage permissions (SAF picker/save needs none). No accounts, no
  analytics SDK beyond AdMob.
- Privacy policy: host a URL covering local-first processing (media never
  leaves the device), AdMob advertising, and the UMP consent flow.
- Content rating questionnaire + category + contact details.

## 7. Signing

CI signs with `KEYSTORE_BASE64`/`KEY_ALIAS`/`KEYSTORE_PASSWORD`/
`KEY_PASSWORD` secrets (never in repo). Decide BEFORE first upload:
Play App Signing (recommended — Google holds the upload key, CI keystore
is the upload key) vs self-managed. Rotation pointers: Play Console →
Setup → App integrity.

## 8. Rollout stages

internal track (team + your devices, matrix green) → closed track
(1–2 day bake, crash-free + ANR watch) → production staged rollout
(10% → 50% → 100%, 2-day bakes). Hold on: crash spike, consent-form
complaints, or storage-fill reports.

## Appendix A — listing copy draft (text only; shoot assets on hardware)

- Short (80): "FFmpeg on your phone: convert, compress, trim, extract, join."
- Full: local-first media studio — conversion, target-size compression,
  keyframe trimming, audio/frame/GIF/subtitle extraction, loudness
  mastering, filter stack, live-stream recording, clip joining, camera/mic
  capture. No account, no uploads; ads support development (consent-gated).
- Category: Video Players & Editors. Content rating: everyone (no UGC
  sharing — outputs save/share via the user, nothing publishes in-app).
- Screenshots to capture (≥2, portrait + landscape mix): Home grid,
  Convert with pair-matrix note, Cut scrub + keyframes, Result A/B,
  Audio Studio audition, Dossier, Capture, History with banner.

## Appendix B — known limitations (do not promise otherwise)

- Mobile wheel is the capability floor (`docs/why-ffmpeg-lite.md`): no
  H.264/HEVC/VP9/AV1 or MP3 encode on-device; HTTPS via the app stack.
- `mandatory:true` is advisory (modal≠hard block).
- `http://` capture follows the platform cleartext default (recorded by
  the AAB inspection step per build).
- GIF single-pass buffers full segments in memory (30s+ segments heavy).
- HLS downloads cap at the user setting (default 2 GB) with per-download
  override — multi-GB VOD needs the override.
