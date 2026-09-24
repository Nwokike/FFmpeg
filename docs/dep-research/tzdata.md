# tzdata 2026.4 — Complete API Reference

> Package: `tzdata` 2026.4 (IANA release **2026d**) — zic-compiled IANA time zone database as an installable Python package (PEP 615 fallback provider).
> Role in this repo: **transitive dev-only dependency** (`flet-cli → cookiecutter → arrow → tzdata`). NOT in runtime `dependencies`, NOT in the APK.
> Environment inspected: `<repo>\.venv` (CPython 3.14.7, `uv` venv, INSTALLER=`uv`).

## Files

Package dir: `.venv\Lib\site-packages\tzdata` — **627 files total** (`find`, `__pycache__` excluded — there is none shipped).

| Path | Content |
|---|---|
| `tzdata/__init__.py` | 2 statements (read in full, see below) |
| `tzdata/zones` | Plain-text manifest: one zone key per line (canonical zones, aliases and legacy links, e.g. `Africa/Lagos`, `US/Eastern`, `Asia/Calcutta`, `WET`, `HST`) |
| `tzdata/zoneinfo/__init__.py` | Empty (namespace marker only) |
| `tzdata/zoneinfo/` | **625 files**: 618 compiled zone binaries + 7 non-zone files |

The 7 non-zone files under `zoneinfo/`:

| File | Type / head observed |
|---|---|
| `tzdata.zi` | ASCII text, `# version 2026d` — the concatenated zic source input (rules + zones) this wheel was compiled from |
| `leapseconds` | ASCII text, public-domain NIST/IERS-derived leap-second table |
| `zone.tab` | Deprecated per-country zone table (points readers at `zone1970.tab`) |
| `zone1970.tab` | Per-country zone table, post-1970 agreement view |
| `zonenow.tab` | Zone table for users who only care about current/future agreement |
| `iso3166.tab` | ISO 3166 alpha-2 country codes |
| `__init__.py` | Empty |

Zone binaries: **no `.tzdata` extension** (that suffix belongs to pytz-era naming) — they are extensionless **TZif v2 "slim"** files, e.g. `zoneinfo/Africa/Lagos` → `file` reports `timezone data (slim), version 2, … 4 transition times`. Sampled key dirs: `Africa/` (incl. `Lagos`), `America/` (incl. `Argentina/` subdir, `New_York`, `Atikokan`), `Asia/` (`Kolkata`, `Kathmandu`, `Pyongyang`), `Europe/` (`Kyiv`, `Busingen`), `Pacific/` (`Chatham`, `Kiritimati`), plus top-level aliases (`CET`, `EST5EDT`, `GB-Eire`, `Navajo`, `W-SU`, `Zulu`, …). Duplicate zones (e.g. `Africa/Abidjan` == `Africa/Accra`, same SHA-256 in RECORD) are stored as separate identical files, not symlinks (wheel-safe on Windows).

`__init__.py` in full:

```python
# IANA versions like 2020a are not valid PEP 440 identifiers; the recommended
# way to translate the version is to use YYYY.n where `n` is a 0-based index.
__version__ = "2026.4"

# This exposes the original IANA version number.
IANA_VERSION = "2026d"
```

Note: the comment claims a *0-based* index, but the observed mapping is effectively **1-based** (`2026.4` ↔ `2026d`, the 4th 2026 release; same convention as `2024.1` ↔ `2024a`). Trust `IANA_VERSION`, not the comment.

