# repath 0.9.0 — Complete API Reference

> **Correction to the assignment brief:** repath 0.9.0 is **NOT** an SVG
> path-data parser. There is no SVG tokenizer, no `M/L/H/V/C/S/Q/T/A/Z`
> command handling, no parse-tree node types, and nothing for path
> length/bounds anywhere in the package. Ground truth (single 296-line
> module, verified below): repath is a **port of the `pathToRegexp` Node
> module to Python — it compiles Express-style route patterns
> (`/user/:id`, `/files/*`) into PCRE regex strings**, with named capture
> groups, plus a reverse templating function. Its consumer is flet's
> **navigation/router layer**, not SVG rendering (`ft.Path` SVG data is
> passed through to Flutter as a string; no Python-side SVG math exists).

## Files

The installed distribution contains exactly **two** payload files
(`RECORD` hashes verified at research time):

| File | Size | Role |
|---|---|---|
| `.venv/Lib/site-packages/repath.py` | 296 lines, ~8 KB | The entire library — one flat module, no package dir, no submodules |
| `.venv/Lib/site-packages/repath-0.9.0.dist-info/` | 7 files | `METADATA`, `WHEEL`, `RECORD`, `INSTALLER`, `LICENSE`, `REQUESTED`, `top_level.txt` (`top_level.txt` = `repath`) |

Module-level constants in `repath.py`:

- `REGEXP_TYPE = type(re.compile(''))` — used to detect pre-compiled regex input in `pattern()`.
- `PATH_REGEXP` — the master tokenizer regex (verbose mode). Alternation
  branches: `escaped` (`\\.`), then optional `prefix` (`[/.]`) + one of
  named param (`:name`, optional `(capture)` + optional `suffix` `[+*?]`),
  anonymous `(group)` + optional suffix, or bare `asterisk` (`*`).
- `PATTERNS` — three segment templates used by `tokens_to_pattern`:
  `REPEAT = '(?:{prefix}{capture})*'`,
  `OPTIONAL = '(?:{prefix}({name}{capture}))?'`,
  `REQUIRED = '{prefix}({name}{capture})'`.

## Metadata

From `repath-0.9.0.dist-info/METADATA` (Metadata-Version 2.1):

- **Name / Version:** `repath 0.9.0`
- **Summary:** "Generate regular expressions form ExpressJS path patterns" (sic)
- **License:** MIT (`License: MIT`, classifier `OSI Approved :: MIT License`; `LICENSE` file = MIT, copyright 2015 Synacor, Inc.)
- **Requires-Python:** *not declared* (no `Requires-Python` field). Classifiers claim Py 2 + 3 (stale — the code imports `six`).
- **Dependencies:** exactly one — `Requires-Dist: six (>=1.9.0)`.
  **No `pyparsing` pin exists** — the brief's "pyparsing? — verify" is answered: repath's only tokenizer is stdlib `re` (`PATH_REGEXP`); pyparsing is not involved.
- Upstream: `https://github.com/nickcoutsos/python-repath`, port of `pathToRegexp`.

Who requires it (verified by grepping all `*.dist-info/METADATA`):

- **`flet-1.0.0.dist-info/METADATA` contains `Requires-Dist: repath>=0.9.0`** (unconditional, all platforms). flet 1.0 declares no upper pin.
- Nothing else in the venv requires it. `six` itself is pulled in only via this chain.

## Module-by-module API

The whole library is the single module `repath` (`import repath`). Eight
public functions, no classes, no exceptions of its own (raises stdlib
`KeyError` / `ValueError` / `TypeError` from templating only).

### `parse(string)` → `list`

Tokenize an Express-style path into raw tokens (strings for literals,
dicts for parameters).

- Signature: `parse(string)` — one positional arg, no defaults, no kwargs.
- Token dict keys: `name` (str; numeric `str(key)` counter for anonymous
  params/groups), `prefix` (the literal prefix char or `''`), `delimiter`
  (`prefix or '/'`), `optional` (`suffix in ('?', '*')`), `repeat`
  (`suffix in ('+', '*')`), `pattern` (capture source, group-escaped).
- Default capture when none given: `'.*'` for bare `*`, else `'[^<delim>]+?'`.
- Escaped chars (`\\.` branch) are appended literally to the pending literal
  and produce no token.
