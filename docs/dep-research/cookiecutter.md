# cookiecutter 2.7.1 — Complete API Reference

> Project scaffolding engine. **Not imported by app source at all** — its consumer is `flet-cli`, which calls `cookiecutter.main.cookiecutter()` twice: once in `flet create` (renders the app scaffold) and once per `flet build` (renders the Flutter/Android bootstrap from `flet-build-template.zip` + `[tool.flet]` keys). This makes cookiecutter the mechanism behind the most build-critical correctness fact in this repo: **wrong `[tool.flet]` keys are silently dropped** (extra context keys with no matching `{{ cookiecutter.* }}` placeholder render nothing and raise nothing).
>
> Version 2.7.1 · Requires-Python `>=3.10` · License: BSD (LICENSE + AUTHORS.md in dist-info `licenses/`) · Console script: `cookiecutter = cookiecutter.__main__:main` · Verified against installed source in `.venv/Lib/site-packages/cookiecutter/` (17 `.py` files, no subpackages).

## Files

All 17 modules (flat layout, no subpackages):

| File | Role |
|---|---|
| `__init__.py` | `__version__` only (via `importlib.metadata.version("cookiecutter")`) |
| `__main__.py` | `python -m cookiecutter` → `cookiecutter.cli.main(prog_name="cookiecutter")` |
| `main.py` | `cookiecutter()` top-level orchestration function |
| `cli.py` | Click CLI (`main` command, all flags) |
| `config.py` | `~/.cookiecutterrc` / `COOKIECUTTER_CONFIG` config system |
| `prompt.py` | Interactive prompting (rich-based), Jinja-in-`cookiecutter.json` rendering, choice/bool/dict readers |
| `generate.py` | `generate_context()` + `generate_files()` + `generate_file()` — render engine |
| `repository.py` | `determine_repo_dir()` — template source resolution (local / git / hg / zip) |
| `vcs.py` | `clone()` — git/hg clone + checkout pinning |
| `zipfile.py` | `unzip()` — zip template download/extract (password-protected supported) |
| `hooks.py` | `pre_prompt` / `pre_gen_project` / `post_gen_project` hook lifecycle |
| `environment.py` | `StrictEnvironment` (StrictUndefined + default extensions) |
| `extensions.py` | 5 built-in Jinja extensions (Jsonify, RandomString, Slugify, UUID, Time/arrow) |
| `replay.py` | `dump()` / `load()` — replay JSON files in `~/.cookiecutter_replay/` |
| `find.py` | `find_template()` — locates `{{cookiecutter.*}}` dir inside repo |
| `utils.py` | `rmtree`, `work_in`, `make_sure_path_exists`, `create_env_with_context`, `create_tmp_repo_dir` |
| `log.py` | `configure_logger()` (stdout INFO/DEBUG + optional `--debug-file`) |
| `exceptions.py` | 17-exception hierarchy (all subclass `CookiecutterException`) |

## Metadata (full Requires-Dist subgraph)

From `cookiecutter-2.7.1.dist-info/METADATA` — 8 direct deps (this documents the **entire subgraph** cookiecutter drags in; all are dev/build-time only for this app, none serve the Flet runtime):

```
Requires-Dist: binaryornot>=0.4.4
Requires-Dist: Jinja2<4.0.0,>=2.7
Requires-Dist: click<9.0.0,>=7.0
Requires-Dist: pyyaml>=5.3.1
Requires-Dist: python-slugify>=4.0.0
Requires-Dist: requests>=2.23.0
Requires-Dist: arrow
Requires-Dist: rich
```

As observed in `uv.lock`: `name = "cookiecutter"`, version `2.7.1`, sdist+wheel from PyPI (upload 2026-03-04). `flet-cli` lists `{ name = "cookiecutter" }` among its own deps — that edge is the only reason cookiecutter is in this venv. Nested transitive notes: `arrow` pulls dateutil/tzdata; `python-slugify` pulls `text-unidecode`; `rich` pulls pygments/markdown-it-py (shared with other packages in the lock); `Jinja2` pulls markupsafe; `requests` pulls urllib3/certifi/charset-normalizer/idna. `RECORD` confirms the wheel payload is exactly the 17 `.py` files above + `Scripts/cookiecutter.exe` + dist-info.

