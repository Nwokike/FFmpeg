# MarkupSafe 3.0.3 — Complete API Reference

> Safe string markup for HTML/XML. Escapes `& < > ' "` so untrusted text
> displays literally; `Markup` marks a string as already-safe so frameworks
> (Jinja2) won't double-escape it. Pallets project, production-stable.
> Ground truth: `.venv/Lib/site-packages/markupsafe/` + `markupsafe-3.0.3.dist-info/`.

## Files

Package dir `.venv/Lib/site-packages/markupsafe/` (excluding `__pycache__`):

| File | Role |
|---|---|
| `__init__.py` | Entire public API (~397 lines): `escape`, `escape_silent`, `soft_str`, `Markup`, `EscapeFormatter`, `_MarkupEscapeHelper`, protocols, `__getattr__` |
| `_native.py` | Pure-Python fallback escaper, 8 lines (`_escape_inner`) |
| `_speedups.c` | C source for the compiled escaper (shipped in sdist/wheel builds) |
| `_speedups.cp314-win_amd64.pyd` | Compiled C escaper actually imported on this machine (`try: from ._speedups import _escape_inner`) |
| `_speedups.pyi` | Type stub for the C module: `def _escape_inner(s: str, /) -> str: ...` |
| `py.typed` | Empty marker — package ships inline types |

Dist-info `markupsafe-3.0.3.dist-info/`: `METADATA`, `RECORD`, `WHEEL`,
`INSTALLER` (content: `uv`), `REQUESTED` (empty), `top_level.txt`
(content: `markupsafe`), `licenses/LICENSE.txt` (BSD-3-Clause, Pallets 2010).

No `__init__.pyi` — typing is inline (`py.typed`, `from __future__ import annotations`).

## Metadata

From `METADATA` (Metadata-Version 2.4):

- **Name / Version:** `MarkupSafe 3.0.3`
- **Summary:** "Safely add untrusted strings to HTML/XML markup."
- **License:** `License-Expression: BSD-3-Clause`, `License-File: LICENSE.txt`
  (3-clause BSD: retain copyright notice, no endorsement via holder name).
- **Requires-Python:** `>=3.9` (app runs 3.14 — compatible).
- **Requires-Dist:** *none* — zero runtime pins/dependencies.
- **Classifiers:** Production/Stable, OS Independent, `Typing :: Typed`.
- **Wheel tag (this install):** `cp314-cp314-win_amd64`, `Root-Is-Purelib: false`
  (platform wheel because of the compiled `_speedups`).

## Module-by-module API

### `markupsafe._native` / `markupsafe._speedups` — the escaper

```python
def _escape_inner(s: str, /) -> str: ...
```

Pure-Python body (`_native.py`); C version in `_speedups` is behavior-identical.
Replacement order matters (`&` first to avoid double-escaping):

```python
s.replace("&", "&amp;").replace(">", "&gt;").replace("<", "&lt;")
 .replace("'", "&#39;").replace('"', "&#34;")
```

Only these 5 characters are escaped. `/`, `` ` ``, `=`, non-ASCII pass through.
`__init__.py` prefers the C version, falls back to `_native` on `ImportError`.
Raises `AttributeError`/`TypeError` only if given a non-`str` (callers coerce first).

### `markupsafe.escape(s, /) -> Markup`

Replace `& < > ' "` with HTML-safe sequences; honor pre-marked-safe objects.

```python
def escape(s: t.Any, /) -> Markup:
```

Behavior, in order:

1. `type(s) is str` (exact type, not subclass — proxy-safe) → escape chars,
   wrap in `Markup`. Fast path.
2. `hasattr(s, "__html__")` → return `Markup(s.__html__())` **unescaped**
   (trusted — see protocol section).
3. Else `Markup(_escape_inner(str(s)))`.