- Example (verified live in this venv):
  `parse('/user/:id')` →
  `['/user', {'name': 'id', 'prefix': '/', 'delimiter': '/', 'optional': False, 'repeat': False, 'pattern': '[^/]+?'}]`
- Raises: none (never raises on any input; garbage becomes literal strings).

### `tokens_to_pattern(tokens, end=True, strict=False)` → `str`

Compile a token list into an anchored regex source string.

- Named params whose name contains `[a-zA-Z]` become `(?P<name>…)` groups
  (name passed through `re.escape`); purely numeric names stay anonymous.
- Repeat tokens wrap the capture with the `REPEAT` template; optional vs
  required selects the `OPTIONAL`/`REQUIRED` segment template.
- Trailing-slash handling: unless `strict`, a trailing `/` on the last
  literal is stripped and `(?:/(?=$))?` appended (trailing slash optional).
- `end=True` appends `$` (full match); `end=False` appends `(?=/|$)` (prefix
  match, unless `strict` with trailing slash → appends nothing).
- Result always starts with `^`.
- Corner case: **empty token list raises `IndexError`** (`tokens[-1]`).
- Examples (verified):
  `pattern('/user/:id')` → `^/user/(?P<id>[^/]+?)(?:/(?=$))?$`;
  optional `/files/:name?` → `^/files(?:/(?P<name>[^/]+?))?(?:/(?=$))?$`.

### `pattern(path, **options)` → `str`

Dispatching entry point — the function flet actually calls.

- `path` may be: a pattern string (→ `tokens_to_pattern(parse(path), …)`),
  a **list of patterns** (→ `(?:p1|p2|…)` alternation, verified:
  `['/a','/b/:x']` → `(?:^/a(?:/(?=$))?$|^/b/(?P<x>[^/]+?)(?:/(?=$))?$)`),
  or a **compiled regex** (returns `path.pattern` verbatim).
- `**options` are `end` / `strict`, forwarded to `tokens_to_pattern`.

### `compile(path, flags=0, **options)` → `re.Pattern`

`re.compile(pattern(path, **options), flags)`. Note the docstring typo
("comiled regular expresion"). `flags` are stdlib `re` flags.

### `match(path, string, flags=0, **options)` → `re.Match | None`

Compile-and-match one-liner. **Bug to be aware of:** the body calls
`compile(path, flags=0, **options)` — the `flags` argument is accepted but
**hard-coded to `0`, so caller-supplied flags are silently ignored**.

### `tokens_to_template(tokens)` → callable

Returns `template_function(obj)` that renders a path from a param dict:

- String tokens are copied verbatim; param values are validated against
  `^<pattern>$` and URL-quoted (`urllib.quote`).
- Missing non-optional value → `KeyError('Expected "{name}" to be defined')`;
  value failing its pattern → `ValueError('Expected "{name}" to match …')`.
- List value on a non-repeat token → `TypeError('Expected "{name}" to not
  repeat')`; empty list on a required repeat token →
  `ValueError('Expected "{name}" to not be empty')`. Repeat items after the
  first are joined with `delimiter` (path-join semantics).
- Verified: `template('/user/:id')({'id': '42'})` → `'/user/42'`.

### `template(path)` → callable

`tokens_to_template(parse(path))` — precompile a pattern string into its
render function.

### `escape_string(string)` / `escape_group(group)` → `str`

Helpers: `escape_string` backslash-escapes `[.+*?=^!:${}()[\]|]` (literals
safe for regex splicing); `escape_group` escapes `[=!:$()]` inside capture
sources.

### Pattern-language cheat sheet (what the syntax supports)

| Syntax | Meaning | Example pattern |
|---|---|---|
| `:name` | required named segment (`[^/]+?`) | `/user/:id` |
| `:name(custom)` | named with custom capture | `/:test(\d+)?` |
| `(group)` | anonymous group, positional name | `/route(\d+)` |
| `*` | bare wildcard (`.*`) | `/*` |
| suffix `?` / `*` / `+` | optional / optional-repeat / repeat | `/files/:p*` |
| prefix `.` | dot-delimited params | `/:file.:ext` |
| `\x` | literal escape | `/\:` |
| list input | alternation | `['/a', '/b']` |

## App usage & correctness

- **Direct app usage: zero.** `grep -rn "repath"` over `src/`, `tests/`,
  `tools/` returns nothing (exit 1). The app never imports it; no misuse
  possible at the app layer.
