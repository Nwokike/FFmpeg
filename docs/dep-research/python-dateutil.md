# python-dateutil 2.9.0.post0 — Complete API Reference

Import name: `dateutil`. Package name on PyPI: `python-dateutil`.
Role in this app: **transitive dependency** — pulled in by `arrow 1.4.0`
(`uv.lock`: `arrow → {python-dateutil, tzdata}`). No app module imports
`dateutil` directly (verified: zero hits for `dateutil|relativedelta|rrule|
gettz|tzutc|tzlocal|isoparse` across `src/`, `tests/`, `tools/`).
History timestamps use epoch floats (`Job.created_at: float =
field(default_factory=time.time)` in `src/core/state.py`), and the only
`datetime` usage in app code is log-line formatting
(`src/core/logger_handler.py`).

---

## Files

18 `.py` files under
`<repo>\.venv\Lib\site-packages\dateutil`
(`__pycache__` excluded), plus the bundled zoneinfo tarball:

| File | Lines | Contents |
|---|---|---|
| `__init__.py` | 26 | Lazy `__getattr__` re-export of 7 submodules; `__version__ = '2.9.0.post0'` via `_version.py` |
| `_version.py` | 5 | Setuptools-scm stub: `__version__ = version = '2.9.0.post0'`, tuple `(2, 9, 0)` |
| `_common.py` | 44 | `weekday` base class (`weekday`, `n`, `__call__(n)` → `MO(+1)` style) |
| `easter.py` | 90 | `easter(year, method=EASTER_WESTERN)`; constants `EASTER_JULIAN=1`, `EASTER_ORTHODOX=2`, `EASTER_WESTERN=3` |
| `parser/__init__.py` | 62 | Re-exports `parse, parser, parserinfo, isoparse, isoparser, ParserError, UnknownTimezoneWarning`; private `_timelex/_tzparser/_resultbase/_parsetz` wrapped with DeprecationWarning |
| `parser/_parser.py` | 1613 | Generic fuzzy parser: `parser`, `parse()`, `parserinfo`, `ParserError`, `UnknownTimezoneWarning`, `DEFAULTPARSER`, `DEFAULTTZPARSER`, `_tzparser`, `_parsetz` |
| `parser/isoparser.py` | 416 | Strict parser: `isoparser(sep=None)`, `isoparse` = `DEFAULT_ISOPARSER.isoparse` |
| `relativedelta.py` | 599 | `relativedelta`, weekday singletons `MO..SU` |
| `rrule.py` | 1737 | `rrule`, `rruleset`, `rrulestr`, freq consts 0–6, weekday subclass (rejects `n==0`) |
| `tz/__init__.py` | 12 | Re-exports everything from `.tz` + `DeprecatedTzFormatWarning` |
| `tz/_common.py` | 419 | `enfold()`, `_tzinfo` (fold-aware `fromutc`), `tzrangebase` abstract DST-range base |
| `tz/_factories.py` | 80 | `_TzSingleton` (tzutc), `_TzOffsetFactory` (tzoffset cache), `_TzStrFactory` (tzstr cache) |
| `tz/tz.py` | 1849 | `tzutc`, `tzoffset`, `tzlocal`, `tzfile`, `tzrange`, `tzstr`, `tzical`, `gettz`, `datetime_ambiguous/exists`, `resolve_imaginary`, `UTC` |
| `tz/win.py` | 370 | `tzwin`, `tzwinlocal`, `tzres` — raises `ImportError` on non-Windows (this venv: file present; importable since host is Windows) |
| `tzwin.py` | 3 | Shim: `from .tz.win import *` |
| `utils.py` | 64 | `today(tzinfo=None)`, `default_tzinfo(dt, tzinfo)`, `within_delta(dt1, dt2, delta)` |
| `zoneinfo/__init__.py` | 168 | Deprecated bundled-DB access: `get_zonefile_instance()`, `gettz()` (DeprecationWarning), `gettz_db_metadata()` (deprecated) |
| `zoneinfo/dateutil-zoneinfo.tar.gz` | — | Bundled Olson DB snapshot (156 KB) backing `ZoneInfoFile` |
| `zoneinfo/rebuild.py` | 75 | Script to rebuild the tarball from system zoneinfo |

