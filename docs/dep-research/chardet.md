# chardet 5.2.0 — Complete API Reference

Universal charset/encoding detector (Mozilla UniversalDetector port).
Pure-Python statistical detection: BOM sniffing → UTF-16/32 zero-byte
analysis → escape-sequence state machines → multi-byte distribution
analysis → single-byte bigram models → Latin-1/MacRoman fallbacks.

> Scope note: there is **no** `CharsetMatch`, `CharsetDecision`,
> `ElementState`, or `coerce_linesep` in chardet — those names belong to
> `charset-normalizer` (also installed, 3.5.1). chardet returns a plain
> `ResultDict` (`{"encoding", "confidence", "language"}`).

## Files

49 `.py` files (plus `py.typed`). No `__pycache__` counted. Layout:

```
chardet/
  __init__.py            public API: detect(), detect_all()
  __main__.py            `python -m chardet` wrapper
  version.py             __version__ = "5.2.0"
  resultdict.py          ResultDict TypedDict
  universaldetector.py   UniversalDetector orchestrator
  enums.py               InputState, LanguageFilter, ProbingState,
                         MachineState, SequenceLikelihood, CharacterCategory
  charsetprober.py       CharSetProber base + static filters
  charsetgroupprober.py  CharSetGroupProber fan-out
  mbcharsetprober.py     MultiByteCharSetProber base
  mbcsgroupprober.py     MBCSGroupProber (9 CJK probers + UTF-8)
  sbcsgroupprober.py     SBCSGroupProber (16 single-byte probers)
  sbcharsetprober.py     SingleByteCharSetProber + SingleByteCharSetModel
  utf8prober.py          UTF8Prober
  utf1632prober.py       UTF1632Prober
  escprober.py           EscCharSetProber (HZ / ISO-2022-*)
  escsm.py               HZ_SM_MODEL, ISO2022CN/JP/KR_SM_MODEL
  latin1prober.py        Latin1Prober (ISO-8859-1)
  macromanprober.py      MacRomanProber (MacRoman)
  hebrewprober.py        HebrewProber (visual/logical decider)
  codingstatemachine.py  CodingStateMachine (next_state/get_current_charlen/...)
  codingstatemachinedict.py  CodingStateMachineDict TypedDict
  chardistribution.py    CharDistributionAnalysis + EUC* per-encoding subclasses
  mbcssm.py              UTF8/SJIS/EUC-JP/GB2312/EUC-KR/CP949/Big5/EUC-TW/JOHAB models
  big5prober.py / sjisprober.py / eucjpprober.py / gb2312prober.py /
    euckrprober.py / cp949prober.py / euctwprober.py / johabprober.py
  langbulgarianmodel.py / langgreekmodel.py / langhebrewmodel.py /
    langhungarianmodel.py (UNUSED — Hungarian disabled) /
    langrussianmodel.py / langthaimodel.py / langturkishmodel.py
  big5freq.py / euckrfreq.py / euctwfreq.py / gb2312freq.py /
    jisfreq.py / johabfreq.py / jpcntx.py (EUC-JP context analyzer)
  cli/__init__.py (empty) / cli/chardetect.py (chardetect entry point)
  metadata/__init__.py / metadata/languages.py (Language training metadata)
```

## Metadata

From `chardet-5.2.0.dist-info/METADATA` (+ `WHEEL`, `entry_points.txt`, `RECORD`):

| Field | Value |
|---|---|
| Name / Version | `chardet` / `5.2.0` (2023-08-01, `version.py`) |
| License | **LGPL** (`License: LGPL`; classifier `LGPLv2+`). `LICENSE` = LGPL-2.1 text + Mozilla/Mark Pilgrim header. Copyleft-weak implict for bundled mobile app — prefer MIT alternative for first-party code |
| Pure-Python | **Yes**. `WHEEL`: `Root-Is-Purelib: true`, `Tag: py3-none-any`. No C extensions, no `Requires-Dist`. `Requires-Python: >=3.7` (works on 3.14) |
| Console script | `chardetect = chardet.cli.chardetect:main` (`Scripts/chardetect.exe` in RECORD) |
| Installer | `uv`; `REQUESTED` empty → **not a direct dependency** (transitive) |
| Public surface | `__all__ = ["UniversalDetector", "detect", "detect_all", "__version__", "VERSION"]` |

## Module-by-module API

### `chardet/__init__.py` — top-level functions

```python
def detect(byte_str: bytes | bytearray,
           should_rename_legacy: bool = False) -> ResultDict
def detect_all(byte_str: bytes | bytearray,
               ignore_threshold: bool = False,
               should_rename_legacy: bool = False) -> list[ResultDict]
```