Dist-info: `.venv\Lib\site-packages\tzdata-2026.4.dist-info\` — `METADATA`, `WHEEL`, `INSTALLER` (contains `uv`), `REQUESTED` (**0 bytes** — confirms tzdata was never requested directly; purely transitive), `top_level.txt` (`tzdata`), `RECORD` (**635 lines**; 625 under `tzdata/zoneinfo`), `licenses/LICENSE` + `licenses/licenses/LICENSE_APACHE`.

## Metadata

From `METADATA` (Metadata-Version 2.4):

| Field | Value |
|---|---|
| Name / Version | `tzdata` / `2026.4` |
| Summary | Provider of IANA time zone data |
| Requires-Python | `>=2` (data-only wheel, py2.py3-none-any) |
| Requires-Dist | **none — zero runtime pins** (this is data) |
| License (packaging) | `Apache-2.0` |
| Classifiers | Production/Stable, Developers, Python 2 + 3 |

**License clarification** (the brief asked about "JSI/Affero" — neither applies): the *wrapper/packaging* is **Apache-2.0** (Paul Ganssle / Stan Ulbrych, see `licenses/LICENSE` + `LICENSE_APACHE`); the *IANA tz database content itself* (`tzdata.zi`, compiled zones, `.tab` files) is **public domain** (each source file carries a public-domain notice, e.g. `tzdata.zi`: "This zic input file is in the public domain"). License-safe for a shipped app; keep the wheel's license files if redistributing.

**Dependency chain (verified, not assumed):**

- `arrow 1.4.0` METADATA: `Requires-Dist: tzdata;python_version>='3.9'` (**unconditional on py≥3.9 — not Windows-only**), plus `python-dateutil>=2.7.0` and `backports.zoneinfo==0.2.1;python_version<'3.9'`.
- `python-dateutil 2.9.0.post0` METADATA: only requires `six>=1.5`. **dateutil does NOT depend on tzdata** — correction to the brief: on Windows dateutil falls back to its *own bundled* `dateutil/zoneinfo/dateutil-zoneinfo.tar.gz` snapshot (present in this venv), not to the `tzdata` package.
- Chain into this repo: `pyproject [dependency-groups] dev: flet-cli` → `flet-cli 1.0.0` (`Requires-Dist: cookiecutter>=2.6.0`) → `cookiecutter 2.7.1` → `arrow` → `tzdata`. Confirmed in `uv.lock` (`tzdata 2026.4` wheel `sha256:c2169a8b…`, sdist `sha256:f1b8bd36…`).
- Runtime `project.dependencies` = `av, flet*, httpx` only. **tzdata/arrow/cookiecutter/dateutil reach the dev venv via `flet-cli`; none of them is packaged into the APK** (flet-cli consumes `project.dependencies` for the mobile bundle, not the dev group).

## Programming interface (zoneinfo interplay)

**tzdata exports no functions, no classes, no resources API.** Verified empirically: `dir(tzdata)` → only `IANA_VERSION` (plus dunder/`__version__`); `hasattr(tzdata, 'open_tzfile')` → `False` (there is no such API — `importlib.resources` on the `tzdata.zoneinfo` tree is the closest equivalent, but that is not a supported interface). Its entire "API" is: **being installed and importable so stdlib `zoneinfo` (PEP 615) can find IANA data where the OS provides none.**

Wiring, verified live on this machine (CPython 3.14.7, `zoneinfo.TZPATH == ()`, no `TZPATH` env var):

1. `zoneinfo.ZoneInfo(key)` lookup order: `TZPATH` dirs → system paths (`/usr/share/zoneinfo`, …) → **`tzdata` package fallback** (CPython's `_zoneinfo` consults `importlib`-visible `tzdata/zoneinfo` itself). `ZoneInfo("Africa/Lagos")` succeeded **even before any explicit `import tzdata`** — mere installation suffices on CPython; `import tzdata` is belt-and-braces (and the documented idiom) to guarantee the fallback exists, e.g. first import in `main.py` if adopted.
2. `TZPATH` env var + `zoneinfo.reset_tzpath()` had **no effect** here (still `()`): on Windows there is no system database to point at, so the package fallback does all the work. On Android (Bionic ships zoneinfo files, but not at CPython's search paths and not reliably visible to the bundled interpreter) the same applies: **the `tzdata` package is the database**.
3. `ZoneInfo("Africa/Lagos").utcoffset(datetime(2026,1,1))` → `1:00:00`; `America/New_York` July → UTC-4. `len(zoneinfo.available_timezones())` → **598** keys (fewer than the 618 on-disk binaries; the manifest `zones` file lists the full canonical+alias set).

The stdlib surface you program against (signatures observed on 3.14):

```python
ZoneInfo(key)                          # constructor; raises ZoneInfoNotFoundError if key missing everywhere
ZoneInfo.no_cache(key)                 # (*, key) -> uncached instance; bypasses the strong cache
ZoneInfo.clear_cache(*, only_keys=None)# drop cached instances (tests, tzdata upgrades)
ZoneInfo.from_file(file_obj, key=None) # build from an open TZif binary stream
zoneinfo.available_timezones()         # -> set[str], 598 keys with tzdata 2026.4
zoneinfo.reset_tzpath(to=None)         # re-read TZPATH env var; no-op value-add on Win/Android
zoneinfo.TZPATH                        # () on this machine — package fallback active
```

Minimal correct usage pattern for this app's targets:

```python
import tzdata  # noqa: F401  — guarantees the PEP 615 fallback on Windows/Android
from zoneinfo import ZoneInfo

lagos = ZoneInfo("Africa/Lagos")
aware = datetime.fromtimestamp(epoch_float, tz=ZoneInfo("Africa/Lagos"))
```

Version linkage: `tzdata.__version__ == "2026.4"` (PEP 440) ↔ `tzdata.IANA_VERSION == "2026d"` ↔ `tzdata.zi: # version 2026d`. IANA cadence is irregular (several releases/year); pin or bump deliberately — a stale tzdata means stale DST rules (e.g. a government changing DST dates ships in the next IANA letter release).

## App usage & correctness

