# binaryornot 0.4.4 — Complete API Reference

Ultra-lightweight pure-Python heuristic to guess whether a file is binary
or text. Port of the textiness check from Perl's `pp_fttext`, via
Eli Bendersky's Python translation, extended with a `chardet` fallback so
high-confidence decodable encodings are accepted as text.

> Scope note: there are only **three** source files (`__init__.py`,
> `check.py`, `helpers.py`). There is **no** `checks.py`, **no**
> `__main__.py` (so no CLI / `python -m binaryornot`), and **no**
> `clean_text_from_binary` — that name does not exist in this package.
> The public surface is exactly `is_binary(filename)` and
> `is_binary_string(bytes)` plus the `get_starting_chunk` / `print_as_hex`
> helpers.

## Files

3 `.py` files, no `__pycache__` counted. From RECORD (`sha256` hashes
omitted here; see dist-info RECORD):

```
binaryornot/
  __init__.py            version metadata only (no exports!)
  check.py               is_binary(filename)
  helpers.py             get_starting_chunk(), is_binary_string(),
                         print_as_hex(), _printable_ascii/_printable_high_ascii
binaryornot-0.4.4.dist-info/
  METADATA               name/version/license/deps (BSD, chardet>=3.0.2)
  DESCRIPTION.rst        long description (README + changelog)
  WHEEL                  py2.py3-none-any wheel
  top_level.txt          "binaryornot"
  metadata.json          duplicate metadata (md_version 1.1)
  INSTALLER / REQUESTED  installer stamp; REQUESTED is empty (transitive dep)
  RECORD                 11 entries (7 dist-info + 3 source + RECORD itself)
```

## Metadata

From `binaryornot-0.4.4.dist-info/METADATA` (Metadata-Version 2.0):

| Field | Value |
|---|---|
| Name / Version | `binaryornot` / `0.4.4` (2017-04-13) |
| Summary | "Ultra-lightweight pure Python package to check if a file is binary or text." |
| Author | Audrey Roy Greenfeld (`__init__.py`: `__author__ = 'Audrey Roy'`, `__email__ = 'audreyr@gmail.com'`, `__version__ = '0.4.4'`) |
| License | `BSD` (field) + classifier `License :: OSI Approved :: BSD License`. **Not** CC0/public-domain. No LICENSE file is shipped in the wheel (RECORD confirms: only `__init__.py`, `check.py`, `helpers.py` + dist-info) — the "LICENSE" ground-truth path in the brief does not exist in the installed 0.4.4 wheel. |
| Requires-Dist | `chardet (>=3.0.2)` — **verified**: venv has `chardet 5.2.0`, which satisfies the pin. This is the correct installed `chardet` version. |
| Requires-Python | **Absent** — no `Requires-Python` field in METADATA. Classifiers claim Py 2.7 / 3.3–3.6, but the code runs on 3.14 (only Py2-compat shim is a dead `if bytes is str` branch). |
| Status | `Development Status :: 5 - Production/Stable` |

Dependency chain (all verified in-venv):

```
flet-cli 1.0.0  ──Requires-Dist──▶  cookiecutter >= 2.6.0
cookiecutter 2.7.1  ──Requires-Dist──▶  binaryornot >= 0.4.4
binaryornot 0.4.4  ──Requires-Dist──▶  chardet >= 3.0.2  (installed: 5.2.0 ✓)
```

`cookiecutter/generate.py:15` does `from binaryornot.check import is_binary`
(used to decide whether a template file should be rendered as text or
copied as binary). So binaryornot is a **dev-time transitive** dependency:
it ships in the venv only because `flet-cli` (a dev/build tool, already in
`pyproject.toml` dev deps) pulls `cookiecutter`. It is **not** a direct app
dependency and is never imported by `src/`, `tests/`, or `tools/`.

## Module-by-module API

### `binaryornot/__init__.py` — version metadata only

```python
__author__ = "Audrey Roy"
__email__ = "audreyr@gmail.com"
__version__ = "0.4.4"
```

Note: it exports **nothing** — `from binaryornot import is_binary` fails;
callers must use `from binaryornot.check import is_binary`
(as cookiecutter does) or `from binaryornot.helpers import is_binary_string`.

### `binaryornot/check.py` — file-level entry point

```python
def is_binary(filename):
    """
    :param filename: File to check.
    :returns: True if it's a binary file, otherwise False.
    """
```

- Behaviour: (1) short-circuits `True` for the single known-binary
  extension list `binary_extensions = ['.pyc']` via
  `filename.endswith(ext)` — note this is a **string suffix test**, so a
  `pathlib.Path` argument raises `AttributeError` (no `.endswith`); pass
  `str`. (2) Otherwise reads the starting chunk and delegates to
  `is_binary_string`.
- Exceptions: none raised by this function itself. `IOError`/`OSError`
  from the open is swallowed inside `get_starting_chunk` (it `print(e)`s
  and returns `None`); `is_binary_string(None)` then returns `False`
  (falsy input ⇒ "text"). So a **missing/unreadable file silently reports
  `False` (text)** — check existence/permissions yourself first.
