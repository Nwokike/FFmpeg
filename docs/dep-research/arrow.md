# arrow 1.4.0 — Complete API Reference

> Better dates & times for Python. Human-friendly creation, manipulation, formatting,
> conversion, spans/ranges, and localized humanization. Inspired by moment.js / requests.
> Docs: https://arrow.readthedocs.io · Source: https://github.com/arrow-py/arrow

## Files

Package dir (read-only): `<repo>\.venv\Lib\site-packages\arrow`

| File | Lines | Role |
|---|---|---|
| `__init__.py` | 42 | Public re-exports + `__all__` |
| `_version.py` | 1 | `__version__ = "1.4.0"` |
| `api.py` | 121 | Module-level `get` / `now` / `utcnow` / `factory` over a shared `_factory` |
| `arrow.py` | 1903 | The `Arrow` class (all instance API, factories, spans, humanize, dunders) |
| `constants.py` | 173 | `MAX_TIMESTAMP*`, ordinals, `DEFAULT_LOCALE`, `DEHUMANIZE_LOCALES` |
| `factory.py` | 339 | `ArrowFactory` — all `get()` overload dispatch, `now`, `utcnow` |
| `formatter.py` | 141 | `DateTimeFormatter` + `FORMAT_*` constants |
| `locales.py` | 6652 | 85 `Locale` subclasses, `get_locale`, `describe`/`describe_multi` |
| `parser.py` | 937 | `DateTimeParser`, `TzinfoParser`, `ParserError`/`ParserMatchError` |
| `util.py` | 117 | `next_weekday`, `is_timestamp`, `validate_ordinal`, `normalize_timestamp`, `iso_to_gregorian`, `validate_bounds` |
| `py.typed` | 0 | PEP-561 marker — package ships inline type hints |

Notes:

- There is **no `types.py`** in 1.4.0 despite the assignment brief naming one; type aliases
  (`TZ_EXPR`, `_T_FRAMES`, `_BOUNDS`, `_GRANULARITY`, `TimeFrameLiteral`) live in
  `arrow.py` / `locales.py` directly.
- `__pycache__` directories skipped per instructions.
- `RECORD` (sha256) lists all 15 installed files; `REQUESTED` is empty (transitive install,
  nobody asked for arrow directly); `INSTALLER` = `uv`; `WHEEL` generator `flit 3.12.0`,
  tag `py3-none-any`.

`__init__.py` exports (`__all__`, 18 names):

```python
(
    __version__,
    get,
    now,
    utcnow,
    Arrow,
    ArrowFactory,
)
(
    FORMAT_ATOM,
    FORMAT_COOKIE,
    FORMAT_RFC822,
    FORMAT_RFC850,
    FORMAT_RFC1036,
)
(
    FORMAT_RFC1123,
    FORMAT_RFC2822,
    FORMAT_RFC3339,
    FORMAT_RFC3339_STRICT,
)
FORMAT_RSS, FORMAT_W3C, ParserError
```

## Metadata

From `arrow-1.4.0.dist-info/METADATA` (Metadata-Version 2.4) + `uv.lock`:

- **Name / Version:** `arrow 1.4.0` (sdist 2025-10-18, `sha256:ed0cc050…`).
- **Summary:** "Better dates & times for Python". Keywords: arrow,date,time,datetime,timestamp,timezone,humanize.
- **Requires-Python:** `>=3.8` (classifiers list 3.8–3.14; env here is Python 3.14).
- **Runtime pins:**
  - `python-dateutil>=2.7.0` (resolved in `uv.lock` to **2.9.0.post0**) — used for
    `tz` (`dateutil.tz`), `relativedelta` (shift math), `rrule` (next_weekday),
    `datetime_ambiguous` / `datetime_exists` / `resolve_imaginary` (DST handling).
  - `backports.zoneinfo==0.2.1; python_version<'3.9'` — not active on 3.14.
  - `tzdata; python_version>='3.9'` — active; resolved to **tzdata 2026.4** (IANA DB for `ZoneInfo`).
  - **`typing_extensions` is NOT a dependency.** All hints are stdlib `typing` only.