`RECORD` lists 27 installed files (18 `.py` + `tzwin.py` shim + tarball +
8 dist-info entries).

## Metadata

From `python_dateutil-2.9.0.post0.dist-info/METADATA` (+ `LICENSE`, `WHEEL`):

- **Version:** `2.9.0.post0` (post-release of 2.9.0; `_version_tuple = (2, 9, 0)`).
- **Requires-Dist:** `six >=1.5` — the ONLY runtime pin. Installed: `six 1.17.0`
  (satisfies). **No `pytz` dependency, no extras** (`Provides-Extra` absent).
  Verified: `pytz` is NOT in the venv dependency closure; `tzdata` comes via
  `arrow`, not dateutil.
- **License:** dual `Apache-2.0 OR BSD-3-Clause` for contributions after
  2017-12-01; pre-2017 code BSD-3-Clause only. Classifiers list both
  `OSI Approved :: BSD License` and `Apache Software License`. `LICENSE` file
  header is the Apache 2.0 text with the dual-license note in METADATA body.
  Safe for proprietary/app-store distribution; keep the LICENSE attribution.
- **Requires-Python:** `!=3.0.*,!=3.1.*,!=3.2.*,>=2.7` — effectively Python
  ≥ 2.7 / ≥ 3.3. Python 3.14 (this app) is fine. Code still carries
  `six`/`PY2` shims and a pre-3.6 `_DatetimeWithFold` fallback — dead weight,
  not a risk.
- **Wheel:** `py2.py3-none-any`, `zip-safe`.

## Module-by-module API

### `dateutil.parser` — generic fuzzy parser (`parser/_parser.py`)

```python
parse(timestr, parserinfo=None, *,
      default=None, ignoretz=False, tzinfos=None,
      dayfirst=None, yearfirst=None, fuzzy=False, fuzzy_with_tokens=False)
parser(info=None).parse(timestr, default=None, ignoretz=False, tzinfos=None, **kwargs)
DEFAULTPARSER  # parser(parserinfo()) singleton backing parse()
DEFAULTTZPARSER  # _tzparser() singleton backing _parsetz()
```

- `default`: missing components are taken from it; when omitted it is
  `datetime.now()` with time zeroed (midnight today). So `parse("March 5")`
  inherits *this year*.
- `dayfirst`/`yearfirst`: resolve ambiguous numeric dates (`01/05/09`).
  Both default `False` (US `MM/DD/YY`). `parserinfo(dayfirst=False,
  yearfirst=False)` bakes in app-wide defaults; pass a custom `parserinfo`
  for EU-style dates.
- `fuzzy=True`: skip unknown tokens (`"Today is January 1, 2047 at 8:21AM"`).
  `fuzzy_with_tokens=True` implies fuzzy and returns `(datetime, skipped_tokens)`.
- `ignoretz=True`: drop any zone info, return naive datetime. `tzinfos` ignored.
- `tzinfos`: `dict[str, int|tzinfo]` (name → seconds-east or tzinfo) or
  callable `(tzname, tzoffset) -> tzinfo|int|None`. Needed for abbreviations
  like `BRST`/`CST` that the built-in table (`parserinfo.UTCZONE`,
  `TZOFFSET`, e.g. `EST=-18000`, `EDT=-14400`, `GMT/UTC/Z`) does not know.
  Unknown zones emit `UnknownTimezoneWarning` and come back naive.
- `parserinfo.convertyear(year, century_specified=False)`: 2-digit-year pivot
  — years `< 69` → 2000s, else 1900s.
