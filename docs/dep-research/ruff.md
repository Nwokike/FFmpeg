# ruff 0.16.8 — Complete Reference

Linter + formatter for the v1.0 lint gate. Rust binary shipped as a Python wheel;
the `.py` files are only a binary-locator shim. 970 rules total; the app selects
380 of them across 12 families.

## Files

Package dir `<repo>\.venv\Lib\site-packages\ruff`
contains exactly 3 Python files — no lint logic in Python, everything is the compiled binary:

- `__init__.py` — re-exports `find_ruff_bin` only (`__all__ = ["find_ruff_bin"]`).
- `_find_ruff.py` — locates `ruff.exe` by probing (in order): `sysconfig` scripts dir,
  base-prefix scripts dir, `<venv>/Scripts` derived from the module path
  (`Lib/site-packages/ruff` → parent + `Scripts` on win32), `bin/` next to the
  package root (pip `--target` layout), user-scheme scripts dir. Raises
  `RuffNotFound` listing searched locations.
- `__main__.py` — `python -m ruff ...` shim: `subprocess.run([ruff, *argv])` on
  win32 (exit 2 on KeyboardInterrupt), `os.execvp` elsewhere.

Binary: `<repo>\.venv\Scripts\ruff.exe`
(26,408,448 bytes, win_amd64, maturin 1.14.1 build). Dist-info RECORD confirms the
wheel ships only the exe + 3 shims + METADATA/LICENSE/sbom.

## Metadata

From `ruff-0.16.8.dist-info/METADATA` (+ WHEEL/INSTALLER/RECORD):

- Version `0.16.8`, summary "An extremely fast Python linter and code formatter,
  written in Rust.", home `https://docs.astral.sh/ruff`, repo
  `https://github.com/astral-sh/ruff` (Astral, backed; powers Airflow/FastAPI/Pandas).
- License: MIT (`License-Expression: MIT`, `licenses/LICENSE`). Requires-Python `>=3.7`.
- Entry points: **none** — `importlib.metadata` reports zero entry points; the console
  interface is the `ruff.exe` launcher only (`python -m ruff` via the shim).
  No importable API: `import ruff` exposes just `find_ruff_bin`.
- Installer: `uv`. Default config baked in: `line-length = 88`, `indent-width = 4`,
  `target-version = "py310"`, `fixable = ["ALL"]`, quote-style double, indent spaces,
  magic-trailing-comma respected, `line-ending = "auto"`.
- Rule status model: every rule carries `fix` availability (`Always` 250 /
  `Sometimes` 229 / none 491 of 970) and stability (`Stable since …` vs preview).

## CLI commands & flags

`ruff --help` top level: `check | rule | config | linter | clean | format | server |
analyze | version | help`, plus `-v/-q/-s` logging, `--color auto|always|never`,
`--config <path|KEY=VALUE>` (overrides all config files), `--isolated`.

- `ruff check [FILES]` (default `.`; `-` = stdin). Selection:
  `--select/--ignore/--extend-select`, `--per-file-ignores/--extend-per-file-ignores`,
  `--fixable/--unfixable/--extend-fixable`, `--target-version
  py37…py315`, `--preview`, `--extension ext:lang`. Fix control: `--fix`,
  `--unsafe-fixes`, `--show-fixes`, `--diff` (implies `--fix-only`), `--fix-only`,
  `--exit-non-zero-on-fix`. Reporting: `--output-format
  concise|full|json|json-lines|junit|grouped|github|gitlab|pylint|rdjson|azure|sarif`
  (+ `RUFF_OUTPUT_FORMAT`), `-o/--output-file`, `--statistics` (per-rule hit counts),
  `--ignore-noqa`, `--add-noqa[=REASON]`, `--add-ignore[=REASON]` (preview: rule names
  instead of codes), `--show-files`, `--show-settings`, `-w/--watch`, `-e/--exit-zero`,
  `-n/--no-cache`, `--cache-dir`, `--stdin-filename`, `--exclude/--extend-exclude`,
  `--respect-gitignore/--force-exclude`.
- `ruff format [FILES]` — `--check` (exit 1 if anything would change),
  `--diff`, `--range <start:end>` (single file only), `--line-length`,
  `--target-version`, `--preview`, `--output-format` (with `--check`),
  `--exit-non-zero-on-format`, cache/exclude flags. NOTE: `format` takes NO
  `--select/--fix` flags — it is unconditional; opt-out is only via
  `[tool.ruff.format] exclude` or `# fmt: skip` / `# fmt: off…on` comments.
