# charset-normalizer 3.5.1 — Complete API Reference

> Import name: `charset_normalizer`. Universal charset detector (MIT). Pure Python + Cython
> speedups (`md`/`cd` ship as both `.py` and compiled `.pyd` in this venv — SpeedUp ON).
> Zero runtime dependencies. Python `>=3.7` (3.14 running here).

## Files

Package dir: `.venv/Lib/site-packages/charset_normalizer/` (11 `.py` files; no `detect.py`,
no `md_common.py`, no `normalizer.py` — follow this actual layout):

| File | Role |
|---|---|
| `__init__.py` | Public exports: `from_bytes`, `from_fp`, `from_path`, `is_binary`, `detect`, `CharsetMatch`, `CharsetMatches`, `set_logging_handler`, `__version__`/`VERSION`; installs `NullHandler` on `charset_normalizer` logger |
| `api.py` | Detection entry points (`from_bytes`, `from_fp`, `from_path`, `is_binary`) |
| `models.py` | `CharsetMatch`, `CharsetMatches`, `CliDetectionResult`, `CoherenceMatch(es)` aliases |
| `legacy.py` | `detect()` — chardet-compatible shim over `from_bytes().best()` |
| `md.py` (+ `md.cp314-win_amd64.pyd`) | Mess/chaos detector: `mess_ratio()` + 10 `MessDetectorPlugin`s + `CharInfo` cache |
| `cd.py` (+ `cd.cp314-win_amd64.pyd`) | Coherence/language detector: `coherence_ratio()` + frequency tables consumers |
| `utils.py` | Char classifiers, BOM/SIG + PEP263 helpers, `iana_name`, `cut_sequence_chunks`, `set_logging_handler` |
| `constant.py` | `ENCODING_MARKS`, `IANA_SUPPORTED` (99), `IANA_SUPPORTED_SIMILAR`, `CHARDET_CORRESPONDENCE`, `FREQUENCIES` (~50 languages), `TOO_SMALL_SEQUENCE=32`, `TOO_BIG_SEQUENCE=10_000_000`, `TRACE=5` |
| `cli/__main__.py` | `cli_detect()` + `query_yes_no()` + backported `FileType("rb")` |
| `cli/__init__.py` | Re-exports `cli_detect`, `query_yes_no` |
| `__main__.py` | `python -m charset_normalizer` → `cli_detect()` |
| `version.py` | `__version__ = "3.5.1"`, `VERSION = ['3','5','1']` |
| `py.typed` | PEP 561 marker (fully typed package) |

`__pycache__/` holds only bytecode — skipped.

## Metadata

From `charset_normalizer-3.5.1.dist-info/METADATA` (+ `entry_points.txt`, `RECORD`, `WHEEL`):

- **Name/Version:** `charset-normalizer 3.5.1` (sdist+wheel hashes pinned in `uv.lock`; release 2026-08-15).
- **License:** MIT (`licenses/LICENSE`, Tahri Ahmed R.). Summary: *"The Real First Universal
  Charset Detector. Open, modern and actively maintained alternative to Chardet."*
- **Requires-Python:** `>=3.7`. **Requires-Dist:** none (no runtime deps). **Provides-Extra:**
  `unicode-backport` only.
- **Entry point** (`entry_points.txt`, `[console_scripts]`): `normalizer = charset_normalizer.cli:cli_detect`
  (installed as `Scripts/normalizer.exe` per `RECORD`). Also runnable as
  `python -m charset_normalizer` and `python -m charset_normalizer.cli`.
- **3.5.x changelog highlights:** Cython replaces mypyc for `md`/`cd` (abi3 wheels, no hidden
  imports for PyInstaller); multibyte-first codec ordering; deferred single-byte full decode;
  definitive-match + language-family skips + same-family cap (perf); empty-payload logging fix;
  `CharsetMatch == non-alias-str` no longer raises; `multi_byte_usage` returns `0.0` on empty.

## Module-by-module API

### `api.py` — detection entry points

