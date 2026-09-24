# mdurl 0.1.2 — Complete API Reference

> Markdown URL utilities. Python port of the JS `mdurl` package (from the
> markdown-it JS ecosystem). Import name: `mdurl`. Version installed: **0.1.2**.
> Role in this app: **pure transitive dependency** — `markdown-it-py → mdurl`.
> No direct app usage; all URL render/normalize work happens inside
> `markdown_it.common.normalize_url`.

---

## Files

Package dir: `.venv/Lib/site-packages/mdurl/` — 6 payload files, no tests,
no data (RECORD below lists all 13 installed files including dist-info):

| File | Purpose |
|---|---|
| `__init__.py` | Public surface: re-exports + `__all__` + `__version__` |
| `_url.py` | `URL` NamedTuple (8 fields) |
| `_parse.py` | Node-`url.parse` port: `url_parse()` (+ private `MutableURL` builder) |
| `_format.py` | `format(url) -> str` serializer |
| `_encode.py` | Percent-encoder `encode()` + char-set constants + cache |
| `_decode.py` | Percent-decoder `decode()` + char-set constants + cache |
| `py.typed` | PEP-561 marker — package ships inline types |

No `__pycache__` counted (build artifact). No `_split.py`/`_quote.py` in this
version — the actual module split is `_parse` / `_format` / `_encode` /
`_decode` / `_url`; `_split`/`_quote` names from the assignment brief do not exist.

Full RECORD (`mdurl-0.1.2.dist-info/RECORD`):

```text
mdurl-0.1.2.dist-info/INSTALLER
mdurl-0.1.2.dist-info/LICENSE
mdurl-0.1.2.dist-info/METADATA
mdurl-0.1.2.dist-info/RECORD
mdurl-0.1.2.dist-info/REQUESTED
mdurl-0.1.2.dist-info/WHEEL
mdurl/__init__.py
mdurl/_decode.py
mdurl/_encode.py
mdurl/_format.py
mdurl/_parse.py
mdurl/_url.py
mdurl/py.typed
```

`__init__.py` in full (the entire public surface is these 10 names):

```python
__all__ = (
    "decode",
    "DECODE_DEFAULT_CHARS",
    "DECODE_COMPONENT_CHARS",
    "encode",
    "ENCODE_DEFAULT_CHARS",
    "ENCODE_COMPONENT_CHARS",
    "format",
    "parse",
    "URL",
)
__version__ = "0.1.2"

from mdurl._decode import DECODE_COMPONENT_CHARS, DECODE_DEFAULT_CHARS, decode
from mdurl._encode import ENCODE_COMPONENT_CHARS, ENCODE_DEFAULT_CHARS, encode
from mdurl._format import format
from mdurl._parse import url_parse as parse
from mdurl._url import URL
```

## Metadata

Source: `mdurl-0.1.2.dist-info/METADATA` (Metadata-Version 2.1):

| Field | Value |
|---|---|
| Name / Version | `mdurl` / `0.1.2` |
| Summary | `Markdown URL utilities` |
| Requires-Python | `>=3.7` (no upper bound) |
| Requires-Dist | **none** — zero runtime dependencies |
| License classifier | `License :: OSI Approved :: MIT License` |
| Typing | `Typing :: Typed` (ships `py.typed`) |
| Wheel | `py3-none-any`, pure lib, built by `flit 3.7.1`, installed by `uv` |
| Homepage | `https://github.com/executablebooks/mdurl` |

LICENSE file: dual-copyright MIT — `Copyright (c) 2015 Vitaly Puzrin,
Alex Kocharin` (original JS mdurl) + `Copyright (c) 2021 Taneli Hukkinen`
(Python port); `_parse.py` additionally carries the Joyent/Node `url.parse`
MIT grant. Standard MIT "AS IS, no warranty" text. No NOTICE/patent grant.
Vendoring-safe.