- `ruff rule <CODE> | --all [--output-format text|json]` — full prose explanation,
  example, fix availability per rule. `ruff config [KEY] [--output-format text|json]`
  documents every key with type/default/example — the offline settings reference.
- `ruff linter` — lists all 60+ upstream linter families and their codes
  (AIR ERA FAST YTT ANN ASYNC S BLE FBT B A COM C4 CPY DTZ T10 DJ EM EXE FIX FA INT
  ISC ICN LOG G INP PIE T20 PYI PT Q RSE RET SLF SIM SLOT TID TD TC ARG PTH FLY I C90
  NPY PD N PERF E/W DOC D F PGH PL UP FURB RUF TRY …).
- `ruff clean` (drop `.ruff_cache`), `ruff server [--preview]` (LSP),
  `ruff analyze graph [--direction dependencies|dependents] [--detect-string-imports]`
  (import map — handy for the services/screens layering audit), `ruff version`.

## Config keys

`ruff config` top level: `cache-dir, extend, output-format, output-prefer-rule-codes,
fix, unsafe-fixes, fix-only, show-fixes, required-version, preview, exclude,
extend-exclude, extend-include, force-exclude, include, respect-gitignore, extension,
builtins, namespace-packages, target-version, per-file-target-version, src,
line-length (default 88), indent-width (4), lint, format, analyze`.

`[tool.ruff.lint]` keys: `select, ignore, extend-select, extend-ignore (deprecated),
fixable (default ["ALL"]), unfixable, extend-fixable, extend-safe-fixes,
extend-unsafe-fixes, per-file-ignores, extend-per-file-ignores, exclude,
explicit-preview-rules, allowed-confusables, dummy-variable-rgx
(default `^(_+|(_+[a-zA-Z0-9_]*[a-zA-Z0-9]+?))$`), task-tags, logger-objects,
typing-modules, typing-extensions, external, preview, future-annotations`,
plus one sub-table per linter family (`flake8-annotations … isort, mccabe,
pep8-naming, pycodestyle, pydocstyle, pyflakes, pylint, pyupgrade, pydoclint, ruff`).

`[tool.ruff.format]` keys (all ruff-format does): `exclude, preview, indent-style
(default "space"), quote-style (default "double"), nested-string-quote-style,
skip-magic-trailing-comma (default false), line-ending (default "auto"),
docstring-code-format (default false), docstring-code-line-length`.

Selection semantics (verified via `ruff config lint.extend-select`):

- `select` **replaces** the default rule set; `extend-select` **adds** to active rules
  (defaults or `select`). More-specific prefixes beat less-specific ones on ties;
  `ignore` wins over `select` for the same prefix.
- `per-file-ignores = {"tests/**.py" = ["S101"]}` maps glob → codes; leading `!`
  negates the pattern; `extend-per-file-ignores` appends instead of replacing.
- `fix = true` in config turns on fixes for plain `ruff check` (CLI `--fix/--no-fix`
  still wins); without it, `--fix` runs are opt-in. `fixable = ["ALL"]` default means
  every safe fix applies; gate unsafe ones with `extend-unsafe-fixes` + `--unsafe-fixes`.
- `target-version`: explicit key beats `project.requires-python`; unset falls back to
  `requires-python` inference, else `py310`. Drives UP rewrites (e.g. `X | Y` unions,
  `except*`), PTH suggestions, and what `format` may emit. Here `requires-python =
  ">=3.14"` already infers `py314`, so the explicit `target-version = "py314"` is
  belt-and-braces, not load-bearing.
- noqa semantics: `# noqa: CODE` (comma list) suppresses a line; bare `# noqa`
  suppresses all; RUF100 (`unused-noqa`, fix Always, in the selected RUF family)
  flags stale directives so dead suppressions can't accumulate. `--ignore-noqa`
  re-lints from scratch; `--add-noqa` writes missing directives mechanically.
- Formatter vs checker interplay: the formatter owns style (quotes, wrapping,
  trailing commas); overlapping style rules must stay off — E501 is correctly
  ignored here. Known conflict class: `ISC001` (explicit string concat) fights the
  formatter and is rightly absent. `line-length = 100` steers both isort wrapping
  and `format`, but the formatter treats it as a preference, not a hard cap.