- Accepts: ISO/RFC-2822/`ctime` (`Sat Oct 11 17:13:46 UTC 2003`), month names
  (full/abbreviated), `AM/PM`, numeric offsets (`-0300`, `-03:00`, `-03`,
  `GMT+3` with inverted-sign correction), tz abbreviations, weekday names
  (validated, mostly ignored), `,`/`.`/`/`/`-` separators, fractional seconds
  (`_parsems`, dot/comma), bare times (date from `default`).
- Failure modes — raises `ParserError` (subclass of `ValueError`) for unknown
  format / dateless string / impossible date (`Feb 30`); `TypeError` for
  non-string input; `OverflowError` for out-of-range years. `parser._parse()`
  returns `(None, None)` internally on `IndexError/ValueError`.

### `dateutil.parser.isoparser` — strict ISO-8601 (`parser/isoparser.py`)

```python
isoparser(sep=None)
isoparser.isoparse(dt_str) -> datetime
isoparser.parse_isodate(datestr) -> date
isoparser.parse_isotime(timestr) -> time
isoparser.parse_tzstr(tzstr, zero_as_utc=True) -> tzinfo
isoparse  # DEFAULT_ISOPARSER.isoparse
```

- Dates: `YYYY`, `YYYY-MM`, `YYYY-MM-DD`/`YYYYMMDD`, ordinal `YYYY-DDD`,
  week `YYYY-Www[-D]`/`YYYYWww[D]`. Times: `hh`, `hh:mm`/`hhmm`,
  `hh:mm:ss`/`hhmmss`, up to 6 fractional-second digits (`.` or `,`).
  `24:00` midnight allowed (only with all-zero rest; rolls to next day).
  Offsets: `Z`/`z`, `±HH`, `±HHMM`, `±HH:MM`; zero offsets → `tz.UTC`
  (`tzutc` singleton); others → `tzoffset(None, seconds)`.
- `sep=None` accepts any single separator char between date and time; pass
  `sep='T'` for strict ISO. Non-ASCII input → `ValueError`. Unspecified
  components default to lowest (`2024-05` → May 1, `00:00:00`).
- Raises `ValueError` on trailing garbage, inconsistent separators, bad
  ordinal/weekday. **Prefer over `parse()` for machine-generated tags**
  (`creation_time`, ID3): faster, deterministic, no `dayfirst` traps, strict
  errors instead of silent misparse.

### `dateutil.relativedelta` (`relativedelta.py`)

```python
relativedelta(dt1=None, dt2=None, *,
  years=0, months=0, weeks=0, days=0, leapdays=0,
  hours=0, minutes=0, seconds=0, microseconds=0,        # plural = RELATIVE
  year=None, month=None, day=None, hour=None, minute=None,
  second=None, microsecond=None,                        # singular = ABSOLUTE (replace)
  weekday=None, yearday=None, nlyearday=None)
```

- Absolute-then-relative application order: year → month → day → hour →
  minute → second → microsecond, **weekday last**. `day=1, MO(1)` = first
  Monday of month; `relativedelta(months=+6)` = calendar-aware +6 months with
  end-of-month clamping (`Jan 31 + 1 month` → `Feb 28/29`).
- `weekday`: `MO..SU` singletons from this module (also mirrored in `rrule`).
  `MO(1)`/`MO(+1)` = next Monday-or-today (no-op if already Monday);
  `MO(-1)` = last Monday-or-today; `FR(2)` = 2nd Friday onward. Bare `MO` ≡
  `MO(+1)`. Int accepted (`0=MO`).
- `relativedelta(dt1, dt2)` diff mode: `years/months` calendar part +
  `seconds/microseconds` remainder; iterates month adjustment for end-of-month
  overshoot. Only accepts date/datetime pairs (`TypeError` otherwise).
- Extras: `weeks` property (derived from `days`); `.normalized()` cascades
  float remainders down; `+`/`-`/`*`/`/`/`abs`/`neg` supported; `years/months`
  must be integral (`ValueError` on floats); float absolute values →
  `DeprecationWarning`. `bool(rd)` False when empty.

### `dateutil.rrule` (`rrule.py`)