## Module-by-module API

### `main.cookiecutter()` — the one function that matters

```python
def cookiecutter(
    template: str,
    checkout: str | None = None,
    no_input: bool = False,
    extra_context: dict[str, Any] | None = None,
    replay: bool | str | None = None,
    overwrite_if_exists: bool = False,
    output_dir: str = '.',
    config_file: str | None = None,
    default_config: bool = False,
    password: str | None = None,
    directory: str | None = None,
    skip_if_file_exists: bool = False,
    accept_hooks: bool = True,
    keep_project_on_failure: bool = False,
) -> str:  # returns absolute path of generated project dir
```

Pipeline order (read from source): (1) reject `replay` + (`no_input`/`extra_context`) combos → `InvalidModeException`; (2) `get_user_config()`; (3) `determine_repo_dir()` (abbreviations → clone/unzip/local); (4) `run_pre_prompt_hook()` if `accept_hooks` (works on a **temp copy** of the repo, then switches `repo_dir` to it); (5) `_patch_import_path_for_repo` pushes `repo_dir` onto `sys.path` (so `cookiecutter.json` `_extensions` and hook modules import); (6) recursive escape hatch — if context contains `template`/`templates` keys, pick a nested template and **recurse**; (7) `prompt_for_config()` unless replay; (8) inject `_template`, `_output_dir`, `_repo_dir`, `_checkout` into context + snapshot `_cookiecutter` (non-underscore keys); (9) `dump()` replay file **always**; (10) `generate_files()`; (11) rmtree temp dirs. Example:

```python
from cookiecutter.main import cookiecutter

cookiecutter("gh:audreyfeldroy/cookiecutter-pypackage")  # interactive
cookiecutter(
    "cookiecutter-pypackage/",
    no_input=True,
    extra_context={"project_name": "x"},
    overwrite_if_exists=True,
)  # headless (flet-cli style)
```

### CLI (`cli.py`) — all flags

`cookiecutter [TEMPLATE] [EXTRA_CONTEXT... key=value]` plus: `--no-input`, `-c/--checkout`, `--directory` (subdirectory holding `cookiecutter.json` — exactly what flet-cli uses to pick the app template inside a multi-template repo), `-v/--verbose`, `--replay` (bool, mutually exclusive with `--no-input`/extra context), `--replay-file PATH`, `-f/--overwrite-if-exists`, `-s/--skip-if-file-exists`, `-o/--output-dir` (default `.`), `--config-file`, `--default-config`, `--debug-file`, `--accept-hooks {yes,ask,no}` (default `yes`; `ask` → `click.confirm("Do you want to execute hooks?")`), `-l/--list-installed` (works with no TEMPLATE arg), `--keep-project-on-failure`, `-V/--version`, `-h/--help`. Password comes from `COOKIECUTTER_REPO_PASSWORD` env. Top-level `try` maps `ContextDecodingException, OutputDirExistsException, EmptyDirNameException, InvalidModeException, FailedHookException, UnknownExtension, InvalidZipRepository, RepositoryNotFound, RepositoryCloneFailed` → message + `sys.exit(1)`; `UndefinedVariableInTemplate` additionally prints the full sorted context JSON.

### Config (`config.py`)

`DEFAULT_CONFIG = {'cookiecutters_dir': '~/.cookiecutters/', 'replay_dir': '~/.cookiecutter_replay/', 'default_context': OrderedDict([]), 'abbreviations': {'gh': 'https://github.com/{0}.git', 'gl': '…gitlab…', 'bb': '…bitbucket…'}}`. `get_user_config(config_file=None, default_config=False)`: `default_config=True` → defaults only; dict → merged over defaults; explicit `config_file` → `get_config()` (YAML, recursive `merge_configs`, expands env vars + `~` in both dirs; raises `ConfigDoesNotExistException` / `InvalidConfiguration`); else `COOKIECUTTER_CONFIG` env (missing path **raises**); else `~/.cookiecutterrc` if present, else defaults. Helpers: `merge_configs()` (deep dict merge preserving e.g. extra abbreviations), `_expand_path()`, `get_config()`.