- Example:

```python
from binaryornot.check import is_binary

is_binary("subtitle.srt")  # False
is_binary("clip.mp4")  # True (chunk heuristic, not the extension list)
is_binary("module.pyc")  # True (extension short-circuit)
```

### `binaryornot/helpers.py` — the heuristic

```python
def get_starting_chunk(filename, length=1024):
    """
    :param filename: File to open and get the first little chunk of.
    :param length: Number of bytes to read, default 1024.
    :returns: Starting chunk of bytes.
    """


def is_binary_string(bytes_to_check):
    """
    :param bytes: A chunk of bytes to check.
    :returns: True if appears to be a binary, otherwise False.
    """


def print_as_hex(s):
    """Print a string as hex bytes."""
```

Constants:

- No `CHECK_BYTES` / `CHECK_LEN` names exist — the sample size is the
  `length=1024` default parameter of `get_starting_chunk`. Pass a larger
  `length` for bigger samples, or call `is_binary_string` on your own
  bytes to skip the file read (and the 1024 cap) entirely.
- `_printable_ascii = b'\n\r\t\f\b' + bytes(range(32, 127))` — the five
  permitted control chars plus printable ASCII.
- `_printable_high_ascii = bytes(range(127, 256))` — everything ≥ 0x7F,
  i.e. "high" bytes including DEL.

How the 1024-sample heuristic works (`is_binary_string`), step by step:

1. **Empty ⇒ text.** `if not bytes_to_check: return False`. Note this also
   swallows `None` (the unreadable-file path from `get_starting_chunk`).
2. **Ratio 1 — control chars.** Strip `_printable_ascii`;
   `nontext_ratio1 = len(remainder) / len(chunk)`.
3. **Ratio 2 — high bytes.** Strip `_printable_high_ascii`;
   `nontext_ratio2 = len(remainder) / len(chunk)` — because *all* bytes
   ≥ 0x7F are stripped, `nontext_ratio2` is actually the fraction of LOW
   non-printable bytes… in practice it measures how much of the chunk is
   neither printable-ASCII nor high-byte, i.e. C0/C1 controls. (The
   variable naming/docstring frame it as "high ASCII" from the original
   Perl code, but with this `_printable_high_ascii` table it functions as
   a second control-char ratio.)
4. **Likely-binary vote:**
   `is_likely_binary = (ratio1 > 0.3 and ratio2 < 0.05) or (ratio1 > 0.8 and ratio2 > 0.8)`.
5. **chardet fallback.** `chardet.detect(chunk)`; if `confidence > 0.9`
   and `encoding != 'ascii'`, try decoding with the detected encoding —
   success sets `decodable_as_unicode = True` (`LookupError` /
   `UnicodeDecodeError` are caught and logged at debug level).
6. **Verdict:** likely-binary **and** not decodable ⇒ `True`; likely-binary
   but decodable ⇒ `False` (text wins); not-likely-binary but decodable ⇒
   `False`; not-likely-binary and not decodable ⇒ `True` only if the chunk
   contains `b'\x00'` or `b'\xff'` (NUL/0xFF check runs **last**, only on
   this path), else `False`.

Example (bytes-level, no file I/O):

```python
from binaryornot.helpers import is_binary_string, get_starting_chunk

is_binary_string(b"WEBVTT\n\n00:00.000 --> 00:01.000\nHi\n")  # False
is_binary_string(bytes.fromhex("89504E470D0A1A0A") * 100)  # True
chunk = get_starting_chunk("clip.mp4", length=4096)  # bigger sample
is_binary_string(chunk)
```

Logging: `check.py` and `helpers.py` both log decisions at `DEBUG` via
module loggers (`binaryornot.check`, `binaryornot.helpers`); enable with
`logging.basicConfig(level=logging.DEBUG)` to see `nontext_ratio1/2`,
`detected_encoding`, and the decodability outcome.

No CLI: there is no `__main__.py`, no `console_scripts` entry point, and
`python -m binaryornot` fails. (The sibling `chardet` package *does* ship
a `chardetect` CLI; do not confuse the two.)

## App usage & correctness

(a) **Chain.** `pyproject.toml` declares `flet-cli>=1.0.0` (dev/build tool)
→ `flet-cli 1.0.0` requires `cookiecutter>=2.6.0` → `cookiecutter 2.7.1`
requires `binaryornot>=0.4.4` → `binaryornot 0.4.4` requires
`chardet>=3.0.2` (venv: 5.2.0 ✓). Grep over `src/`, `tests/`, `tools/`
for `binaryornot|is_binary|binary_or_not` returns **zero hits** — the app
never imports it. The single in-venv consumer is cookiecutter's template
renderer (`generate.py:15`). Correctness of the chain: pins all resolve,
no version conflicts.