```python
YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, MINUTELY, SECONDLY = range(7)
rrule(
    freq,
    dtstart=None,
    interval=1,
    wkst=None,
    count=None,
    until=None,
    bysetpos=None,
    bymonth=None,
    bymonthday=None,
    byyearday=None,
    byeaster=None,
    byweekno=None,
    byweekday=None,
    byhour=None,
    byminute=None,
    bysecond=None,
    cache=False,
)
rruleset(cache=False)  # .rrule/.rdate/.exrule/.exdate, dedup + exclusion merge
rrulestr(
    s,
    dtstart=None,
    cache=False,
    unfold=False,
    forceset=False,
    compatible=False,
    ignoretz=False,
    tzids=None,
    tzinfos=None,
)
```

- RFC-5545 superset: `INTERVAL`, `COUNT`, `UNTIL`, `BYSETPOS` (1..366,
  nonzero), `BYMONTH/DAY/YEARDAY/WEEKNO/WEEKDAY/HOUR/MINUTE/SECOND`,
  `BYEASTER` (needs `easter` lazy import), `WKST`. Frequency defaults when no
  BY-xxx given: YEARLY → same month/day, MONTHLY → same monthday, WEEKLY →
  same weekday as `dtstart`.
- `dtstart` defaults to `now()` (tz-aware now if `until` is aware);
  `dtstart`+`until` aware/naive mismatch → `ValueError`;
  `count`+`until` together → `DeprecationWarning`.
- Consume: iteration, `rr[i]`/`rr.count()`/`dt in rr`, `.before(dt, inc=False)`,
  `.after(dt, inc=False)`, `.xafter(dt, count, inc)`, `.between(after, before,
  inc, count)`, `str(rr)` round-trips to RFC string, `.replace(**kwargs)`.
  `byweekday=MO(2)` = 2nd Monday; `BYSETPOS=-1` = last of set.
- `rrulestr` parses `RRULE:`/`RDATE`/`EXDATE`/`EXRULE`/`DTSTART`/`TZID` text;
  `forceset=True` always returns `rruleset`; `unfold=True` handles folded
  iCalendar lines.

### `dateutil.tz` (`tz/tz.py`, `tz/win.py`, `tz/_common.py`)

```python
gettz(name=None)          # best-match dispatch, cached (same input → same object)
tzutc()                   # UTC singleton (alias UTC); utcoffset 0, dst 0
tzoffset(name, offset)    # fixed offset; offset = seconds int or timedelta; cached
tzlocal()                 # OS local zone via time.timezone/altzone/tzname
tzfile(fileobj, filename=None)        # tzfile(5) parser: /usr/share/zoneinfo, /etc/localtime
tzrange(stdabbr, stdoffset, dstabbr, dstoffset, start, end)  # relativedelta-based DST range
tzstr(s, posix_offset=False)          # 'EST5EDT', 'AEST-10AEDT-11,M10.1.0/2,M4.1.0/3'
tzical(fileobj)           # .keys() / .get(tzid) from VTIMEZONE blocks
tzwin(name) / tzwinlocal()            # Windows registry zones; None on non-Windows import path
enfold(dt, fold=1)
datetime_ambiguous(dt, tz=None) -> bool
datetime_exists(dt, tz=None) -> bool  # False in DST gaps
resolve_imaginary(dt) -> datetime      # fall FORWARD across gap
```

- `gettz` resolution order: IANA file/zoneinfo path → `tzlocal()` for
  empty/`None` → Windows names (on win32) → `tzstr` for `EST5EDT`-style →
  `tzfile`. Returns `None` for garbage (does NOT raise).
- `fold`/PEP-495: `tzfile`/`tzlocal`/`tzrange` set `fold` on `fromutc`;
  `datetime_ambiguous` checks both folds; `datetime_exists` round-trips via
  UTC. `tzwin` lacks full fold support — prefer IANA names even on Windows.
- `tzical(fileobj)`: path str or stream of RFC-5545 `VTIMEZONE`; `get(tzid)`
  with 0 zones → `ValueError("no timezones defined")`, >1 zone without tzid →
  `ValueError`.