- **Real consumer chain (verified in installed flet 1.0.0 source):**
  1. `flet/controls/template_route.py` — `TemplateRoute.match()` compiles
     the user-supplied route template with `repath.pattern(route_template)`
     and runs `re.match`, exposing named params as attributes
     (e.g. `self.user_id`). This is the **public API the FFmpeg app would
     touch** for deep-link / parameterized routes.
  2. `flet/components/router.py` (`_try_match`, lines ~181–308) — the
     internal `Route` tree matcher calls `repath.pattern(full_path)` for
     exact matches (index routes, leaf routes, parent-with-component) and
     `repath.pattern(full_path, end=False)` for prefix matches (recursive
     routes, parent routes), threading `match.groupdict()` into
     `_RouteMatch.params`. Sibling-precedence logic (specific child before
     recursive self-match) sits on top of these prefix matches.
- **Correctness notes for app developers:**
  - Route matching inherits repath semantics exactly: trailing slash is
    optional by default, `:param` never spans `/`, `*` spans everything.
  - The `match()` flags bug (above) means case-insensitive route matching
    via `repath.match(..., flags=re.IGNORECASE)` silently does nothing —
    but flet's own call sites use `repath.pattern` + `re.match` and never
    hit this path, so it is latent, not active.
  - `six` usage (`six.string_types`, `six.text_type`, `urllib.quote`) is a
    compat shim; on Python 3.14 it behaves as `str` + `urllib.parse.quote`.

## Considerations for v1

- **SVG relevance: none — correct the record.** The brief assumed repath =
  SVG path parsing; it is route-pattern → regex. The app's
  `src/assets/icon.svg` / `icon_white.svg` ship via flet's asset pipeline
  and in-app `ft.Image(src="icon.svg")` / `ft.Icon` rendering, none of
  which touches repath. The flet-cli launcher-icon warning (SVG dropped
  for native icons) is likewise unrelated to this package — do not cite
  repath as a factor in any icon/SVG decision.
- **What repath actually enables for v1:** parameterized in-app navigation
  (`TemplateRoute`, `Route(path="/job/:job_id")`) — relevant only if the
  FFmpeg app adopts deep-linkable routes (e.g. `/job/<id>`, `/preset/<n>`).
  If the app stays single-view, repath is pure transitive weight.
- **Dependency risk: low but stale.** Single-purpose 8 KB module, MIT,
  one deps (`six>=1.9.0` — itself unmaintained upstream but stable and
  tiny). flet pins `repath>=0.9.0` with no ceiling, so a future repath
  0.10+ with changed codegen could silently alter route matching; the
  exposure is flet's, not the app's, and requires no app-side pin.
- **No action required:** no direct import, no vendoring, no version work.
  If the team adds routed navigation in v1, write route-template tests
  against `TemplateRoute` (named-param extraction, optional segments,
  trailing-slash tolerance) rather than against repath directly.

## Gotchas

1. **Not an SVG library.** Any v1 doc/design referencing "repath for SVG
   path math" is wrong; `ft.Path` SVG strings go to the Flutter engine
   untouched.
2. **`match()` drops `flags`.** `repath.match(p, s, flags=re.IGNORECASE)`
   compiles with `flags=0` (hard-coded). Use `re.match(repath.pattern(p),
   s, flags)` if flags matter.
3. **No `Requires-Python` in METADATA** — tooling that trusts metadata
   alone sees "any Python"; the code is Py2/3-via-six and works on 3.14
   in practice (verified import + calls in this venv).
4. **Numeric-named params are anonymous groups.** `parse('/(\\d+)')`
   yields `name='0'` and `tokens_to_pattern` emits a non-named group, so
   `match.groupdict()` will NOT contain it — read it positionally.
5. **`pattern()` on a compiled regex returns it verbatim** — `end`/`strict`
   options are silently ignored in that branch.
6. **Empty token list crashes** `tokens_to_pattern` with `IndexError`
   (only reachable via direct `tokens_to_pattern([])` calls, not via
   `pattern('')` — that yields one empty-string token, fine).
7. **`template()` quoting asymmetry:** scalar values are UTF-8-encoded
   before quoting (`quote(value.encode('utf8'), …)`), list items are
   quoted as `str` — non-ASCII repeat values may behave inconsistently.
