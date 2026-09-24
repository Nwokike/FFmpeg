# packaging 26.3 — Complete API Reference

> Core packaging primitives (PEP 440 / 508 / 425 / 503 / 639 …). Pure-Python, **zero runtime dependencies**.
> Installed at `<repo>\.venv\Lib\site-packages\packaging`
> (venv Python 3.14, app `requires-python = ">=3.14"`). Calendar versioning (`YY.N`).

## Files

Public modules (all fully read for this report):

| File | Contents |
|---|---|
| `__init__.py` | Package version constants only (`__version__ = "26.3"`); no API |
| `version.py` | PEP 440 `Version`, `parse`, `InvalidVersion`, `normalize_pre` (26.1), `VERSION_PATTERN` |
| `specifiers.py` | PEP 440 `Specifier`, `SpecifierSet`, `InvalidSpecifier`, `BaseSpecifier` |
| `requirements.py` | PEP 508 `Requirement`, `InvalidRequirement` |
| `markers.py` | PEP 508 markers: `Marker`, `default_environment`, `InvalidMarker`, `UndefinedComparison`, `UndefinedEnvironmentName`, `Environment`, `EvaluateContext` |
| `tags.py` | PEP 425 wheel tags: `Tag`, `sys_tags`, `parse_tag`, `cpython_tags`, `generic_tags`, `compatible_tags`, `pure_python_tags` (26.3), `platform_tags`, `mac_platforms`, `ios_platforms`, `android_platforms`, `create_compatible_tags_selector` (26.1) |
| `utils.py` | `canonicalize_name`, `is_normalized_name`, `canonicalize_version`, `parse_wheel_filename`, `parse_sdist_filename`, `NormalizedName`, `BuildTag`, `InvalidName/Wheel/SdistFilename` |
| `licenses/__init__.py` | PEP 639/SPDX: `canonicalize_license_expression`, `InvalidLicenseExpression`, `NormalizedLicenseExpression` |
| `metadata.py` | Core metadata: `Metadata.from_raw/from_email/as_rfc822`, `parse_email`, `RawMetadata`, `InvalidMetadata`, `RFC822Message/Policy` |
| `ranges.py` | **New in 26.3**: set-algebra `VersionRange` over specifier sets |
| `pylock.py` | PEP 751 lock-file parsing (`PylockValidationError`, …) |
| `direct_url.py` | PEP 610 direct-URL (`DirectUrl`, `ArchiveInfo`, `DirInfo`, `VcsInfo`, `DirectUrlValidationError`) |
| `dependency_groups.py` | PEP 735 (`resolve_dependency_groups`, `DependencyGroupResolver`, `CyclicDependencyGroup`, …) |
| `errors.py` | `ExceptionGroup` shim (builtin on 3.11+, minimal backport below) |
| `py.typed` | Empty marker — the package ships inline types |

Private helpers (not public API): `_parser.py` + `_tokenizer.py` (PEP 508 grammar),
`_ranges.py` (interval engine behind specifiers + `ranges.py`), `_structures.py`
(pickle-compat shim for pre-26.1 `Version` pickles), `_elffile.py` / `_manylinux.py` /
`_musllinux.py` (ELF parsing for manylinux/musllinux platform tags).

## Metadata

From `packaging-26.3.dist-info/METADATA`:

- **Name / Version:** `packaging 26.3`
- **Requires-Python:** `>=3.9` (classifiers list 3.9–3.15, CPython + PyPy, free-threading resilient)
- **License:** `License-Expression: Apache-2.0 OR BSD-2-Clause` — **dual license**.
  Dist-info ships three files under `licenses/`: `LICENSE`, `LICENSE.APACHE`, `LICENSE.BSD`.
  (`__init__.py` also states `__license__ = "BSD-2-Clause or Apache-2.0"`.)
- **Runtime pins: none.** There is no `Requires-Dist` — zero dependencies, so it can
  never introduce a version conflict. Safe to add as a direct dependency.
- **Wheel:** pure-Python `py3-none-any`, built with `flit 3.12.0` (`WHEEL` file).
  `INSTALLER`/`REQUESTED` present; `RECORD` lists 26 files with sha256 hashes.