### Prompt (`prompt.py`)

Two-pass `prompt_for_config(context, no_input=False)`: pass 1 scalars/choices/bools, pass 2 dicts; keys starting `_` (single) pass through unrendered, `__`-prefixed render without prompting, `__prompts__` pops out as human-readable labels. Per-key types: list → numbered `read_user_choice` (first item is the `no_input` default); bool → `YesNoPrompt` (`1/true/t/yes/y/on` vs `0/false/f/no/n/off`); dict → `JsonPrompt` (must decode to a JSON object); else `read_user_variable` with the Jinja-rendered default. `render_variable()` recursively renders defaults against the gradually-populated context — this is the "Jinja-in-JSON" feature (`{{ cookiecutter.project_name.replace(' ', '_') }}` as a later default). `choose_nested_template()` supports new-style `templates: {key: {path, title, description}}` and old-style `template: ["label (path)"]` (regex-extracts `(path)`, rejects absolute paths). `prompt_and_delete()` governs cached clone/zip reuse (`no_input=True` = always re-download). Raises `UndefinedVariableInTemplate` (carries `.message`, `.error`, `.context`) on render failure.

### Generate (`generate.py`)

`generate_context(context_file='cookiecutter.json', default_context=None, extra_context=None)` — JSON-decodes (→ `ContextDecodingException`), keys under file stem, applies user defaults then overrides via `apply_overwrites_to_context()` (choice vars: extra value must be a member — invalid choice raises `ValueError`; for a plain choice the override is moved to list position 0 = new default; bools accept yes/no strings). `generate_files(repo_dir, context=None, output_dir='.', overwrite_if_exists=False, skip_if_file_exists=False, accept_hooks=True, keep_project_on_failure=False) -> str`: `find_template()` requires exactly one child dir containing `cookiecutter` + Jinja delimiters (else `NonTemplatedInputDirException`); renders the project dir name; runs `pre_gen_project` hook; walks the template with Jinja loader `['.', '../templates']`; per-file `generate_file()` copies binaries untouched (`binaryornot.is_binary`), renders text, preserves detected newlines (or `_new_lines` context override) and file modes (`shutil.copymode`); `_copy_without_render` context key + `is_copy_only_path()` (fnmatch) exempts paths; runs `post_gen_project` hook. On hook failure the project dir is deleted unless it pre-existed or `keep_project_on_failure=True` (deprecated alias `_run_hook_from_repo_dir` still present).

### VCS (`vcs.py`) + repository (`repository.py`) + zipfile (`zipfile.py`)

`identify_repo()` — `git+`/`hg+` prefix wins; else `git` substring → git, `bitbucket` substring → hg, else `UnknownRepoType`. `clone(repo_url, checkout=None, clone_to_dir='.', no_input=False)` — `shutil.which` gate (→ `VCSNotInstalled`), `git clone` + `git checkout <ref>` in one flow (hg gets `--` injection guard), maps "not found" → `RepositoryNotFound`, bad ref (`error: pathspec`/`unknown revision`) → `RepositoryCloneFailed`, cached dir → `prompt_and_delete` round-trip. `determine_repo_dir(template, abbreviations, clone_to_dir, checkout, no_input, password=None, directory=None) -> tuple[str, bool]` — expand `gh:`/`gl:`/`bb:` → zip? (`unzip`, cleanup=True) → URL? (`clone`, cleanup=False) → local path or `<clone_to_dir>/<template>`; appends `directory` to candidates when set; requires `cookiecutter.json` (→ `RepositoryNotFound` listing every candidate). `unzip()` caches URL zips in `clone_to_dir`, requires non-empty archive with a top-level directory (else `InvalidZipRepository`), unpacks to a fresh `tempfile.mkdtemp()`, handles password-protected zips via `password` param then interactive retry (3 attempts; `no_input` → immediate `InvalidZipRepository`).