- **Extras:** `doc` (doc8, sphinx>=7, sphinx-autobuild, sphinx-autodoc-typehints,
  sphinx_rtd_theme>=1.3), `test` (dateparser==1.*, pre-commit, pytest, pytest-cov,
  pytest-mock, pytz==2025.2, simplejson==3.* — `for_json` protocol targets simplejson).
- **License:** Apache Software License 2.0 (`LICENSE` under `licenses/`, License-File: LICENSE,
  classifier "OSI Approved :: Apache Software License"). Commercial-app safe; keep the
  license file if vendoring.
- **Status:** Development Status 5 - Production/Stable, OS Independent.

## Module-by-module API

### 1. `api.py` — module functions (delegates to internal `ArrowFactory()`)

```python
def get(*args, **kwargs) -> Arrow   # docstring copied from ArrowFactory.get
def utcnow() -> Arrow
def now(tz: TZ_EXPR | None = None) -> Arrow
def factory(type: Type[Arrow]) -> ArrowFactory
```

`get()` overloads (same five in `api.py` and `ArrowFactory.get`):

1. `get(*, locale='en-us', tzinfo=None, normalize_whitespace=False)` → now UTC
2. `get(*args: int, locale=..., tzinfo=..., normalize_whitespace=...)` → `Arrow(y, m, d, …)` passthrough
3. `get(obj: Arrow|datetime|date|struct_time|tzinfo|int|float|str|tuple, *, locale, tzinfo, normalize_whitespace)`
4. `get(arg1: datetime|date, arg2: TZ_EXPR, *, locale, tzinfo, normalize_whitespace)`
5. `get(arg1: str, arg2: str|list[str], *, locale, tzinfo, normalize_whitespace)`

`now(tz)` accepts any **timezone expression** (see TZ_EXPR below); `None` → local zone.

### 2. `factory.py` — `ArrowFactory(type=Arrow)`

`ArrowFactory(type)` lets you build a custom `Arrow` subclass (`arrow.factory(type)` helper).

`get(*args, **kwargs)` dispatch (kwargs: `locale='en-us'`, `tzinfo=None`, `normalize_whitespace=False`):

| Input | Result | Errors |
|---|---|---|
| `()` | `Arrow.utcnow()`, or `Arrow.now(tz)` if `tzinfo=` given | — |
| `(None,)` | — | `TypeError: Cannot parse argument of type None.` |
| `(int/float/Decimal/str-numeric,)` | `Arrow.fromtimestamp(v, tz or UTC)`; ms/µs auto-normalized | `ValueError` if not a timestamp or `too large` |
| `(Arrow,)` | copy via `fromdatetime(arg.datetime, tzinfo)` | — |
| `(datetime,)` | `fromdatetime` (naive → UTC unless `tzinfo=` overrides) | — |
| `(date,)` | `fromdate` (midnight UTC unless overridden) | — |
| `(tzinfo,)` | `now(tzinfo)` — current time **in** that zone | — |
| `(str,)` | `DateTimeParser(locale).parse_iso(s)` → `fromdatetime` | `ParserError` |
| `(struct_time,)` | `utcfromtimestamp(calendar.timegm(arg))` | — |
| `(tuple3,)` ISO week `(yyyy, ww, d)` | `iso_to_gregorian(*t)` → `fromdate` | `ValueError` week 1–53, day 1–7 |
| `(datetime\|date, tz-expr)` | `fromdatetime/fromdate` with replacement zone | `TypeError` on bad 2nd type |
| `(str, fmt\|[fmts])` | `DateTimeParser(locale).parse(s, fmt)` → `fromdatetime` | `ParserMatchError`/`ParserError` |
| `(y, m, d[, H, M, S, us], tzinfo=, fold=)` 3+ args | direct `Arrow(...)` constructor | `TypeError`/`ValueError` from datetime |
| unknown single/double type | — | `TypeError: Cannot parse single argument of type …` |

`tzinfo=` kwarg **replaces** the zone except for forms explicitly UTC or with positional zone.
`normalize_whitespace=True` collapses `\s+` → single space before parsing.

```python
ArrowFactory.utcnow(self) -> Arrow
ArrowFactory.now(self, tz: TZ_EXPR | None = None) -> Arrow  # None → local zone
```

