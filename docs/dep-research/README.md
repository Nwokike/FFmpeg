# Dependency research corpus

The per-package dossiers in this directory are source-read snapshots captured during the FFmpeg v1.0 audit. They remain useful as historical API evidence, but the release lockfile and installed environment are authoritative for what v1.0.0 actually ships.

The current release pins the complete Flet stack at 1.0.1:

- `flet`, `flet-ads`, `flet-audio`, `flet-audio-recorder`, `flet-camera`, `flet-permission-handler`, and `flet-video`
- `flet-cli`, `flet-desktop`, and `flet-platform-assets` in the development/build group

The 2026-09-24 revalidation against the installed Flet 1.0.1 source passed the application entrypoint verifier, all screen/route regression tests, and the locked test suite. Historical dossiers that mention Flet 1.0.0 are not claims about the current binary; see [`../flet-1.0.1-revalidation.md`](../flet-1.0.1-revalidation.md) for the current compatibility notes.