- Summary: *"Core utilities for Python packages"* — version handling, specifiers,
  markers, requirements, tags, metadata, lockfiles, utilities.

## Module-by-module API

### `packaging.version` — PEP 440 versions

```python
parse(version: str) -> Version                      # == Version(version); raises InvalidVersion
normalize_pre(letter: str, /) -> str                # 26.1: 'alpha'->'a', 'beta'->'b', 'c'/'pre'/'preview'->'rc', 'rev'/'r'->'post'
class InvalidVersion(ValueError): ...

class Version(_BaseVersion):
    def __init__(self, version: str) -> None         # raises InvalidVersion
    @classmethod
    def from_parts(cls, *, epoch: int = 0, release: tuple[int, ...],  # 26.1; release REQUIRED
                   pre: tuple[str, int] | None = None, post: int | None = None,
                   dev: int | None = None, local: str | None = None) -> Self
    def __replace__(self, **kwargs) -> Self          # 26.0; keys: epoch/release/pre/post/dev/local;
                                                    # None clears; pre is normalized (26.1); no-change returns self
    # properties
    epoch -> int                                     # Version("1!2.0").epoch == 1
    release -> tuple[int, ...]                       # Version("1.2.3").release == (1, 2, 3)
    pre -> tuple[Literal["a","b","rc"], int] | None  # Version("1.2.3a1").pre == ('a', 1)
    post -> int | None                               # Version("1.2.3.post1").post == 1
    dev -> int | None                                # Version("1.2.3.dev1").dev == 1
    local -> str | None                              # Version("1.2.3+abc").local == 'abc'
    public -> str                                    # str without +local
    base_version -> str                              # epoch + release only ("1!1.2.3dev1+abc" -> "1!1.2.3")
    is_prerelease -> bool                            # pre or dev set
    is_postrelease -> bool
    is_devrelease -> bool
    major / minor / micro -> int                     # release[0/1/2] or 0 if absent
```

- Full ordering (`< <= == != >= >`, hashable, `str()` round-trips canonical form).
  Canonical forms: `1.0a5`, `1.0rc1`, `1.0.post1`, `1.0.dev1`, `1!2.0`, `1.0+local`.
  `1.0.0 == 1` (trailing zeros stripped for comparison).
- Order: `dev-only < a < b < rc < final < post`; `local` sorts after public;
  in local segments strings sort before ints; epoch dominates everything.
- Accepts leading `v` and surrounding whitespace (`Version("v1.0 ")` works).
- `__match_args__ = ("_str",)` — structural pattern matching on the string form (26.0).
- Stable pickle format (26.2+); pre-26.1 pickles still load (`_structures.py` shim).
- `VERSION_PATTERN`: unanchored regex for embedding; compile with
  `re.VERBOSE | re.IGNORECASE`. Raises `InvalidVersion(ValueError)` on garbage.

Example:

```python
from packaging.version import Version, parse, InvalidVersion

Version("1.10.0") > Version("1.9.0")  # True  (numeric, NOT lexicographic)
Version("1.0a5") < Version("1.0")  # True
Version("1.0.0") == Version("1")  # True
try:
    Version("not-a-version")
except InvalidVersion as e:
    ...
```

### `packaging.specifiers` — PEP 440 specifiers