```python
from charset_normalizer import from_bytes, from_fp, from_path, is_binary

from_bytes(
    sequences: bytes | bytearray,
    steps: int = 5, chunk_size: int = 512,
    threshold: float = 0.2,                 # max tolerable mean chaos 0..1
    cp_isolation: list[str] | None = None,  # restrict candidates (debug/focus)
    cp_exclusion: list[str] | None = None,  # exclude candidates
    preemptive_behaviour: bool = True,      # honor BOM/SIG + PEP263/charset declarations
    explain: bool = False,                  # TRACE log detection (temp StreamHandler)
    language_threshold: float = 0.1,        # min coherence to report a language
    enable_fallback: bool = True,           # ascii/utf-8/specified last-resort match
) -> CharsetMatches
from_fp(fp: BinaryIO, ...) -> CharsetMatches        # reads fp, does not close it
from_path(path: str | bytes | PathLike, ...) -> CharsetMatches  # opens "rb"; may raise OSError/IOError
is_binary(fp_or_path_or_payload, ..., enable_fallback: bool = False) -> bool  # True == binary (no match)
```

- Raises `TypeError` if `from_bytes` gets non-bytes. Empty input returns `[CharsetMatch(b"", "utf_8", 0.0, ...)]`.
- Pipeline: BOM/SIG → prioritized `[sig?, specified?, ascii, utf_8]` → all `IANA_SUPPORTED_MB_FIRST`
  (multibyte first). Each candidate: strict-decode (single-byte decode deferred until after chaos
  probing) → sample `steps` chunks of `chunk_size` → `mess_ratio` per chunk, early-stop after
  `len(offsets)/4` (min 2) bad chunks or `mean >= threshold` → `coherence_ratio` per chunk →
  `CharsetMatch`. Fast exits: chaos `0.0` on prioritized codec; early-stop winner once
  ascii+utf_8+specified tested; BOM owner; definitive match (coherence ≥ 0.5) then skips
  other-family + caps same-family SB (+7); multibyte-definitive skips remaining single-byte.
- `steps`/`chunk_size` auto-shrink when payload is smaller; `>=10 MB` payloads use lazy decode
  (only first ~500 KB strict-checked, `CharsetMatch._string` stays `None` until `str()`).
- `cp_isolation`/`cp_exclusion` accept aliases (normalized via `iana_name`). With `explain=True`
  plus 1–2 `cp_isolation` entries, `mess_ratio(debug=True)` logs per-plugin ratios.

```python
results = from_path("subs/film.srt")
best = results.best()  # CharsetMatch | None
print(best.encoding, best.language, best.percent_chaos)
text = str(best)  # decoded str (lazy)
utf8_bytes = best.output()  # re-encoded UTF-8 (default), errors="replace"
```

### `models.py` — `CharsetMatch` / `CharsetMatches`

```python
class CharsetMatch:
    def __str__(self) -> str            # decoded payload (lazy; strict decode; strips utf-7 BOM char)
    def output(self, encoding: str = "utf_8") -> bytes  # re-encode; "replace"; patches PEP263/charset header ≤8KB
    def __eq__(self, other) -> bool     # vs CharsetMatch (encoding+fingerprint) or str (alias-safe, non-strict)
    def __lt__(self, other) -> bool     # sort: chaos asc; chaos diff <0.5% → coherence desc (>0.02 gap) else multi_byte_usage desc
    def add_submatch(self, other) -> None  # dedup bucket; raises ValueError on bad type/self
    @property encoding -> str           # IANA-ish name with underscores, e.g. "cp1252", "utf_8", "shift_jis"
    @property encoding_aliases -> list[str]
    @property bom / byte_order_mark -> bool
    @property languages -> list[str]    # all detected, e.g. ["French", ...]; may be []
    @property language -> str           # top language or "Unknown"; ascii-heavy → "English" inference
    @property chaos -> float            # mean mess 0..~1 (lower = cleaner)
    @property coherence -> float        # top language fit 0..1
    @property percent_chaos / percent_coherence -> float  # ×100, 3dp
    @property raw -> bytes | bytearray  # untouched input
    @property submatch -> list[CharsetMatch] / has_submatch -> bool
    @property alphabets -> list[str]    # Unicode blocks, e.g. ["Basic Latin", "Latin-1 Supplement"]
    @property could_be_from_charset -> list[str]  # self + submatches decoding to identical str
    @property fingerprint -> int        # hash(str(self)) — dedup key
    @property multi_byte_usage -> float # 1 - len(str)/len(raw); 0.0 when empty
```

```python
class CharsetMatches:  # sorted best-first container (NOT a list)
    def best(self) -> CharsetMatch | None
    def first(self) -> CharsetMatch | None   # BC alias of best()
    def append(self, item: CharsetMatch) -> None  # ValueError on wrong type; dedups identical fingerprint+chaos as submatch (<10MB)
    def __iter__, __len__, __bool__          # falsy when nothing detected (= binary)
    def __getitem__(self, item: int | str) -> CharsetMatch  # index or encoding/alias (searches could_be_from_charset); KeyError
```