Pin status in this project (`uv.lock`): `markdown-it-py 4.2.0` depends on
`{ name = "mdurl" }` (unpinned — resolves to latest 0.1.2, sdist+wheel hashes
recorded in lock). `markdown-it-py`'s own METADATA pins `mdurl~=0.1`, so any
`0.1.x >= 0.1.2` satisfies it; 0.1.2 (Aug 2022) is the newest release and the
package is effectively frozen upstream — no churn risk.

## Module-by-module API

### `_url.py` — the `URL` tuple

```python
class URL(NamedTuple):
    protocol: str | None
    slashes: bool
    auth: str | None
    port: str | None
    hostname: str | None
    hash: str | None
    search: str | None
    pathname: str | None
```

Immutable value object; use `parsed._replace(hostname=...)` for edits (exactly
what `markdown_it.common.normalize_url` does for punycode recoding). Note the
deliberate deviations from Node documented at the top of `_parse.py`: no
leading slash added to paths, backslashes NOT converted, trailing colon kept in
path, nothing percent-encoded on parse, no `host`/`path`/`query` composite
properties — derive them via `format()`.

### `_parse.py` — `parse()` (exported as `mdurl.parse`)

```python
def url_parse(url: URL | str, *, slashes_denote_host: bool = False) -> URL
# alias: mdurl.parse = url_parse
```

- `URL` input is returned **as-is** (identity fast path).
- `str` input is split into the 8 `URL` fields. Fast path: when
  `slashes_denote_host` is False and the string has no `#`, a
  `SIMPLE_PATH_PATTERN` regex handles bare paths (`pathname` + `search` only).
- `slashes_denote_host=True` (what markdown-it-py always passes) treats
  `//host/...` as host-bearing even without a scheme.
- Host parsing: last-`@` auth split, port pulled off via `:port$`, IPv6
  brackets unwrapped (`hostname` loses `[]`), labels validated against
  `^[+a-z0-9A-Z_-]{0,63}$` with non-ASCII placeholder-tolerant fallback, and
  hostnames > 255 chars are **blanked to `""`**.
- Module constants (public by import, but internal in practice):
  `PROTOCOL_PATTERN`, `PORT_PATTERN`, `SIMPLE_PATH_PATTERN`, `DELIMS`,
  `UNWISE`, `AUTO_ESCAPE`, `NON_HOST_CHARS`, `HOST_ENDING_CHARS`,
  `HOSTNAME_MAX_LEN = 255`, `HOSTNAME_PART_PATTERN/START`,
  `HOSTLESS_PROTOCOL` (`javascript:` never has a host),
  `SLASHED_PROTOCOL` (`http/https/ftp/gopher/file`).
- Private builder `MutableURL` (fields default `None`/`slashes=False`;
  methods `.parse(url, slashes_denote_host)`, `.parse_host(host)`) — never
  import directly; `url_parse` is the entry point.

Verified behavior (venv interpreter):

```python
>>> import mdurl
>>> mdurl.parse("http://example.org:8080/path?q=1#frag", slashes_denote_host=True)
URL(protocol='http:', slashes=True, auth=None, port='8080',
    hostname='example.org', hash='#frag', search='?q=1', pathname='/path')
>>> mdurl.parse("notaurl")
URL(protocol=None, slashes=False, auth=None, port=None,
    hostname=None, hash=None, search=None, pathname='notaurl')
```

### `_format.py` — `format()`

```python
def format(url: URL) -> str
```

Serializes `protocol + "//"? + auth@ + [ipv6]hostname + :port + pathname +
search + hash`; every field falls back to `""` except `slashes` (bool).
IPv6 hostnames containing `:` are re-wrapped in `[...]`.

```python
>>> mdurl.format(mdurl.parse("http://example.org:8080/path?q=1#frag"))
'http://example.org:8080/path?q=1#frag'
```

### `_encode.py` — `encode()`

```python
ENCODE_DEFAULT_CHARS = ";/?:@&=+$,-_.!~*'()#"
ENCODE_COMPONENT_CHARS = "-_.!~*'()"

def encode(string: str, exclude: str = ENCODE_DEFAULT_CHARS,
           *, keep_escaped: bool = True) -> str
```