- `detect`: one-shot. Wraps `bytearray()` coercion → `UniversalDetector.feed`
  → `close()`. Raises `TypeError("Expected object of type bytes or bytearray,
  got: ...")` for `str`/anything else. No `coerce_linesep` parameter
  (that is charset-normalizer-only). Returns `{"encoding": str | None,
  "confidence": float, "language": str | None}`.
- `detect_all`: returns **ranked** per-prober list (`sorted(-confidence)`)
  when `input_state == HIGH_BYTE`, else `[detector.result]`. Each entry has
  ISO→Windows remap + optional legacy rename applied. `ignore_threshold=True`
  includes probers below `MINIMUM_THRESHOLD` (0.20).
- `should_rename_legacy=False` default. When `True`, applies `LEGACY_MAP`:
  `ascii→Windows-1252`, `iso-8859-1→Windows-1252`, `tis-620→ISO-8859-11`,
  `iso-8859-9→Windows-1254`, `gb2312→GB18030`, `euc-kr→CP949`,
  `utf-16le→UTF-16`.
- Examples:

```python
import chardet

chardet.detect(b"Hello world")  # {'encoding': 'ascii', 'confidence': 1.0, 'language': ''}
chardet.detect("déjà".encode("latin-1"))
chardet.detect_all(open("subs.srt", "rb").read(), ignore_threshold=True)
chardet.detect(raw, should_rename_legacy=True)  # legacy→superset names
```

### `resultdict.py` — result shape

```python
class ResultDict(TypedDict):  # plain dict at runtime on py<3.8 path
    encoding: Optional[str]
    confidence: float
    language: Optional[str]
```

`encoding` may be `None` (no prober cleared threshold / empty input).
`language` is e.g. `"Russian"`, `"Greek"`, `"Hebrew"`, `"Chinese"`,
`"Japanese"`, `"Korean"`, `"Thai"`, `"Turkish"`, `"Bulgarian"`, or `""`
(UTF-8/Latin-1/MacRoman/UTF-16/32 have empty language).

### `universaldetector.py` — `UniversalDetector` lifecycle

```python
UniversalDetector(lang_filter: LanguageFilter = LanguageFilter.ALL,
                  should_rename_legacy: bool = False)
u.feed(byte_str: bytes | bytearray) -> None
u.close() -> ResultDict
u.reset() -> None
u.result: ResultDict          # {"encoding": None, "confidence": 0.0, "language": None} init
u.done: bool                  # True => stop feeding, read u.result
u.input_state: int            # InputState property (read-only)
u.has_win_bytes: bool         # 0x80-0x9F seen (property)
u.charset_probers: list[CharSetProber]  # property; empty until first HIGH_BYTE feed
u.MINIMUM_THRESHOLD = 0.20    # class attr
u.ISO_WIN_MAP / LEGACY_MAP / HIGH_BYTE_DETECTOR / ESC_DETECTOR / WIN_BYTE_DETECTOR
```

Pipeline in `feed()`: BOM check (first chunk only: UTF-8-SIG, UTF-32,
X-ISO-10646-UCS-4-3412/2143, UTF-16 → `done=True`, confidence 1.0) →
ASCII/high-byte/ESC triage → `UTF1632Prober` → `EscCharSetProber` (ESC_ASCII
only) → `[MBCSGroupProber (+SBCSGroupProber if lang_filter & NON_CJK),
Latin1Prober, MacRomanProber]` (HIGH_BYTE only). Early-exits when any prober
returns `FOUND_IT` or `done` already set (`feed` after `done` is a no-op;
empty chunk is a no-op). `close()` picks max-confidence prober above 0.20
with ISO→Windows remap; pure-ASCII → `ascii/1.0`; ESC_ASCII with no hit keeps
`encoding=None`. `reset()` clears result/flags and resets all child probers
for document reuse. No exceptions except propagating `AssertionError` on
internal invariant; feeds never raise on weird bytes.

Streaming example:

```python
from chardet import UniversalDetector

u = UniversalDetector()  # or UniversalDetector(lang_filter=LanguageFilter.NON_CJK)
with open("unknown.srt", "rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
        u.feed(chunk)
        if u.done:
            break
print(u.close())
u.reset()  # reuse for next file
```

### `enums.py`