### 3. `arrow.py` — `class Arrow`

Constructor (always **aware**; naive input becomes UTC):

```python
Arrow(year, month, day, hour=0, minute=0, second=0, microsecond=0,
      tzinfo: TZ_EXPR | None = None,   # None → UTC; str parsed; pytz objects re-parsed via .zone
      **kwargs)                        # only fold=0|1 accepted
```

`TZ_EXPR = Union[tzinfo, str]` where str is:

- IANA name `'US/Pacific'`, `'Europe/Berlin'`, `'Africa/Nairobi'` (via `ZoneInfo`);
- ISO offset `'+07:00'`, `'-07:00'`, `'+0200'`, also `'(UTC+02:00)'`-ish prefix forms;
- `'local'` (device zone), `'utc'` / `'UTC'` / `'Z'` (UTC).

Raises `ValueError: {x!r} not recognized as a timezone` (via `_get_tzinfo`) on bad strings,
`ParserError` from `TzinfoParser.parse` underneath.

Classmethod factories:

```python
Arrow.now(tzinfo: tzinfo | None = None) -> Arrow        # None → local; NOTE: tzinfo object only (no str here — use arrow.now('…') instead)
Arrow.utcnow() -> Arrow
Arrow.fromtimestamp(ts: int|float|str, tzinfo: TZ_EXPR | None = None) -> Arrow  # None → local!
Arrow.utcfromtimestamp(ts: int|float|str) -> Arrow
Arrow.fromdatetime(dt: datetime, tzinfo: TZ_EXPR | None = None) -> Arrow  # naive → UTC default
Arrow.fromdate(d: date, tzinfo: TZ_EXPR | None = None) -> Arrow           # midnight, UTC default
Arrow.strptime(date_str: str, fmt: str, tzinfo: TZ_EXPR | None = None) -> Arrow  # datetime-strptime codes, NOT arrow tokens
Arrow.fromordinal(ordinal: int) -> Arrow  # TypeError if not int/bool; ValueError if out of 1..datetime.max.toordinal()
```

`fromtimestamp`/`utcfromtimestamp` accept ms/µs magnitudes via `normalize_timestamp`
(> MAX_TIMESTAMP and < MAX_MS → /1000; < MAX_US → /1e6; else `ValueError: … too large`).
Windows-safe: `MAX_TIMESTAMP` falls back to year-3000 (64-bit) / 2038 (32-bit) constants.
`Arrow.min` / `Arrow.max` are prebuilt from `datetime.min/max` (naive → UTC).

Ranges / spans (frames: `year(s) month(s) week(s) day(s) hour(s) minute(s) second(s) microsecond(s) quarter(s)`; anything else → `ValueError`):

```python
Arrow.range(frame, start: Arrow|datetime, end=None, tz=None, limit=None) -> Generator[Arrow, None, None]
# end may be INCLUDED (unlike builtin range). end or limit REQUIRED else ValueError.
# tz REPLACES zones of start/end — pass naive + tz, or aware same-zone without tz.
Arrow.span_range(frame, start, end, tz=None, limit=None, bounds="[)", exact=False) -> Iterable[tuple[Arrow, Arrow]]
Arrow.interval(frame, start, end, interval=1, tz=None, bounds="[)", exact=False) -> Iterable[tuple[Arrow, Arrow]]  # interval<1 → ValueError
```

Instance span/floor/ceil:

```python
Arrow.span(frame, count=1, bounds="[)", exact=False, week_start=1) -> tuple[Arrow, Arrow]
# bounds in (), (], [), [] (validate_bounds else ValueError); week_start 1(Mon)..7(Sun) else ValueError.
# default [) floor = 03:00:00, ceil = 03:59:59.999999; '[]' ceil rolls to next frame start.
Arrow.floor(frame, **kwargs) -> Arrow   # span(frame)[0]; accepts week_start
Arrow.ceil(frame, **kwargs) -> Arrow    # span(frame)[1]
```

Mutation / conversion (all return **new** objects; `Arrow` is effectively immutable):

