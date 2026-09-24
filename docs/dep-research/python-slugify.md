# python-slugify 9.1.0 — Complete API Reference

Import name: `slugify`. Distribution name: `python-slugify`. Version: **9.1.0**.
Role in this venv: **transitive-only** dependency — nothing in `src/`, `tests/`, or
`tools/` imports it (see "App usage"). Boundary: transliteration backend
`text_unidecode` is covered by a separate agent; this report covers `slugify` only
and notes the boundary where behavior crosses it.

## Files

Package dir: `.venv/Lib/site-packages/slugify/` — 7 files (no `__pycache__` counted):

| File | Purpose |
|---|---|
| `__init__.py` | Re-exports: `from .special import *`, `from .slugify import *`, plus 8 dunder metadata names from `__version__` |
| `slugify.py` | Public `slugify()` dispatcher + modern pipeline (`_modern_slugify`, `_modern_truncate`); `__all__ = ['slugify', 'smart_truncate', 'Backend', 'ReplacementStage', 'Algorithm']` |
| `_legacy.py` | **Frozen** legacy pipeline + public `smart_truncate()`; docstring forbids behavior changes (2,688-case differential baseline) |
| `special.py` | Optional locale substitution lists: `CYRILLIC`, `GERMAN`, `GREEK`, `PRE_TRANSLATIONS`; helper `add_uppercase_char()` |
| `__main__.py` | `python -m slugify` CLI + `main()` entry point |
| `__version__.py` | `__title__='python-slugify'`, `__version__='9.1.0'`, author Val Neekman, `__license__='SPDX-License-Identifier: MIT'` |
| `py.typed` | Empty marker — package ships inline types |

Dist-info: `.venv/Lib/site-packages/python_slugify-9.1.0.dist-info/` contains
`METADATA`, `RECORD`, `entry_points.txt`, `WHEEL`, `INSTALLER` (content `uv`),
`REQUESTED` (empty — not a direct install), `top_level.txt` (`slugify`),
`licenses/LICENSE`. RECORD also installs `../../Scripts/slugify.exe` (Windows
console script, 47 KB).

## Metadata