```python
class InputState: PURE_ASCII=0; ESC_ASCII=1; HIGH_BYTE=2        # plain ints, not Enum
class LanguageFilter(Flag): NONE=0x00; CHINESE_SIMPLIFIED=0x01; CHINESE_TRADITIONAL=0x02;
    JAPANESE=0x04; KOREAN=0x08; NON_CJK=0x10; ALL=0x1F;
    CHINESE=(SIMPLIFIED|TRADITIONAL); CJK=(CHINESE|JAPANESE|KOREAN)
class ProbingState(Enum): DETECTING=0; FOUND_IT=1; NOT_ME=2
class MachineState: START=0; ERROR=1; ITS_ME=2
class SequenceLikelihood: NEGATIVE=0; UNLIKELY=1; LIKELY=2; POSITIVE=3
    SequenceLikelihood.get_num_categories() -> 4
class CharacterCategory: UNDEFINED=255; LINE_BREAK=254; SYMBOL=253; DIGIT=252; CONTROL=251
    # anything < CONTROL (251) counts as a letter
```

No `CharsetDecision`/`ElementState` exist here (charset-normalizer vocabulary).

### `charsetprober.py` — `CharSetProber` base

```python
CharSetProber(lang_filter: LanguageFilter = LanguageFilter.NONE)
.reset() -> None; .feed(byte_str) -> ProbingState  # abstract
.get_confidence() -> float  # 0.0 base
.charset_name: Optional[str]  # None base; str per subclass
.language: Optional[str]      # abstract
.state: ProbingState; .active: bool; .lang_filter; .logger
.SHORTCUT_THRESHOLD = 0.95
@staticmethod filter_high_byte_only(buf) -> bytes
@staticmethod filter_international_words(buf) -> bytearray
@staticmethod remove_xml_tags(buf) -> bytes   # currently only Latin1Prober uses it
```

### Group / multi-byte / single-byte bases

- `CharSetGroupProber(CharSetProber)`: `.probers: list`, `._best_guess_prober`,
  `._active_num`. `feed` fans out, deactivates `NOT_ME` probers, returns
  `FOUND_IT` on first winner; `get_confidence` returns 0.99/0.01 on terminal
  states else best active child confidence.
- `MultiByteCharSetProber` (`mbcharsetprober.py`): `.distribution_analyzer`,
  `.coding_sm`, `._last_char`; `feed` steps the state machine byte-by-byte
  and feeds completed char pairs to the distribution analyzer; shortcut to
  `FOUND_IT` past `SHORTCUT_THRESHOLD` with enough data.
- `SingleByteCharSetProber` (`sbcharsetprober.py`):
  `SingleByteCharSetModel(charset_name, language, char_to_order_map,
  language_model, typical_positive_ratio, keep_ascii_letters, alphabet)` NamedTuple;
  `__init__(model, is_reversed=False, name_prober=None)` (`is_reversed=True`
  = visual-Hebrew backwards lookup). Constants `SAMPLE_SIZE=64`,
  `SB_ENOUGH_REL_THRESHOLD=1024`, `POSITIVE_SHORTCUT_THRESHOLD=0.95`,
  `NEGATIVE_SHORTCUT_THRESHOLD=0.05`.

### Concrete prober inventory (charset → language)