- `datetime.timestamp()` interplay: naive datetimes are interpreted as LOCAL
  time by CPython — attach `tzinfo` first (`default_tzinfo(dt, tzlocal())` or
  `dt.replace(tzinfo=tzutc())` for UTC) or timestamps shift by the UTC offset.

### `dateutil.utils` / `easter` / `zoneinfo`

```python
today(tzinfo=None)  # today at midnight, tz-aware if tzinfo given
default_tzinfo(dt, tzinfo)  # stamp tzinfo onto NAIVE datetimes only; aware pass through
within_delta(dt1, dt2, delta)  # abs(dt1-dt2) <= abs(delta); timedelta compare
easter(year, method=EASTER_WESTERN)
ZoneInfoFile(stream).get(
    name
) / get_zonefile_instance()  # bundled-DB access (zoneinfo.gettz deprecated)
```

## App usage & correctness

**(a) Dependency chain (verified in venv + `uv.lock`).**

```
ffmpeg app  ──(no direct dateutil import)──▶  arrow 1.4.0  ──▶  python-dateutil 2.9.0.post0 ──▶ six 1.17.0
                                                                    ▲
                                              (arrow also pulls tzdata; dateutil does NOT need pytz/tzdata)
```

Arrow's concrete dateutil touchpoints (read in installed source):

- `arrow/arrow.py`: `from dateutil import tz as dateutil_tz`, `from
  dateutil.relativedelta import relativedelta`. `Arrow.shift()` adds
  `relativedelta(**kwargs)` (adds `quarters` support on top); imaginary-time
  guard calls `dateutil_tz.datetime_exists()` /
  `dateutil_tz.resolve_imaginary()`. `Arrow.ambiguous` /
  `Arrow.nonexistent` delegate to `datetime_ambiguous` / `datetime_exists`.
  `Arrow.to(tz)` accepts dateutil tz objects. **Arrow's string parser is its
  own (`DateTimeParser`, token/regex based) — it does NOT fall back to
  `dateutil.parser.parse`.** So `parse()`/`isoparse()` are genuinely unused
  in the current stack.
- `arrow/util.py`: `next_weekday()` = `rrule(WEEKLY, dtstart, byweekday, count=1)[0]`.
- Surprisingly, **arrow is declared but never imported** by app code either
  (no `import arrow` hit in `src/`): the whole `arrow→dateutil` chain is
  currently dormant. Date handling today = epoch floats + media-packet
  timestamps + one log `strftime`.

**(b) Misuse / correctness findings.**

- No direct misuse — there is no direct use at all. Indirect exposure is via
  arrow only, and arrow uses `relativedelta`/`tz` correctly (DST-safe shift,
  imaginary-time resolution opt-in via `check_imaginary`).
- Naive-datetime risk is **latent, not active**: if future code parses
  `creation_time`/ID3 strings with `parse()` and stores the result without
  normalizing, `datetime.timestamp()` will misinterpret naive values as local
  time. The report's v1 guidance (always `default_tzinfo(..., tzlocal())` or
  `.astimezone(tzutc())` at the boundary) pre-empts this.

**(c) Responsibility split — arrow vs dateutil (recommended).**

- **arrow**: user-facing display/humanize, `shift()` arithmetic, spans,
  `to()` conversions, `next_weekday`. Keep for anything rendered in Flet UI.