`CliDetectionResult(path, encoding, encoding_aliases, alternative_encodings, language, alphabets,
has_sig_or_bom, chaos, coherence, unicode_path, is_preferred)` + `.to_json()` — the CLI row object
(`__dict__` property returns the JSON dict).

### `legacy.py` — chardet-compatible `detect()`

```python
detect(byte_str: bytes, should_rename_legacy: bool = False, **kwargs) -> {"encoding","language","confidence"}
```

- `confidence = 1.0 - chaos`; auto `-0.2` when `≥0.9` on tiny (`<32 B`) non-unicode, no-BOM samples.
- `utf_8` + BOM → `"utf_8_sig"`; names mapped through `CHARDET_CORRESPONDENCE`
  (e.g. `cp1252→Windows-1252`, `utf_8→utf-8`) unless `should_rename_legacy=True`.
- Extra kwargs only trigger a warning; non-bytes raises `TypeError`. Kept for migration, not removal.

### `md.py` — chaos (`mess_ratio`) and plugins

```python
mess_ratio(decoded_sequence: str, maximum_threshold: float = 0.2, debug: bool = False) -> float
```

Samples every 32nd/64th/128th char (by length <511/<1024/else), sums 10 plugin ratios, early-exits
at threshold, returns `round(..., 3)`. ASCII-only input fast-paths (7 detectors provably 0.0).
`CharInfo` (slots) pre-computes per-codepoint flags once (`lru_cache`; 128-entry ASCII table):
printable/alpha/upper/lower/space/digit/ascii/case-variable/latin/accentuated/CJK/katakana
(+halfwidth)/arabic (+isolated form)/ligature/superscript/sentence-open-punct/glyph/punct/sym/
range/sep/emoticon/safe/common-CJK/unaccented.

| Plugin | Flags chaos when |
|---|---|
| `TooManySymbolOrPunctuation` | punct+2×symbol ≥ 30% of chars |
| `TooManyAccentuated` | accentuated ≥ 35% (needs ≥8 chars) |
| `Unprintable` | `8×unprintable/n`; `1.0` if ESC present |
| `SuspiciousDuplicateAccent` | back-to-back same-base accented pairs |
| `SuspiciousRange` | adjacent Unicode ranges from incompatible families (needs >13 chars) |
| `SuperWeirdWord` | bad-word chars/words; `1.0` on invalid word; long foreign/camel/inverse-caps words |
| `CjkUncommon` | >50% uncommon CJK (÷5; needs ≥4 chars) |
| `SuspiciousKatakana` | only-halfwidth katakana + 3 uncommon CJK → `1.0` |
| `ArchaicUpperLower` | archaic alternating-case runs in non-ASCII ≤64-char chunks |
| `ArabicIsolatedForm` | isolated-form Arabic share (needs ≥8 chars) |

Extend via `class P(MessDetectorPlugin): feed_info(char, info); reset(); @property ratio`.

### `cd.py` — coherence (language) detection

```python
coherence_ratio(decoded_sequence: str, threshold: float = 0.1, lg_inclusion: str | None = None) -> CoherenceMatches  # [(language, ratio)] desc
alphabet_languages(chars, ignore_non_latin=False) -> list[str]
characters_popularity_compare(language, ordered_chars) -> float   # ValueError if language unknown
alpha_unicode_split(seq) -> list[str]        # splits mixed-script text into per-alphabet layers
merge_coherence_ratios(list[CoherenceMatches]) -> CoherenceMatches
filter_alt_coherence_matches(m) -> CoherenceMatches  # folds "English—"→"English" etc.
encoding_languages(iana) / mb_encoding_languages(iana) -> list[str]  # lru_cached; SB raises OSError on multibyte input
encoding_unicode_range(iana) -> list[str]
unicode_range_languages(range) -> list[str]
get_target_features(lang) -> (has_accents, pure_latin)
```

Letter-frequency tables (`constant.FREQUENCIES`) per language; `alpha_unicode_split` separates e.g.
Latin vs Hebrew layers, each layer votes via rank-order comparison; layers `<32` chars skipped.
`lg_inclusion="a,b"` restricts candidates (`"Latin Based"` ⇒ latin-only mode).

### `utils.py` — helpers worth reusing directly