```python
>>> from markupsafe import Markup, escape
>>> escape("<script>alert(document.cookie);</script>")
Markup('&lt;script&gt;alert(document.cookie);&lt;/script&gt;')
>>> escape(Markup("<b>hi</b>"))   # already safe → NOT escaped
Markup('<b>hi</b>')
>>> escape(42)
Markup('42')
>>> escape("a & b")
Markup('a &amp; b')
>>> escape('"quoted"')            # " → &#34;  (NOT &quot;)
Markup('&#34;quoted&#34;')
>>> escape("it's")                # ' → &#39;
Markup('it&#39;s')
>>> escape("a/b `x` = y é")       # ISN'T escaped
Markup('a/b `x` = y é')
```

Exceptions: whatever `str(s)` / `s.__html__()` raise propagate; no MarkupSafe-specific
exception. Note the `Markup("…")` vs `escape("…")` asymmetry is the whole library.

### `markupsafe.escape_silent(s: Any | None, /) -> Markup`

Like `escape` but `None` → `Markup('')` instead of `Markup('None')`.

```python
>>> escape(None)
Markup('None')
>>> escape_silent(None)
Markup('')
>>> escape_silent("<x>")
Markup('&lt;x&gt;')
```

For optional template values.

### `markupsafe.soft_str(s: Any, /) -> str`

`str(s)` unless already `str` — critically, preserves a `Markup` instance as-`Markup`
instead of downgrading to `str` (which would cause double-escaping downstream):

```python
def soft_str(s):  # if not isinstance(s, str): return str(s); return s
```

```python
>>> value = escape("<User 1>")   # Markup('&lt;User 1&gt;')
>>> escape(str(value))           # downgraded → double-escaped
Markup('&amp;lt;User 1&amp;gt;')
>>> escape(soft_str(value))      # preserved → stable
Markup('&lt;User 1&gt;')
```

Jinja2 uses this internally when concatenating. App code joining template parts
should prefer it over `str()`.

### `markupsafe.Markup(str)` — the safe-string subclass

Constructor **marks safe without escaping** (delegates to `__html__` if present):

```python
def __new__(cls, object: t.Any = "",
            encoding: str | None = None, errors: str = "strict") -> Self
```

```python
>>> Markup("Hello, <em>World</em>!")   # NOT escaped — marked safe
Markup('Hello, <em>World</em>!')
>>> Markup(42)
Markup('42')
>>> Markup(b"<b>", encoding="utf-8")   # bytes + encoding path
Markup('<b>')
>>> class Foo:
...     def __html__(self): return '<a href="/foo">foo</a>'
>>> Markup(Foo())                      # unwraps __html__
Markup('<a href="/foo">foo</a>')
```

#### `__html__` / `__html_format__` protocols

```python
class _HasHTML(t.Protocol):
    def __html__(self, /) -> str: ...

def __html__(self, /) -> Self:  # on Markup — returns self
def __html_format__(self, format_spec: str, /) -> Self:
    if format_spec:
        raise ValueError("Unsupported format specification for Markup.")
    return self
```

Any object with `__html__()` is trusted: `escape()` and `Markup()` use its return
value verbatim. `__html_format__(spec)` exists so `"{x:spec}".format` works on
`Markup`; a **non-empty spec raises `ValueError`**.

`EscapeFormatter.format_field(value, format_spec)` dispatch:

- `__html_format__` present → call it, then `escape()` the result.
- `__html__` present (no `__html_format__`) + non-empty spec → `ValueError`
  (class must define `__html_format__` to accept specifiers).
- else → `string.Formatter.format_field`, then `escape()`.

#### Interpolation — `%` is safe, `str.format` is safe, f-strings are NOT

`__mod__` escapes every argument via `_MarkupEscapeHelper`:

```python
>>> Markup("<em>%s</em>") % ("foo & bar",)
Markup('<em>foo &amp; bar</em>')
>>> Markup("<em>%(name)s</em>") % {"name": "<x>"}
Markup('<em>&lt;x&gt;</em>')
```

`_MarkupEscapeHelper`: `__str__`/`__repr__` return the *escaped* form
(`__repr__` escapes `repr(obj)`; `__getitem__` re-wraps for `%`-mapping chains);
`__int__`/`__float__` return raw numbers (nothing to escape).