```python
class InvalidSpecifier(ValueError): ...

class Specifier(BaseSpecifier):
    def __init__(self, spec: str = "", prereleases: bool | None = None) -> None
    @property operator -> str                    # e.g. ">="
    @property version -> str                     # e.g. "1.2.3"
    @property prereleases -> bool | None         # explicit override, else autodetect
    def contains(self, item: Version | str, prereleases: bool | None = None) -> bool
    def filter(self, iterable, prereleases: bool | None = None, key: Callable | None = None) -> Iterator
    # __contains__ ("1.2.3" in Specifier(">=1.2.3")), __str__/__repr__/__hash__/__eq__
    # == ignores prereleases flag; "==1.2.3" == "== 1.2.3.0" is True

class SpecifierSet(BaseSpecifier):
    def __init__(self, specifiers: str | Iterable[Specifier] = "", prereleases: bool | None = None) -> None
    def __and__(self, other: SpecifierSet | str) -> SpecifierSet   # intersection; ValueError if True-vs-False prerelease overrides clash
    def __len__ / __iter__ / __contains__ / __str__ / __hash__ / __eq__
    def contains(self, item, prereleases: bool | None = None, installed: bool | None = None) -> bool
    def filter(self, iterable, prereleases: bool | None = None, key: Callable | None = None) -> Iterator
    def is_unsatisfiable(self) -> bool           # 26.1: ">=2.0,<1.0" -> True
    def to_range(self) -> VersionRange            # 26.3
    def is_subset / is_superset / is_disjoint(self, other: SpecifierSet) -> bool  # 26.3; TypeError unless SpecifierSet; ValueError on ===
```

Operators: `==` (wildcards `==1.0.*`, locals allowed), `!=`, `~=`
(compatible release, needs ≥2 segments: `~=1.4.5` ≡ `>=1.4.5,==1.4.*`),
`>= <= > <`, `===` (arbitrary **case-insensitive string match**, no parsing).
Raises `InvalidSpecifier(ValueError)` on bad syntax.

`>=1.0.0` semantics: numeric PEP 440 comparison; `Specifier(">=1.0.0").contains("1.3.0a1")`
is **True** under the default policy (see Gotchas). `filter()` follows PEP 440:
prereleases are yielded **only if no final release** in the input satisfies the set,
unless `prereleases=True`. `key=` (26.1) extracts a version from each item.

Example:

```python
from packaging.specifiers import SpecifierSet

s = SpecifierSet(">=1.0.0,<2.0.0")
"1.5" in s  # True
list(s.filter(["1.2", "1.3", "1.5a1"]))  # ['1.3']
list(s.filter(["1.2", "1.5a1"]))  # ['1.5a1']  (only candidate)
combined = SpecifierSet(">=1.0") & "<2.0,!=1.5"  # <SpecifierSet('!=1.5,<2.0,>=1.0')>
SpecifierSet(">=2.0,<1.0").is_unsatisfiable()  # True
```

### `packaging.requirements` — PEP 508 requirements

```python
class InvalidRequirement(ValueError): ...
class Requirement:
    def __init__(self, requirement_string: str) -> None   # raises InvalidRequirement
    name: str                     # as spelled, e.g. "Foo"
    url: str | None               # PEP 508 direct reference ("pkg @ https://…")
    extras: set[str]              # e.g. {"socks"} for "requests[socks]"
    specifier: SpecifierSet
    marker: Marker | None
    # __str__ round-trips; __eq__/__hash__ canonicalize name+extras+specifier (23.2/26.3);
    # stable pickle (26.2), now preserving the specifier prereleases override (26.3)
```

Example:

```python
from packaging.requirements import Requirement

r = Requirement('requests[socks]>=2.8.1; python_version > "3.8"')
r.name, r.extras, str(r.specifier), str(r.marker)
# ('requests', {'socks'}, '>=2.8.1', 'python_version > "3.8"')
Requirement("Foo") == Requirement("foo")  # True (name canonicalized)
```

### `packaging.markers` — PEP 508 environment markers

```python
EvaluateContext = Literal["metadata", "lock_file", "requirement"]
class InvalidMarker(ValueError): ...
class UndefinedComparison(ValueError): ...
class UndefinedEnvironmentName(KeyError): ...   # 26.3: was ValueError, now KeyError subclass
class Environment(TypedDict):  implementation_name, implementation_version, os_name,
    platform_machine, platform_release, platform_system, platform_version,
    python_full_version, platform_python_implementation, python_version, sys_platform

def default_environment() -> Environment   # fresh copy each call; computed once per process & cached (26.3:
                                           # patching platform/sys/os afterwards has NO effect)

class Marker:
    def __init__(self, marker: str) -> None        # raises InvalidMarker
    def evaluate(self, environment: Mapping[str, str | AbstractSet[str]] | None = None,
                 context: EvaluateContext = "metadata") -> bool
        # raises UndefinedComparison (bad version compare), UndefinedEnvironmentName (missing key)
    def __and__ / __or__(self, other: Marker) -> Marker   # 26.1 combinators
    # __str__/__repr__/__hash__/__eq__, stable pickle
```