```python
unicode_range(ch: str) -> str | None        # official block name via binary search (Unicode 17 table)
is_accentuated(ch) / remove_accent(ch) -> str   # strip to base letter via decomposition
is_latin/is_cjk/is_hiragana/is_katakana/is_hangul/is_thai/is_arabic/is_arabic_isolated_form/is_cjk_uncommon(ch) -> bool
is_punctuation/is_symbol/is_emoticon/is_separator/is_case_variable/is_unprintable/is_unicode_range_secondary(name) -> bool
any_specified_encoding(seq, search_zone=8192) -> str | None   # PEP263/charset/XML declaration sniff
identify_sig_or_bom(seq) -> (iana | None, mark: bytes)
should_strip_sig_or_bom(iana) -> bool       # False only for utf_16/utf_32
iana_name(cp, strict=True) -> str           # alias→canonical ("windows-1252"→"cp1252"); ValueError if strict+unknown
is_multi_byte_encoding(name) -> bool        # lru_cached; UTF family + _codecs_{cn,hk,iso2022,jp,kr,tw}
cp_similarity(a, b) -> float / is_cp_similar(a, b) -> bool   # ≥80% byte-map overlap (precomputed table)
cut_sequence_chunks(...) -> Generator[str]  # BOM/iso2022/MB-aware chunker used by from_bytes
set_logging_handler(name="charset_normalizer", level=INFO, format_string=...) -> None
```

### `cli` — the `normalizer` command (all flags)

```text
normalizer [-h] [-v] [-a] [-n] [-m] [-r] [-f] [-i] [-t THRESHOLD] [--version] file [file ...]
  -v, --verbose           TRACE detection logs to stdout
  -a, --with-alternative  include non-best matches (top-level JSON becomes a list)
  -n, --normalize         write UTF-8 normalized copy: <name>.<encoding>.<ext> (skips utf* inputs)
  -r, --replace           with -n: overwrite original (prompts; needs -n)
  -f, --force             with -r: no prompt (needs -r)
  -i, --no-preemptive     ignore BOM/declared-charset hints
  -t, --threshold         max chaos 0..1 (default 0.2)
  -m, --minimal           print bare encoding only (no JSON)
  --version               "Charset-Normalizer 3.5.1 - Python 3.14 - Unicode 17 - SpeedUp ON"
```

JSON row: `path, encoding, encoding_aliases, alternative_encodings, language, alphabets,
has_sig_or_bom, chaos, coherence, unicode_path, is_preferred`. Exit codes: `0` ok, `1` bad
flag combo/threshold, `2` write error. `-r` without `-n` and `-f` without `-r` are rejected.

### Detection strategy vs chardet

- **charset-normalizer:** brute-force — strict-decode with ~99 IANA codecs, keep what decodes,
  rank by *chaos* (typographic mess heuristics) then *coherence* (letter-frequency fit), with
  BOM/declaration preemption. No training data; encoding-agnostic; uncapped input (10× faster
  than uncapped chardet on a 272 MB file per upstream bench); sub-ms medians; UnicodeDecodeError-safe;
  also returns language/alphabets/BOM/aliases.
- **chardet 5.2.0** (also installed, dev-transitive): per-encoding state-machine probers +
  Bayesian confidence, caps input (`max_bytes`), needs a model per encoding. Good calibrated
  `confidence`, but slower on big files and blind to encodings without a dedicated prober.
- Rule of thumb: chardet answers *"which byte-table produced this?"*; charset-normalizer answers
  *"which decoding renders the most human-plausible text?"* — the latter is what a subtitle/media
  app wants.

## App usage & correctness

- **Dependency chain (corrected): charset-normalizer does NOT come via httpx.**
  `httpx 0.28.1` `METADATA` lists only `anyio, certifi, httpcore, idna` (+extras) and its source
  contains zero `charset_normalizer`/`chardet` imports. The real chain is
  **dev-group `flet-cli → cookiecutter → requests 2.34.2 → charset_normalizer<4,>=2`**
  (plus `flet-cli → chardet<6` and `binaryornot → chardet`, which is why **both** detectors are in
  the venv). Neither is in `pyproject.toml` `dependencies` (runtime is only `av, flet*, httpx`).