`format` / `format_map` route through `EscapeFormatter`, so fields are escaped:

```python
>>> template = Markup("Hello <em>{name}</em>")
>>> template.format(name='"World"')
Markup('Hello <em>&#34;World&#34;</em>')
```

**Footgun:** a plain f-string builds a `str` *before* `Markup` sees it —
interpolation is never escaped:

```python
user = "<script>alert(1)</script>"
Markup(f"<em>{user}</em>")  # DANGEROUS — markup injected verbatim
Markup("<em>{u}</em>").format(u=user)  # SAFE — user escaped
Markup("<em>%s</em>") % (user,)  # SAFE
Markup("<em></em>").join([user])  # SAFE (join escapes items)
```

#### String operations (all return `Markup` unless noted)

- `__add__` / `__radd__`: escape the *other* operand, keep self verbatim.
  `Markup("<em>Hello</em> ") + "<foo>"` → `Markup('<em>Hello</em> &lt;foo&gt;')`.
  Non-`str`/non-`__html__` operand → `NotImplemented` (→ `TypeError`).
- `join(iterable)`: escapes **each item**, separator kept verbatim.
- `replace(old, new, count=-1)`: escapes `new` only (`old` matched literally).
- `ljust / rjust / center(width, fillchar=" ")`: escape `fillchar` only
  (default space is inert). `zfill`, `expandtabs`, case ops take no strings —
  pure `Markup(...)` rewrap.
- `split / rsplit / splitlines / partition / rpartition / __getitem__ /
  capitalize / title / lower / upper / swapcase / casefold /
  removeprefix / removesuffix / strip / lstrip / rstrip / translate /
  __mul__ / __rmul__`: structural rewraps, no escaping (slices of safe text
  stay safe).
- `unescape() -> str` (plain `str`, NOT `Markup`): entity-decodes via
  `html.unescape`. `Markup("Main &raquo; <em>About</em>").unescape()` →
  `'Main » <em>About</em>'`.
- `striptags() -> str`: unescapes, strips `<!-- -->` comments then `<...>` tags
  with naive `find` loops (unterminated `<`/`<!--` left in place), collapses
  whitespace. `'Main » About'`. Naive — not a sanitizer against crafted input.
- `Markup.escape(s)` classmethod: `escape(s)` coerced to the subclass
  (`cls(rv)` when `type(rv) is not cls`).
- `__repr__`: `Markup('...')` form.

#### Helpers / dunder

- `class EscapeFormatter(string.Formatter)` — `__slots__ = ("escape",)`;
  `__init__(self, escape: _TPEscape)`; override `format_field` as above.