- Percent-encodes everything outside `a-zA-Z0-9` + `exclude` (per-char 128-slot
  lookup cache keyed by `exclude` string).
- `keep_escaped=True` (default): existing valid `%XX` sequences pass through
  untouched — encoding is **idempotent**.
- Non-BMP: lone surrogates become `%EF%BF%BD` (U+FFFD); astral pairs are
  encoded via `urllib.parse.quote`; other non-ASCII via `quote` per char.

```python
>>> mdurl.encode("a b?c=d&e")   # space encoded; ? = & left alone by default set
'a%20b?c=d&e'
```

### `_decode.py` — `decode()`

```python
DECODE_DEFAULT_CHARS = ";/?:@&=+$,#"
DECODE_COMPONENT_CHARS = ""

def decode(string: str, exclude: str = DECODE_DEFAULT_CHARS) -> str
```

- Decodes `%XX` runs (regex `(%[a-f0-9]{2})+`, case-insensitive) with manual
  1–4 byte UTF-8 assembly; malformed sequences yield U+FFFD per byte-group.
- `exclude`: decoded bytes whose char is in `exclude` are **re-encoded**
  (left as `%XX`) — so reserved delimiters survive by default; pass
  `DECODE_COMPONENT_CHARS` (`""`) to decode everything.
- Per-`exclude` 128-slot cache (`get_decode_cache`); `repl_func_with_cache`
  is the regex callback.

```python
>>> mdurl.decode("a%20b%3Fc")   # %20 -> space; %3F stays (%3F is '?' in default set)
'a b%3Fc'
```

### How it complements markdown-it-py's linkify

`linkify-it-py` *detects* bare URLs in text; mdurl *normalizes* parsed link
destinations. The actual call sites are in
`.venv/Lib/site-packages/markdown_it/common/normalize_url.py`:

```python
def normalizeLink(url: str) -> str:  # link destinations [label](dest)
    parsed = mdurl.parse(url, slashes_denote_host=True)
    if parsed.hostname and (
        not parsed.protocol or parsed.protocol in ("http:", "https:", "mailto:")
    ):
        with suppress(Exception):
            parsed = parsed._replace(hostname=_punycode.to_ascii(parsed.hostname))
    return mdurl.encode(mdurl.format(parsed))


def normalizeLinkText(url: str) -> str:  # autolink display text <dest>
    parsed = mdurl.parse(url, slashes_denote_host=True)
    # ... punycode to_unicode ...
    return mdurl.decode(mdurl.format(parsed), mdurl.DECODE_DEFAULT_CHARS + "%")
```

Plus `validateLink()` (same module) which blocks
`^(vbscript|javascript|file|data):` except `data:image/(gif|png|jpeg|webp);` —
the XSS gate for rendered markdown links. mdurl itself does **no** scheme
validation.

## App usage & correctness

**(a) Dependency chain (all verified from installed METADATAs + `uv.lock`):**

```text
flet 1.0 (ft.Markdown widget)
 └─ renders release-notes markdown in update dialog
rich 15.0.0  ──Requires-Dist: markdown-it-py (>=2.2.0)
 └─ rich.markdown renderer (terminal; not on the mobile path)
markdown-it-py 4.2.0 ──Requires-Dist: mdurl~=0.1
 └─ mdurl 0.1.2  (normalizeLink / normalizeLinkText as above)
(linkify-it-py is only a markdown-it-py *extra* ("linkify"), not installed here)
```

Grep over `src/`, `tests/`, `tools/` for `mdurl`: **zero hits** — no direct
import anywhere. The package is exercised only when markdown containing links
is rendered.

**(b) Misuse:** none. Correct by absence — the app never hand-rolls URL
parsing around mdurl, never touches its privates (`MutableURL`,
`get_*_cache`, `repl_func_with_cache` stay internal), and never re-implements
what `normalizeLink` already does.

**(c) v1 relevance — indirect but load-bearing.** The app launches URLs in two
places with **no allowlist/normalization choke point today**:

