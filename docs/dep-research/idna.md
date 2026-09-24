# idna 3.20 — Complete API Reference

Internationalized Domain Names in Applications (IDNA 2008, RFC 5891) plus
Unicode UTS #46 compatibility mapping. Pure-Python, no runtime dependencies.
Unicode tables generated from **Unicode 18.0.0**. Thread-safe (no mutable
global state).

## Files

Package dir: `.venv/Lib/site-packages/idna/` (RECORD hashes verified, see
`idna-3.20.dist-info/RECORD`). `__pycache__` excluded.

| File | Lines | Role |
|---|---|---|
| `__init__.py` | 48 | Public surface; re-exports from `core`, plus `unicode_version`, `__version__`, `intranges_contain` |
| `core.py` | 863 | All logic: errors, checks, `alabel`/`ulabel`, `encode`/`decode`, `uts46_remap` |
| `codec.py` | 225 | `codecs`-registered **`"idna2008"`** codec (NOT `"idna"`) |
| `compat.py` | 44 | IDNA 2003 shims: `ToASCII`, `ToUnicode`, `nameprep` stub |
| `intranges.py` | 55 | Compressed int-range sets + `O(log n)` membership test |
| `idnadata.py` | 1933 | Generated tables: `scripts`, `joining_types`, `codepoint_classes` (`__version__ = "18.0.0"`) |
| `uts46data.py` | 17117 | Generated UTS #46 tables: `uts46_starts`, `uts46_statuses`, `uts46_replacements` (`__version__ = "18.0.0"`) |
| `cli.py` | 133 | `main()` for `python -m idna` / `idna` console script |
| `__main__.py` | 7 | `python -m idna` trampoline → `cli.main()` |
| `package_data.py` | 1 | `__version__ = "3.20"` |
| `py.typed` | 0 | PEP 561 typed-package marker |

> Note: there is **no `idna.uts46` submodule** and no `uts46_encode` /
> `uts46_decode` / `TransitionalProcessing` names (those belong to the old
> `encodings.idna` / IDNA-2003 world). UTS #46 is reached via
> `encode(..., uts46=True)`, `decode(..., uts46=True)`, or `uts46_remap()`.

## Metadata

From `idna-3.20.dist-info/METADATA` (Metadata-Version 2.5, built with
`flit 4.1.0`, `py3-none-any` wheel):

- **Name / Version:** `idna 3.20`
- **Summary:** Internationalized Domain Names in Applications (IDNA)
- **License:** `BSD-3-Clause` (License-Expression; full text in
  `dist-info/licenses/LICENSE.md`, copyright 2013–2026 Kim Davies and
  contributors)
- **Requires-Python:** `>=3.9` (classifiers list 3.9–3.15, CPython + PyPy;
  running here on Python 3.14)
- **Runtime pins: none.** Zero `Requires-Dist` entries for normal installs.
  Dev-only extras (`extra == "all"`): `ruff`, `mypy`, `ty`, `pytest`,
  `hypothesis`, `coverage` — none installed in this venv.
- **Entry point** (`entry_points.txt`): `[console_scripts] idna=idna.cli:main`
- **Lock:** `uv.lock` pins `idna 3.20` with both sdist and wheel hashes from
  PyPI (published 2026-09-17). It is **not** in `pyproject.toml`
  `dependencies` directly — it arrives transitively (see below).
- `INSTALLER` + `REQUESTED` present (explicitly requested at some point, but
  currently only required transitively).

Reverse dependencies (verified in their METADATAs):

- `httpx 0.28.1`: `Requires-Dist: idna` (unpinned, unconditional)
- `requests`: `Requires-Dist: idna<4,>=2.5` (satisfied by 3.20)

## Module-by-module API

### `idna/__init__.py` — public surface

```python
import idna

idna.__version__  # "3.20"      (from package_data)
idna.unicode_version  # "18.0.0"    (from idnadata)
```

`__all__`: `__version__`, `unicode_version`, `IDNABidiError`, `IDNAError`,
`InvalidCodepoint`, `InvalidCodepointContext`, `alabel`, `check_bidi`,
`check_hyphen_ok`, `check_initial_combiner`, `check_label`, `check_nfc`,
`decode`, `encode`, `intranges_contain`, `ulabel`, `uts46_remap`,
`valid_contextj`, `valid_contexto`, `valid_label_length`,
`valid_string_length`.