### Hooks (`hooks.py`), environment/extensions, replay, find, utils, log, exceptions

Hooks: `_HOOKS = ['pre_prompt', 'pre_gen_project', 'post_gen_project']`; `find_hook()` matches basename sans extension (excludes `~` backups; any extension — `.py` runs under `sys.executable`, else executed directly, with `shell=True` on Windows); scripts are **Jinja-rendered with full context to a temp file** before execution (`run_script_with_context`); non-zero exit → `FailedHookException` (`ENOEXEC` → "empty file or missing shebang" hint); `run_pre_prompt_hook()` copies the repo to a temp dir so pre-prompt mutations never touch the cache. `StrictEnvironment` = `StrictUndefined` + always-on Jsonify/RandomString/Slugify/UUID/Time extensions + any `_extensions` from context (import failure → `UnknownExtension`); `create_env_with_context()` additionally forwards `_jinja2_env_vars` (e.g. custom delimiters) into the env constructor. Time tags: `{% now 'UTC' %}`, `{% now 'UTC' - 'days=2' %}` via arrow. Replay: `dump()`/`load()` JSON to `~/.cookiecutter_replay/<template>.json` (auto-created; always written even on interactive runs). `find_template()`, `work_in()` (chdir ctx manager), `create_tmp_repo_dir()`, `make_executable()`, `simple_filter()` (one-function Jinja filter decorator for templates). `configure_logger(stream_level='DEBUG'|'INFO', debug_file=None)`. Exceptions (17, all `CookiecutterException` subclasses): `NonTemplatedInputDirException`, `UnknownTemplateDirException`, `MissingProjectDir`, `ConfigDoesNotExistException`, `InvalidConfiguration`, `UnknownRepoType`, `VCSNotInstalled`, `ContextDecodingException`, `OutputDirExistsException`, `EmptyDirNameException`, `InvalidModeException`, `FailedHookException`, `UndefinedVariableInTemplate` (structured: `.message/.error/.context`), `UnknownExtension`, `RepositoryNotFound`, `RepositoryCloneFailed`, `InvalidZipRepository`.

## App usage & correctness

Grep result: **zero hits in app source** (`pyproject.toml` / `src/` untouched by cookiecutter). The chain is entirely through `flet-cli` (verified call sites in installed `flet_cli`):

1. `flet_cli/commands/create.py::render_and_generate_new_project` — `from cookiecutter.main import cookiecutter; cookiecutter(template_url, checkout=None, directory=options.template, output_dir=…, no_input=True, overwrite_if_exists=True, extra_context=template_data)` where `template_data` = `{template_name, flet_version, sep, platform, out_dir, project_name (slugified), description?}`. Local path when running flet from source, else the versioned `DEFAULT_APP_TEMPLATE_URL` zip.
2. `flet_cli/commands/build_base.py::create_flutter_project` — the build-critical one. Renders the Flutter bootstrap from `templates/build` (or cached `flet-build-template.zip` via `get_cached_template_zip`) with `no_input=True, overwrite_if_exists=True, extra_context={k: v for … template_data if v is not None}`, guarded by a `HashStamp` (`build/<…>/.hash/template-1`) so re-render only happens on input change; failures `rmtree` the flutter dir. `template_data` is assembled from `[tool.flet]` keys (boot-screen merge helper `name` + base64 `options_b64`, icons, splash, permissions, gradle properties…).

