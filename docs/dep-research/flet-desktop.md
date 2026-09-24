# flet-desktop 1.0.0 — Complete API Reference

> **Purpose.** `flet-desktop` is the desktop runtime/launcher for Flet 1.0. It
> provisions the compiled Flutter desktop client (downloaded once from GitHub
> Releases into `~/.flet/client/`, or bundled by `flet pack`) and spawns it as a
> subprocess pointed at the Python app's page URL. It owns the entire
> boot-the-Flutter-shell handshake: artifact selection, extraction, launch argv,
> PID-file lifecycle, and platform taskbar identity. It is **not** imported by
> app code directly — `flet.app.run()` imports and drives it.

---

## Files

Package dir: `.venv/Lib/site-packages/flet_desktop/` — 3 source files, **no
bundled binaries or assets** (the `app/` dir referenced by `get_package_bin_dir()`
does not exist in this install; all clients arrive via download into
`~/.flet/client/`).

| File | Size | Role |
|---|---|---|
| `__init__.py` | 24,521 B (702 lines) | All runtime logic: flavor/distro detection, download, cache, launch |
| `win_taskbar.py` | 10,601 B (317 lines) | Windows AppUserModel taskbar-identity stamping (ctypes/COM) |
| `version.py` | 18 B | `version = "1.0.0"` — single source of truth for client release tag |

(`__pycache__/` + `.pyc` excluded per instructions.)

Dist-info (`flet_desktop-1.0.0.dist-info/`): `METADATA`, `RECORD`, `WHEEL`,
`INSTALLER`, `top_level.txt`, `REQUESTED` (empty). **No `entry_points.txt`**
(no console scripts), **no LICENSE file shipped** (license declared as
`Apache-2.0` SPDX expression only).

---

## Metadata

From `METADATA` (Metadata-Version 2.4):

- **Name / Version:** `flet-desktop 1.0.0`
- **Summary:** "Flet Desktop client in Flutter"
- **License:** `Apache-2.0` (`License-Expression`)
- **Requires-Python:** `>=3.10` (app runs 3.14 — fine)
- **Dependencies (exact):**
  - `flet==1.0.0` (hard pin — desktop client and SDK must match; enforced at
    runtime by `flet.utils.pip.ensure_flet_desktop_package_installed`, which
    raises `RuntimeError("flet-desktop version mismatch")` on drift)
  - `rich>=13.0.0` (floor only — used for the one-time download progress bar)
- **Entry points:** none.
- **RECORD hashes:** `__init__.py` sha256 `Vko-5748…`, `win_taskbar.py`
  sha256 `spz3etm…`, `version.py` sha256 `4se2-QR…`.

---

## Module-by-module API

### `flet_desktop/__init__.py`

**Boot flow** (what happens when `ft.run(main)` uses the default
`view=AppView.FLET_APP`): `flet/app.py` → `ensure_flet_desktop_package_installed()`
→ `open_flet_view_async(page_url, assets_dir, hidden)` → `__locate_and_unpack_flet_view`
→ `ensure_client_cached()` → `Popen`/`create_subprocess_exec` → `__apply_taskbar_props`
→ app waits on `fvp.wait()` → `close_flet_view(pid_file)`.

Public functions (all importable from `flet_desktop`):

```python
def get_package_bin_dir() -> str
```
Returns `<package>/app` — directory for PyInstaller-bundled client archives.
Empty/absent in a normal wheel install; download path is then used.
Side effect: none.

```python
def get_artifact_filename() -> str
```
Release artifact name for this platform. `flet-windows.zip` |
`flet-macos.tar.gz` | `flet-linux-{distro}[-light]-{arch}.tar.gz`.
Side effect: none. Example: on this project's Windows CI → `flet-windows.zip`.

```python
def ensure_client_cached() -> Path
```
Idempotent provisioning: returns `~/.flet/client/flet-desktop-{flavor}-{version}[-{fp12}]`.
Fast path touches `.last-used`; slow path extracts bundled archive or downloads
from GitHub Releases to a temp dir, then **atomically renames** into place
(race-safe; concurrent extractors share the winner). Fingerprinted caches trigger
30-day stale-sibling GC. Raises whatever `urllib`/`tarfile`/`zipfile` raise on
network or corrupt-archive failure.