Version-valued keys (`python_version`, `python_full_version`, `platform_release`,
`implementation_version`) compare via `Specifier` semantics; `extra` names are
PEP 685-normalized; `"name" in extras` / `dependency_groups` set-membership supported.
`context="metadata"` injects `extra=""`; `"lock_file"` injects empty `extras` +
`dependency_groups` frozensets.

Example:

```python
from packaging.markers import Marker, default_environment

Marker('python_version > "3.8"').evaluate()  # True on 3.14
Marker('sys_platform == "win32"').evaluate()  # True on Windows
Marker('os_name == "posix" and python_version >= "3.12"').evaluate(
    {"os_name": "posix", "python_version": "3.14"}
)  # True (merged over defaults)
```

### `packaging.tags` — PEP 425 wheel tags (wheel choice)

```python
class Tag:
    def __init__(self, interpreter: str, abi: str, platform: str) -> None  # lowercased, hashable
    interpreter / abi / platform -> str
    # __str__ "cp314-cp314-win_amd64"; __eq__/__hash__; stable pickle
class InvalidTag(ValueError): ...        # 26.3: bad interpreter / empty component / != 3 parts
class UnsortedTagsError(ValueError): ... # 26.1
class TooManyTagsError(ValueError): ...  # 26.3: compressed set exceeds limit

def parse_tag(tag: str, *, validate_order: bool = False, limit: int | None = None) -> frozenset[Tag]
def sys_tags(*, warn: bool = False) -> Iterator[Tag]        # best match FIRST; interpreter > platform > ABI
def cpython_tags(python_version=None, abis=None, platforms=None, *, warn=False) -> Iterator[Tag]
def generic_tags(interpreter=None, abis=None, platforms=None, *, warn=False) -> Iterator[Tag]
def compatible_tags(python_version=None, interpreter=None, platforms=None) -> Iterator[Tag]
def pure_python_tags(python_version=None) -> Iterator[Tag]  # 26.3; py3*-none-any chain
def platform_tags() -> Iterator[str]                        # dispatches: mac / iOS / Android / Linux / Emscripten / generic
def mac_platforms(version: AppleVersion | None = None, arch: str | None = None) -> Iterator[str]
def ios_platforms(version=None, multiarch=None) -> Iterator[str]              # 24.2
def android_platforms(api_level: int | None = None, abi: str | None = None) -> Iterator[str]  # 25.0; min API 16
def interpreter_name() -> str        # "cp"/"pp"/… via INTERPRETER_SHORT_NAMES
def interpreter_version(*, warn=False) -> str
def create_compatible_tags_selector(tags: Iterable[Tag]) -> Callable[[Iterable[tuple[T, AbstractSet[Tag]]]], Iterator[T]]  # 26.1
PythonVersion = Sequence[int]; AppleVersion = tuple[int, int]
```

26.3 change: native `linux_*` platform tags now order **before** manylinux/musllinux.
Critical for wheel choice: intersect a wheel's `parse_wheel_filename(...)[3]` tag set
with `set(sys_tags())`; first `sys_tags()` hit wins (or use the selector helper).

Example:

```python
from packaging import tags
from packaging.utils import parse_wheel_filename

supported = set(tags.sys_tags())
_, _, _, wheel_tags = parse_wheel_filename("av-18.1.0-cp314-cp314-win_amd64.whl")
bool(wheel_tags & supported)  # is this wheel installable here?
```

### `packaging.utils` — names, versions, filenames

