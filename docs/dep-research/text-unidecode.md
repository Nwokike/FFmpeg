# text-unidecode 1.3 — Complete API Reference

ASCII transliteration (basic port of Perl `Text::Unidecode`). Import name `text_unidecode`.
Verified against the installed wheel in `.venv/Lib/site-packages/` (Python 3.14 venv, installer `uv`).

## Files

Package layout (there is **no** top-level `text_unidecode.py`, **no** `__main__.py`, **no** `codes.py`):

| Path (under `.venv/Lib/site-packages/`) | Size | Notes |
|---|---|---|
| `text_unidecode/__init__.py` | 484 bytes, 22 lines | Entire implementation (see below) |
| `text_unidecode/data.bin` | 311,077 bytes | Transliteration table, UTF-8, entries separated by `\x00` |
| `text_unidecode/__pycache__/__init__.cpython-314.pyc` | — | Imported fine on 3.14 |
| `text_unidecode-1.3.dist-info/` (8 files) | — | METADATA, RECORD, LICENSE.txt, DESCRIPTION.rst, WHEEL, top_level.txt (`text_unidecode`), metadata.json, INSTALLER (`uv`), REQUESTED |

`data.bin` structure: `pkgutil.get_data(__name__, 'data.bin').decode('utf8').split('\x00')`
produces a flat list `_replaces` of **65,535 entries** (verified at runtime), i.e. one entry
per codepoint U+0001–U+FFFF, indexed `codepoint - 1`. Head of the binary is the ASCII
identity range (`A`→`A`, …); entries from U+0080 on are transliterations, many with
trailing spaces (e.g. U+4E1C 东 → `'Dong '`). There are no `ONE_TO_ONE` / `ONE_TO_MANY`
dicts — that two-table design belongs to the full `Unidecode` package, not here.
Codepoints above U+FFFF (astral plane: emoji, some CJK-Ext, historic scripts) have **no**
entry.

## Metadata

- **Name / Version:** `text-unidecode` 1.3. Summary: "The most basic Text::Unidecode port". Author: Mikhail Korobov (kmike84@gmail.com). Home: https://github.com/kmike/text-unidecode/
- **Dependencies / pins:** none. `Requires-Dist` is absent; zero runtime deps.
- **`Requires-Python`:** absent (not declared). Classifiers claim 2.7 and 3.4–3.7, but the
  package imports and runs on 3.14 (22-line, syntax-stable code).
- **License — dual, Artistic-or-GPL (NOT BSD):** `License: Artistic License` with
  classifiers for Artistic License, GPL, and GPLv2+. `LICENSE.txt` opens with
  "you can redistribute it and/or modify it under the terms of either: GPL or GPLv2+,
  or Artistic License" followed by the full Perl Artistic License 1.0 text. Practical
  reading for v1.0: use/aggregate under the Artistic terms (clause 8 expressly permits
  embedding/aggregation in larger distributions); the GPL alternative is what obliges
  copyleft, so do not elect it. METADATA's own docstring admits the trade-off:
  "If you're OK with GPL-only, use unidecode (it has better memory usage and better
  transliteration quality)."
- **Wheel:** pure-Python `py2/py3-none-any`, built with `bdist_wheel 0.29.0`.

## Module-by-module API

One module only: `text_unidecode/__init__.py` (complete source, 22 lines):

```python
_replaces = pkgutil.get_data(__name__, "data.bin").decode("utf8").split("\x00")


def unidecode(txt):
    chars = []
    for ch in txt:
        codepoint = ord(ch)
        if not codepoint:
            chars.append("\x00")
            continue
        try:
            chars.append(_replaces[codepoint - 1])
        except IndexError:
            pass
    return "".join(chars)
```

### `unidecode(txt)` — full signature, semantics, edge cases

- **Exact signature: `unidecode(txt)` — a single positional parameter. There is NO
  `errors` parameter** (no `'replace'`/`'ignore'`/`'strict'` modes). Calling
  `unidecode(s, errors='replace')` raises `TypeError`. Error handling is hard-wired:
  unknown codepoints are silently **dropped**.
