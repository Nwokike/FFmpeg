# iniconfig 2.3.0 — Complete API Reference

> Brain-dead simple read-only INI parser. Upstream: https://github.com/pytest-dev/iniconfig
> Role in this repo: **transitive test-stack plumbing only** — required by pytest 9.1.1 for
> legacy `.ini`/`.cfg` config discovery. The app itself never imports it.

## Files

Package dir: `.venv/Lib/site-packages/iniconfig` — 6 entries, 4 real source files
(`__pycache__` skipped). Dist-info: `iniconfig-2.3.0.dist-info/`
(`INSTALLER`, `METADATA`, `RECORD`, `REQUESTED`, `WHEEL`, `licenses/LICENSE`,
`top_level.txt`). RECORD hashes verified present for all 12 installed files.

| File | Size class | Purpose |
|---|---|---|
| `__init__.py` | ~250 lines | Public API: `IniConfig`, `SectionWrapper`, re-exports |
| `_parse.py` | ~164 lines | Tokenizer + grammar (`parse_ini_data`, `parse_lines`, `_parseline`) |
| `exceptions.py` | 17 lines | `ParseError` |
| `_version.py` | setuptools-scm generated | `__version__ = '2.3.0'`, `version_tuple = (2, 3, 0)` |
| `py.typed` | empty marker | Package ships inline types (PEP 561) |

`__all__ = ["IniConfig", "ParseError", "COMMENTCHARS", "iscommentline"]`.
There is **no** `api.py` / `parse.py` — the layout is `__init__` + private `_parse`.

## Metadata

From `iniconfig-2.3.0.dist-info/METADATA` (Metadata-Version 2.4):

- **Name / Version:** `iniconfig` 2.3.0 (`_version.py`: `__version__ = version = '2.3.0'`,
  `__version_tuple__ = version_tuple = (2, 3, 0)`, commit id `None`).
- **Summary:** "brain-dead simple config-ini parsing".
- **License:** `License-Expression: MIT`; license file `licenses/LICENSE`
  (MIT, © 2010–2023 Holger Krekel and others). No ambiguity — pure MIT.
- **Requires-Dist:** none. Zero runtime dependencies (stdlib only: `os`,
  `collections.abc`, `typing`).
- **Requires-Python:** `>=3.10`. Classifiers list 3.10–3.14; tested here on 3.14.
- **Wheel:** `py3-none-any`, pure lib, built with setuptools 80.9.0.
- **Reverse dependency:** `pytest-9.1.1.dist-info/METADATA` declares
  `Requires-Dist: iniconfig>=1.0.1`. Installed 2.3.0 satisfies it.

## Module-by-module API

### `exceptions.py` — `ParseError`

```python
class ParseError(Exception):
    path: Final[str]
    lineno: Final[int]  # 0-based internally!
    msg: Final[str]

    def __init__(self, path: str, lineno: int, msg: str) -> None: ...
    def __str__(self) -> str: ...  # f"{path}:{lineno + 1}: {msg}"
```

`super().__init__(path, lineno, msg)` so `args == (path, lineno, msg)`.
Five raise sites, all in `_parse.parse_ini_data` / `parse_lines` / `_parseline`:

| Message | Condition |
|---|---|
| `"no section header defined"` | key/value line before any `[section]` |
| `"empty section name"` | bare `[]` header |
| `"unexpected value continuation"` | indented line with no preceding key/value (or directly after a section header) |
| `f"duplicate section {section!r}"` | section header repeated |
| `f"duplicate name {name!r}"` | key repeated within one section |
| `f"unexpected line: {line!r}"` | non-indented line with neither `=` nor `:` |

### `_parse.py` — grammar

```python
COMMENTCHARS = "#;"  # module constant, also re-exported


class ParsedLine(NamedTuple):
    lineno: int
    section: str | None
    name: str | None  # None  => section header token
    value: str | None  # None  => section header token


def parse_ini_data(
    path: str, data: str, *, strip_inline_comments: bool, strip_section_whitespace: bool = False
) -> tuple[Mapping[str, Mapping[str, str]], Mapping[tuple[str, str | None], int]]: ...


def parse_lines(
    path: str,
    line_iter: list[str],
    *,
    strip_inline_comments: bool = False,
    strip_section_whitespace: bool = False,
) -> list[ParsedLine]: ...


def _parseline(
    path, line, lineno, strip_inline_comments, strip_section_whitespace
) -> tuple[str | None, str | None]: ...


def iscommentline(line: str) -> bool: ...  # line.lstrip()[:1] in COMMENTCHARS
```

Return convention of `_parseline`: `(name, value)` new entry · `(section, None)`
new section · `(None, continuation)` append · `(None, None)` blank/comment.

**Parsing rules (exact):**

1. **Comment lines:** `line.lstrip()[:1] in "#;"` → line discarded. Note: whitespace
   before `#`/`;` is fine; an *indented* `# comment` is still a comment, NOT a
   continuation.