| Module / class | `charset_name` | `language` | Notes |
|---|---|---|---|
| `utf8prober.UTF8Prober` | `utf-8` | `""` | `ONE_CHAR_PROB=0.5`; confidence `1-0.99*0.5^n` for n<6 MB chars, else 0.99 |
| `utf1632prober.UTF1632Prober` | `utf-32be/le`, `utf-16be/le`, fallback `utf-16` | `""` | Zero-pattern stats; `MIN_CHARS_FOR_DETECTION=20`, `EXPECTED_RATIO=0.94`; `NOT_ME` after 4 KiB; confidence 0.85/0.0 |
| `escprober.EscCharSetProber` | detected SM name (e.g. `ISO-2022-JP`) | SM language | Only builds SMs in `lang_filter` (SIMPLIFIED→HZ+ISO-2022-CN, JAPANESE→ISO-2022-JP, KOREAN→ISO-2022-KR); confidence 0.99/0.0 |
| `big5prober.Big5Prober` | `Big5` | `Chinese` | MBCSGroup member |
| `gb2312prober.GB2312Prober` | `GB2312` | `Chinese` | |
| `euctwprober.EUCTWProber` | `EUC-TW` | `Taiwan` | |
| `eucjpprober.EUCJPProber` | `EUC-JP` | `Japanese` | |
| `sjisprober.SJISProber` | via `context_analyzer.charset_name` (SHIFT_JIS) | `Japanese` | Uses `jpcntx.py` |
| `euckrprober.EUCKRProber` | `EUC-KR` | `Korean` | |
| `cp949prober.CP949Prober` | `CP949` | `Korean` | |
| `johabprober.JOHABProber` | `Johab` | `Korean` | |
| `latin1prober.Latin1Prober` | `ISO-8859-1` | `""` | Confidence `*0.73` deliberately deprioritized; `NOT_ME` on illegal class transition |
| `macromanprober.MacRomanProber` | `MacRoman` | `""` | Same `*0.73`; prior `_freq_counter[2]=10` anti-bias; `ODD` class for rare symbols |
| `hebrewprober.HebrewProber` | `windows-1255` / `ISO-8859-8` | `Hebrew` | Helper only — always `DETECTING` (confidence unused); `set_model_probers(logical, visual)`; final-letter scoring (`MIN_FINAL_CHAR_DISTANCE=5`, `MIN_MODEL_DISTANCE=0.01`) |
| SBCS singles | `windows-1251`/`KOI8-R`/`ISO-8859-5`/`MacCyrillic`/`IBM866`/`IBM855` (Russian); `ISO-8859-7`/`windows-1253` (Greek); `ISO-8859-5`/`windows-1251` (Bulgarian); `TIS-620` (Thai); `ISO-8859-9` (Turkish); `windows-1255` logical+visual (Hebrew) | per model | Hungarian `ISO-8859-2`/`windows-1250` models exist (`langhungarianmodel.py`) but are **commented out** in `SBCSGroupProber` pending retraining |

`MBCSGroupProber.probers` order: UTF-8, SJIS, EUC-JP, GB2312, EUC-KR, CP949,
Big5, EUC-TW, JOHAB. `SBCSGroupProber` order is load-bearing (source comment:
reordering breaks tests).

### Supporting machinery

- `codingstatemachine.CodingStateMachine(sm)`: `reset()`,
  `next_state(c: int) -> MachineState`, `get_current_charlen()`,
  `get_coding_state_machine()`, `.language`, `.active`. Table-driven over
  `mbcssm.py` / `escsm.py` models.
- `chardistribution.CharDistributionAnalysis`: `feed(chars, char_len)`,
  `get_confidence()`, `got_enough_data()` (`ENOUGH_DATA_THRESHOLD=1024`,
  `MINIMUM_DATA_THRESHOLD=3`), `reset()`; per-encoding subclasses set
  `*_CHAR_TO_FREQ_ORDER` tables (freq modules + `jpcntx.py`).
- `metadata/languages.Language`: training-only metadata (`name`, `iso_code`,
  `use_ascii`, `charsets`, `alphabet`, `wiki_start_pages`); not used at
  detection runtime.
- `cli/chardetect.py`: `description_of(lines, name="stdin", minimal=False,
  should_rename_legacy=False) -> Optional[str]`; `main(argv=None)` with
  `input` (default stdin binary), `--minimal`, `-l/--legacy`, `--version`.

## App usage & correctness

(a) **Why installed — transitive dev-tooling only, zero app imports.**

- `grep -rni chardet src tests pyproject.toml` → **no hits**. No `import
  chardet`, no `detect()`/`UniversalDetector` call, no test coverage.
- `pyproject.toml [project] dependencies` are `av, flet*, httpx` — chardet
  is absent; it arrives via `[dependency-groups] dev → flet-cli>=1.0.0`.
- Chain (verified in `uv.lock` + dist METADATAs): `flet-cli 1.0.0`
  `Requires-Dist: chardet<6` (direct) **and** `binaryornot<0.5` →
  `binaryornot 0.4.4 Requires-Dist: chardet>=3.0.2` → `cookiecutter>=2.6.0`
  `Requires-Dist: binaryornot>=0.4.4`. Call site:
  `cookiecutter/generate.py: is_binary(infile)` →
  `binaryornot/check.py: is_binary` → `helpers.is_binary_string` →
  `chardet.detect(bytes_to_check)` (confidence>0.9 + non-ascii ⇒ try decode).
  So chardet only runs when `flet-cli` scaffolds a template — never in the
  shipped app.
- `requests 2.34.2` lists `chardet<8,>=3.0.2; extra == "use-chardet-on-py3"`
  but the active requirement is `charset_normalizer<4,>=2`; the extra is not
  enabled here. `charset-normalizer 3.5.1` (MIT) is the live HTTP decoder.

(b) **Misuse:** none found (nothing to misuse — it is unused at runtime).
Do **not** copy the `binaryornot` pattern (`confidence > 0.9` gate) for media
text; it is tuned for template scaffolding, not subtitles.