- **Name / Version:** `python-slugify` 9.1.0. `Requires-Python: >=3.10`.
  Classifiers cover CPython 3.10–3.14 (matches app's Python 3.14).
- **License:** `License-Expression: MIT` (own code). METADATA long description
  warns dependency licenses differ: text-unidecode offers Artistic/GPL,
  Unidecode is GPL, AnyASCII is ISC — evaluate before bundling decisions.
- **Hard pin (base install):** `Requires-Dist: text-unidecode>=1.3` (unconditional).
- **Extras (opt-in, additive — they never remove text-unidecode):**
  - `[unidecode]` → `Unidecode>=1.1.1`
  - `[anyascii]` → `anyascii>=0.3.2`
  - There is **no** `[unicode]` extra in 9.x (older docs mention it; verify:
    METADATA lists only `unidecode` and `anyascii` in `Provides-Extra`).
  - There is **no** `pyuca` extra. There is **no** dependency-free install.
- **Entry points** (`entry_points.txt`): one console script —
  `slugify = slugify.__main__:main`.
- **uv.lock:** `python-slugify 9.1.0` with `dependencies = [{ name = "text-unidecode" }]`,
  sdist + wheel hashes pinned.

## Module-by-module API

### `slugify.slugify()` — full signature (identical in `slugify.py` dispatcher and `_legacy.slugify`)

```python
def slugify(
    text: str | bytes | bytearray,
    entities: bool = True,
    decimal: bool = True,
    hexadecimal: bool = True,
    max_length: int = 0,
    word_boundary: bool = False,
    separator: str = DEFAULT_SEPARATOR,   # '-'
    save_order: bool = False,
    stopwords: Iterable[str] = (),
    regex_pattern: re.Pattern[str] | str | None = None,
    lowercase: bool = True,
    replacements: Iterable[Iterable[str]] = (),
    allow_unicode: bool = False,
    *,
    replacement_stage: ReplacementStage = 'both',  # 'both' | 'pre' | 'post'
    backend: Backend = 'auto',                     # 'auto' | 'text-unidecode' | 'unidecode' | 'anyascii'
    algorithm: Algorithm = 'legacy',               # 'legacy' | 'modern' (dispatcher only)
) -> str
```

Notes on the assignment's guessed kwargs: there is **no** `unique` parameter
(slugs are never deduplicated — caller owns uniqueness). `AUTO_TRUNCATE` /
`LOWERCASE` module constants do **not** exist; the only module constant is
`DEFAULT_SEPARATOR = '-'` (also imported by cookiecutter). Positional order of
the first 13 params is frozen for backward compat; the last three are
keyword-only.

Parameter semantics (from METADATA long description + source):

- `text`: `str`, or UTF-8 `bytes`/`bytearray` (invalid bytes ignored). Anything
  else raises `TypeError`.
- `entities` / `decimal` / `hexadecimal`: independently decode named HTML
  entities (`&eacute;`), decimal refs (`&#233;`), hex refs (`&#xE9;`).
  Legacy decodes **after** transliteration with all-or-nothing per-kind
  substitution; modern decodes **before** transliteration and handles invalid
  refs independently (surrogates `U+D800–U+DFFF` left as-is). Legacy hex
  accepts lowercase `x` only; modern accepts `x` and `X`.
- `max_length`: `0` or negative = unlimited. **Legacy** budgets internal dashes
  *before* separator mapping, so a wide separator can overshoot the limit;
  **modern** budgets final emitted characters including delimiters. Modern
  rejects `bool`/`non-int` with `TypeError` (legacy silently treated `True` as 1).
- `word_boundary`: prefer whole words; shorter later words can still fill the
  budget (`slugify('one two three four', max_length=12, word_boundary=True)`
  → `'one-two-four'`). If no word fits, falls back to a hard cut.
- `save_order`: with `word_boundary`, stop at the first oversized word instead
  of skipping it (`... save_order=True` → `'one-two'`).
- `separator`: literal emitted delimiter; may be `''` or multi-char.
  Legacy quirk: existing `-` also map to it, and truncation is budgeted in
  dashes (see above). Empty separator + `smart_truncate` raises `ValueError`
  only via the public legacy helper path.
- `stopwords`: whole normalized dash-separated tokens removed post-cleanup.
  Case-insensitive when `lowercase=True`; stopwords are **not** transliterated.
  Legacy consumes iterators across passes; modern snapshots once.
- `regex_pattern`: matches **disallowed** characters (not allowed ones),
  overriding the default filter. Empty string keeps historical default behavior.
- `lowercase`: `str.lower()`; `False` preserves case.
- `replacements`: ordered `(old, new)` literal rules. Default `both` = two
  passes (before AND after cleanup — so `('a','aa')` on `'a'` yields `'aaaa'`);
  `'pre'` runs once before normalization; `'post'` runs once after cleanup and
  stopword removal and is **not re-sanitized** (can intentionally reintroduce
  punctuation — never treat output as a security sanitizer).
- `allow_unicode`: NFKC normalization, **no transliteration**;
  `slugify('影師嗎', allow_unicode=True) == '影師嗎'`. `backend` is still
  validated but ignored for transliteration.
- `backend`: `'auto'` (default) prefers installed Unidecode, falls back to
  text-unidecode; explicit choices never fall back (`ModuleNotFoundError` if
  missing). Imports are lazy. Backends disagree: `'影師嗎'` → `'ying-shi-ma'`
  (text-unidecode/Unidecode) vs `'yingshima'` (AnyASCII) — pin the backend for
  persisted identifiers.
- `algorithm`: `'legacy'` default, frozen forever; `'modern'` opts into early
  entity decoding, snapshotted rules, stable stopword membership, final-length
  budgeting, strict type validation. Unknown value → `ValueError`. CLI default
  is also legacy.

Examples (verified against METADATA + source):

```python
from slugify import slugify

slugify("C'est déjà l'été.")  # 'c-est-deja-l-ete'
slugify("影師嗎", backend="text-unidecode")  # 'ying-shi-ma'
slugify("影師嗎", allow_unicode=True)  # '影師嗎'
slugify("a&#39;b")  # 'ab' (legacy default)
slugify("a&#39;b", algorithm="modern")  # 'a-b'
slugify("ÜBER", replacements=GERMAN, replacement_stage="pre")  # 'ueber'
slugify("Café au lait — 100% ✔", max_length=20, word_boundary=True)
```

Empty/whitespace/fully-filtered input can return `''` — caller picks a fallback.

### `smart_truncate()` (public, in `_legacy.py`, re-exported)

```python
def smart_truncate(string: str, max_length: int = 0,
                   word_boundary: bool = False, separator: str = " ",
                   save_order: bool = False) -> str
```

Legacy behavior preserved: `strip(separator)` strips a **charset**; `0` =
unlimited; negatives keep slicing semantics; empty separator raises
`ValueError`. Modern `slugify()` does NOT use it (private `_modern_truncate`).

### `special.py` — locale substitution lists

`CYRILLIC` (ё→e, я→ya, х→h, у→y, щ→sch, ю→u), `GERMAN` (ä→ae, ö→oe, ü→ue),
`GREEK` (χ→ch, Ξ→X, ϒ→Y, υ/ύ/ϋ/ΰ→y), combined `PRE_TRANSLATIONS`.
`add_uppercase_char()` derives uppercase variants in place. These are **opt-in**
`replacements=` arguments, never applied automatically.

### `__main__.py` — CLI behavior

`slugify TEXT...` or `echo TEXT | python -m slugify --stdin`
(mutually exclusive; empty input → `''`). Flags mirror the API:
`--no-entities/--no-decimal/--no-hexadecimal`, `--max-length N`,
`--word-boundary`, `--save-order`, `--separator S`, `--stopwords w...`,
`--regex-pattern P`, `--no-lowercase`, `--replacements OLD->NEW...`,
`--allow-unicode`, plus `--algorithm legacy|modern`, `--backend ...`,
`--replacement-stage ...`. Multi-valued options need `--` before positional
text: `slugify --stopwords the in a hurry -- the quick brown fox ...`.
Exits `-1` on `KeyboardInterrupt`.

## App usage & correctness (filename sanitization audit)

**Dependency chain (verified):**

```
python-slugify 9.1.0  ←  cookiecutter 2.7.1 (Requires-Dist: python-slugify>=4.0.0)
                      ←  flet-cli 1.0.0 dev tooling (`flet create` scaffolding)
```

- `cookiecutter/extensions.py` does `from slugify import slugify as pyslugify`
  + `from slugify.slugify import DEFAULT_SEPARATOR` for its Jinja2 `slugify`
  filter. No app runtime code touches either.
- `pyproject.toml` has **no** mention of slugify/cookiecutter (grep clean);
  `uv.lock` carries both as locked transitive packages. `REQUESTED` is empty:
  nobody asked for slugify directly.
- (a) **Chain:** transitive dev-scaffolding dep only. (b) **Misuse:** none —
  zero imports in `src`/`tests`/`tools`. (c) **Underuse:** yes, and it matters —
  see below. Removing it is NOT recommended (it is flet-cli's transitive dep;
  pruning belongs to upstream).

**How the app builds output filenames today (all 8 sites hand-roll, no sanitizer):**

| Site | Code (representative) |
|---|---|
| convert | `f"{Path(media_path).stem}_converted.{container_fmt}"` |
| cut | `f"{Path(media_path).stem}_trimmed{ext}"` |
| compress | `f"{stem}_compressed_{int(target_mb)}MB.mp4"` |
| extract (audio/stream/frames/gif) | `f"{stem}_audio.{fmt}"`, `f"{stem}.{ext}"`, `f"{stem}_frames/"`, `f"{stem}_animated.gif"` |
| filters | `f"{stem}_filtered{ext}"` |
| audio master | `f"{stem}_mastered.{audio_format}"` |
| join / capture | timestamp-based, already safe (`joined_{epoch}.mp4`, `photo_{epoch}.jpg`) |
| streams | `f"stream_{ts}.{ext}"` — safe |

The six `stem`-derived sites pass the **raw source stem** straight into
`get_temp_dir() / out_name`. Verdict: **works today by luck, not by design —
mildly buggy, worth fixing for v1:**

1. **Windows reserved chars** (`<>:"/\|?*`): harmless in the POSIX-style temp
   tier, but `save_media_file()` forwards the same `name` to the native
   `save_file` dialog AND the `Downloads/` fallback copy — a source file named
   e.g. `Q&A: final?.mp4` produces an unsaveable/shortened name on Windows.
2. **Reserved basenames** (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`,
   `LPT1`–`LPT9`) and **trailing dots/spaces**: stripped or rejected by Win32 —
   slugify alone does not fix these either; needs the extra guard below.
3. **Unicode/emoji/control chars** in source names (common from mobile shares):
   pass through raw; fine on Android, lossy on some Windows locales.
4. **Length**: no cap; deep temp paths + long stems can exceed `MAX_PATH`
   edge cases on Windows.
5. The **only** sanitization in the codebase is `cache_bytes()`
   (`src/core/storage_paths.py`): `ch if ch.isalnum() or ch in "._-"
  else "_"` — a per-char allowlist with no reserved-name check, no length cap,
  no case/whitespace normalization. Hand-rolled and weaker than one `slugify()`
  call; it should delegate to the shared helper.

**History keys** (`main.py` `_persist_history`, `storage.get/set("history_jobs")`)
store full `output_path` strings, not slugs — no slugify interaction, no change needed.

## Underused APIs to adopt

v1 recommendation: add ONE helper (e.g. `core/storage_paths.py::safe_output_name()`)
and route all six stem-derived builders + `cache_bytes` through it:

```python
from slugify import slugify
from pathlib import Path

WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_output_name(stem: str, suffix: str, ext: str, max_stem: int = 80) -> str:
    base = (
        slugify(stem, separator="_", max_length=max_stem, word_boundary=True, save_order=True)
        or "media"
    )
    if base.upper() in WINDOWS_RESERVED:
        base = f"_{base}"
    return f"{base}{suffix}{ext}".rstrip(" .")  # trailing dots/spaces are illegal on Win32
```

Why this shape: `separator="_"` keeps `name_stem` + `_converted`-style suffixes
readable; `max_length` + `word_boundary` + `save_order` caps length without
splitting words; `or "media"` covers slugify's empty-string case; the reserved
set + trailing-strip covers what slugify explicitly does **not** promise
(its docs: "not guaranteed filesystem-safe on every OS"). Keep default
`algorithm='legacy'` + `backend='auto'` (text-unidecode is already installed)
for deterministic output; do NOT set `allow_unicode=True` for filenames.
`GERMAN`/`CYRILLIC` pre-translations are unnecessary — the backend already
transliterates. `smart_truncate`, `stopwords`, `replacements`, and the CLI are
not needed by the app.

## Gotchas

1. **Not a filename sanitizer by itself.** Upstream docs say slugs are not
   guaranteed unique, filesystem-safe, or URL-safe. Reserved names, trailing
   dots/spaces, collisions, and path traversal (`../` — though `Path.stem`
   already strips directories) remain the caller's job.
2. **Backend drift changes persisted strings.** `auto` prefers Unidecode when
   installed; AnyASCII disagrees (`yingshima` vs `ying-shi-ma`). History v1
   stores paths, not slugs, so drift is cosmetic — but pin backend if slugs
   ever become keys.
3. **`max_length` semantics differ by algorithm.** Legacy can overshoot with
   wide separators; modern budgets final characters. The helper above relies on
   modern-correct budgeting only if `algorithm='modern'` is passed; with legacy
   + single-char `_` separator the difference is nil.
4. **Double-pass `replacements` footgun.** Default `both` applies rules twice
   (`('a','aa')` → `'aaaa'`); irrelevant unless custom rules are added — don't add any.
5. **`regex_pattern` matches disallowed chars** (inverse of most sanitizers);
   default pattern is correct for filenames — leave it alone.
6. **License asymmetry.** Own code MIT, but base dep text-unidecode is
   Artistic/GPL-optional and optional Unidecode is GPL — fine for server-side
   use, but confirm with the mobile-bundling story before shipping new backends.
7. **Do not "clean up" the transitive dep.** It belongs to `flet-cli` via
   `cookiecutter`; removing it from the lock breaks scaffolding, not the app.