(b) **Misuse.** None — unused code cannot be misused. Two latent traps
worth knowing if it is ever adopted: (1) `is_binary` takes a `str` path
only — passing `pathlib.Path` crashes on `.endswith` (wrap with `str()`);
(2) missing files return `False` instead of raising, so a typo'd path
looks like a text file.

(c) **Underuse — is it worth adopting for v1?** Candidate call sites in
this media app:

- `src/core/engine_probe.py:195` — `path.read_text(encoding="utf-8")` on
  a probe-cache JSON file. If the cache is corrupt/binary, this raises
  `UnicodeDecodeError` (unhandled at that line — only `json.loads` errors
  are conventionally expected). A binary pre-check could route to
  cache-invalidate instead of crashing.
- `src/services/storage_service.py:65` — `Path(path).open(encoding="utf-8")`
  with a broad `except (OSError, ValueError)` that already converts decode
  failures into a warning + `{}` fallback, so the binary-crash case is
  already handled gracefully there.
- Future user-file intake (subtitle/playlist/probe sidecars dropped onto
  the app): binary-vs-text triage before choosing a media parser vs a
  text parser.

Recommendation: **do NOT add binaryornot as a direct dependency; prefer
`charset-normalizer`'s `is_binary()` (already installed, 3.5.1)** if a
binary guard is ever needed. Rationale: (1) binaryornot 0.4.4 is
effectively unmaintained (last release 2017, `Requires-Python` absent,
dead Py2 branches, swallows `IOError` with a `print`); (2) its heuristic
delegates to the legacy `chardet` engine while the app's modern stack
(`requests`/`httpx` via flet) already standardises on charset-normalizer;
(3) `charset_normalizer.is_binary(fp_or_path_or_payload, steps=5,
chunk_size=512, threshold=0.20, ...)` accepts `str | PathLike | BinaryIO |
bytes` (no `str()`-wrapping trap), samples `steps × chunk_size` bytes
with a tunable threshold, and is actively maintained. The marginal benefit
of binaryornot over that is nil, and adding a direct pin would freeze a
2017 API into v1 for no gain.

## Underused APIs to adopt

None from binaryornot — deliberately. If the v1 hardening pass wants a
binary guard at `engine_probe.py:195` (probe-cache read) or at future
file-drop intake, adopt this instead (already installed, no new pin):

```python
from charset_normalizer import is_binary  # 3.5.1, in-venv

if is_binary(path):  # accepts str | PathLike | bytes | file object
    ...  # invalidate cache / reject as non-text sidecar
else:
    payload = json.loads(path.read_text(encoding="utf-8"))
```

Only if the team insists on zero-new-imports conservatism: `from
binaryornot.check import is_binary` works today via the transitive pin,
but that relies on flet-cli → cookiecutter keeping the dependency, which
could vanish in any minor release — do not build v1 features on it.

## Gotchas

1. **No `Path` support.** `is_binary(Path(...))` raises
   `AttributeError: 'PosixPath'/'WindowsPath' object has no attribute
   'endswith'`. Always pass `str(path)`.
2. **Missing/unreadable files report "text".** `get_starting_chunk`
   catches `IOError`, `print()`s it, returns `None`; `is_binary_string`
   treats falsy input as text. Verify `Path.is_file()` first.
3. **Only 1024 bytes are sampled** by default — content past the first KB
   is invisible to `is_binary()`. A mostly-text file with a binary
   payload appended later still reads as text. Raise `length` or use
   `is_binary_string` on a larger/whole-file read for sidecar triage.
4. **UTF-16/32 text without BOM misdetects as binary.** UTF-16LE ASCII
   text is ~50% NUL bytes; the control-char ratio exceeds 0.3 and chardet
   on a 1024-byte sample may not reach 0.9 confidence, so the NUL check
   fires `True`. Same for any text containing literal NULs when chardet is
   unsure. Subtitle/playlist files are near-always UTF-8/ASCII so this is
   a corner case, but probe JSON written by third-party tools in UTF-16
   would trip it.
5. **Small files are noisy.** Ratios over a handful of bytes swing wildly;
   a 3-byte file with one control char is 33% "nontext". Do not trust the
   verdict on tiny inputs without a size floor.
6. **`b'\xff'` alone can flip the verdict** on the not-likely-binary path
   (e.g. a lone 0xFF byte in an otherwise-text chunk when chardet
   confidence is low).
7. **Legacy `chardet` engine + `print()` on errors.** Every
   `is_binary_string` call runs full chardet detection (slow-ish per
   file; fine for occasional sidecar checks, not for directory scans),
   and I/O errors go to stdout instead of logging/exceptions.
8. **Transitive-only presence.** It is in the venv solely via
   flet-cli → cookiecutter (build tooling). If flet-cli ever drops
   cookiecutter, `import binaryornot` breaks at runtime. Never rely on it
   without a direct pin — and per the recommendation, prefer
   charset-normalizer instead.