- `src/components/update_dialog.py:42` — `_launch()` passes `e.data`
  (tapped link from `ft.Markdown` release notes, `on_tap_link`, line 66) and
  `GITHUB_RELEASE_URL`/`PLAYSTORE_URL` (line 45) straight to
  `url_launcher.launch_url`. Release notes come from `core/changelog.py`
  (`notes_for()`), which is bundled and trusted today — but any future remote
  notes feed would make `e.data` attacker-influenced.
- `src/screens/settings_screen.py:302` — launches `GITHUB_RELEASE_URL`
  (constant, safe).

The known gap is a `safe_launch_url` choke point that should (1) parse the
candidate with `mdurl.parse(url, slashes_denote_host=True)` or
`urllib.parse.urlsplit`, (2) lowercase/compare `hostname` against an allowlist
(`github.com`, `play.google.com`, ...), (3) reject non-`http(s)` schemes —
`markdown_it`'s own `validateLink` regex (`BAD_PROTO_RE`/`GOOD_DATA_RE`) is the
template. mdurl's `parse` + `format` round-trip (`normalizeLink` pattern:
punycode → `format` → `encode`) is exactly the normalization primitive such a
gate wants before comparing hostnames (handles case, trailing-dot, `%`-forms
consistently).

What mdurl does **NOT** do (do not mistake it for validation): no scheme
allowlisting (`javascript:` parses fine — it just sets `HOSTLESS_PROTOCOL`),
no hostname allowlisting, no IDNA by itself (markdown-it-py adds `_punycode`;
mdurl leaves unicode hosts as-is), no reachability check, over-long hostnames
silently blanked (could surprise an equality check — treat `hostname in
(None, "")` as reject).

## Considerations for v1

1. **Keep as-is (transitive).** No direct pin needed; `markdown-it-py`'s
   `mdurl~=0.1` floor is satisfied. Package is frozen upstream since 2022 —
   expect zero churn.
2. **Add the `safe_launch_url` gate before v1** (uses mdurl-style parsing, not
   an mdurl upgrade): single function in `core/` used by `update_dialog._launch`
   and `settings_screen`; allowlist hosts; `http(s)`-only; reject empty/blank
   hostname; log-and-block otherwise. Reuse `markdown_it.common.normalize_url`
   idioms (`slashes_denote_host=True`, punycode, `BAD_PROTO_RE`) rather than
   inventing new ones.
3. **Prefer `urllib.parse` over a new direct `mdurl` import** for the gate if
   stdlib suffices (one less import surface to document); mdurl remains the
   reference for *render-path* normalization semantics.
4. License posture: MIT, vendoring-safe, no attribution action required beyond
   the existing bundled LICENSE handling.

## Gotchas

- **`parse` ≠ validation.** `mdurl.parse("javascript:alert(1)")` succeeds;
  scheme rejection is the caller's job (`validateLink` pattern).
- **`format(parse(x))` is not the identity for weird input**: backslashes are
  preserved (Node compat broken deliberately), over-255-char hostnames vanish
  to `""`, IPv6 brackets move between `hostname` and the serialized form.
- **`encode` default set keeps `?`, `&`, `=`, `#`, `;`, `/`, `:` literal** —
  right for full URLs, wrong for encoding a *query value*; use
  `ENCODE_COMPONENT_CHARS` (`-_.!~*'()`) for components.
- **`decode` default set re-encodes reserved chars** — `decode("%3F")` stays
  `%3F`; pass `DECODE_COMPONENT_CHARS` to fully decode.
- **`keep_escaped=False` double-encodes** (`%20` → `%2520`); keep the default
  unless you are encoding raw user text you know is unencoded.
- **`URL` input to `parse` returns the same object** — mutating via
  `_replace` is safe (new object), but don't assume a copy was made for free.
- **Cache keying**: encode/decode caches are keyed by the `exclude` string —
  exotic per-call `exclude` values grow the dict; stick to the two constants
  (plus the documented `"..." + "%"` variant) in hot paths.
- **`slashes_denote_host` default is `False`** — `"//evil.com/x"` without it
  parses as a *path*, so hostname checks see `None`; always pass `True` when
  the input may be scheme-relative (markdown-it-py does).