Grep over `src/`, `tests/`, `tools/` for `tzdata|zoneinfo|ZoneInfo|open_tzfile|reset_tzpath|TZPATH|arrow|dateutil`: **zero hits** — the app never touches time zones today.

What the app does with time (all epoch floats — correct):

- `src/core/state.py:100-101` — `Job.created_at: float = time.time()`, `finished_at: float | None`. Persisted in `src/main.py:304,322` (`history_jobs` storage, capped at 50) and stamped at `src/main.py:541,549,555`. Epoch storage is DST-immune. Good.
- `history_screen.py` (182 lines): renders counts/search/filter only — **no timestamp is ever displayed** (grep for `strftime|fromtimestamp|created` empty). No relative-time ("2h ago") UI exists.
- Filenames (`capture_screen.py:373,395,533`, `join_screen.py:154`, `probe_screen.py:254,267`, `streams_screen.py:101`) and `ad_service.py:161` use `int(time.time())` — monotonic-ish unique-ish suffixes, no tz involvement.
- **Only local-time touchpoint:** `src/core/logger_handler.py:22` — `datetime.fromtimestamp(record.created).strftime("%H:%M:%S")` for the Settings Activity Terminal. This is *naive* local time via the OS C runtime — works without any IANA database, but is DST-fold-ambiguous and untestable across zones. Cosmetic only; not a crash bug.

Failure mode if someone adds `ZoneInfo(...)`/arrow display code without promoting tzdata: on the dev PC it would *appear* to work (venv has tzdata transitively), then raise `ZoneInfoNotFoundError` in the **release APK** (dev deps excluded from the flet bundle) and on any machine without the transitive chain. The same trap applies to `dateutil.tz.gettz("Africa/Lagos")` (returns `None` → silent naive fallback) and to arrow's `arrow.get(ts).to("Africa/Lagos")`.

## Considerations for v1

1. **Ship v1 as-is with epoch floats; do not add tzdata yet.** Current code is tz-correct by avoidance. Adding a 350 KB data wheel (wheel `347494` bytes per `uv.lock`) with zero consumers is pure APK bloat.
2. **Promote to runtime `dependencies` the moment any of these lands:** arrow-based relative timestamps ("3h ago" in History), user-visible local times from epoch floats, or schedules/recurrence (`dateutil.rrule`). Preferred form: add `tzdata` **directly** (data-only, no transitive weight, Apache-2.0 + public-domain) and code against stdlib `zoneinfo` — do not pull all of `arrow` just for humanize. If you do adopt arrow, its `tzdata;python_version>='3.9'` pin covers the database automatically on 3.14.
3. **If promoted, add `import tzdata  # noqa: F401` at app startup** (e.g. `src/main.py`) — harmless on desktop Linux (system db wins), load-bearing on Windows dev and Android where it is the *only* database.
4. **Keep an update cadence.** IANA ships DST-rule changes as new letter releases; `uv.lock` currently pins wheel `sha256:c2169a8b…`. Revisit quarterly or when targeting regions with volatile DST policy (Africa/Lagos itself is stable UTC+1, but users travel).
5. **Test matrix:** `ZoneInfo("Africa/Lagos")` + a DST zone (`America/New_York`, July vs January offsets) on (a) Windows dev venv *without* tzdata installed (expect `ZoneInfoNotFoundError` — proves the fallback matters), (b) with it, (c) release APK on arm64/x86_64.

## Gotchas

- **Dev-works/release-crashes trap** (above): the transitive dev chain masks the missing runtime dep. Any tz PR must be validated against a packaged build, not the dev venv.
- **`__version__` ≠ IANA version**: `"2026.4"` vs `"2026d"`; the "0-based index" comment in `__init__.py` is misleading (observed mapping is 1-based). Use `IANA_VERSION` when reporting data freshness to users/support.
- **dateutil is self-sufficient and stale**: its bundled `dateutil-zoneinfo.tar.gz` is an old snapshot — `tz.gettz()` may disagree with `ZoneInfo` on recent rule changes. Prefer stdlib `zoneinfo` + `tzdata`.
- **`available_timezones()` (598) ≠ files on disk (618) ≠ `zones` manifest lines**: aliases, deprecated links (`Asia/Calcutta`, `America/Atka`, `W-SU`) and cross-links inflate the file count. Always validate user-facing zone lists against `available_timezones()`, not directory listings.
- **Naive `fromtimestamp` in `logger_handler.py:22`**: fine for a debug terminal, but never use that pattern for job timestamps — always `datetime.fromtimestamp(ts, tz=timezone.utc)` then `.astimezone(target)` once a target zone exists.
- **No `TZPATH`/`reset_tzpath` needed** on our targets: verified no-op here; don't add env-var machinery — the package fallback is the mechanism.
- **Wheel is `py2.py3-none-any`, `Requires-Python: >=2`, zero deps**: it installs anywhere and never conflicts; promotion risk is essentially nil beyond ~350 KB.