## Rule families

970 rules (`rule --all --output-format json`). Per-prefix counts:
A 6, AIR 13, ANN 11, ARG 5, ASYNC 16, B 43, BLE 1, C 20, COM 3, CPY 1, D 48, DJ 7,
DOC 7, DTZ 10, E 60, EM 3, ERA 1, EXE 5, F 43, FA 2, FAST 3, FBT 3, FIX 4, FLY 1,
FURB 36, G 8, I 2, ICN 3, INP 1, INT 3, ISC 4, LOG 7, N 16, NPY 4, PD 13, PERF 6,
PGH 5, PIE 8, PLC 16, PLE 38, PLR 33, PLW 29, PT 31, PTH 35, PYI 55, Q 5, RET 8,
RSE 1, RUF 79, S 73, SIM 30, SLF 1, SLOT 3, T 3, TC 9, TD 7, TID 5, TRY 10, UP 49,
W 7, YTT 10 (+1 codeless entry). The 12 selected families total 380 rules
(E 60, F 43, W 7, I 2, UP 49, B 43, SIM 30, PERF 6, RUF 79, ASYNC 16, PTH 35, TRY 10).

Notables in the selected set (spot-checked via `ruff rule`):

- E: E501 line-too-long (no fix — ignored here, formatter owns it); E731/E741 live here.
- F: F401 unused-import, F841 unused-variable (both Sometimes-fixable).
- W: W291/W293 trailing/blank-line whitespace (Always fixable).
- I: I001 unsorted-imports (Sometimes fixable — isort-compatible ordering).
- UP: UP035 deprecated-import, UP037 quoted-annotation (Always fixable); py314 target
  unlocks the newest rewrites.
- B: B006 mutable-default, B008 function-call-in-default (no fix — audit manually),
  B017 assert-raises-exception (suppressed once in tests, see below), B904/B905/B911.
- SIM: SIM102–SIM108 collapsible/if-expression rules (Sometimes fixable).
- PERF: PERF401 manual-list-comprehension (Sometimes fixable).
- RUF: RUF100 unused-noqa (Always fixable — keeps the 11 noqa honest).
- ASYNC: ASYNC210/212 blocking-http, ASYNC220–222 subprocess, ASYNC230 open,
  ASYNC240 blocking-path (no fix — all 9 src suppressions are this one),
  ASYNC250/251 input/sleep.
- PTH: PTH123 builtin-open et al. (Sometimes fixable → `Path.open`).
- TRY: TRY003 raise-vanilla-args + TRY300 return-in-try — both deliberately ignored
  (house style); TRY200 reraise-no-cause, TRY301–TRY400 active.

## App usage & correctness (actual check output)

Config — `pyproject.toml:114-136`: `[tool.ruff] line-length = 100`,
`target-version = "py314"`; `[tool.ruff.lint]` selects the 12 families above,
`ignore = ["E501", "TRY003", "TRY300"]` with the M3 comment (186 hits → 0).
All keys valid; no typos; `select` (replace-defaults) is intentional and complete.

CI — `.github/workflows/build-all.yml:40-43` (`quality` job, after `uv sync`):
`uv run ruff check src/ tests/` then `uv run ruff format --check src/ tests/`,
both must pass before `pytest -q`. The format gate **exists** — but the tree
currently fails it (below).

noqa inventory — 9× `ASYNC240` in `src/` (all "trivial stat/exists check"):
`src/screens/capture_screen.py:350,482`, `src/services/media_io.py:45,67,86,90,135,138`,
`src/screens/filters_screen.py:100`; plus `tests/conftest.py:64` (F401, engine-wheel
smoke import) and `tests/test_concat.py:112` (B017, broad `pytest.raises(Exception)`
probe). All carry reasons; all codes are in the selected families so RUF100 guards them.

Live runs from the app root (read-only, 2026-09-23):

- `.venv\Scripts\ruff.exe check src tests --statistics` → `All checks passed!`,
  exit 0, **0 findings** — no `--statistics` table printed (nothing to count).
  The M3 zero-hit state holds.