What this means for this app: the Android/Flutter bootstrap is cookiecutter-rendered, and cookiecutter's contract is **unknown context keys are inert** — extra keys render nothing, and `StrictUndefined` only fires on variables the template *references*, never on context keys the template *ignores*. So the flet-cli finding stands on a cookiecutter mechanism: `min_sdk_version`, `usesCleartextTraffic`, `app.boot_screen.startup_message`-style keys that don't match the template's `{{ cookiecutter.* }}` placeholders are silently dropped with exit 0. Build-correctness checks must therefore be done at the `[tool.flet]` layer (diff keys against the template's placeholders / flet-cli's `template_data` assembly), never by trusting "cookiecutter ran clean". Related behaviors that bite: `overwrite_if_exists=True` means a changed template hash **restores placeholder assets over generated ones** (flet-cli compensates with `template_digest` hand-off to icon/splash stamps); `no_input=True` forces first-choice defaults and re-download of cached zips on version bumps; `~/.cookiecutters` / `~/.cookiecutter_replay` caches persist across builds (stale-template debugging starts there); non-UTF8 or comment-containing `cookiecutter.json` fails hard (`ContextDecodingException` — JSON, not YAML). Weight note: the whole 8-package subgraph (jinja2, click, arrow, rich, requests, pyyaml, binaryornot, python-slugify + their transitives) is **dev/build-only via flet-cli** — it ships nothing into the Flutter APK and serves nothing at app runtime; do not trim it without breaking `flet create`/`flet build`.

## Underused APIs to adopt

For v1 (all headless-safe patterns, mirroring exactly how flet-cli already calls it):

- **Scaffold the 17 screen/test boilerplate**: ship a local template dir (`tools/templates/screen/{{cookiecutter.slug}}/…`) and call `cookiecutter(template=<path>, no_input=True, extra_context={…}, overwrite_if_exists=False, skip_if_file_exists=True, output_dir='src')`. `skip_if_file_exists` makes re-runs additive — the safe generator default.
- **`directory=` for a monorepo of generators**: one `tools/templates/` repo holding `screen/`, `release-notes/`, `screen-test/` sub-templates selected per invocation — same mechanism flet-cli uses for multi-template repos.
- **Replay files as the spec**: every run auto-writes `~/.cookiecutter_replay/<name>.json`; check a `replay/` dir of golden JSONs into the repo so `cookiecutter(…, replay='replay/screen.json')` deterministically regenerates fixtures in CI (note the constraint: replay forbids `no_input`/`extra_context` in the same call).
- **`_copy_without_render` + `_extensions` + `_jinja2_env_vars` context keys**: binary fixtures copy verbatim; `slugify`/`uuid4`/`random_ascii_string`/`jsonify`/`{% now %}` generate identifiers client-side instead of in Python glue.
- **Hooks for post-scaffold wiring**: `post_gen_project.py` (rendered with context) to append export lines / register routes — gated by `accept_hooks` and debuggable with `keep_project_on_failure=True` in `tools/` runs.
- **Config pinning**: `config_file='tools/cookiecutter.yaml'` (custom abbreviations, frozen `default_context`) instead of ambient `~/.cookiecutterrc`, so scaffolds are machine-independent.

## Gotchas

1. Silent key drops (the big one): extra context keys never error — verify `[tool.flet]` keys against the template, not the exit code.
2. `no_input=True` = first list item wins + cached zips re-downloaded; `replay` is exclusive with `no_input`/`extra_context` (`InvalidModeException`).
3. `overwrite_if_exists=True` restores placeholders over generated assets on re-render — never point it at a dir containing hand edits without `skip_if_file_exists`.
4. `StrictUndefined` raises only on referenced-but-missing variables (`UndefinedVariableInTemplate` carries the full context — good for `--verbose` debugging, but it also means a typo'd `{{ cookiecutter.* }}` fails the whole build, not just one file).
5. `find_template` needs exactly one `{{cookiecutter.*}}`-named dir; `cookiecutter.json` must be strict JSON (no comments/trailing commas).
6. Hooks execute arbitrary code from the template (rendered first, shell on Windows) — only render trusted templates; `--accept-hooks ask/no` exists for that.
7. Caches live outside the repo (`~/.cookiecutters`, `~/.cookiecutter_replay`) — "works on my machine" staleness hides there; `prompt_and_delete` re-download prompts hang headless runs unless `no_input=True`.
8. `identify_repo` sniffs the URL string (`'git' in url` → git) and hg needs `hg+`; `unzip` demands a top-level directory in the archive.
9. Pre-prompt hooks run on a temp copy; `sys.path` gets the repo dir appended during render (template `_extensions` import from there).
10. Binary detection is heuristic (`binaryornot`) — ambiguous text files with odd encodings can copy unrendered; non-UTF8 template files fail at render.