- **Direct usage: NONE — no MISUSE either.** `grep` for `charset_normalizer|charset-normalizer|
  chardet|from_bytes|from_path` over `src/`, `tests/`, `tools/` finds no detector calls
  (sole `from_path` hit is Flet's `ft.ShareFile.from_path` in `src/services/media_io.py:145`).
  `UpdateService.check_for_updates` (`src/services/update_service.py`) uses `httpx.AsyncClient`
  + `resp.json()` — JSON is UTF-8/16/32 by spec and httpx handles charset itself, so no detector
  is needed there. Nothing to fix; nothing is decoded wrongly *through* this package today.
- **Latent risk (UTF-8 hardcoding, detector absent):** the app assumes UTF-8 everywhere —
  `read_text/write_text(encoding="utf-8")` in `engine_probe.py`, `probe_screen.py`,
  `engine_service.py` (incl. the SRT/ASS/VTT writers at lines ~119–138), `storage_service.py`,
  and `dialogue.decode("utf-8", errors="replace")` (`engine_service.py:1642`). Any non-UTF-8
  sidecar or embedded text hit (notably `engine_service.py:1699` `f.read_bytes()` on subtitle
  attachments) either raises or mojibake-replaces instead of detecting.

## Underused APIs to adopt

All v1-safe (stdlib-only, ~ms cost, pure functions). Recommended helper
(`src/services/text_decode.py`, new file): `safe_decode(raw: bytes) -> tuple[str, str]` =
`best = from_bytes(raw).best(); return (str(best), best.encoding) if best else
(raw.decode("utf-8","replace"), "utf-8")`, then:

1. **Subtitle sidecar detection (highest value).** SRT/ASS/VTT in the wild are cp1250/1/2/6,
   iso8859-*, shift_jis, gb18030, koi8_r… Route every non-ffmpeg-produced subtitle read through
   `from_bytes`/`from_path(...).best()`: (a) decode `f.read_bytes()` hits before parsing;
   (b) replace the `utf-8/replace` ASS dialogue decode; (c) show `best.language + encoding` in
   the extract screen ("Detected French · cp1252") and offer one-tap `best.output()` normalize
   to UTF-8 on import. `cp_isolation` can bias toward the UI locale; keep default `threshold=0.2`.
2. **ffprobe/metadata tag repair.** Legacy MP4/ID3 tags often decode as latin1-mojibake —
   re-run suspect strings' original bytes via `from_bytes` instead of trusting them.
3. **ffmpeg log decoding.** Windows console output may be cp1252/cp936: decode `stderr` bytes
   with the detector before surfacing in terminal screen/log files.
4. **M3U/playlist + probe-cache reads.** `is_binary()` gate before parsing downloaded/attached
   playlists; `from_path` fallback when the UTF-8 probe cache read fails.
5. **One-detector standard: keep charset-normalizer, do not adopt chardet.**
   MIT-clean, maintained, faster uncapped, decode-safe, and its `language`/`alphabets` fit the
   subtitle UX. chardet stays in the venv only for `flet-cli`/`binaryornot` (dev tooling) —
   app code should import `charset_normalizer` exclusively. **Action:** add
   `"charset-normalizer>=3,<4"` to runtime `dependencies` (it is currently dev-transitive via
   `requests`; a direct import without a direct pin risks mobile-packaging/pruning surprises).

## Gotchas

- `<32 B` samples are unreliable (`detect()` docks 0.2 confidence); mixed-language/HTML skews
  `language`; short single-word files can tie — inspect `percent_chaos`/`coherence`, not just rank.
- `threshold` is a chaos ceiling: raise toward 1.0 to force a guess on noisy bytes, lower to
  reject junk; `enable_fallback=False` (or `is_binary()`) avoids the ascii/utf-8 last resort
  masking binaries.
- BOM/SIG stripped except utf_16/32 (kept, needs BOM); utf_7 never wins without its SIG;
  `preemptive_behaviour=False` / `--no-preemptive` disables declaration bias (XML/HTML `charset=`,
  PEP263 `coding=`) when it misleads.
- `str(match)` on `≥10 MB` inputs decodes lazily — fine, but `match.raw` pins the bytes;
  `output()` uses `"replace"`, never raises. `match["alias"]` lookup raises `KeyError` when absent;
  `best()` returns `None` (guard before `str()`); `detect()["confidence"]` is `1−chaos`, not a
  calibrated probability.
- Logging: `NullHandler` by default; `explain=True`/`-v` emits custom `TRACE(5)` — call
  `set_logging_handler()` once if you want detector logs in release diagnostics.
- `normalizer -n` never touches files without the flag; `-r` needs `-n`, `-f` needs `-r`;
  normalize output name inserts encoding (`film.cp1252.srt`); utf* inputs are skipped with a notice.