```python
NormalizedName = NewType("NormalizedName", str)
BuildTag = Union[tuple[()], tuple[int, str]]
class InvalidName(ValueError): ...
class InvalidWheelFilename(ValueError): ...
class InvalidSdistFilename(ValueError): ...

def canonicalize_name(name: str, *, validate: bool = False) -> NormalizedName
    # PEP 503: Django -> 'django', oslo.concurrency -> 'oslo-concurrency'; validate=True raises InvalidName
def is_normalized_name(name: str) -> bool        # 23.2
def canonicalize_version(version: Version | str, *, strip_trailing_zero: bool = True) -> str
    # '1.0.0' -> '1'; strip_trailing_zero=False keeps '1.0.0'; garbage returned UNCHANGED
def parse_wheel_filename(filename: str, *, validate_order: bool = False
    ) -> tuple[NormalizedName, Version, BuildTag, frozenset[Tag]]
    # raises InvalidWheelFilename (bad ext/part-count/name/version/build/tag; 26.3 also on
    # non-identifier interpreter, empty tag component, empty project name)
def parse_sdist_filename(filename: str) -> tuple[NormalizedName, Version]
    # .tar.gz/.zip only, splits on LAST dash; raises InvalidSdistFilename (26.3: empty name)
```

### `packaging.licenses` — PEP 639 license expressions

```python
NormalizedLicenseExpression = NewType("NormalizedLicenseExpression", str)
class InvalidLicenseExpression(ValueError): ...
def canonicalize_license_expression(raw_license_expression: str) -> NormalizedLicenseExpression
# "mit and (apache-2.0 or bsd-2-clause)" -> 'MIT AND (Apache-2.0 OR BSD-2-Clause)'
# Unknown ids, bad syntax, bad LicenseRef- raise InvalidLicenseExpression. Case-insensitive,
# AND/OR/WITH (+ WITH exception: "MIT WITH Classpath-exception-2.0"), trailing "+" kept.
```

### `packaging.metadata` — core metadata (METADATA/PKG-INFO)

```python
class InvalidMetadata(ValueError):
    field: str
    def __init__(self, field: str, message: str) -> None
def parse_email(data: bytes | str) -> tuple[RawMetadata, dict[str, list[str]]]  # (recognized, unparsed)
class Metadata:
    @classmethod def from_raw(cls, data: RawMetadata, *, validate: bool = True) -> Metadata
    @classmethod def from_email(cls, data: bytes | str, *, validate: bool = True) -> Metadata
    def as_rfc822(self) -> RFC822Message      # 26.0
    # attributes (enriched, validated): metadata_version (required, must be known),
    # name (required, validated), version -> Version (required), summary (single-line),
    # description_content_type, dynamic (lowercased), provides_extra (normalized),
    # requires_dist -> list[Requirement], requires_python -> SpecifierSet,
    # license_expression -> NormalizedLicenseExpression, license_files (relative, '/'-joined),
    # import_names/import_namespaces (2.5), project_urls, classifiers, … (optional -> None)
class RFC822Policy(email.policy.EmailPolicy): ...    # 26.0
class RFC822Message(email.message.EmailMessage):
    def __init__(self) -> None
    def as_bytes(self, unixfrom=False, policy=None) -> bytes
```

Note how metadata reuses this package: `version` → `Version`,
`requires_python` → `SpecifierSet`, `requires_dist` → `Requirement`s.

### `packaging.ranges` — set algebra (NEW in 26.3)

```python
class VersionRange:   # construct via SpecifierSet.to_range(), full(), empty(), singleton() — NOT directly
    @classmethod def full(cls, *, admit_arbitrary=True, prereleases=None) -> VersionRange
    @classmethod def empty(cls, *, prereleases=None) -> VersionRange
    @classmethod def singleton(cls, version: Version | str, *, prereleases=None) -> VersionRange
    def intersection / union / complement / difference  (+ & | ~ - operators)
    def is_subset / is_superset / is_disjoint(self, other: VersionRange) -> bool
    def contains(self, item, prereleases=None, ...) -> bool   # "1.5" in r
    def filter(self, iterable, prereleases=None, key=None) -> Iterator
    def to_specifier_set(self) -> SpecifierSet | None         # None when no PEP 440 form exists
    @property is_empty -> bool
    # operands must share the same configured prereleases policy (else ValueError)
```