```python
Arrow.clone() -> Arrow
Arrow.replace(**{year,month,day,hour,minute,second,microsecond,tzinfo,fold}) -> Arrow
# week/quarter → ValueError (absolute set not supported); unknown key → ValueError: Unknown attribute.
# tzinfo REPLACES without conversion (compare .to() which CONVERTS).
Arrow.shift(check_imaginary=True, **{years,months,weeks,days,hours,minutes,seconds,microseconds,quarters,weekday}) -> Arrow
# quarters → months×3; weekday int 0(Mon)..6(Sun) or dateutil MO..SU (result >= start for ints);
# bad key → ValueError listing valid frames; imaginary DST times auto-resolved unless check_imaginary=False.
Arrow.to(tz: TZ_EXPR) -> Arrow   # convert; 'local'/'utc' accepted
```

Formatting / humanizing:

```python
Arrow.format(fmt="YYYY-MM-DD HH:mm:ssZZ", locale="en-us") -> str
Arrow.humanize(other=None, locale="en-us", only_distance=False, granularity="auto"|str|list) -> str
Arrow.dehumanize(input_string: str, locale="en_us") -> Arrow
Arrow.__format__(formatstr) -> str   # f"{arw:'YYYY-MM-DD'}" works; "" → str(arw) == isoformat
```

`humanize` signature detail:

- `other`: `None` (→ now in self's zone), `Arrow`, or `datetime` (naive assumed in self's zone).
  Anything else → `TypeError`.
- `granularity="auto"`: `<10s → "just now"`; then second(s)/minute/minutes/hour/hours/day/days/week(s)/month(s)/year(s) thresholds per `_SECS_MAP` (month=30.5d, quarter=91.5d, year=365d).
- `granularity="second"|"minute"|"hour"|"day"|"week"|"month"|"quarter"|"year"`: single-unit output.
- `granularity=[...]`: multi-unit, e.g. `["hour","minute"]` → `"2 hours and 11 minutes ago"` (needs `and_word`; en has it). Empty list → `ValueError`; unknown → `ValueError`; untranslated frame → `ValueError … not currently translated …`.
- `only_distance=True` drops "in/ago" (`"2 hours"`); en + `now` → `"instantly"`.
- `locale` unknown → `ValueError: Unsupported locale …`.

`dehumanize` parses `"2 days ago"` / `"in a month"` back to `Arrow` via `shift()`; supported
locales = `DEHUMANIZE_LOCALES` (~170 names incl. `en`, `fr`, `de`, `ja`, `zh-cn`, …);
unsupported → `ValueError`; unparseable → `ValueError`.

Properties / attributes:

```python
Arrow.tzinfo -> tzinfo        # never None
Arrow.datetime -> datetime    # the wrapped aware datetime
Arrow.naive -> datetime       # tzinfo stripped (wall time kept)
Arrow.timestamp() -> float    # .timestamp() in UTC
Arrow.int_timestamp -> int
Arrow.float_timestamp -> float
Arrow.fold -> int             # 0/1 ambiguous-wall-time disambiguator
Arrow.ambiguous -> bool       # dateutil.datetime_ambiguous
Arrow.imaginary -> bool       # not dateutil.datetime_exists (skipped DST wall time)
Arrow.week -> int             # ISO week via __getattr__ (isocalendar()[1])
Arrow.quarter -> int          # (month-1)//3+1 via __getattr__
# every other datetime attr (year..microsecond, date/time fns, dst(), …) proxies via __getattr__.
```

Queries / datetime passthroughs:

```python
Arrow.is_between(start: Arrow, end: Arrow, bounds="()") -> bool  # non-Arrow → TypeError; bounds validated
Arrow.date() -> date;  Arrow.time() -> time;  Arrow.timetz() -> time
Arrow.astimezone(tz) -> datetime;  Arrow.utcoffset() -> timedelta|None;  Arrow.dst() -> timedelta|None
Arrow.timetuple() -> struct_time;  Arrow.utctimetuple() -> struct_time
Arrow.toordinal() -> int;  Arrow.weekday() -> int (0-6);  Arrow.isoweekday() -> int (1-7)
Arrow.isocalendar() -> tuple;  Arrow.isoformat(sep="T", timespec="auto") -> str
Arrow.ctime() -> str;  Arrow.strftime(fmt) -> str   # NOTE: strftime codes, NOT arrow tokens
Arrow.for_json() -> str     # == isoformat(); simplejson protocol
# NOTE: there is NO fromjson/from_json in 1.4.0 (grep confirms). Deserialize with arrow.get(iso_string).
```