```python
def find_macos_app_bundle(directory) -> Path | None
```
First sorted `*.app` directly inside `directory`; `None` if missing — lets the
caller fall through to the next client source instead of raising.

```python
def open_flet_view(page_url, assets_dir, hidden) -> tuple[subprocess.Popen, str]
async def open_flet_view_async(page_url, assets_dir, hidden) -> tuple[asyncio.subprocess.Process, str]
```
Spawn the desktop client pointed at `page_url`; append `assets_dir` as a CLI
arg when set; set `FLET_HIDE_WINDOW_ON_START=true` in the child env when
`hidden`. Return `(process, pid_file)` — the pid_file **must** be passed to
`close_flet_view`. The client binary writes its own PID there so the Python
side can SIGKILL it later. Also applies Linux `argv[0]` identity and Windows
taskbar props as side effects.

```python
def close_flet_view(pid_file) -> None
```
Reads PID from `pid_file`, `os.kill(pid, SIGKILL)`, removes the file. All
termination failures swallowed; file removal attempted regardless. `None` or
missing file → no-op.

Private helpers (name-mangled, documented for completeness):

| Helper | Role |
|---|---|
| `__get_desktop_flavor()` | `"full"` vs `"light"`: `FLET_DESKTOP_FLAVOR` env → `[tool.flet].desktop_flavor` in cwd `pyproject.toml` → default (`light` on Linux, `full` elsewhere) |
| `__get_system_glibc_version()` | `(major, minor)` via `gnu_get_libc_version`; `(0,0)` on failure |
| `__get_linux_distro_id()` | Picks newest `_GLIBC_DISTRO_TABLE` entry ≤ system glibc; `FLET_LINUX_DISTRO` overrides. Table: 2.28→debian10, 2.31→ubuntu20.04, 2.35→ubuntu22.04, 2.36→debian12, 2.39→ubuntu24.04 |
| `__get_client_storage_dir(fingerprint?)` | Cache path builder; `-{fp12}` suffix isolates `flet pack`-patched clients |
| `__get_archive_fingerprint(path)` | 12-hex-char SHA-256; prefers `<archive>.sha256` sidecar (validated against live file size, else re-hashed); caches result |
| `__gc_stale_client_dirs(cache_dir, max_age_days=30)` | Evicts unused fingerprinted siblings via rename-then-delete (Windows-safe); sweeps `.trash-*` leftovers |
| `__download_with_progress(url, dest, desc)` | `urllib` + `rich.Progress(transient=True)` chunked (8 KiB) download |
| `__download_flet_client(file_name)` | URL = `https://github.com/flet-dev/flet/releases/download/v{version}/{file}`; `FLET_CLIENT_URL` overrides wholesale; prints one-time "Preparing Flet…" notice |
| `__linux_identity_args(args)` | If `FLET_APP_ID` set on Linux: launch as `[app_id, *rest]` with `executable=<real binary>` so GLib/GTK derive WM_CLASS/Wayland app_id per app instead of "flet". Rejects values with `/` or control chars |
| `__apply_taskbar_props(pid)` | Windows-only; delegates to `win_taskbar.apply_relaunch_props_async` when `FLET_APP_USER_MODEL_ID` is set |
| `__locate_and_unpack_flet_view(page_url, assets_dir, hidden)` | 3-tier resolution per OS: `build/<os>/` outputs → `FLET_VIEW_PATH` → cached/downloaded client; builds platform argv (`[exe, url, pid]` Windows/Linux; `open <app> -n -W --args <url> <pid>` macOS); injects child env |

**Environment variables honored** (complete):

| Variable | Read in | Effect |
|---|---|---|
| `FLET_DESKTOP_FLAVOR` | `__get_desktop_flavor` | `full`/`light` client selection (else pyproject/default) |
| `FLET_LINUX_DISTRO` | `__get_linux_distro_id` | Override glibc→distro mapping |
| `FLET_CLIENT_URL` | `__download_flet_client` | Replace the GitHub Releases download URL entirely |
| `FLET_VIEW_PATH` | `__locate_and_unpack_flet_view` | Dev client dir (expects `flet.exe` / `.app` / `flet` inside) |
| `FLET_HIDE_WINDOW_ON_START` | set (not read) | Written `=true` into child env when `hidden=True` |
| `FLET_APP_ID` | `__linux_identity_args` | Linux taskbar/Wayland app identity via `argv[0]` |
| `FLET_APP_USER_MODEL_ID` | `__apply_taskbar_props` | Gates Windows taskbar stamping |
| `FLET_APP_RELAUNCH_COMMAND` / `FLET_APP_RELAUNCH_DISPLAY_NAME` / `FLET_APP_RELAUNCH_ICON` | `win_taskbar` | Explicit taskbar relaunch props (else derived from the UserModelID-as-path) |