```python
from packaging.specifiers import SpecifierSet

r = SpecifierSet(">=1.0,<2.0").to_range()
"1.5" in r  # True
r.is_subset(SpecifierSet(">=1.0").to_range())  # True
```

### `pylock.py` / `direct_url.py` / `dependency_groups.py` (summary)

- `pylock`: PEP 751 `pylock.toml` parsing — `is_valid_pylock_path`, `PackageVcs`,
  `PylockValidationError`, `PylockUnsupportedVersionError`, `PylockSelectError`.
- `direct_url`: PEP 610 — `DirectUrl.from_dict/to_dict/validate`,
  `VcsInfo`/`ArchiveInfo`/`DirInfo`, `DirectUrlValidationError`.
- `dependency_groups`: PEP 735 — `resolve_dependency_groups(...)`,
  `DependencyGroupResolver.lookup/resolve`, `DependencyGroupInclude`,
  `CyclicDependencyGroup`, `DuplicateGroupNames`, `InvalidDependencyGroupObject`.

## App usage & correctness

**Dependency chain (transitive only).** Zero direct references: `grep -rln "packaging"`
over `src/ tests/ tools/ .github/ pyproject.toml version.json` returns **nothing**,
and no test or tool file imports it. `uv.lock` shows exactly two reverse-dependencies
on `packaging 26.3`:

1. `flet-cli` (dev group: `flet-cli>=1.0.0`) — needs it for build/packaging flows;
2. `pytest>=9.1.1` (dev group) — needs it for requirement/marker handling.

So `packaging` rides along with the **dev toolchain**, not the shipped app
(`[project] dependencies` = av, flet*, httpx — none require it). It is installed
in the venv but never imported at runtime.

**How the app compares versions today: correct — but narrow.**

- `src/services/update_service.py:19-34` (`UpdateService.check_for_updates`):
  fetches the remote `version.json`, reads `build_number` as `int`, and compares
  `remote_build > BUILD_NUMBER` (`:27`). **Integer comparison — no lexicographic
  bug.** The classic `"1.10.0" > "1.9.0" == False` string trap does not occur here.
- **Gap, not bug:** the manifest's `"version": "1.0.0"` string is fetched but
  **never compared** — only `build_number` gates the update. A release that bumps
  `version` without bumping `build_number` would be silently missed. There is no
  hand-rolled version *parsing* anywhere (no `split(".")`, no tuple compares), so
  nothing to replace — but also no PEP 440 validation of the remote payload.
- `tests/test_version_sync.py:28-51`: the v1.0 sync gate asserts **exact string
  equality** `pyproject version == version.json version == APP_VERSION` and
  `build_number` equality, plus a changelog entry. Correct as a drift guard, but
  string equality is stricter than PEP 440 identity: `"1.0"` vs `"1.0.0"` are the
  same release yet would fail the gate. No `packaging` use.
- `src/core/constants.py` (`_read_build_from_pyproject`): re-reads version/build
  from `pyproject.toml` at import with try/except fallback — plain `str`/`int`
  handling, no version semantics involved. Fine as-is.

**Misuse found: none.** No string version comparisons (`latest > current`
lexicographic), no hand-rolled comparators — the one ordering decision in the app
is integer-based and sound.

## Underused APIs to adopt

Ranked by v1.0 value (all are zero-dependency, stdlib-free additions):

1. **`Version` as a second update gate (recommended).** In
   `src/services/update_service.py:26-27`, after the `build_number` check, also
   compare `Version(data["version"]) > Version(APP_VERSION)` inside
   `try/except InvalidVersion`. Catches version-only releases the build gate
   misses, and `InvalidVersion` gives free validation of a corrupt manifest.
   Cost: ~5 lines + `packaging` moves to `[project] dependencies`.
2. **`canonicalize_version` in the sync gate.** In `tests/test_version_sync.py:31`,
   compare `canonicalize_version(...)` on both sides so `1.0 == 1.0.0` stops being
   a false drift failure as versions gain trailing segments.
3. **`SpecifierSet` for `requires-python` validation.** `pyproject.toml` declares
   `requires-python = ">=3.14"`; a CI check `SpecifierSet(">=3.14").contains(f"{sys.version_info…}")`
   fails fast on a wrong interpreter instead of surfacing as an `av`/flet wheel error.