Math / comparison:

```python
Arrow + timedelta|relativedelta -> Arrow;  Arrow - timedelta|relativedelta -> Arrow
Arrow - Arrow|datetime -> timedelta;  datetime - Arrow -> timedelta  (__rsub__)
==/!=/ >/>=/</<= vs Arrow|datetime (tz-aware compare); == vs other types → False (not NotImplemented)
hash(Arrow) == hash(datetime)
repr → <Arrow [2013-05-05T12:30:45+00:00]>;  str → isoformat
```

### 4. `formatter.py` — `DateTimeFormatter(locale='en-us')`

```python
DateTimeFormatter.format(dt: datetime, fmt: str) -> str   # (defined without self; called on instance)
```

Full token table (escape with `[…]`, e.g. `'[Today is] YYYY-MM-DD'`):

| Token | Output | Example |
|---|---|---|
| `YYYY` / `YY` | 4-digit / 2-digit year (locale-aware CJK variants) | 2013 / 13 |
| `MMMM` / `MMM` / `MM` / `M` | month name / abbrev / 02d / digit | May / May / 05 / 5 |
| `DDDD` / `DDD` | day-of-year 03d / digit | 129 / 129 |
| `DD` / `D` / `Do` | 02d / digit / ordinal (`Do` locale regex) | 09 / 9 / 9th |
| `dddd` / `ddd` / `d` | weekday name / abbrev / ISO 1-7 | Thursday / Thu / 4 |
| `HH` / `H` / `hh` / `h` | 24h 02d / 24h / 12h 02d / 12h | 13 / 13 / 01 / 1 |
| `mm` / `m`, `ss` / `s` | minute / second, padded + unpadded | 05 |
| `SSSSSS`…`S` | microsecond truncated to 6…1 digits | 970460 → SSS=970 |
| `X` / `x` | unix timestamp (float str) / µs int str | 1367992474.29… |
| `ZZZ` | `dt.tzname()` (may be None) | PDT |
| `ZZ` / `Z` | `+HH:MM` / `+HHMM` (naive dt → UTC offset!) | -07:00 / -0700 |
| `a` / `A` | locale meridian lower / upper | pm / PM |
| `W` | ISO week-date `YYYY-Www-d` | 2013-W19-4 |

Named presets (`arrow.FORMAT_*`): `ATOM="YYYY-MM-DD HH:mm:ssZZ"`,
`COOKIE="dddd, DD-MMM-YYYY HH:mm:ss ZZZ"`, `RFC822="ddd, DD MMM YY HH:mm:ss Z"`,
`RFC850="dddd, DD-MMM-YY HH:mm:ss ZZZ"`, `RFC1036=RFC822`, `RFC1123/RFC2822/RSS="ddd, DD MMM YYYY HH:mm:ss Z"`,
`RFC3339="YYYY-MM-DD HH:mm:ssZZ"`, `RFC3339_STRICT="YYYY-MM-DDTHH:mm:ssZZ"`, `W3C=ATOM`.
Default `format()` = `"YYYY-MM-DD HH:mm:ssZZ"`.

### 5. `parser.py` — parsing

```python
class ParserError(ValueError)          # base; also exported at top level
class ParserMatchError(ParserError)    # single-format mismatch (lets multiformat keep trying)

DateTimeParser(locale="en-us", cache_size=0)
DateTimeParser.parse_iso(datetime_string, normalize_whitespace=False) -> datetime
DateTimeParser.parse(datetime_string, fmt: str|list[str], normalize_whitespace=False) -> datetime
TzinfoParser.parse(tzinfo_string: str) -> tzinfo   # raises ParserError
```

Parser hints (all formats `parse_iso` tries, in order — date × time × tz):