**Window configuration note:** window title/size/position are **not** set here —
they are `page.window_*` / `page.title` properties sent over the page protocol.
The only window knobs in this package are hidden-at-start and taskbar identity.

**Asset serving:** `assets_dir` is passed as a trailing CLI arg to the client
binary (see `__locate_and_unpack_flet_view`, `__init__.py:696-697`); the client
serves those files locally. `FLET_APP_WEB` view passes `None` instead (served
by the Python web server).

**CLI `run` integration:** `ft.run(...)` defaults to `view=AppView.FLET_APP`,
so every plain `ft.run(main, assets_dir=...)` boots this package. `flet run`
(CLI dev command) funnels through the same `flet.app.run` path.

### `flet_desktop/win_taskbar.py`

Windows-only COM helpers (module imports `ole32`/`shell32`/`shlwapi`/`user32` at
top level — **importing it on Linux/macOS raises**; guarded by `is_windows()` at
the call site).

```python
class GUID(ctypes.Structure)       # Win32 GUID; optional "{...}" string init via CLSIDFromString
class PROPERTYKEY(ctypes.Structure) # fmtid: GUID + pid: uint32
class PROPVARIANT(ctypes.Structure) # minimal VT_LPWSTR-capable mapping
def apply_relaunch_props_async(pid: int) -> None
```
`apply_relaunch_props_async`: no-op unless `os.name == "nt"` **and**
`FLET_APP_USER_MODEL_ID` is set. Otherwise spawns a daemon thread that polls
(up to window appearance, 200 ms cadence) for the top-level `HWND` of class
`FLUTTER_RUNNER_WIN32_WINDOW` owned by `pid`, then stamps
`System.AppUserModel.ID` + `RelaunchCommand` (+ `DisplayName`, `IconResource`
when derivable) via `SHGetPropertyStoreForWindow`. PID-recycling-safe: holds a
`SYNCHRONIZE` handle for the whole poll and matches by window class. All COM
failures degrade to `logger.warning`. When the UserModelID is an existing file
path, relaunch/display/icon default to `"<path>"` / basename / `"<path>,0"`.

### `flet_desktop/version.py`

```python
version = "1.0.0"
```
Pinned by `flet==1.0.0` metadata and cross-checked at runtime by
`flet.utils.pip.ensure_flet_desktop_package_installed` (auto-installs if
missing, raises on mismatch).

---

## App usage & correctness

**(a) Correct usage.**