2. **Blank lines:** after `rstrip()`, empty → skipped.
3. **Sections:** line starts with `[`. Trailing comment stripped by
   `line.split(c)[0].rstrip()` for each of `#`, `;` — so
   `[section1] # comment` works (this is the documented example). Must then end
   with `]`; the inner text is the name verbatim (whitespace preserved unless
   `strip_section_whitespace=True`, which `.strip()`s section **and key** names —
   Unicode-aware — for issue #4). Gotcha: `[unclosed` does **not** raise; it falls
   through as `(None, realline.strip())`, i.e. a *continuation* of the previous value.
4. **Values:** line does NOT start with whitespace. `=` is tried first:
   `line.split("=", 1)`; if the *name part* contains `:` a `ValueError` is forced
   and `:` is tried instead (`line.split(":", 1)`). So `key=value` wins;
   `key: value` works; `a:b=c` parses as key `a:b`… no — `:` in name forces the
   colon split, so `a:b=c` → key `a`, value `b=c`. Neither separator →
   `ParseError("unexpected line")`. Key is always `.strip()`ed; value is
   `.strip()`ed, then inline comments stripped iff requested (naive
   `value.split(c)[0].rstrip()` per comment char — see Gotchas).
5. **Continuations:** line starts with whitespace → `.strip()`ed (plus optional
   inline-comment strip) and appended to the previous value joined with `"\n"`.
   Multi-line values need no backslash; `name2=` followed by indented `line1`/`line2`
   yields `"line1\nline2"` (documented example). Error if nothing precedes, or the
   preceding token is a section header.
6. **Duplicates are fatal** (unlike `configparser`, which overwrites): duplicate
   section or duplicate key in the same section → `ParseError`.
7. **Case sensitivity:** names/keys are stored verbatim; `Key` ≠ `key`. No
   lowercasing anywhere.
8. **Types:** everything is `str`. No interpolation, no `DEFAULT` section, no
   type inference. `convert=` callables on `get()` are the only coercion hook.
9. **Order:** insertion-ordered dicts; `SectionWrapper.__iter__` /
   `IniConfig.__iter__` yield in source-line order (sorted by recorded lineno).

### `__init__.py` — `IniConfig` / `SectionWrapper`

```python
class IniConfig:
    path: Final[str]
    sections: Final[Mapping[str, Mapping[str, str]]]
    _sources: Final[Mapping[tuple[str, str | None], int]]  # 0-based linenos

    def __init__(
        self,
        path: str | os.PathLike[str],
        data: str | None = None,
        encoding: str = "utf-8",
        *,
        _sections=None,
        _sources=None,
    ) -> None: ...
    @classmethod
    def parse(
        cls,
        path: str | os.PathLike[str],
        data: str | None = None,
        encoding: str = "utf-8",
        *,
        strip_inline_comments: bool = True,  # <-- default True
        strip_section_whitespace: bool = False,
    ) -> "IniConfig": ...
    def lineof(self, section: str, name: str | None = None) -> int | None: ...
    def get(
        self,
        section: str,
        name: str,
        default: _D | None = None,
        convert: Callable[[str], _T] | None = None,
    ) -> _D | _T | str | None: ...
    def __getitem__(self, name: str) -> SectionWrapper: ...  # KeyError if missing
    def __iter__(self) -> Iterator[SectionWrapper]: ...  # line-number order
    def __contains__(self, arg: str) -> bool: ...  # section test


class SectionWrapper:
    config: Final["IniConfig"]
    name: Final[str]

    def __init__(self, config: "IniConfig", name: str) -> None: ...
    def lineof(self, name: str) -> int | None: ...
    def get(self, key: str, default=None, convert=None): ...  # 5 overloads, mirrors IniConfig
    def __getitem__(self, key: str) -> str: ...  # KeyError if missing
    def __iter__(self) -> Iterator[str]: ...  # keys in line order
    def items(self) -> Iterator[tuple[str, str]]: ...
```

Semantics:

- **Constructor vs `parse()`:** `IniConfig(path)` reads the file as UTF-8 and parses
  with `strip_inline_comments=False` (legacy behavior — `value  # comment` keeps the
  comment). `IniConfig.parse(path)` defaults `strip_inline_comments=True`. Same file,
  different values — the single most surprising API fact. `parse()` also offers
  `strip_section_whitespace` (opt-in, issue #4). Both accept `data=` to parse a
  string without touching disk (`path` is then only used for error messages).
- **`lineof(section, name=None)`:** 1-based line number (`stored + 1`), or `None`
  when the section/key is unknown. `SectionWrapper.lineof(key)` is the same scoped
  to its section.
- **`get(section, name, default=None, convert=None)`:** returns `default` when the
  section *or* the key is missing (indistinguishable); applies `convert(value)` only
  on hit. Five `@overload`s give precise `default`/`convert` typing. Documented
  example: `ini.get('section1', 'name1b', [], lambda x: x.split(","))` → list.
- **`__getitem__`:** `ini['section1']['name1']` — raises `KeyError` on a missing
  section *or* key. `SectionWrapper.__getitem__` reads through
  `config.sections[name][key]`.
- **Iteration:** `for section in ini` yields `SectionWrapper`s in file order;
  `for key in ini['s']` yields keys in file order; `.items()` yields
  `(key, value)` pairs in file order. `'section' in ini` tests section presence.
- **Read-only:** no `set`/`write`/`save` API anywhere. To persist, serialize by hand.

Minimal example (from METADATA docs, verified against the grammar):

```ini
# example.ini
[section1] # comment
name1=value1  # comment
name1b=value1,value2  # comment

[section2]
name2=
    line1
    line2
```

```python
import iniconfig

ini = iniconfig.IniConfig.parse("example.ini")  # inline comments stripped
ini["section1"]["name1"]  # 'value1'
ini.get("section1", "name1b", [], lambda x: x.split(","))  # ['value1', 'value2']
[x.name for x in ini]  # ['section1', 'section2']
"section1" in ini  # True
ini.lineof("section1", "name1")  # 1-based source line
```

## App usage & correctness

- **Direct usage: none.** `grep -rn "iniconfig"` over `src/`, `tests/`, `tools/`
  returns zero hits — no import, no config file consumed via this library.
- **Chain: `pytest → iniconfig`.** `pytest-9.1.1.dist-info/METADATA` requires
  `iniconfig>=1.0.1`. Three touch points inside the installed pytest:
  - `_pytest/config/findpaths.py::_parse_ini_config` — parses legacy `pytest.ini` /
    `setup.cfg` (`[pytest]` / `[tool:pytest]` sections), converting
    `iniconfig.ParseError` into `UsageError`. Only the `.ini`/`.cfg` branch;
    `.toml` files go through `tomllib` and never touch iniconfig.
  - `_pytest/pytester.py` — imports `IniConfig`, `SectionWrapper` for the
    `pytester.makeini` test-harness helper.
  - `_pytest/legacypath.py` — re-exports `SectionWrapper`.
- **This repo's pytest config is TOML** (`pyproject.toml [tool.pytest.ini_options]`
  with `pythonpath = ["src"]`, `testpaths = ["tests"]`), so even the pytest chain
  never invokes iniconfig during our runs — it is exercised only in pytest's
  rootdir probing for stray `.ini`/`.cfg` files. Correctly installed, never
  meaningfully used here.
- **Misuse:** none possible — zero direct references. Nothing to fix.

## Considerations for v1

- **Ship/keep:** yes, keep as an untracked transitive test dependency (comes with
  pytest; zero cost, zero pins needed). Do not add it to direct dependencies —
  nothing imports it.
- **App config direction is TOML, not INI:** `[tool.flet]`, `[tool.pytest.ini_options]`,
  `[tool.ruff]` already live in `pyproject.toml`. Stay that course for v1.
- **If the app ever wants a tiny sidecar config** (e.g. `.env`-like engine presets
  for the FFmpeg mobile UI), what iniconfig offers: 4-file dependency-free parser,
  order-preserving, multi-line values, precise `path:line:` errors, `convert=` hook
  for typed access. What it lacks (deal-breakers for app config): **read-only, no
  write API**; **all values are `str`** (no int/bool/list natives — TOML wins);
  **no interpolation or `DEFAULT` inheritance**; naive inline-comment stripping
  mangles values containing `#`/`;` (URLs, hex colors like `#3c8038`, passwords);
  duplicate keys are hard errors rather than last-wins. For v1, `tomllib` (stdlib)
  or the existing TOML config is strictly preferable.

## Gotchas

1. **Constructor vs `parse()` disagree on inline comments** (`False` vs `True`).
   `IniConfig("f.ini")["s"]["k"]` may return `"foo # comment"` where
   `IniConfig.parse("f.ini")["s"]["k"]` returns `"foo"`. Always use `parse()`.
2. **Naive comment stripping** — `value.split("#")[0]` splits inside quoted
   strings, URLs (`http://x/#frag`), hex colors, and passwords. A value containing
   `#` or `;` is silently truncated when stripping is on, silently kept when off.
3. **Unclosed `[section` is a continuation, not an error** — silently glued onto
   the previous value with `\n`.
4. **Duplicate section/key = hard `ParseError`**, unlike `configparser` last-wins.
5. **`key: value` only when `=`-split fails or the pre-`=` name contains `:`**;
   `a:b=c` parses as key `a`, value `b=c` — not key `a:b`.
6. **Indented `#`/`;` lines are comments**, never continuations — you cannot put a
   literal comment-looking line inside a multi-line value.
7. **Keys and sections are case-sensitive**; no normalization anywhere.
8. **`get()` conflates missing section and missing key** (both → `default`), and
   `lineof()` returns `None` for both — check `in` first if the distinction matters.
9. **`ParseError.lineno` is 0-based** but `str(exc)` and `lineof()` are 1-based —
   don't mix them when reporting.
10. **No write path** — there is no dump/serialize counterpart; round-tripping
    requires hand-rolled output.