- Dates: `YYYY-MM-DD, YYYY-M-DD, YYYY-M-D, YYYY/MM/DD, YYYY/M/DD, YYYY/M/D, YYYY.MM.DD, YYYY.M.DD, YYYY.M.D, YYYYMMDD, YYYY-DDDD, YYYYDDDD, YYYY-MM, YYYY/MM, YYYY.MM, YYYY, W` (ISO week-date like `2013-W19-4`). NOTE `YYYYMM` deliberately omitted (ambiguous vs YYMMDD).
- Times after `T` or single space: `HH, HHmm, HH:mm, HHmmss, HH:mm:ss, + fraction (.micros)` in basic or extended form; tz suffix parsed as `Z` (basic `+HHMM`/`Z`) or `ZZ` (extended `+HH:MM`/`Z`).
- Multiple spaces, or `T` + spaces → `ParserError: Expected an ISO 8601-like string…`.
- `parse(s, fmt|[fmts])`: tokens are the formatter tokens (incl. `X` unix-ts, `x` expanded ms/µs auto-normalized, `ZZZ` tz-name, `MMMM/MMM` locale month names, `dddd/ddd` weekday → next-weekday resolution, `Do` locale ordinal, `a/A` meridian, `W` ISO week-date, `S` fractional with banker's rounding, `YY` pivot 68 → 1900/2000, `DDDD/DDD` needs year + forbids month, hour 24 only for exact midnight). `[…]` = literal. Stricter-than-naive word boundaries let dates be found inside sentences but reject `blah1998-09-12blah`.
- `TzinfoParser` accepts `'local'`, `'utc'/'UTC'/'Z'`, ISO offsets (`+HH`, `+HHMM`, `+HH:MM`, `(UTC…)` prefixes), else `ZoneInfo(name)`; else `ParserError: Could not parse timezone expression …`.
- `normalize_whitespace=True` is the escape hatch for sloppy strings (`re.sub(r"\s+"," ",…)`).

`_build_datetime` defaults missing fields to `1-01-01 00:00:00` (naive unless tz token present) —
so `arrow.get("2019")` → year only, and midnight-24:00 rolls to next day.

### 6. `locales.py` — i18n (6652 lines, 85 classes)

```python
get_locale(name: str) -> Locale              # case-insensitive, _ ↔ - normalized; else ValueError: Unsupported locale
get_locale_by_class_name(name: str) -> Locale
class Locale: names, timeframes, meridians, past, future, and_word,
  month_names/abbreviations (1-indexed, ["", Jan..]), day_names/abbreviations (1-indexed ["", Mon..]),
  ordinal_day_re, describe(), describe_multi(), day_name(), month_number(), meridian(), ordinal_number(), …
```

English sample: `past="{0} ago"`, `future="in {0}"`, `and_word="and"`,
`"just now"/"a minute"/"an hour"/"{0} hours"…`. Sub-locales (`en-gb`, `fr-ca`, `pt-br`,
`de-ch`, `zh-cn/tw/hk`, `ar/Levant…`, `sr`…) override strings/plural rules/ordinals/meridians.

**Adding a locale** (auto-registers via `__init_subclass__`, duplicate name → `LookupError`):

```python
from arrow.locales import Locale
class KlingonLocale(Locale):
    names = ["kl", "kl-kl"]
    past = "{0} ret"          # required
    future = "in {0}"         # required
    and_word = "and"          # optional (multi-granularity join)
    timeframes = {"now": "now", "second": "a second", "seconds": "{0} seconds", …}  # all 17 TimeFrameLiteral keys
    meridians = {"am": "am", "pm": "pm", "AM": "AM", "PM": "PM"}
    month_names = ["", "January", …];  month_abbreviations = ["", "Jan", …]
    day_names = ["", "Monday", …];     day_abbreviations = ["", "Mon", …]
    ordinal_day_re = r"((?P<value>\d+)(st|nd|rd|th))"   # for Do parsing
    def _ordinal_number(self, n): return f"{n}th"       # override for 1st/2nd/3rd etc.
```

### 7. `util.py` + `constants.py`

```python
next_weekday(start_date: date|datetime|None, weekday: 0-6) -> datetime  # ValueError outside 0-6
is_timestamp(v) -> bool          # bool excluded; int/float/numeric-str True
validate_ordinal(v)             # TypeError non-int; ValueError outside 1..max
normalize_timestamp(ts: float) -> float   # ms/µs → s; too large → ValueError
iso_to_gregorian(y, w, d) -> date         # ValueError week 1-53 / day 1-7
validate_bounds(b)              # must be () (] [) [] else ValueError
MAX_TIMESTAMP / MAX_TIMESTAMP_MS / MAX_TIMESTAMP_US / MAX_ORDINAL / MIN_ORDINAL / DEFAULT_LOCALE="en-us"
```

## App usage & correctness

Why installed: **transitive only.** `pyproject.toml` never lists arrow (runtime deps are
`av, flet, flet-ads, flet-audio, flet-audio-recorder, flet-camera, flet-permission-handler,
flet-video, httpx`; dev adds `flet-cli, flet-desktop, pytest, ruff`). Chain in `uv.lock`:

```text
flet (1.0.0) [dev: flet-cli] → flet-cli (1.0.0) → cookiecutter → arrow (1.4.0) → python-dateutil (2.9.0.post0) + tzdata (2026.4)
```

`REQUESTED` is empty → pip/uv auto-pulled it; removing `flet-cli`/`cookiecutter` would drop it.

(a) **Direct usage: NONE.** `grep -rni arrow src tests` returns only Flet icon constants
(`PLAY_ARROW_ROUNDED`, `ARROW_BACK_ROUNDED`, `ARROW_UPWARD/DOWNWARD_ROUNDED`) — zero
`import arrow` / `arrow.` calls. `uv.lock` confirms the only `arrow` consumer is `cookiecutter`.

(b) **Misuse: none possible (unused), but current hand-rolled datetime code has real issues:**

- `src/core/logger_handler.py:22` — `datetime.fromtimestamp(record.created).strftime("%H:%M:%S")`
  is **naive-local**: correct wall time on-device but unusable for cross-device/export ordering;
  no date, no tz, no ms.
- `src/main.py:541/549/555` — `job.finished_at = time.time()` raw epoch floats: fine for math,
  opaque in storage/debug; no `started_at` pairing visible for duration.
- `capture_screen.py:373/395/533`, `join_screen.py:154`, `probe_screen.py:254/267`,
  `streams_screen.py:101` — filenames `photo_{int(time.time())}.jpg`, `rec_….{ext}`,
  `joined_…`, `{stem}_dossier_….md`: collision-prone within one second, unsortable-by-eye,
  no human date.
- `ad_service.py:161` — `now = time.time()` cooldown math: correct use, keep as-is (monotonic would be even better).
- `history_screen.py` — renders `job_card_view` with **no timestamp at all** (only search/filter/delete).
- `update_service.py` — parses `version.json` build numbers, ignores any date fields.
- `core/changelog.py` — `CHANGELOG` keyed by version string, no dates.

(c) **Correctness note:** because arrow is already in the venv (via cookiecutter), importing it
costs nothing extra at runtime — but it is NOT a declared dependency, so any v1 adoption must
add `arrow>=1.4.0` (or `arrow==1.4.0`) to `pyproject.toml` `dependencies`, else a
`flet-cli`-free production lock could silently lose it.

## Underused APIs to adopt

All optional for v1, ordered by value. (No app source modified per task rules.)

1. **History relative timestamps** — `history_screen.py` + `job_card.py`:
   `arrow.get(job.finished_at).humanize()` → "3 hours ago"; title tooltip
   `arrow.get(job.finished_at).to('local').format('YYYY-MM-DD HH:mm')`. Requires storing an
   epoch/datetime on the job (only `finished_at` exists today).
2. **Job duration display** — `humanize(other, only_distance=True)` or `describe_multi`:
   `arrow.get(end).humanize(start, only_distance=True)` → "2 minutes"; multi-granularity
   `humanize(granularity=["hour","minute"])` → "1 hour and 3 minutes".
3. **Filename-safe stamps** — replace `int(time.time())` with
   `arrow.now().format('YYYYMMDD-HHmmss')` → `photo_20260923-143022.jpg`; add `SSSSSS`/counter
   on collision; `[…]` escapes literals (`'YYYY-MM-DD[at]HH-mm'`).
4. **Log timestamps** — `logger_handler.py`: `arrow.now().format('HH:mm:ss')` today, or
   `arrow.now().format('YYYY-MM-DD HH:mm:ssZZ')` for exportable diagnostics; `for_json()` for JSON logs.
5. **Changelog dates** — `core/changelog.py`: store ISO dates per version, render
   `arrow.get(date_str).format('MMMM D, YYYY')` ("September 23, 2026").
6. **Update-service release dates** — `update_service.py`: `arrow.get(remote["published_at"]).humanize()`
   → "released 2 days ago"; `is_between()` to gate "new in last 7 days" badges.
7. **Parsing robustness** — `arrow.get(s)` handles ISO incl. `Z`/offsets/basic `YYYYMMDD` out of the box;
   `get(s, ['MM/DD/YYYY','YYYY-MM-DD HH:mm:ss'])` multi-format fallback; `normalize_whitespace=True`
   for pasted media metadata strings. Never hand-roll `strptime` again.
8. **Spans for grouping** — `Arrow.span('day'/'week'/'month')`, `span_range`, `interval` can bucket
   history ("Today / This week / Older") and batch-queue analytics without manual floor/ceil math.

## Gotchas

1. **Naive-in = UTC, not local.** `arrow.get(datetime(2013,5,5))` → midnight **UTC**; aware datetimes
   keep their zone. `Arrow.fromtimestamp(ts)` with no zone → **local**, but `arrow.get(ts)` → **UTC**.
   Pick one path and stick to it; prefer `arrow.get(ts).to('local')` for display.
2. **`replace(tzinfo=…)` ≠ `to(…)`.** `replace` re-labels the wall time; `to` converts it. Mixing them
   up shifts displayed times by the UTC offset.
3. **`humanize()` without TZ lies across zones.** Naive `other` is assumed in `self`'s zone; always
   compare aware↔aware (`arrow.get(a).to('local')` vs `arrow.get(b).to('local')`).
4. **`ZZ` vs `Z` vs `ZZZ`.** `ZZ` → `+HH:MM`, `Z` → `+HHMM`, `ZZZ` → `tzname()` (can be `None`/ambiguous).
   Default format uses `ZZ`.
5. **`X`/`x` parse *and* format.** `format('X')` dumps epoch; `get(s,'X')` reads it; `x` is ms/µs
   auto-normalized — handy for JS-style timestamps from web manifests.
6. **No `fromjson`.** The brief's `fromjson` doesn't exist in 1.4.0; serialize with `for_json()`/`isoformat()`,
   deserialize with `arrow.get(s)`.
7. **`strptime` uses `%`-codes, `get(s, fmt)` uses arrow tokens.** Don't mix them.
8. **`str` vs `datetime` in `get`.** `arrow.get('2013-05-05')` parses ISO; `arrow.get(dt, 'US/Pacific')`
   re-zones a datetime. Two strings = value + format.
9. **Bool is not a timestamp** (`is_timestamp(True)` → False); `get(None)` → `TypeError`; absurd
   timestamps → `ValueError: too large`; bad zones → `ParserError` (or `ValueError` from `_get_tzinfo`).
10. **DST edge cases.** `shift()` resolves imaginary times by default (`check_imaginary=True`);
    inspect `.ambiguous`/`.imaginary`/`.fold` around fall-back/spring-forward transitions.
11. **`range()` includes `end`, needs `end` or `limit`.** Unbounded `range(frame, start)` raises;
    cap exports with `limit=` to avoid infinite iteration.
12. **Locale gaps.** `humanize(locale='xx')` → `ValueError: Unsupported locale`; some locales lack
    `quarter`/`week` frames; `dehumanize` supports only `DEHUMANIZE_LOCALES` (~170 tags).
13. **Transitive-only today.** Don't `import arrow` in shipped code until it's promoted to
    `pyproject.toml` `dependencies`; otherwise a lock without `cookiecutter` breaks the app.
14. **`YYYYMM` won't parse** (deliberately omitted); `YYYYMMDD` will. `YY` pivots at 68 (→1900/2000).