- **dateutil (direct)**: `isoparse` for container/ID3 tag strings (strict >
  arrow's lenient parser for machine tags), `rrule` for recurrence schedules
  arrow cannot express, `relativedelta` weekday/month-end math where arrow's
  `shift` is insufficient, `tz` (gettz/tzlocal/datetime_exists) for
  history-timestamp correctness. Import from `dateutil.*` directly for these;
  do not route them through arrow wrappers.

## Underused APIs to adopt

1. **Recurring/scheduled jobs — `rrule`/`rruleset`.**
   `"repeat every weekday at 18:00"` →
   `rrule(DAILY, dtstart=today_18h, byweekday=(MO,TU,WE,TH,FR))`.
   Exclusions (skip holidays) via `rruleset().exdate(holiday)`.
   Persist the rule with `str(rule)` (RFC string) in `storage.json` next to
   the job, rehydrate with `rrulestr(s, dtstart=...)`. Next-fire =
   `rule.after(datetime.now(tzlocal()))`. No new dependency needed.
2. **Robust metadata-date parsing — `isoparse` + `parse` fallback.**
   ffprobe `format.tags.creation_time` is ISO-8601 (`2023-05-01T12:34:56Z`)
   → `isoparse()` (strict, fast, correct tz). ID3 `TDRC`/`TYER` frames and
   odd container tags (`"2023/05/01 12:34:56 +0200"`, bare years) →
   `parse(s, tzinfos={...}, default=datetime(1970,1,1))`, then normalize to
   aware UTC. Never `datetime.strptime` a dozen formats by hand.
3. **Timezone-safe history — `tzlocal`/`tzutc`/`default_tzinfo`.**
   `Job.created_at/finished_at` are epoch floats (good — unambiguous). At
   display time: `datetime.fromtimestamp(ts, tzlocal())` → local wall time;
   for sorting/export: `.astimezone(tzutc()).isoformat()`. Guard DST edges
   in any future scheduler with `datetime_exists()`/`resolve_imaginary()`.
   `utils.today(tzlocal())` gives midnight-local day buckets for "jobs today".
4. **`relativedelta` calendar math** for retention/scheduling UI ("keep
   history 3 months": `now + relativedelta(months=-3)` — month-end safe,
   unlike `timedelta(days=90)`) and "first Monday of month" style presets
   (`day=1, weekday=MO(1)`).
5. **`within_delta`** for flaky timestamp assertions in tests (packet-times vs
   wall-clock).

## Gotchas

1. `parse()` without `default` inherits **today's date** for missing fields;
   dayfirst defaults `False` (`01/05/09` = Jan 5 US-style). Always pass
   `dayfirst`/`default` explicitly for user input.
2. `parse()` returns **naive** datetimes when the string has no zone (and with
   `ignoretz=True`). Naive + `.timestamp()` = interpreted as local time.
   Normalize at the boundary.
3. Unknown tz abbreviations → `UnknownTimezoneWarning` + naive result (silent
   data corruption if warnings are filtered). Supply `tzinfos` for any
   non-standard abbreviation.
4. `isoparse` has **no fuzzy parsing** — garbage raises `ValueError`, never
   guesses. That is the point; catch it and fall back to `parse(..., fuzzy=True)`.
5. `rrule` requires `dtstart`/`until` aware-naive consistency (`ValueError`
   otherwise); `count`+`until` together is deprecated. Iteration is infinite
   without `count`/`until` — always bound it or use `.xafter(count)`.
6. `gettz('garbage')` returns `None`, not an exception. `gettz()`/`gettz('')`
   returns local time. Cache identity holds (`gettz(a) is gettz(a)`).
7. `tzstr('GMT+3')` = UTC+3 (dateutil inverts POSIX by default); pass
   `posix_offset=True` for true POSIX semantics.
8. `dateutil.zoneinfo.gettz` is deprecated — use `dateutil.tz.gettz`
   (system zoneinfo) instead. The bundled tarball DB can lag the OS DB.
9. `tzwin*` exists only on Windows; `tz.win` import raises `ImportError`
   elsewhere — but this app ships on desktop+mobile, so gate with
   `sys.platform` or just use IANA names via `gettz` everywhere.
10. `relativedelta(months=…)` clamps to month end; `weekday` with `n=0`
    raises in `rrule.weekday` (but not in `_common.weekday`); `ParserError`
    is a `ValueError` — `except ValueError` already covers it.
11. `six` is a hard runtime dep (`six>=1.5`, have 1.17.0) — do not prune it;
    conversely `pytz` is NOT required by anything in this chain.