(c) **Underuse — real v1 openings, currently hand-rolled as UTF-8-only:**

- `src/services/engine_service.py`: writers `_write_srt/_write_ass/_write_vtt`
  always `Path.write_text(..., encoding="utf-8")`; `extract_subtitles()`
  decodes `rect.dialogue` bytes as `dialogue.decode("utf-8",
  errors="replace")`. Importing an external `.srt/.ass/.vtt` of unknown
  provenance (Latin-1, Windows-1252/1251/1253, Shift_JIS, GB2312…) will
  mojibake or silently replace — chardet-style detection + confidence gate
  is exactly the missing step before `bytes.decode()`.
- Same gap for any future "open subtitle file", ID3/metadata-as-bytes, or
  ffmpeg log/report decoding paths (today `av.open(...)` handles media
  bytes; text side-channels are assumed UTF-8).

## Underused APIs to adopt

If the team adds unknown-encoding text ingest before v1, the useful subset is
small — everything else (prober subclasses, frequency tables, `Language`,
`CodingStateMachine`, Hebrew internals) should stay untouched:

1. `chardet.detect(raw: bytes) -> ResultDict` — one-shot for small files
   (subtitle sidecars, cue sheets, log snippets). Gate on
   `confidence >= 0.5–0.9`, fall back to `utf-8/errors="replace"`, never trust
   `encoding=None`.
2. `UniversalDetector` + `feed`/`done`/`close`/`reset` — large/streaming files;
   break on `done`, reuse via `reset()`. Pass
   `lang_filter=LanguageFilter.NON_CJK` when media is known Western to skip
   CJK probers.
3. `detect_all(..., ignore_threshold=True)` — debugging ambiguous files
   (e.g. Windows-1252 vs ISO-8859-1); surfaces runner-ups.
4. `chardetect` CLI / `python -m chardet file.srt` — triage user-reported
   mojibake without writing code.
5. `should_rename_legacy=True` — normalize `GB2312→GB18030`,
   `EUC-KR→CP949`, `ascii/iso-8859-1→Windows-1252` before `bytes.decode()`.

Recommended helper shape (illustrative, not committed):

```python
import chardet


def decode_unknown(raw: bytes) -> str:
    r = chardet.detect(raw)
    enc, conf = r["encoding"], r["confidence"]
    if enc and conf >= 0.5:
        try:
            return raw.decode(enc)
        except LookupError, UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")
```

## Gotchas

- **Returns `None`:** `encoding` is `None` when nothing clears 0.20 or input
  was empty — always check before `decode()`. Returned names
  `X-ISO-10646-UCS-4-3412/2143` are **not decodable by Python**.
- **Short text is unreliable:** single-byte models need volume
  (`SB_ENOUGH_REL_THRESHOLD=1024` seqs; `ENOUGH_DATA_THRESHOLD=1024` chars);
  UTF-16/32 needs ~20 chars; one-line cues often misclassify — prefer full
  file + confidence gate.
- **Legacy/Windows remapping surprises:** `ascii` stays `ascii` unless
  `should_rename_legacy`; `iso-8859-*` silently becomes `Windows-125*` when
  `0x80–0x9F` bytes were seen (`has_win_bytes`); `TIS-620→ISO-8859-11` only
  under legacy rename.
- **Deprioritized fallbacks:** Latin-1/MacRoman confidence ×0.73; UTF-16/32
  caps at 0.85; group `FOUND_IT` reports 0.99 regardless of margin.
- **`str` input raises `TypeError`** — pass `bytes`/`bytearray` only. `feed`
  after `done` is silently ignored; forgetting `close()` leaves `result`
  empty; `UniversalDetector` instances are single-use unless `reset()`.
- **ESC probers are filter-gated:** with a narrow `lang_filter` some
  ISO-2022/HZ models are never built; default `ALL` for general use.
- **Hebrew/Hungarian quirks:** Hebrew answer (`windows-1255` vs
  `ISO-8859-8`) is decided by `HebrewProber`, not the model probers;
  Hungarian (`iso-8859-2`/`windows-1250`) is **disabled** — Hungarian text
  will misattribute.
- **Perf:** `detect()` runs ~25 probers over the whole buffer; reuse one
  `UniversalDetector`, feed in 8 KiB chunks, break on `done`. Short-circuit
  pure-ASCII/BOM paths before paying for statistics.
- **License:** LGPL-2.1+ — fine as an unmodified transitive dev dep, but a
  reason to avoid hard-coding it into the shipped app when an MIT
  alternative is already installed.
