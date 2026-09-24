# Flet 1.0.1 revalidation — 2026-09-24

The v1.0.0 release environment was moved from Flet 1.0.0 to the matching Flet 1.0.1 package line. The lockfile now pins the core package, every extension used by the app, and the CLI/desktop build tools at 1.0.1.

## Verified

- Installed runtime reports `flet 1.0.1` on Python 3.14.7.
- The Flet MCP verifier imported the real `src/main.py` entrypoint and completed static plus sandboxed dynamic checks with no diagnostics.
- `SegmentedButton.selected` is a `list[str]`, `Image.src` accepts raw SVG bytes, and `Router(..., manage_views=True)` matches the installed 1.0.1 source.
- The installed extension constructors and UMP methods used by capture, preview, and ads match the application call sites.
- The complete offline test suite and whole-repository Ruff/format gates pass.
- `uv lock --check`, frozen mobile export, workflow YAML parsing, and release identity validation pass.

## Compatibility boundary

The source keeps parenthesized multi-exception clauses and configures Ruff's formatter for conservative syntax output. The app still requires Python 3.14, but this avoids depending on Python 3.14-only formatting when another Flet validation runtime imports the code.

The local engine probe reports no hardware devices in this desktop wheel. Hardware decode remains enabled by default and falls back to software when no device is available. HLS and DASH protocol probes are also capability-dependent; the Streams screen reports the live wheel's supported protocols rather than promising unsupported inputs.