- `.venv\Scripts\ruff.exe format --check src tests` → exit 1:
  **5 files would be reformatted, 62 already formatted**:
  `src/app_shell.py`, `src/main.py`, `src/screens/terminal_screen.py`,
  `src/services/command_parser.py`, `tests/test_command_parser.py`.
  Diffs are pure wrapping (collapse/expand calls and sets to the 100-col width),
  EXCEPT two hunks in `command_parser.py` (~lines 157/179) where the formatter
  rewrites `except (ValueError, IndexError):` as `except ValueError, IndexError:`.
  Verified safe: the comma form parses to the identical `Tuple` ExceptHandler AST
  and catches identically at runtime on 3.14 — legal style normalization, not a bug
  (but it will startle reviewers; expect it in the format PR).

Misuse found: none blocking. Two soft spots: (a) no `per-file-ignores` for `tests/`
— harmless today (tests pass clean) but any future S/PT/ANN adoption or
assert-heavy test will need `tests/**` carve-outs up front; (b) `select` replaces
defaults, so anything Astral adds to the default set later is silently off until
someone re-syncs — `required-version = "==0.16.8"` would at least make upgrades
deliberate (currently unpinned in config; only the dev-group floor `ruff>=0.16.8`
pins it).

## Underused config to adopt

Highest value for v1 (all additive, zero current hits to fix except the format run):

1. **Run the formatter once**: `ruff format` on the 5 files above (or
   `ruff format --diff` to review first). CI's format gate is red until then —
   this is the single blocking lint item for v1.
2. **PT (flake8-pytest-style, 31 rules) + `per-file-ignores`**: `extend-select =
   ["PT"]` with `"tests/**.py" = [...]` carve-outs gives `raises`-match,
   fixture-parentheses, and parametrize-name checks on the 20-file suite for free.
3. **ARG (5) + DTZ (10)**: ARG flags unused kwargs in screens/services callbacks;
   DTZ enforces tz-aware datetimes (job-queue timestamps) — both fit the codebase.
4. **TD/FIX (11) + `task-tags`**: surfaces bare TODOs in CI output; combine with
   `lint.task-tags = ["TODO", "FIXME", "HACK"]` so v1 ships with a visible debt list.
5. **`fix = true` + `unsafe-fixes = "hint"`**: makes local `ruff check` apply safe
   fixes by default while CI (no `--fix`) stays a pure gate. Never add `--fix` to
   the CI steps — a gate that heals itself hides diffs.
6. **`ruff check --statistics` in CI logs** (or `--output-format=github`): free
   per-rule trending when the first post-M3 violation lands.
7. **Incompatible-rule hygiene**: keep ISC off (formatter conflict, already off);
   if anyone proposes `COM812` (trailing commas, preview) note it requires
   `skip-magic-trailing-comma = false` (already the default) to agree with format.
8. **`ruff analyze graph src`** in docs: one-shot import map to evidence the
   screens→services→engine layering for the v1 review.
9. Preview-gated extras worth a look post-v1: `FURB` (refurb, 36), `C4`
   (comprehensions, 20), `RET` (flake8-return, 8), `PERF` is already on.

## Gotchas

- `select` replaces defaults; `extend-select` augments. Auditing "why isn't rule X
  on" starts here. `ruff check --show-settings src/main.py` prints the resolved
  380-rule list — ground truth beats reading TOML.
- E501-off + formatter-on is the blessed pairing; re-enabling E501 with `format`
  produces unwinnable wrap wars. Same for any Q/quote rule vs `quote-style`.
- RUF100 means every `# noqa` must earn its keep — including the 9 ASYNC240s. If a
  path check moves into a sync helper, its noqa starts failing the build. Good.
- ASYNC240 vs house style: Flet event handlers are sync; only `async def` bodies
  trigger it. The 9 suppressions are all genuinely synchronous stat calls — but
  each is a main-thread disk hit on mobile; revisit under a startup-latency pass.
- `except (A, B)` → `except A, B` under `format` (observed 0.16.8): valid,
  AST-identical, runtime-verified — do not "fix" it back by hand; the gate will
  just rewrite it again.
- Cache: results live in `.ruff_cache/` (excluded by default); stale-cache
  weirdness clears with `ruff clean`. `--force-exclude` is needed for ruff to skip
  files passed explicitly on the CLI (default: explicit paths override excludes).
- `target-version` only understands ≤ py315; `requires-python = ">=3.14"` already
  implies py314, so the explicit key is documentation-grade redundancy — keep it.