### `idna/core.py` — everything else

**Top-level encode / decode** (verified live in this venv):

```python
def encode(
    s: str | bytes | bytearray,
    strict: bool = False,
    uts46: bool = False,
    std3_rules: bool = False,
    transitional: bool = False,  # DEPRECATED, ignored, warns
) -> bytes: ...


def decode(
    s: str | bytes | bytearray,
    strict: bool = False,
    uts46: bool = False,
    std3_rules: bool = False,
    display: bool = False,
) -> str: ...
```

Semantics:

- `encode` splits on label separators, runs each label through `alabel()`,
  rejoins with `.`. `strict=False` (default) also treats `U+3002` (ideographic
  full stop), `U+FF0E` (fullwidth full stop), `U+FF61` (halfwidth ideographic
  full stop) as separators; `strict=True` splits only on ASCII `.`.
- Bytes input to `encode` must already be ASCII or `IDNAError(code="invalid_ascii")`.
- `uts46=True` first runs `uts46_remap(s, std3_rules)` (mapping: case-fold,
  width-fold, NFC). `std3_rules` only has an effect together with `uts46`.
- `decode` splits the same way, runs each label through `ulabel()`.
  `display=True` passes an undecodable `xn--`-prefixed label through
  unchanged (lowercased) instead of raising — per UTS #46 §4 / WHATWG "domain
  to Unicode", intended for display/URL-library use.