- **Input:** `str`. `bytes` input raises `TypeError: ord() expected string of length 1,
  but int found` (iterating bytes yields ints) — decode to `str` first.
- **Returns:** always `str` (possibly `''`).
- **Per-character rules:** ASCII passes through unchanged; NUL (`\x00`) is *preserved*
  in the output (strip it before using results in paths); codepoints U+0001–U+FFFF map
  through `_replaces` (unknown ones contribute `''`); codepoints above U+FFFF are
  silently skipped (verified: `'emoji \U0001F600 test'` → `'emoji  test'`).
- **No exceptions** for unmapped characters by design; pure function, no global state,
  thread-safe, deterministic. Import cost is one ~311 KB read + 65k-entry split.
- **No CLI:** there is no `__main__.py`, so `python -m text_unidecode` fails
  (`No module named text_unidecode.__main__`). No argv/stdin modes exist.

### Verified transliteration examples (all run against the venv)

| Input | Output | Note |
|---|---|---|
| `"Křišťálově čistá"` | `'Kristalove cista'` | Czech diacritics folded |
| `"какой-то текст"` (METADATA doc example) | `'kakoi-to tekst'` | Cyrillic |
| `"东"` | `'Dong '` | **trailing space** — `.strip()` required |
| `"北京 Beijing 中国"` | `'Bei Jing  Beijing Zhong Guo '` | Pinyin-ish readings, doubled spaces |
| `"日本語タイトル"` | `'Ri Ben Yu taitoru'` | Japanese → readings, not meaning |
| `"مرحبا بالعالم"` | `'mrHb bl`lm'` | Arabic is lossy, barely readable |
| `"Beyoncé — naïve façade"` | `'Beyonce -- naive facade'` | Em-dash → `--` |
| `"François Müller Straße"` | `'Francois Muller Strasse'` | `ß` → `ss`, `Œ` → `OE` |
| `"Ångström Øre Æsop Œuvre ẞ ß"` | `'Angstrom Ore AEsop OEuvre Ss ss'` | Ligature expansions |
| `"®©™°±µ¶"` | `'(r)(c)tmdeg+-uP'` | Symbol approximations |
| `"ﬁ ligature –—…‘’"` | `"fi ligature ---...''"` | `ﬁ` → `fi` |
| `"plain ascii stays"` | unchanged | Identity |
| `""` | `""` | Empty in/out |
| `chr(0)` | `'\x00'` | NUL preserved — strip for paths |

## App usage & correctness

(a) **Dependency chain (all verified via installed METADATAs):**
`flet-cli 1.0.0` → `Requires-Dist: cookiecutter>=2.6.0` → `cookiecutter 2.7.1` →
`Requires-Dist: python-slugify>=4.0.0` → `python-slugify 9.1.0` →
`Requires-Dist: text-unidecode>=1.3` (**mandatory**; full `Unidecode>=1.1.1` is only
under the `unidecode` extra). `cookiecutter/extensions.py` imports `pyslugify` for its
Jinja `slugify` filter (used when `flet create` renders templates). `slugify 9.1.0`
`_transliterate()` with the default `backend='auto'` tries `import unidecode`, falling
back to `import text_unidecode` — and the full `Unidecode` package (like `anyascii`)
is **not installed** in this venv, so the live transliteration backend today **is**
`text_unidecode`. Note: `flet-cli` sits in the `dev` dependency group in
`pyproject.toml`, so this chain is currently dev-tooling-only, and neither `slugify`
nor `text_unidecode` appears in `dependencies` — grep for `slugify|unidecode` across
`src`, `tests`, `tools/` returns **zero hits**.

(b) **Misuse:** none — the app never calls it directly.

(c) **Underuse — the v1 filename-safety gap.** Six screens build output paths from the
raw media stem with no transliteration: `src/screens/audio_screen.py:52`
(`{stem}_mastered.{fmt}`), `extract_screen.py:55` (`{stem}_audio/subtitles`),
...[truncated 3010 chars]