- `pyproject.toml:20-23` — `flet-desktop>=1.0.0` correctly in the **dev**
  dependency group (desktop client is a dev-run/pack-time concern; mobile
  builds don't need it). Lower bound matches installed `1.0.0`.
- `src/main.py:738-739` — correct minimal entry:
  `assets_dir = str(Path(__file__).resolve().parent / "assets")` +
  `ft.run(main, assets_dir=assets_dir)`. Absolute assets path (robust to cwd),
  default `FLET_APP` view → desktop client receives assets as CLI arg.
- `src/main.py:185` — `page.title = APP_NAME` sets the window title via the
  supported channel (page protocol, not this package).
- `src/core/constants.py:72-74`, `src/core/storage_paths.py` — app reads
  `FLET_APP_STORAGE_{DATA,CACHE,TEMP}` (server-injected storage env), orthogonal
  to but compatible with the desktop client's env inheritance (`{**os.environ}`).
- CI (`build-all.yml:169-306`) builds desktop via `flet build windows/linux`
  (flet-cli path) — right layer; `flet-desktop` is not (and should not be)
  invoked by CI directly. `FLET_CLI_NO_RICH_OUTPUT=1` keeps the rich progress
  bar out of logs.

**(b) Misuse — none found.** No direct `import flet_desktop` in `src/`,
`tools/`, or `tests/`; no hand-rolled subprocess launch of the client; no
`FLET_*` env vars set that would fight the launcher. `close_flet_view`'s
SIGKILL semantics are owned by `flet/app.py`, not app code — nothing to fix.

**(c) Underuse (config the app never sets).** No `desktop_flavor` key under
`[tool.flet]` (`pyproject.toml:33`); no `FLET_VIEW_PATH` / `FLET_CLIENT_URL` /
`FLET_APP_ID` anywhere in repo; no `AppView.FLET_APP_HIDDEN` launch path; no
window-size properties in `main.py` beyond title. All defaulted — acceptable for
a mobile-first app, but see below for the two that matter for v1.0 desktop runs.

---

## Underused APIs to adopt

1. **`[tool.flet].desktop_flavor = "full"`** (`pyproject.toml:33`, add one
   line). The default is already `full` off-Linux, and this app's Linux dev
   machines would silently get the `light` client (fewer platform channels).
   Pinning `full` makes desktop test runs deterministic across OSes. Zero risk.
2. **`page.window_width` / `page.window_height` (+ `page.window_min_width` /
   `page.window_min_height`)** in `main()` near `src/main.py:185`. The desktop
   window currently opens at whatever size the cached Flutter client defaults
   to — on a media-transcoding app with dense tables this is visibly
   arbitrary. Setting an initial size (e.g. 1280×800, min 1024×640) costs three
   lines and fixes first-run presentation. (Page-protocol API, surfaced here
   because flet-desktop itself offers no size knob — by design.)
3. **`FLET_APP_ID` (Linux dev runs only).** Without it every `ft.run` window
   groups under "flet" in the taskbar/dock. Export
   `FLET_APP_ID=ng.kiri.ffmpeg` in the desktop dev workflow if Linux desktop
   testing matters for v1.0; ignore otherwise.
4. Skip: `FLET_VIEW_PATH`, `FLET_CLIENT_URL`, `FLET_APP_HIDDEN`, Windows
   `FLET_APP_USER_MODEL_ID` — only relevant for client developers, offline/air-
   gapped provisioning, splash-hidden boot, and `flet pack`ped executables
   respectively. None apply pre-v1.0.

---

## Gotchas

1. **First run downloads ~100 MB+ from GitHub Releases.** `ensure_client_cached`
   (`__init__.py:334-399`) downloads on cache miss with only a console line and
   a rich progress bar. Fresh CI/dev machines appear to hang; `FLET_CLI_NO_RICH_OUTPUT`
   is already set in CI, but document the download for new contributors.
2. **Cache is keyed by version+flavor+fingerprint under `~/.flet/client/`.**
   Bumping `flet` without bumping `flet-desktop` raises version-mismatch at
   startup (by design — never pin them apart). Stale fingerprinted siblings GC
   after 30 days of disuse; the vanilla cache dir is never GC'd.
3. **`close_flet_view` SIGKILLs.** (`__init__.py:539-561`). On Windows
   `os.kill(pid, SIGKILL)` terminates without cleanup; a killed client can
   leave its temp pid-file behind (removed in `finally`) or, if the process
   dies first, the `except: pass` hides it. Not app-actionable, but explains
   orphan `flet.exe` processes after a crashed debug session.
4. **`win_taskbar.py` is not import-safe off Windows.** Top-level
   `ctypes.OleDLL/WinDLL` loads mean any stray `import flet_desktop.win_taskbar`
   on Linux/macOS crashes — always go through `open_flet_view*`, which guards
   with `is_windows()`. The app never imports it directly (verified).
5. **Linux `argv[0]` trickery.** `__linux_identity_args` (`__init__.py:424-468`)
   passes `executable=` to `Popen`, so `ps` shows the app ID, not the binary
   path — don't be confused when debugging desktop processes.
6. **macOS launch goes through `open -n -W`.** (`__init__.py:660`.) `-W` blocks
   until the app exits (that's the `await fvp.wait()`), and `-n` allows a
   second instance alongside an installed copy — two FFmpeg windows can result.
7. **No entry points / no CLI surface.** Everything is driven via
   `flet.app.run`; there is nothing to invoke, version-check, or smoke-test in
   this package directly. The meaningful assertion for v1.0 readiness is
   `flet_desktop.version.version == flet.version.flet_version` (currently
   `1.0.0 == 1.0.0`).