- `transitional=True` emits `DeprecationWarning` ("Transitional processing is
  deprecated in UTS #46 and has no effect") and is otherwise ignored; it will
  be removed in a future version.

Examples (all executed against the installed 3.20):

```python
>>> idna.encode('münchen')
b'xn--mnchen-3ya'
>>> idna.encode('ドメイン.テスト')
b'xn--eckwd4c7c.xn--zckzah'
>>> idna.decode('xn--mnchen-3ya')
'münchen'
>>> idna.decode('xn--eckwd4c7c.xn--zckzah')
'ドメイン.テスト'
>>> idna.encode('Königsgäßchen')
# InvalidCodepoint: Codepoint U+004B at position 1 ... not allowed
>>> idna.encode('Königsgäßchen', uts46=True)
b'xn--knigsgchen-b4a3dun'   # UTS #46 lowercases first
>>> idna.encode('UPPER.com', uts46=True)
b'upper.com'
```

**Per-label primitives:**

```python
def alabel(label: str) -> bytes: ...


# Validate + Punycode-encode one label. Pure-ASCII input that already
# validates is returned unchanged as bytes. Result gets the b"xn--" ACE
# prefix for non-ASCII input. Raises if the A-label would exceed 63 octets.


def ulabel(label: str | bytes | bytearray) -> str: ...


# Inverse of alabel. Punycode-decodes xn-- labels and REJECTS the label
# unless re-encoding reproduces the input (RFC 5891 §5.3 canonical-encoding
# check — kills "fake A-labels" such as xn---bbk).
```

**Validation helpers** (all importable from `idna` top level):

```python
def check_label(label: str | bytes | bytearray) -> None
# Full IDNA 2008 per-label gauntlet, in order: NFC (check_nfc), hyphens
# (check_hyphen_ok), no-leading-combiner (check_initial_combiner),
# per-codepoint PVALID / CONTEXTJ / CONTEXTO classification (RFC 5892),
# Bidi rule (check_bidi). Empty label -> IDNAError.

def check_bidi(label: str, check_ltr: bool = False) -> bool
# RFC 5893 Bidi rule. Skipped for LTR-only labels unless check_ltr=True.
# Violations -> IDNABidiError with codes bidi_rule_1..6 / bidi_unknown_direction.

def check_hyphen_ok(label: str) -> bool
# No leading/trailing "-" (code hyphen_start_end); no "--" in positions
# 3-4, the ACE-prefix slot (code hyphen_3_4).

def check_initial_combiner(label: str) -> bool
# Rejects labels starting with Unicode category M (code leading_combiner).

def check_nfc(label: str) -> None
# Requires Normalization Form C (code not_nfc).

def valid_contextj(label: str, pos: int) -> bool
# CONTEXTJ rules for U+200C (ZWNJ, App. A.1) and U+200D (ZWJ, App. A.2).

def valid_contexto(label: str, pos: int, exception: bool = False) -> bool
# CONTEXTO rules: U+00B7 middle dot (must sit between two "l"s), U+0375
# (next char must be Greek), U+05F3/U+05F4 (prev char must be Hebrew),
# U+30FB (label must contain Hiragana/Katakana/Han), Arabic-Indic vs
# Extended Arabic-Indic digits must not mix. `exception` is reserved/unused.

def valid_label_length(label: bytes | str) -> bool   # len <= 63
def valid_string_length(domain: bytes | str, trailing_dot: bool) -> bool
# len <= 253 (+1 if trailing dot), RFC 1035.

def uts46_remap(domain: str, std3_rules: bool = True, transitional: bool = False) -> str
# UTS #46 §4 mapping (statuses V kept, D deviation kept, M mapped,
# I ignored, else rejected with code uts46_disallowed). ASCII fast path is
# just lowercasing. std3_rules=True additionally rejects any ASCII char
# other than [a-z0-9-.] (code uts46_std3) — including mapped output such as
# U+FF01 → "!". transitional=True only warns.
```

Internal constants (useful when reading tracebacks): `_alabel_prefix =
b"xn--"`, `_max_input_length = 1024` (defensive pre-check on every entry
point, code `input_too_long`), `_max_domain_length = 253`.

**Exception hierarchy** — all derive from `IDNAError`, which itself derives
from **`UnicodeError`** (so `except UnicodeError` catches idna failures):

```python
class IDNAError(UnicodeError):
    code: str | None  # stable machine-readable rule id (see below)
    text: str | None  # label/domain being validated
    codepoint: int | None  # offending codepoint as int
    position: int | None  # 1-based index within text


class IDNABidiError(IDNAError): ...  # Bidi rule failures


class InvalidCodepoint(IDNAError): ...  # DISALLOWED / UNASSIGNED codepoint


class InvalidCodepointContext(IDNAError): ...  # bad CONTEXTJ/CONTEXTO position
```

Stable `code` values (`_ErrorCode` literal in `core.py`): `input_too_long`,
`label_too_long`, `domain_too_long`, `empty_label`, `empty_domain`, `not_nfc`,
`hyphen_3_4`, `hyphen_start_end`, `leading_combiner`, `disallowed_codepoint`,
`contextj`, `contexto`, `unknown_codepoint`, `bidi_rule_1`…`bidi_rule_6`,
`bidi_unknown_direction`, `invalid_alabel`, `non_canonical_alabel`,
`invalid_ascii`, `invalid_utf8`, `uts46_disallowed`, `uts46_std3`,
`unsupported_errors`. Message wording is explicitly **not** stable — match on
`code`, never on `str(err)`.

Observed live (this venv):

| Input | Result |
|---|---|
| `'-bad'` | `IDNAError code=hyphen_start_end` |
| `'a..b'` | `IDNAError code=empty_label` |
| `'x'*64` (single label) | `IDNAError code=label_too_long` |
| `'ex ample.com'` | `InvalidCodepoint code=disallowed_codepoint` (U+0020) |
| `'a_b.com'` (default AND `uts46=True`) | `InvalidCodepoint code=disallowed_codepoint` (U+005F) |
| emoji, e.g. `'\U0001F600.com'` | `InvalidCodepoint` — emoji are expressly prohibited by the IDNA standard |

### `idna/codec.py` — the `"idna2008"` codec

```python
codecs.register(search_function)  # at import time
```

- `search_function(name)` returns a `CodecInfo` **only for `"idna2008"`**,
  else `None`. So `"hello".encode("idna2008")` works; `"hello".encode("idna")`
  still resolves to the **stdlib IDNA-2003** codec — a different spec.
- `Codec.encode/decode`, `IncrementalEncoder` (buffers a partial trailing
  label until the next separator or `final=True`), `IncrementalDecoder`,
  `StreamWriter`, `StreamReader`. Only the `"strict"` error handler is
  supported; anything else raises `IDNAError(code="unsupported_errors")`.
- Streaming variants enforce the same 253/254-octet domain ceiling as
  `encode`/`decode`.

### `idna/compat.py` — IDNA 2003 shims

```python
def ToASCII(label: str) -> bytes: ...  # == encode(label)
def ToUnicode(label: bytes | bytearray) -> str: ...  # == decode(label)
def nameprep(s: Any) -> None: ...  # always raises NotImplementedError
```

`nameprep` (RFC 3491) does not exist in IDNA 2008; the stub exists only to
fail loudly if legacy code calls it.

### `idna/intranges.py` — range-set helpers

```python
def intranges_from_list(list_: list[int]) -> tuple[int, ...]
# Compress a codepoint list into packed (start << 32 | end) ints.

def intranges_contain(int_: int, ranges: tuple[int, ...]) -> bool
# O(log n) membership via bisect. Exported at top level as idna.intranges_contain.
```

This is how `PVALID`/`CONTEXTJ`/`CONTEXTO`, scripts, and joining types are
stored — one packed int per run instead of per codepoint.

### `idna/idnadata.py` + `uts46data.py` — generated tables

- `idnadata`: `scripts` (Greek, Han, Hebrew, Hiragana, Katakana, …),
  `joining_types`, `codepoint_classes` (`PVALID`, `CONTEXTJ` = just
  U+200C/U+200D, `CONTEXTO`), all as packed intranges. `__version__ = "18.0.0"`.
- `uts46data`: parallel arrays `uts46_starts` / `uts46_statuses` (V/M/D/I/…)
  / `uts46_replacements`, same Unicode version. ~17k lines, ~237 KB — the
  bulk of the package. Regenerated upstream via `tools/idna-data`.
- Caveat from upstream README: some checks also consult the running
  interpreter's `unicodedata`, so on an older Python a brand-new character
  can be rejected as unknown even though the tables know it. On 3.14 with
  Unicode 18.0.0 tables this is a non-issue.

### `idna/cli.py` + `__main__.py` — CLI

```bash
python -m idna [--encode|-e | --decode|-d] [--strict] [domain ...]
# No domains + piped stdin → one domain per line. No mode flag → direction
# auto-chosen from the FIRST input (contains an xn-- label ⇒ decode) and
# applied to all remaining inputs. UTS #46 mapping ON by default; --strict
# disables it. Failures go to stderr, processing continues, exit 1 if any
# conversion failed. --version prints "idna 3.20 (Unicode 18.0.0)".
```

## App usage & correctness

**Grep result: zero direct references.** No file under `src/` or `tests/`
imports `idna`, mentions it, or lists it in `pyproject.toml`. Usage is
entirely **transitive**:

```text
app (src/services/update_service.py)
 └─ httpx 0.28.1  (pyproject: httpx>=0.28.1; METADATA: Requires-Dist: idna)
     └─ idna 3.20  (httpx/_urlparse.py, httpx/_urls.py)
flet bugreport chain → requests → idna<4,>=2.5  (same installed 3.20)
```

**(a) Usage chain — what happens with a non-ASCII host.**
`httpx/_urlparse.py::normalize_host()`:

1. Bracketed `[::1]`-style literals → validated via `ipaddress`, returned raw.
2. Pure-ASCII hosts → lowercased + quoted, idna untouched.
3. Anything else → `idna.encode(host.lower()).decode("ascii")`, wrapped as:

```python
try:
    return idna.encode(host.lower()).decode("ascii")
except idna.IDNAError:
    raise InvalidURL(f"Invalid IDNA hostname: {host!r}")
```

`httpx/_urls.py` mirrors it on the read path: `URL.host` runs
`idna.decode()` for display, `URL.raw_host` stays ACE-encoded ASCII.
Default `idna.encode()` is strict IDNA 2008, **no** UTS #46 mapping — so
`Königsgäßchen`-style uppercase input fails rather than folds.

**(b) Misuse? None found.** The app never calls idna directly, never passes
`transitional=True`, never registers competing codecs, never swallows
`IDNAError` in a way that hides update failures — `UpdateService` catches
broad `Exception` and logs (`"Silent update check skipped: %s"`), returning
`None`, which is the intended silent-background-check behaviour. The console
script entry point (`idna=...`) is installed but unused. Verdict: no app-side
misuse; the transitive wiring is upstream httpx code, correct as shipped.

**(c) v1 failure walk-through.** `UPDATE_CONFIG_URL =
https://raw.githubusercontent.com/.../version.json` (plus
`GITHUB_RELEASE_URL`, `PLAYSTORE_URL` in `src/core/constants.py`) — all pure
ASCII, so idna is a pass-through that cannot fail at runtime. If a future
`version.json` ever carried a Unicode CDN host, the sequence would be:
`idna.encode` raises `InvalidCodepoint`/`IDNAError` → httpx converts to
`httpx.InvalidURL` (a plain `Exception` subclass in `httpx/_exceptions.py`)
→ caught by `UpdateService`'s `except Exception` → warning logged, `None`
returned, no update offered. Silent but safe; a deliberately hostile manifest
cannot crash the app. Note the streams screen (`streams_screen.py`) only
prefix-checks `http(s)://` and hands user stream URLs to the ffmpeg engine,
not httpx — IDN stream hosts bypass idna entirely (engine/DNS concern, not
this package).

## Considerations for v1

1. **Keep update hosts ASCII.** `raw.githubusercontent.com`, `github.com`,
   `play.google.com` are all ASCII — idna can never fire on the update path.
   If a CDN or mirror with a non-ASCII host is ever adopted, pre-convert it
   to its `xn--` ACE form at config time (e.g. `idna.encode(host)`) and store
   ASCII in `constants.py` / `version.json`.
2. **Underscores are illegal, full stop.** Verified: `idna.encode('a_b.com')`
   raises even with `uts46=True`. Internal/test hostnames with `_` will fail
   IDNA validation — use hyphens.
3. **Case is caller's job without UTS #46.** httpx lowercases before calling,
   so `GitHub.COM` works there; bare `idna.encode('UPPER.com')` raises unless
   `uts46=True`. Any future direct call must lowercase or opt into `uts46`.
4. **No action on `transitional`.** Deprecated, warns, no effect — do not pass
   it in new code; expect its removal upstream.
5. **Pinning.** `httpx` depends on unpinned `idna`; `uv.lock` currently pins
   3.20 with hashes. Keep the lock; a future idna 4.x would still satisfy
   `requests` (`<4` would NOT — requests caps at `<4`, so a 4.0 release would
   break that leg; httpx would float). Re-verify if the lock is refreshed.
6. **No API surface to wrap.** The app needs nothing beyond what httpx
   already does. If IDN display is ever shown in UI, use
   `idna.decode(host, display=True)` semantics (same as httpx) so undecodable
   `xn--` labels render as-is instead of raising.

## Gotchas

- `"idna"` ≠ `"idna2008"` in codec land: `str.encode("idna")` is stdlib
  IDNA **2003**; this package registers only `"idna2008"`. Confusing the two
  silently changes validation rules.
- `IDNAError` subclasses **`UnicodeError`**, not `ValueError` — a bare
  `except ValueError` will **miss** every idna failure. Catch `idna.IDNAError`
  (or `UnicodeError`).
- Match on `err.code`, never on the message — codes are documented stable,
  wording is not. `err.text` / `err.codepoint` / `err.position` give the
  1-based failure site for free.
- `decode()` without `display=True` raises on fake/non-canonical `xn--`
  labels (RFC 5891 §5.3 check in `ulabel`). httpx's read path can therefore
  raise on adversarial hosts — handled inside httpx, but don't call
  `idna.decode` on untrusted input without considering `display=True`.
- Length limits are in **octets of the ACE form** (63/label, 253/254/domain),
  not characters — a short-looking Unicode label can still be too long after
  Punycode expansion (`xn--` + punycode).
- Four characters count as dots when `strict=False` (`.`, U+3002, U+FF0E,
  U+FF61). Only `strict=True` splits on ASCII `.` alone.
- `std3_rules=True` without `uts46=True` is a no-op (it is only forwarded to
  `uts46_remap`). Default `encode()` therefore **allows** `_`… no wait, it
  rejects `_` via the base PVALID check anyway (verified above) — but other
  STD3-odd ASCII (uppercase, symbols) passes default `encode` and is only
  rejected under `uts46 + std3_rules`.
- Emoji domains always fail (`InvalidCodepoint`) — by standard design, and
  the industry is phasing them out. Don't try to support them.
- `uts46_remap` NFC-normalises its output; `check_label` enforces NFC on
  input. Pre-composed vs decomposed forms of the "same" label are different
  validation outcomes — normalise early if comparing user input.