4. **`Requirement` sanity checks in CI.** Parse each entry of `[project] dependencies`
   (`"av>=18.1.0"`, …) with `Requirement(...)` to catch typos (`InvalidRequirement`)
   before `uv lock` does.
5. **`Marker.evaluate` for platform-gated logic.** Any future Android-vs-desktop
   branching on dependency applicability should use markers, not `sys.platform` string tests.
6. **`tags` / `parse_wheel_filename` in build tooling.** `pyproject.toml` pins
   `target_arch = ["arm64-v8a", "x86_64"]` with `min_sdk_version = 24` because
   *"av's Android wheels are built at ABI 24"*. `tags.android_platforms(api_level=24, …)`
   and `parse_wheel_filename(...)` can assert that claim mechanically (e.g. verify a
   downloaded `av` wheel's `android_24_*` platform tag is in `sys_tags()`), and
   `create_compatible_tags_selector` picks the best wheel from a list.
7. **`VersionRange` (26.3) for supported-version windows.** If the update manifest
   ever grows `min_supported_version`, `SpecifierSet(">=…").to_range()` +
   `is_subset`/`is_disjoint` expresses "is this install still supported" exactly.

## Gotchas

1. **Single-version `contains` admits prereleases by default (since 26.0).**
   `Specifier(">=1.2.3").contains("1.3.0a1")` is `True`; only an explicit
   `prereleases=False` rejects it. `filter()` instead buffers prereleases and emits
   them only when **no final** satisfies the set. Pass `prereleases=` explicitly
   wherever update/user-facing logic is involved.
2. **Trailing zeros vanish in `==`.** `Specifier("==1.2.3") == Specifier("== 1.2.3.0")`;
   `Version("1.0.0") == Version("1")`. Never compare version *strings* for equality —
   the sync gate (item 2 above) is the one place this bites.
3. **`===` is a literal string match**, case-insensitive, no PEP 440 meaning.
   `SpecifierSet.is_subset/superset/disjoint` raise `ValueError` on `===` sets.
4. **Locals are stripped for `<=`/`==`/`!=`.** `Specifier("==1.0").contains("1.0+local")`
   is `True`. Epochs dominate: `1!0.1 > 99.99`.
5. **`~=` needs two segments** (`~=1.4` ok, `~=1` raises `InvalidSpecifier`).
   `==1.0.*` cannot combine with pre/post/dev/local.
6. **`default_environment()` is cached per process (26.3).** Monkeypatching
   `platform`/`sys`/`os` in tests after first call has no effect — pass an explicit
   `environment=` dict to `Marker.evaluate` instead.
7. **`UndefinedEnvironmentName` is now a `KeyError` (26.3)**, not `ValueError`.
   `except KeyError` handlers catch it; `except ValueError` no longer does.
8. **Unparsable input returns `False`, not an exception** (26.0+):
   `SpecifierSet(">=1.0").contains("garbage")` → `False`. Validate with `Version()`
   first when you need to distinguish "no" from "nonsense".
9. **`Version` accepts `v`-prefixes and whitespace** (`"v1.0 "` parses). Good for
   GitHub release tags; normalize with `str()`/`canonicalize_version` before display.
10. **Pickles are versioned** (stable format 26.2+; old ones still load). `Version`,
    `Specifier`, `SpecifierSet`, `Requirement`, `Marker`, `Tag` are all immutable,
    hashable, and pickle-safe — fine to cache in the job queue or update manifest.
11. **`SpecifierSet("")` matches everything** (including the prerelease-fallback
    rule). `is_unsatisfiable()` (26.1) is the cheap contradiction check for
    composed (`&`) constraints. Combining sets with conflicting explicit
    `prereleases=True` vs `False` raises `ValueError`.
12. **`parse_wheel_filename` splits name/version on fixed dash counts** (4–5 dashes);
    project names with runs of `__` or empty tag components raise `InvalidWheelFilename`
    as of 26.3 — older lenient parses may now fail loudly.