- `class _MarkupEscapeHelper` — `__slots__ = ("obj", "escape")`; see `%` section.
- `__getattr__("__version__")` → deprecated, emits `DeprecationWarning`
  ("will be removed in MarkupSafe 3.1; use
  `importlib.metadata.version("markupsafe")`"); any other name → `AttributeError`.

## App usage & correctness

**Direct usage: none.** Case-insensitive grep for
`markupsafe|MarkupSafe|from markupsafe|import markupsafe|escape_silent|soft_str|__html__|striptags`
over `src/`, `tests/`, `tools/` returns zero hits. No misuse possible — there is
nothing to misuse.

**Dependency chain (transitive only):**

1. App `pyproject.toml` declares neither `jinja2` nor `markupsafe`.
2. `jinja2 3.1.6` is installed in the venv; its `METADATA` declares
   `Requires-Dist: MarkupSafe>=2.0` — the sole installed dist requiring MarkupSafe
   (verified: no other `*.dist-info/METADATA` in the venv mentions it).
3. Per `uv.lock`, Jinja2 arrives via dev/build tooling
   (`cookiecutter → jinja2 → markupsafe`; `cookiecutter` is a `flet-cli` scaffolding
   dependency), i.e. **MarkupSafe ships in the venv for the toolchain, not for
   the shipped app**. `pinned-deps.txt` (production export) contains no
   jinja2/markupsafe entries — consistent with a transitive/dev-only presence.

**Rendering surfaces audited** (where escaping *would* matter if HTML were involved):

- `src/components/update_dialog.py` — `ft.Markdown(notes, extension_set=GITHUB_WEB)`
  with notes from bundled `core/changelog.py` or network
  `update_data["release_notes"]` / `update_data["title"]`. Markdown renderer, not
  Jinja2/HTML — MarkupSafe plays no role. Untrusted-network-markdown risk is a
  Markdown-renderer concern (link taps are explicitly handled via `_launch`), not
  an HTML-injection one.
- `src/screens/probe_screen.py::build_media_report` — builds a *markdown* share
  report interpolating `file_name`, `format_*`, `metadata` values, stream fields,
  chapter titles with plain f-strings. Correct as-is for markdown/share-sheet;
  would need `escape()` only if ever rendered as HTML.
- `job_card.py`, `result_screen.py`, probe detail rows — `ft.Text(...)` native
  text controls. Flet `Text` is not an HTML sink; no escaping layer needed or
  applied. No `ft.Html` / `WebView` usage found anywhere in `src/`.

## Considerations for v1

1. **No action required to ship:** MarkupSafe needs no pin/add — nothing imports
   it at runtime, and its presence is toolchain-transitive. Do not add it to
   `dependencies` unless app code actually imports it.
2. **If an HTML export/share is added** (e.g. Jinja2 HTML dossier, rich-text
   email body, `ft.Html`/WebView preview): route every user-influenced value —
   job names, filenames, probe `metadata` dict values, chapter titles, network
   `release_notes` — through `escape()` or Jinja2 autoescape (`select_jinja_autoescape`
   / `autoescape=True`), and reserve bare `Markup(...)` for app-authored
   template scaffolding only.
3. **Adopt the safe interpolation habit now:** `Markup("<em>{u}</em>").format(u=user)`
   or `Markup("<em>%s</em>") % (user,)`; never `Markup(f"...{user}")`.
   `soft_str()` before `str()` when threading values through helpers to avoid
   double-escaping.
4. **Changelog/release-notes path** (`update_dialog` + `notes_for`): currently
   markdown-rendered. If a future "view in browser / export HTML" feature renders
   `release_notes` as HTML, that network-controlled string is the highest-risk
   sink — `escape()` it or render through an autoescaped Jinja2 template.
5. **Build hygiene:** C speedup (`_speedups.cp314-win_amd64.pyd`) is per-platform;
   mobile builds (arm64/x86_64, minSdk 24) re-resolve via uv — the pure-Python
   `_native` fallback guarantees identical output anywhere. No `Requires-Python`
   conflict (`>=3.9` vs app `>=3.14`).

## Gotchas

- `Markup(x)` does **not** escape; `escape(x)` / `Markup.escape(x)` do. The #1 CVE-class mistake.
- `escape()` trusts `__html__()` return values verbatim — a malicious/buggy
  `__html__` bypasses escaping by design. Only implement it on app-owned types.
- `"` → `&#34;` and `'` → `&#39;` (not `&quot;`/`&apos;`); `/` backtick `=` and
  Unicode are untouched — don't assume broader coverage.
- `str(Markup)` silently drops safety: re-escaping a downgraded string
  double-escapes (`&amp;lt;`). Use `soft_str()`.
- `format`/`%`/`join`/`+` escape *arguments*, never the template itself — which is
  exactly why f-strings (interpolated before the call) are unsafe.
- `__html_format__` with any spec raises `ValueError`; objects defining
  `__html__` without `__html_format__` fail under `"{x:spec}".format`.
- `striptags()` is a naive `find`-loop tag stripper, not an XSS sanitizer.
- `unescape()`/`striptags()` return plain `str` — re-escape before HTML insertion.
- `markupsafe.__version__` is deprecated (DeprecationWarning, removal in 3.1).
