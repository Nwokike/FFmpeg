# flet-cli 1.0.0 — Complete API Reference

> Package: `flet-cli==1.0.0` (build toolchain: `flet build/run/debug/test/pack/publish/...`).
> Ground truth: `<repo>\.venv\Lib\site-packages\flet_cli` + `flet_cli-1.0.0.dist-info\`.
> Related packages (overlap noted, not covered here): `flet_desktop` (native window/client binaries), `flet_platform_assets` (icon/splash pixel rendering).
> All `[tool.flet]` key claims below were verified with `grep get_pyproject` against `flet_cli` source. Key line refs are `flet_cli/commands/build_base.py:<line>` unless stated otherwise.

---

## Files

Wheel file list (from `RECORD`; `__pycache__/*.pyc` skipped — 1 `.py` source each):

```
flet_cli/cli.py                      # root parser, default subcommand, --version/--json
flet_cli/version.py                  # version = "1.0.0"
flet_cli/commands/base.py            # BaseCommand + help formatter
flet_cli/commands/options.py         # Option helper, verbose_option (-v)
flet_cli/commands/flutter_base.py    # BaseFlutterCommand (SDK install, run, cleanup)
flet_cli/commands/build_base.py      # BaseBuildCommand — ALL config parsing + pipeline (3491 lines, ~140 KB)
flet_cli/commands/build.py           # `flet build` (8 targets, macOS/iOS signing lanes)
flet_cli/commands/debug.py           # `flet debug` (flutter run wrapper)
flet_cli/commands/test.py            # `flet test` (provision + pytest driver)
flet_cli/commands/test_host.py       # re-export of provision_test_host for pytest plugin
flet_cli/commands/run.py             # `flet run` (hot-reload dev loop)
flet_cli/commands/pack.py            # `flet pack` (PyInstaller desktop bundler)
flet_cli/commands/publish.py         # `flet publish` (static Pyodide web site -> dist/)
flet_cli/commands/serve.py           # `flet serve` (static file server w/ COOP-COEP)
flet_cli/commands/create.py          # `flet create` (cookiecutter app scaffolding)
flet_cli/commands/clean.py           # `flet clean` (delete build/)
flet_cli/commands/doctor.py          # `flet doctor` (env info)
flet_cli/commands/devices.py         # `flet devices` (flutter devices parser)
flet_cli/commands/emulators.py       # `flet emulators` (list/create/start/delete)
flet_cli/commands/mcp.py             # `flet mcp` (only if flet-mcp installed)
flet_cli/utils/pyproject_toml.py     # load_pyproject_toml -> get_pyproject(dotted.path)
flet_cli/utils/python_versions.py    # python-build manifest pin + resolve_python_version
flet_cli/utils/template_cache.py     # ~/.flet/cache (build-template zips, pyodide, manifest)
flet_cli/utils/hash_stamp.py         # HashStamp (incremental rebuild stamps in build/.hash/)
flet_cli/utils/merge.py              # merge_dict (recursive dict merge)
flet_cli/utils/plist.py              # parse_cli_plist_value / is_supported_plist_value
flet_cli/utils/cli.py                # parse_cli_bool_value, quote_for_shell
flet_cli/utils/processes.py          # run() subprocess helper (UTF-8 codepage fix on Win)
flet_cli/utils/project_dependencies.py # poetry/PEP-621 -> pip requirement strings
flet_cli/utils/flutter.py            # get_flutter_dir (~/flutter/<ver>), install_flutter
flet_cli/utils/android.py            # ANDROID_ARCH_TO_FLUTTER_TARGET_PLATFORM + helpers
flet_cli/utils/android_sdk.py        # AndroidSDK (cmdline-tools, packages, licenses, AVD delete)
flet_cli/utils/jdk.py                # Temurin JDK 17.0.13+11 installer
flet_cli/utils/linux_deps.py         # linux_dependencies tuple (apt list for --version --json)
flet_cli/utils/pyodide.py            # ensure_pyodide (core tarball + micropip/packaging wheels)
flet_cli/utils/distros.py            # download_with_progress / extract_with_progress
flet_cli/utils/ios_sign.py           # installed_provisioning_profiles / find_provisioning_profile
flet_cli/utils/macos_sign.py         # full macOS codesign/notary/pkg stack (1320 lines)
flet_cli/__pyinstaller/__init__.py   # get_hook_dirs()
flet_cli/__pyinstaller/config.py     # temp_bin_dir = None (set at pack time)
flet_cli/__pyinstaller/hook-flet.py  # PyInstaller hook (icons.json, cupertino_icons.json, flet bin)
flet_cli/__pyinstaller/utils.py      # get_flet_bin_path / copy_flet_bin / normalize_tar_entry
flet_cli/__pyinstaller/win_utils.py  # exe icon + version-info stamping
flet_cli/__pyinstaller/macos_utils.py# .app unpack/assemble, icon + version stamping
flet_cli/__pyinstaller/rthooks.dat   # {'flet': ['pyi_rth_localhost_fletd.py']}
flet_cli/__pyinstaller/rthooks/pyi_rth_localhost_fletd.py  # FLET_SERVER_IP + taskbar IDs
```

**No bundled templates/assets in the wheel.** There is no `templates/` or `assets/` dir inside `flet_cli`. All Flutter scaffolding is downloaded at build time as `flet-build-template.zip` (see `DEFAULT_TEMPLATE_URL`, `build_base.py:63-66`) and rendered with **`cookiecutter>=2.6.0`** (installed: `cookiecutter 2.7.1`). Two render sites:

1. `commands/create.py:90,134-142` — `cookiecutter(template_url, checkout, directory=template, output_dir, no_input=True, overwrite_if_exists=True, extra_context=template_data)` where `template_url` = local `templates/app` in a source checkout, else `DEFAULT_APP_TEMPLATE_URL` (`.../flet-app-templates.zip`) at ref `options.template_ref or flet_version`. Context: `{template_name, flet_version, sep, platform, out_dir, project_name (slugified), description?}`.
2. `commands/build_base.py:1762-1947 create_flutter_project()` — `cookiecutter(template_url, checkout, directory=template_dir, output_dir=build/flutter.parent, no_input=True, overwrite_if_exists=True, extra_context={k:v for k,v in template_data.items() if v is not None})`. `template_url` precedence: `--template` / `tool.flet.template.url` > local `templates/build` (source checkout) > **downloaded + cached** `DEFAULT_TEMPLATE_URL.format(version=template_ref)` via `utils/template_cache.py:get_cached_template_zip` → `~/.flet/cache/build-template/v<version>/flet-build-template.zip` (`$FLET_CACHE_DIR` overrides `~/.flet/cache`). `template_ref` precedence: `--template-ref` / `tool.flet.template.ref` / `flet_version`. Re-render is gated by `HashStamp(build/.hash/template-1)` (and `template-2` second pass); the digest chains `template_source + template_ref + template_dir + template_data`, exposed as `self.template_digest` so icon/splash stamps re-run after a re-render (which restores placeholder assets over generated ones).

**Overlaps (not this package's API, but called by it):**

- `flet` package: owns the **`flet` console script** (`flet-1.0.0.dist-info/entry_points.txt`: `[console_scripts] flet = flet.cli:main`; `flet/cli.py:main()` calls `ensure_flet_cli_package_installed()` then `flet_cli.cli.main()`). Also `flet.version.{flet_version,flutter_version}`, `flet.utils.{copy_tree,rmtree,slugify,is_windows,...}`, `flet.utils.pip.{ensure_flet_desktop_package_installed,ensure_flet_web_package_installed,ensure_flet_cli_package_installed}`, `flet.app.DEFAULT_ASSETS_DIR`.
- `flet_desktop`: `open_flet_view/close_flet_view` (`run.py`), `ensure_client_cached/get_artifact_filename` (`__pyinstaller/utils.py`, `pack.py`), taskbar relaunch contract (`pyi_rth_localhost_fletd.py`).
- `flet_platform_assets`: `DEFAULT_SPECS, AssetSpec, IconOptions, SplashOptions, density_size, linux_targets, load_source, parse_hex_color, render_icons, render_splash, square, web_targets_from_manifest, write` — all icon/splash pixel work in `customize_icons/customize_splash_images`.

---

## Metadata

`flet_cli-1.0.0.dist-info/METADATA`:

- `Name: flet-cli`, `Version: 1.0.0`, `License-Expression: Apache-2.0`, `Requires-Python: >=3.10`, author `Appveyor Systems Inc. <hello@flet.dev>`.
- Pins (exact): `flet==1.0.0`, `flet-platform-assets==1.0.0`; floors: `watchdog>=4.0.0`, `packaging>=25.0`, `qrcode>=7.4.2`, `rich>=13.0.0`, `cookiecutter>=2.6.0`; caps: `binaryornot<0.5`, `chardet<6`; conditional: `tomli>=1.1.0; python_version < "3.11"`; extra `mcp: flet-mcp`.
- `entry_points.txt` registers **only** a PyInstaller hook dir (`[pyinstaller40] hook-dirs = flet_cli.__pyinstaller:get_hook_dirs`). It does **not** register the `flet` command — that comes from the `flet` package (`flet = flet.cli:main`).
- `top_level.txt`: `flet_cli`. `RECORD` lists all 53 files (hashes in dist-info `RECORD`).
- `cli.py:89-134 get_parser()` registers subcommands: `create run build clean debug test pack publish serve emulators devices doctor` (+ `mcp` iff `import flet_mcp` succeeds). **`run` is the default subcommand** (`cli.py:176-181 set_default_subparser(parser, "run")`): bare `flet app.py` == `flet run app.py`. A bare `--` splits app-script args off before parsing (`cli.py:137-158 split_script_args`); `--` is an error on any command except `run` (`cli.py:200-206`).
- `flet --version [-V] [--json]` (`cli.py:23-41`): text = `Flet: x\nFlutter: y`; `--json` = `{flet, flutter, linux_dependencies[]}` (Python/Pyodide set intentionally NOT here — lives in python-build manifest, `utils/python_versions.py`).

---

## CLI commands & flags

Every command also takes `-v/--verbose` (count; `-vv` = debug) via `BaseCommand.arguments` (`commands/options.py:35-42`, `commands/base.py:60`). Flutter-based commands (`build/debug/test/devices/emulators`) additionally take `--no-rich-output` (`[env: FLET_CLI_NO_RICH_OUTPUT=]`), `--yes` (auto-install SDKs, no prompt), `--skip-flutter-doctor` (`[env: FLET_CLI_SKIP_FLUTTER_DOCTOR=]`) (`commands/flutter_base.py:89-110`).

### `flet run [script] [args] [-- script_args]` — hot-reload dev loop (`commands/run.py:73-196`)

`script` (default `.`; dir → `main.py`), `script_args` (forwarded as `sys.argv[1:]`, must follow `--`), `-p/--port`, `--host` (`*` = all IPs), `--name` (page route), `-m/--module` (`my_app.main`), `-d/--directory` (watch dir), `-r/--recursive` (watch tree), `-n/--hidden`, `-w/--web` (serve + open browser), `--ios/--android` (serve + print LAN URL + QR; fixed port `8551` unless `-p`), `-a/--assets` (default `assets`; relative resolved vs script dir; missing dir dropped with warning unless it IS the default), `--ignore-dirs` (comma list). Reads only `tool.flet.app.path` from pyproject (`run.py:246`). Dev storage: `.flet/storage/{data,cache,temp}` (+ `.flet/.gitignore` `*`, README); process cwd = `data/`, `FLET_APP_STORAGE_*`/`TMPDIR|TEMP|TMP`/`PYTHONPATH` pointed accordingly; `--web/--ios/--android` set `FLET_FORCE_WEB_SERVER=true`. Not a packaging command — no build flags.

### `flet build <target> [app_path] [flags]` — full pipeline (`commands/build.py`, `commands/build_base.py:326-836`)

Targets (`build.py:60-74`): `macos linux windows web apk aab ipa ios-simulator`. `-o/--output` (default `<app>/build/<dist>` where dist = `windows|macos|linux|web|apk|aab|ipa|ios-simulator`). Pipeline order (`build.py:100-144`): `initialize → validate_target_platform (host matrix) → validate_entry_point → setup_template_data → preflight_macos/ios_signing → create_flutter_project → package_python_app → register_flutter_extensions → create_flutter_project(2nd pass) → update_flutter_dependencies? → customize_icons → customize_splash_images → run_flutter → copy_build_output → sign_macos_app? → cleanup(0)`. Host matrix (`build_base.py:153-226`): apk/aab/web buildable on macOS+Windows+Linux; windows/linux/macos only on their host; ipa/ios-simulator macOS-only; `--show-platform-matrix` prints the table and exits.

Shared build flags (`build_base.py:334-836`) with pyproject/env fallback (precedence everywhere: **CLI > `[tool.flet.<platform>.*]` > `[tool.flet.*]` > env > default**, except where noted):

`--arch` (extend, `target_arch`; Android: `arm64-v8a armeabi-v7a x86_64`, macOS: `arm64 x86_64`), `--exclude` (extend, `app.exclude`), `--project/--artifact/--description/--product/--org/--bundle-id/--company/--copyright` (naming; artifact default falls back to `--project`/project.name/dirname; product same; `project.name` defaults from dirname slugified, `-`→`_`), `--android-adaptive-icon-background`, `--linux-categories` (extend), `--splash-color/--splash-dark-color` (defaults `#ffffff`/`#222222`), `--no-web-splash/--no-ios-splash/--no-android-splash` (store_true→None default; `tool.flet.splash.{web,ios,android}` bool; default enabled), `--ios-team-id/--ios-export-method (default debugging)/--ios-provisioning-profile/--ios-signing-certificate`, `--base-url` (default `/`), `--web-renderer {auto,canvaskit,skwasm}` (default **canvaskit**, `[env: FLET_WEB_RENDERER=]`), `--route-url-strategy {path,hash}` (default `path`, `[env: FLET_WEB_ROUTE_URL_STRATEGY=]`), `--pwa-background-color` (falls through to splash color), `--pwa-theme-color`, `--no-wasm` (web only; inverted `tool.flet.web.wasm == False`), `--no-cdn` (`[env: FLET_WEB_NO_CDN=]`; inverted `tool.flet.web.cdn == False`), `--split-per-abi` (apk only), `--android-legacy-packaging/--compile-app (default on)/--compile-packages (default on)/--swift-package-manager (default on)/--cleanup-app/--cleanup-packages` (all `BooleanOptionalAction` w/ `--no-` inverse; `compile.*` via `get_bool_setting`, `cleanup.app` default False, `cleanup.packages` default True), `--cleanup-app-files/--cleanup-package-files` (extend globs; **setting either forces its `cleanup.*=True`**), `--flutter-build-args` (append, passthrough), `--source-packages` (extend; `SERIOUS_PYTHON_ALLOW_SOURCE_DISTRIBUTIONS`), `--android-extract-packages` (`extract_packages`; Android zip-vs-disk split), `--python-version` (e.g. `3.13`; else `requires-python` else manifest default), `--info-plist/--macos-entitlements` (extend `k=v`, TOML values), `--android-features/--android-permissions` (extend `k=true|false`), `--android-meta-data` (extend `k=v` strings), `--permissions {location,camera,microphone,photo_library}` (cross-platform group expander), `--deep-linking-scheme/--deep-linking-host` (**both required together**; CLI pair overrides pyproject), `--android-signing-key-store (+[env]) / -store-password (+[env]) / -key-password (+[env]) / -key-alias (default upload, +[env])` — note passwords have NO pyproject key, `--macos-signing-identity/--macos-distribution {none,developer-id,app-store} (default none)/--macos-notary-profile/--macos-provisioning-profile/--macos-installer-identity` (each +`FLET_MACOS_*` env; notary falls back to `APPLE_API_KEY{,_ID,_ISSUER}`), `--build-number (int)/--build-version (x.y.z)/--module-name (default main)/--template/--template-dir/--template-ref/--show-platform-matrix`.

`flutter build` args derived (`build.py:146-214`): `build <windows|macos|linux|web|apk|appbundle|ipa|ios>` + `--split-per-abi` (apk, templated) + `--target-platform a,b` (apk/aab when `target_arch`) + `--export-options-plist ios/exportOptions.plist` or `--no-codesign` (ipa) / `--simulator` (ios-simulator) + `--build-number/--build-name` + `flutter.build_args` + `--wasm` (web iff renderer auto|skwasm and not no_wasm) + `--verbose` (-vv). Android signing reaches Gradle as `FLET_ANDROID_SIGNING_*` env (`build_base.py:2970-3000`); serious_python native env via `_serious_python_build_env()` (`build_base.py:2878-2939`).

### `flet debug [macos|linux|windows|web|ios|android] [app_path] [--device-id/-d] [--show-devices] [--release] [--route] + build flags` (`commands/debug.py`)

Same provisioning pipeline as build (test_mode off), then `flutter run -d <device>` (`windows|macos|linux|chrome` defaults; ios/android REQUIRE `--device-id`), `--release`/`--route` (web/ios/android only) appended. `--output` forcibly disabled. `--show-devices` runs `flutter devices` and exits.

### `flet test [macos|linux|windows|ios|android] [app_path] [--device-id/-d] [--tests-dir] [--update-goldens/-u] [--flutter-test-host] [-k] + build flags` (`commands/test.py`)

Provisions in `test_mode=True` (pins `artifact_name=project_name`, injects `flutter_test` + `flet_integration_test` dev deps, scaffolds `integration_test/`), SKIPS release build/icons/splash/output-copy (`test.py:32-50 _provision_steps`), then runs `sys.executable -m pytest <app>/<tests-dir> [-k] [-s if -v]` with env `{PATH+flutter/bin, FLET_TEST_DISABLE_FVM=1, FLET_TEST_FLUTTER_EXE, SERIOUS_PYTHON_{VERSION,SITE_PACKAGES,APP,ANDROID_EXTRACT_PACKAGES,FLUTTER_PACKAGES}, SP_NATIVE_SET, FLET_TEST_{DEVICE_MODE,FLUTTER_APP_DIR,PLATFORM,DEVICE,GOLDEN,VERBOSE}}` (`test.py:76-101`). Requires `pytest` importable (hint: `pip install 'flet[test]'`, run via `uv run flet test`). `--flutter-test-host` reuses a cached host (CI). Programmatic entry: `provision_test_host(project_dir, platform_name, device_id, verbose) -> Path` (`test.py:263-313`, re-exported from `test_host.py`).

### `flet pack script [-i/--icon] [-n/--name] [-D/--onedir] [--distpath] [--add-data] [--add-binary] [--hidden-import] [--product-name] [--file-description] [--product-version] [--file-version] [--company-name] [--copyright] [--codesign-identity] [--bundle-id] [--debug-console] [--uac-admin] [--pyinstaller-build-args] [-y/--yes]` (`commands/pack.py`)

PyInstaller desktop bundler (legacy path, NOT the Flutter `build` pipeline). Prompts to delete non-empty `build/` + `<distpath>` unless `-y`. Patches the staged flet client (`copy_flet_bin`, delete `fletd`, stamp icon/version via `win_utils`/`macos_utils`), compresses `flet/` → deterministic `flet-windows.zip` / `flet-macos.tar.gz` (+`.sha256` sidecar `<hash> <size>`) / linux artifact, runs `PyInstaller.__main__.run([script --noconfirm --noconsole? ... --onefile|--onedir])`. Linux: writes `<app_id>.desktop` + `<app_id>.png` next to the exe (`StartupWMClass=<app_id>`; app_id = `--bundle-id` or `--name` or script stem; `--bundle-id` also bundled as `flet_app_id` for the `FLET_APP_ID` runtime hook).

### `flet publish [script] [--pre] [--python-version] [-a/--assets] [--distpath] [--app-name] [--app-short-name] [--app-description] [--base-url] [--web-renderer] [--route-url-strategy] [--pwa-background-color] [--pwa-theme-color] [--no-cdn]` (`commands/publish.py`)

Static Pyodide website → `dist/`: copies `flet_web` package dir, drops `pyodide+canvaskit` (~52 MB) in CDN mode else stages matching Pyodide (`ensure_pyodide`), copies assets, tars app dir → `dist/app.tar.gz` (excludes dotfiles, `__pycache__`, `requirements.txt`, assets, dist), writes generated `requirements.txt` into the tar, patches `index.html`/`manifest.json` (`patch_index_html` incl. `--pre` micropip flag, `web_renderer` default canvaskit, `route_url_strategy` default path; `patch_manifest_json`; `patch_font_manifest_json` only in `--no-cdn`). Deps: `project.dependencies` > `requirements.txt` > `flet==<ver>`; reads `tool.flet.app.path`, `tool.flet.{product,web.base_url,web.renderer,web.route_url_strategy,web.pwa_*,web.cdn}`, `project.{name,description}`.

### `flet serve [web_root=./build/web] [-p/--port=8000]` (`commands/serve.py`)

Static server with `Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Embedder-Policy: require-corp` + `Access-Control-Allow-Origin: *` (WASM-safe). Used after `flet build web`.

### `flet clean [app_path=.]` / `flet doctor` / `flet devices [ios|android] [--device-timeout=10] [--device-connection=both|attached|wireless]` / `flet emulators [start|create|delete] [emulator] [--cold]` / `flet create [out_dir=.] [--project-name] [--description] [--template=app|extension] [--template-ref]`

`clean` deletes `build/`. `doctor` prints `Flet x on <OS> <rel> (<arch>)` + `Python y (exe)` (Flutter version is a TODO). `devices`/`emulators` require Android SDK (`require_android_sdk=True`), parse `flutter devices|emulators` (`•`-separated rows), render rich tables. `create` renders `flet-app-templates.zip` (see Files). `mcp`: `flet mcp [--transport stdio|streamable-http] [--port 8000]` serve + `flet mcp build [--examples] [--docs] [--output]` index builder (hidden unless `flet-mcp` installed, `cli.py:124-132`).

---

## `[tool.flet] config keys (verified against source)`

Precedence (uniform): **CLI flag > `[tool.flet.<platform>.*]` > `[tool.flet.*]` > env var > default**. Dotted-path accessor returns `None` for any missing segment (`utils/pyproject_toml.py:28-50`); **unknown keys are never validated** (only `[tool.flet.macos.signing.*]` lane names are checked, `build.py:415-434`) — typos elsewhere are silently ignored.

| Key | Read at | Notes |
|---|---|---|
| `org` (+ `<platform>.org`) | `build_base.py:1550` | Reverse-DNS org; CLI `--org`. Per-platform override supported. |
| `bundle_id` (+ `<platform>.bundle_id`) | `:1553` | Full bundle id; CLI `--bundle-id`. Per-platform override supported. |
| `product` | `:1027` | Display name; CLI `--product`. No per-platform subkey (unlike org/bundle_id). |
| `artifact` (+ `<platform>.artifact`) | `:1012` | On-disk binary name; CLI `--artifact`. Android outputs renamed `app[-abi]-release.*` → `<artifact>[-abi].*` (`:3175-3237`). |
| `company`, `copyright` | `:1557,:1559` | About-dialog strings; CLI flags. |
| `build_number` | `build.py:195` | int → `flutter build --build-number`; CLI `--build-number`. |
| `project.version` / `tool.poetry.version` | `build.py:201` | → `--build-name`; CLI `--build-version` wins. App sets `project.version` — correct. |
| `project.{name,description}` / `tool.poetry.{name,description}` | `:1004,:1461` | Name/dirname fallback chain; description → template + pubspec (single-quote escaped). |
| `project.requires-python` | `utils/python_versions.py:165` | PEP 440 SpecifierSet → highest stable matching bundled Python; prerelease lines need explicit opt-in (`==X.Y.*` or `--python-version`). Manifest pinned to python-build `20260908` (`:31`), cached `~/.flet/cache/python-build/` (`$FLET_PYTHON_BUILD_MANIFEST` / `$FLET_PYTHON_BUILD_RELEASE_DATE` overrides). |
| `project.dependencies` (+ `<platform>.dependencies`) / `tool.poetry.dependencies` | `build_base.py:2521` | → `serious_python package -r` (PEP 508 via `project_dependencies.py`; `python` excluded from poetry set). `requirements.txt` fallback; else `flet==<ver>`. `publish.py` uses same minus platform part. |
| `dev_packages` (+ `<platform>.dev_packages`) | `:2535` | `{name: path-or-url}` local overrides → `name @ file://...` + `--no-cache-dir` (disables package-hash cache). |
| `source_packages` (+ `<platform>.source_packages`) | `:2634` | → `SERIOUS_PYTHON_ALLOW_SOURCE_DISTRIBUTIONS`. |
| `extract_packages` (+ `<platform>.extract_packages`) | `:2652` | Merged over `ANDROID_DEFAULT_EXTRACT_PACKAGES` (= `[]`) → `SERIOUS_PYTHON_ANDROID_EXTRACT_PACKAGES` for the Gradle split. CLI `--android-extract-packages`. |
| `app.path` | `:963`, `run.py:246`, `publish.py:211` | Subdir of app root containing `main.py`; `package_app_path = app_path/app.path`. |
| `app.module` | `:970` | Entry module stem (default `main`); CLI `--module-name`. |
| `app.exclude` (+ `<platform>.app.exclude`) | `:2621` | Extra `--exclude` globs for `serious_python package` (always includes `build`; web adds `assets`). CLI `--exclude`. Distinct from `cleanup.*` (exclude = never packaged; cleanup = stripped post-compile). |
| `cleanup.app` (+ `<platform>.cleanup.app`) | `:2672` via `get_bool_setting(:2829)` | Default False; CLI `--cleanup-app`. **Implied True when `cleanup.app_files` non-empty** (`:2679-2695`). |
| `cleanup.packages` (+ `<platform>.cleanup.packages`) | `:2675` | Default True; CLI `--cleanup-packages`. |
| `cleanup.app_files` / `cleanup.package_files` (+ `<platform>.cleanup.*`) | `:2679,:2697` | Glob lists (list or comma string) → `--cleanup-app-files/--cleanup-package-files`; setting either flips its master switch on. CLI `--cleanup-app-files/--cleanup-package-files`. |
| `compile.app` / `compile.packages` (+ `<platform>.compile.*`) | `:2664,:2667` | Default True/True; CLI `--compile-app/--compile-packages` (`--no-` disables). |
| `swift_package_manager` | `:2465` (`_darwin_spm_active`) | Default True (matches Flutter 3.44+ SPM default); iOS/macOS only; CLI `--swift-package-manager/--no-swift-package-manager`. `false` only if SPM disabled in Flutter itself. |
| `target_arch` (+ `<platform>.target_arch`) | `:1369` | List or single string; CLI `--arch` (extend). Android validated vs `{armeabi-v7a,armeabi-v7a→android-arm,arm64-v8a→android-arm64,x86_64→android-x64}` (`utils/android.py:3-7`) AND vs bundled-Python `android_abis`; empty → `python_release.android_abis`; rest → `android_excluded_abis`. |
| `splash.{color,dark_color,android,ios,web}` (+ `<platform>.splash.*`, aliases `icon_bgcolor→icon_background`, `icon_dark_bgcolor→icon_dark_background`, `android_12_fit→icon_fit`) | `:1650-1714` (`splash_setting`, `_resolve_splash`) | Colors default `#ffffff`/`#222222`; toggles default on; CLI `--splash-color/--splash-dark-color/--no-{web,ios,android}-splash`. Same dict drives template XML AND `render_splash` pixels (`:2292`). |
| `icon_background` (+ `<platform>.icon_background`) | `:2132-2186` | `#rrggbb` behind transparent icons (Apple flatten + macOS tile); invalid → warn + white. CLI has NO direct flag (only `--android-adaptive-icon-background` which falls through to this). |
| `android.adaptive_icon_background` | `:1601` | Color resource; CLI `--android-adaptive-icon-background`; falls through to `icon_background("android")`, default `#ffffff`. |
| `macos.icon_style` | `:2068` | `auto` default; passed to `IconOptions`. |
| `permissions` | `:1107` | List from `{location,camera,microphone,photo_library}` (CLI `--permissions`); expands into platform plist/entitlements/permissions/features via `cross_platform_permissions` (`:228-310`). `location` = fine+coarse+background + gps/network features false; `camera` = CAMERA + camera features false; `microphone` = RECORD_AUDIO only (deliberately NO storage perms); `photo_library` = READ_MEDIA_VISUAL_USER_SELECTED. |
| `deep_linking.{scheme,host}` + `android.deep_linking.*` + `ios.deep_linking.*` | `:1345-1367` | **Platform-gated, NOT merged**: iOS builds read ONLY `ios.*`, Android ONLY `android.*`, others read global. CLI pair `--deep-linking-scheme/--deep-linking-host` (both required) overrides. |
| `android.{permission,feature,meta_data,provider,gradle_properties,proguard_rules,proguard_default_rules,split_per_abi,legacy_packaging}` | `:1033,:1043,:1094,:1181,:1186,:1191,:1230,:1250,:1263` | permission values bool or inline-table attrs; feature `k=true/false`; meta_data `k=v` strings; provider `{class: {attrs..., meta_data: {...}}}` (`false`/`{}` skips, `true` or `name` attr rejected); gradle_properties merged over `{org.gradle.jvmargs: -Xmx8G..., android.useAndroidX: true}`; proguard appends over default keeps (`-keep class com.flet.serious_python_android.**`, `-keepnames class *`), `proguard_default_rules=false` drops defaults; split_per_abi bool (CLI `--split-per-abi`); legacy_packaging bool (mmap vs extract `.so`). |
| `android.signing.{key_store,key_alias}` | `build.py:1588` + `build_base.py:2970-3000` | `key_store`: CLI `--android-signing-key-store` / pyproject / `$FLET_ANDROID_SIGNING_KEY_STORE`; presence toggles `options.android_signing`. `key_alias`: CLI / pyproject / `$FLET_ANDROID_SIGNING_KEY_ALIAS`, default `upload`. **Passwords have NO pyproject key**: `$FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD` / `$FLET_ANDROID_SIGNING_KEY_PASSWORD` (either fills both) or CLI flags. |
| `ios.{export_method,export_methods,provisioning_profile,signing_certificate,export_options,team_id}` | `:1409-1443`, `build.py:182-193,289-375` | `export_method` default `debugging`; per-method table `export_methods.{method}.{provisioning_profile,signing_certificate,team_id,export_options}` overrides globals; unsigned ipa → `--no-codesign` → `.xcarchive` only; signed → `--export-options-plist ios/exportOptions.plist`. Preflight validates profile (name/UUID, expiry, team, bundle-id coverage) before building. |
| `macos.{info,entitlement}` + `ios.info` | `:1128,:1158` | `info` merged over permission-group plist (Darwin→`macos.info`, else `ios.info`); CLI `--info-plist k=v` (TOML values, validated by `is_supported_plist_value`). `entitlement` merged over sandbox-off/jit/network defaults (`:1054`); CLI `--macos-entitlements`. macOS signing lanes: `macos.signing.{distribution,identity,installer_identity,provisioning_profile,notary_profile}` + per-lane `macos.signing.{developer-id,app-store}.*` (precedence CLI > lane > flat > env; `build.py:436-905`). |
| `linux.categories` | `:1474` | String or list → freedesktop `Categories` (escaped, default `Utility`); CLI `--linux-categories`. Invalid type → exit 1. |
| `web.{base_url,renderer,route_url_strategy,cdn,wasm,pwa_background_color,pwa_theme_color}` | `:994,:1488,:1499,:1505,:1514,:1518,:1522,:2799` | base_url normalized `/x/`; renderer default `canvaskit` (auto avoided: dart2wasm typed-data tax); route default `path`; `cdn=false` / `--no-cdn` bundles CanvasKit+Pyodide+fonts (CDN mode prunes `canvaskit/` ~37 MB post-copy, `:3153`); `wasm=false` / `--no-wasm` drops `--wasm` target; pwa_background falls through to splash color. Envs: `FLET_WEB_{RENDERER,ROUTE_URL_STRATEGY,NO_CDN}`. |
| `flutter.{build_args,pubspec}` (+ `<platform>.flutter.build_args`) | `build.py:209`, `build_base.py:1919,3002` | build_args appended verbatim (str or nested lists); pubspec deep-merged with per-dependency replace (path-vs-git can't merge) over rendered `pubspec.yaml`. CLI `--flutter-build-args`. |
| `flutter.dependencies` — does NOT exist | `:2527` | Platform deps key is `<platform>.dependencies` (e.g. `tool.flet.android.dependencies`), NOT `flutter.dependencies`. |
| `template.{url,ref,dir}` | `:1785,:1789,:1822` | Custom Flutter bootstrap: git URL / local path, checkout ref, subdir. CLI `--template/--template-ref/--template-dir`. |
| `boot_screen` (+ `<platform>.boot_screen`) | `:1716-1760` | `{name="flet", <name>={options}}` → template as `name` + base64 `options_b64`. Docstring ALSO claims legacy `[tool.flet[.<platform>].app.boot_screen]` / `app.startup_screen` fallback — **not implemented in code** (only `boot_screen` merged). |
| `org/product/...` per-platform | `:1012,:1550,:1553` | Only `artifact/org/bundle_id` (plus `target_arch/app.exclude/source_packages/dev_packages/dependencies/cleanup.*/compile.*/flutter.build_args`) accept `<platform>` scoping. `product/company/copyright` are global-only. |

Android pipeline detail (template merge → manifest → signing → ABI splits): `setup_template_data` builds the cookiecutter context above (incl. `options.{android_permissions,android_features,android_meta_data,android_gradle_properties,android_proguard_rules,android_providers,android_excluded_abis,android_signing,deep_linking}`); `create_flutter_project` renders the Gradle/AndroidManifest template; `package_python_app` runs `dart run serious_python:main package …` (env `SERIOUS_PYTHON_*`); `run_flutter` = `flutter build apk|appbundle [--split-per-abi] [--target-platform android-arm64,...]` with `FLET_ANDROID_SIGNING_*` env; `copy_build_output` harvests `build/app/outputs/{flutter-apk/*,bundle/release/*}` → `build/{apk,aab}/`, renames to `<artifact>.*`. Prior-run outputs inside the Flutter project are wiped first (`build.py:229-243`) so changed `--arch`/names don't leak stale artifacts. Web output additionally prunes `canvaskit/` (CDN mode) and overlays `assets/` (`:3140-3144`).

Asset handling: icons — chain `assets/icon_<platform>.*` → `assets/icon.*` (raster only; `.svg` warned+skipped, `.icns` non-macOS / `.ico` non-Windows filtered; `.png` > `.webp` > `.jpg` > …; `build_base.py:3355-3440`), non-square warned+centered, rendered via `flet_platform_assets.render_icons` into template-declared targets only (android+linux created fresh, rest `declared_only`), stamp `build/.hash/icons` (+`ICONS_GENERATOR_VERSION=1`), orig backup `build/.icons-orig`. Splash — chain `splash[_<platform>]` → `splash` → `icon` → template `images/icon.png`, optional `splash_dark[_<platform>]`, `render_splash` + iOS storyboard patch, stamp `build/.hash/splashes` (`SPLASH_GENERATOR_VERSION=3`). Missing source → keep template placeholders (icons) / transparent 1x1 drawables (Android splash).

`cleanup`/`app_files` logic: `package_python_app` (`:2469-2798`) hashes every package arg (`HashStamp(build/.hash/package)`); unchanged hash → `--skip-site-packages` (keeps prior `build/flutter-packages`, skips site-packages reinstall); `dev_packages` hit appends `--no-cache-dir` and forces full repack. `--exclude` (incl. `build`, +`assets` on web) drops inputs; `--compile-app/--compile-packages` emit `.pyc`; `--cleanup-app/--cleanup-packages` + file globs forwarded to serious_python. `app_files` string-or-list, comma-split supported.

Programmatic APIs: `flet_cli.cli.{get_parser,parse_command_line,main}`; `commands.base.BaseCommand.register_to`; `commands.flutter_base.BaseFlutterCommand.{initialize_command,install_flutter/install_jdk/install_android_sdk,run,cleanup,run_flutter_doctor,update_status}`; `commands.build_base.BaseBuildCommand.*` (all pipeline methods + `get_bool_setting/resolve_no_cdn/build_wasm/escape_*`); `commands.test.provision_test_host`; `utils.{pyproject_toml.load_pyproject_toml, python_versions.resolve_python_version/get_supported_python_versions, template_cache.get_cache_root/get_cached_template_zip, hash_stamp.HashStamp, merge.merge_dict, plist.*, cli.*, processes.run, android.*, android_sdk.AndroidSDK, jdk.install_jdk, ios_sign.*, macos_sign.*}`.

---

## App usage & correctness

App: `<repo>` — `pyproject.toml [tool.flet]` (lines 33-108), `.github/workflows/build-all.yml` (4 build jobs), `tools/{admob,make_icons}.py`, `src/assets/{icon.png,icon_android.png,icon.svg,icon_white.svg}`.

**(a) Correct config (verified):** `org/product/company/build_number/icon_background` globals; `[tool.flet.app] path="src"` (entry `src/main.py` resolves); `[tool.flet.splash] color/dark_color`; `[tool.flet.android] bundle_id/target_arch/adaptive_icon_background`; `[tool.flet.android.meta_data]` AdMob APPLICATION_ID; `[tool.flet.android.permission]` singular key with bool values (+INTERNET default merge); `[tool.flet.android.feature]` singular; `[tool.flet.android.signing] key_store/key_alias` + CI `$FLET_ANDROID_SIGNING_*` secrets (passwords correctly NOT in pyproject); `[tool.flet.android.gradle_properties]` jvmargs override (8G→4G for 7 GB runners); `[tool.flet.cleanup] app_files` list (implies `cleanup.app`); CI `flet build {apk --split-per-abi,aab,windows,linux} --yes --project/--product/--org/--company/--build-version/--build-number -v` flags all valid; `FLET_CLI_NO_RICH_OUTPUT=1` + Temurin JDK 17 setup + `PIP_FIND_LINKS` wheels pre-build all match flet-cli expectations; `icon_android.png` correctly matches the `icon_android.*` lookup.

**(b) MISUSE — keys flet-cli ignores or handles differently (file:line):**

1. `[tool.flet.app.boot_screen] startup_message` (`pyproject.toml:43-44`) — **ignored**. `_resolve_boot_screen` (`build_base.py:1746`) merges ONLY `tool.flet.boot_screen` + `tool.flet.<platform>.boot_screen`; `app.boot_screen` is never read (the "legacy fallback" in the docstring `:1724-1725` has no code). Fix: use `[tool.flet.boot_screen]` with `{name="flet", flet={...}}` shape.
2. `[tool.flet.android] min_sdk_version = 24` (`pyproject.toml:58`) — **ignored**. Zero `min_sdk` hits in `flet_cli`; the template hardcodes minSdk. Remove or carry via custom `--template`.
3. `[tool.flet.android.manifest_application] usesCleartextTraffic` (`pyproject.toml:61-63`) — **ignored**. Zero `manifest_application` hits; manifest merge keys are only `permission/feature/meta_data/provider` (`build_base.py:1181-1266`). Needs a custom template or post-build manifest patch.
4. `[tool.flet.deep_linking] scheme/host` (`pyproject.toml:50-52`) — **not applied to Android builds**. `build_base.py:1345-1363` reads ONLY `tool.flet.android.deep_linking.*` when `package_platform=="Android"` (global is desktop/web-only). Fix: duplicate as `[tool.flet.android.deep_linking] scheme/host` (and `ios` variant when iOS ships).
5. `[tool.flet.android.signing] key_store = "../../../../kiri_keystore.jks"` (`pyproject.toml:87`) — fragile: consumed raw into `FLET_ANDROID_SIGNING_KEY_STORE` (`build_base.py:2970-2976`) with no repo-root resolution, and CI overrides it with an absolute env path anyway. Keep the env path as the single source; drop the relative pyproject value (or make it absolute/host-local).
6. `[tool.flet.cleanup] app = true` (`pyproject.toml:99`) — redundant: non-empty `app_files` forces `cleanup_app=True` (`build_base.py:2679-2695`). Harmless; keep for readability or drop.
7. `target_arch = ["arm64-v8a", "x86_64"]` (`pyproject.toml:56`) — valid values, but `x86_64` is an emulator ABI: with `--split-per-abi` it ships an extra emulator-only APK and widens the AAB. For device/Play releases prefer `["arm64-v8a"]` (+`armeabi-v7a` only if old devices matter); keep `x86_64` for emulator QA builds. (Empty would default to the bundled Python's `android_abis`, `:1405-1407`.)
8. `icon.svg` / `icon_white.svg` in `src/assets` — **never used for launcher icons**: `find_platform_image` (`build_base.py:3388-3394`) drops `.svg` with a warning. Only `icon.png` (+`icon_android.png` for the adaptive foreground) drive icons/splash. Keep SVGs for in-app use only.

**(c) Correct-by-absence:** no `flutter.dependencies` key (correct — the real key is `<platform>.dependencies`); passwords kept in CI secrets (correct — no pyproject key exists); `project.version`/`project.requires-python` used instead of poetry keys (correct — `requires-python = ">=3.14"` resolves via manifest, no `--python-version` needed while 3.14 is the stable default row).

---

## Underused config to adopt

Highest value first (all verified keys/flags; nothing here requires a flet-cli upgrade):

1. **`[tool.flet.android] split_per_abi = true`** (`build_base.py:1033`) — move `--split-per-abi` from the CI command into pyproject so every `flet build apk` (local or CI) splits; CLI flag stays as override.
2. **Cross-platform `permissions = ["camera", "microphone"]`** (`build_base.py:1107`, groups `:250-283`) — app hand-declares `CAMERA`/`RECORD_AUDIO` as raw Android perms only. The groups additionally stamp iOS `NSCameraUsageDescription`/`NSMicrophoneUsageDescription` + macOS entitlements, i.e. the iOS build stays permission-correct for free. Keep the raw `INTERNET/ACCESS_NETWORK_STATE/WAKE_LOCK/MODIFY_AUDIO_SETTINGS` entries (no group covers them).
3. **`[tool.flet.android] extract_packages`** (`:2652`) — `av`/`httpx` native deps are the classic zipimport-`__file__` breakage class (`ANDROID_DEFAULT_EXTRACT_PACKAGES` is empty — no auto-cover). If the release APK ever shows `FileNotFoundError` from inside a dependency, list it here (or `--android-extract-packages`) instead of debugging the zip.
4. **`[tool.flet.android] proguard_rules`** (`:1191`) — app ships `flet-video` (media_kit/pyjnius reach into AARs by name); one `-keep` line here survives R8 where the defaults don't cover a new class. `proguard_default_rules = false` is the escape hatch, not the default.
5. **`cleanup.package_files` + `cleanup.packages` globs** (`:2675,:2697`) — `cleanup.packages` already defaults True, but no package globs are set; strip `*.so` debug symbols/tests and per-platform test fixtures to shrink the APK/AAB.
6. **`[tool.flet.<platform>.app.exclude]` / `--exclude`** (`:2621`) — distinct from cleanup: `ui-spike/`, `src/ui-spike`, `spike.py`, `deps-tree.txt` are currently stripped POST-compile via `cleanup.app_files`; `exclude` drops them from the package input entirely (faster hash, smaller staging). Use both: exclude for never-ship inputs, cleanup for post-compile stripping.
7. **Web keys for the docs site build**: `base_url`, `renderer`, `route_url_strategy`, `cdn`, `wasm`, `pwa_{background,theme}_color` (`:994-1522`) + `flet publish` (static Pyodide) / `flet build web` + `flet serve` — none configured; adopt when the marketing/docs PWA ships (note `pwa_background_color` already falls through to the white splash — set explicitly to `#0f1114` for dark installs).
8. **Per-platform `artifact/org/bundle_id/target_arch`** (`:1012,:1371,:1550`) — adopt `<platform>.artifact` (e.g. `ffmpeg` vs `FFmpeg`) so Windows/Linux installer scripts stop renaming outputs by hand; scope `target_arch` per platform instead of globally.
9. **`flutter.build_args` / `flutter.pubspec`** (`build.py:209`, `build_base.py:1919`) — passthrough for `--dart-define`, release flags, and extra Dart deps without forking the template.
10. **`compile.app/compile.packages`, `source_packages`, `dev_packages`** (`:2535,:2634,:2664`) — pin local-path overrides for patched deps (`dev_packages` implies `--no-cache-dir`, defeating the package hash — use deliberately); `source_packages` for ABI-sensitive sdists like `av`.
11. **Diagnostics loop**: `flet doctor` as a CI pre-step, `flet devices`/`flet emulators` for on-device QA, `flet debug --release` for release-mode device runs, `flet test` (`provision_test_host`) for on-device integration tests, `--skip-flutter-doctor` for fast-fail CI, `flet clean` before version-switch builds (the `.python-version` marker at `:905-915` already force-cleans on interpreter switch; keep `build/` cached between same-version CI runs to hit the `template/package/icons/splashes` hash stamps).
12. **Deep-link + splash validation**: after (b.4), assert the merged manifest/associated-domains in CI; set per-platform `[tool.flet.<platform>.splash]` + `icon_background` per platform (currently one global white/dark pair); `macos.icon_style` + macOS signing lanes (`distributionлям identity/notary_profile/provisioning_profile/installer_identity`, `build.py:383-905`) the moment a macOS target is added; `build_number` auto-bump per CI run (already parameterized — keep).

---

## Gotchas

- **Silent-ignore config**: only `macos.signing.*` lane typos fail loudly (`build.py:415-434`); every other unknown/misspelled `[tool.flet]` key (including b.1–b.3 above) builds fine and does nothing. There is no `--strict-config`.
- **Deep-linking is platform-gated, not merged** (`build_base.py:1345-1367`): global applies to desktop/web only; Android/iOS each need their own subtable. CLI requires BOTH `--deep-linking-scheme` AND `--deep-linking-host`.
- **Android passwords are env/CLI-only** (`build_base.py:2978-2991`): `key_store_password`/`key_password` have no pyproject key; either env var fills both slots when only one is set. Never commit them; the AdMob guard pattern in `build-all.yml:46-56` is the right shape for `swap-ids`-style secret hygiene.
- **`app_files` implies `cleanup.app`, `package_files` implies `cleanup.packages`** (`:2679-2717`); `cleanup.packages` defaults True while `cleanup.app` defaults False.
- **`exclude` ≠ `cleanup`**: exclude keeps files out of the package input; cleanup strips post-compile outputs. `build` is always excluded; `assets/` is excluded from the Python zip on web only (copied to output root instead, `:2629-2631,3140-3144`).
- **Bytecode/Python coupling**: `build/.python-version` (`:905-915`) force-wipes `build/` on interpreter switch (stale `.pyc` = `bad magic number`); the `package` hash otherwise enables `--skip-site-packages` fast rebuilds — don't `flet clean` unconditionally in CI or every build repacks from scratch.
- **`flutter build ipa` exits 0 on export failure** (`build_base.py:3029-3055`): flet detects the missing `.ipa` itself and fails; unsigned builds intentionally yield only `.xcarchive` (`build.py:271-287`). iOS preflight (profile name/UUID, expiry, team, bundle-id) runs BEFORE the long build (`build.py:289-375`) — configure the profile early.
- **macOS `none` lane takes no settings** (`build.py:415-434`): a `[tool.flet.macos.signing.none]` subtable is a hard error; shared values go flat. Ad-hoc (`-`) identity is rejected for `developer-id`/`app-store` lanes.
- **Gradle memory default OOMs 7 GB runners** (`:1075-1081`): `org.gradle.jvmargs=-Xmx8G` is baked in; the app's 4G override is load-bearing, keep it.
- **`.svg` icons are decorative only** (`:3388-3433`); non-square rasters warn and get centered; Android adaptive background is a color resource, not pixels.
- **Template re-render restores placeholder icons** — the `template_digest` → icon/splash stamp chain (`:1828-1833`) handles it, but custom `--template` forks must keep `images/icon.png` + Android `drawable/splash.png` or resource linking fails (`:2360-2368`).
- **Windows duplex**: `flet build windows` (Flutter pipeline) vs `flet pack` (PyInstaller onefile/onedir) are different artifacts with different flag sets; the release workflow uses the former + Inno Setup. `--onedir/--uac-admin` are `pack`-only and rejected on macOS.
- **`run` is the default subcommand** and `--` forwarding is `run`-only (`cli.py`); `devices/emulators` force Android-SDK install prompts — always pass `--yes` in CI.
- **Cache roots**: `$FLET_CACHE_DIR` (else `~/.flet/cache`) holds build-template zips, python-build manifests, and Pyodide runtimes; `$FLET_VIEW_PATH` bypasses the client download for `pack`; `~/flutter/<version>` is the SDK home (arm64 Linux clones+precaches from git instead of a prebuilt archive).
