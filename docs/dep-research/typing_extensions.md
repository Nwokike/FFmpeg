# typing_extensions 4.16.0 — Complete API Reference

Backport of newer typing features (plus PEP-experiment staging area). Single-module wheel, zero dependencies, PSF-2.0. On this app's interpreter (Python 3.14.7) the overwhelming majority of its surface is a pass-through to stdlib — app code must import from `typing`/`annotationlib`/`collections.abc`/`types` instead.

## Files

| Path | Size / notes |
|---|---|
| `.venv/Lib/site-packages/typing_extensions.py` | 4,422 lines, 165,012 bytes. The entire package: one module, no subpackage. Branched per `sys.version_info` — on 3.14 most names are plain re-exports (`X = typing.X`), older-version branches carry the backport implementations. |
| `.venv/Lib/site-packages/typing_extensions-4.16.0.dist-info/METADATA` | 3,310 bytes. Identity, pins, license, classifiers (below). |
| `.venv/Lib/site-packages/typing_extensions-4.16.0.dist-info/RECORD` | 7 rows: `INSTALLER`, `METADATA`, `RECORD`, `REQUESTED`, `WHEEL`, `licenses/LICENSE`, `typing_extensions.py` (hash-pinned). |
| `.venv/Lib/site-packages/typing_extensions-4.16.0.dist-info/WHEEL` | `flit 3.12.0`, `Root-Is-Purelib: true`, `Tag: py3-none-any` — pure-Python wheel. |
| `.venv/Lib/site-packages/typing_extensions-4.16.0.dist-info/INSTALLER` | `uv`. |
| `.venv/Lib/site-packages/typing_extensions-4.16.0.dist-info/REQUESTED` | Empty (not a direct dependency — pulled in transitively). |
| `.venv/Lib/site-packages/typing_extensions-4.16.0.dist-info/licenses/LICENSE` | 13,936 bytes. PSF license history text (CWI → CNRI → BeOpen → PSF). |

## Metadata

- **Name / version:** `typing_extensions 4.16.0`. Summary: "Backported and Experimental Type Hints for Python 3.9+".
- **Dependencies: none.** METADATA contains zero `Requires-Dist` entries — the package itself depends on nothing but stdlib.
- **License:** `License-Expression: PSF-2.0`, `License-File: LICENSE`.
- **`Requires-Python: >=3.9`.** Classifiers list 3.9–3.15 (incl. 3.14, 3.15).
- **Versioning policy (from METADATA body):** SemVer; depend as `typing_extensions ~=x.y` (i.e. `>=x.y, <(x+1)`), not `~=x.y.z`.
- **No `__version__` attribute** at runtime (verified: `hasattr(te, '__version__')` is `False`). Pin by installed distribution metadata, not module attribute.
- **Compat shims not in `__all__`:** `PEP_560 = True`, `GenericMeta = type`, private `_AnnotatedAlias` re-export (kept because downstream users rely on it).

## Exported symbols (complete list)

`len(typing_extensions.__all__) == 121` on this interpreter: 119 static entries + 2 conditional appends active on 3.14 (`CapsuleType`, `no_type_check_decorator`). Every one is enumerated below, grouped as in `__all__`.

**Super-special primitives (13):** `Any` (unconstrained; `isinstance` raises `TypeError`) · `ClassVar` · `Concatenate` (PEP 612 higher-order-function helper; last arg must be a `ParamSpec` or `...`) · `Final` · `LiteralString` (PEP 675, e.g. SQL-guard parameters) · `ParamSpec` (+ PEP 696 `default=`/`infer_variance`) · `ParamSpecArgs` / `ParamSpecKwargs` (`P.args` / `P.kwargs` introspection views) · `Self` (PEP 673, `"self"` return type) · `Type` · `TypeVar` (+ PEP 696 `default=`/`infer_variance`) · `TypeVarTuple` (PEP 646 variadics; `Generic[*Ts]`) · `Unpack` (PEP 646/692 unpack operator; also `**kwargs: Unpack[Movie]` TypedDict-kwargs form).

**ABCs from `collections.abc` (8):** `Awaitable` · `AsyncIterator` · `AsyncIterable` · `Coroutine` · `AsyncGenerator` · `AsyncContextManager` · `Buffer` (3.12+ buffer-protocol ABC; pre-3.12 static-only shim registering `bytes`/`bytearray`/`memoryview`) · `ChainMap`.

**Concrete collection types (7):** `ContextManager` · `Counter` · `Deque` · `DefaultDict` · `NamedTuple` (class + functional syntax; generic NamedTuples; kwargs syntax deprecated → removed in 3.15) · `OrderedDict` · `TypedDict` (class, functional, and inline `TypedDict[...]` forms; `total=`; per-key `Required`/`NotRequired`/`ReadOnly`; `closed=`/`extra_items=` PEP 728 knobs; `__required_keys__` / `__optional_keys__` / `__readonly_keys__` / `__mutable_keys__` / `__total__` / `__closed__` / `__extra_items__` introspection; **no instance/class checks — both raise `TypeError`**).

**Structural protocols (9):** `SupportsAbs` · `SupportsBytes` · `SupportsComplex` · `SupportsFloat` · `SupportsIndex` · `SupportsInt` · `SupportsRound` (all `@runtime_checkable`) · `Reader` / `Writer` (simple blocking-I/O protocols).

**One-off forms & helpers (46):** `Annotated` · `assert_never` (checker exhaustiveness; **raises `AssertionError` at runtime** if reached) · `assert_type` (checker assertion; runtime pass-through returning the value) · `clear_overloads` / `get_overloads` / `overload` (runtime overload registry) · `dataclass_transform` (PEP 681; records `__dataclass_transform__` so checkers synthesize `__init__` for DSL factories — the hook a flet-like control-builder DSL would use) · `deprecated` (PEP 702; emits `DeprecationWarning` at runtime unless `category=None`; sets `__deprecated__`) · `disjoint_base` (PEP 800) · `Doc` (PEP 727 `Annotated[..., Doc("...")]` documentation payloads) · `evaluate_forward_ref` (PEP 649/749 forward-ref evaluation with `owner`/`globals`/`locals`/`type_params`/`format`) · `final` (sets `__final__`; no runtime enforcement) · `Format` (annotationlib `VALUE`/`VALUE_WITH_FAKE_GLOBALS`/`FORWARDREF`/`STRING`) · `get_annotations` (PEP 649-aware annotation reader) · `get_args` / `get_origin` · `get_original_bases` (pre-`__mro_entries__` bases) · `get_protocol_members` (raises `TypeError` for non-protocols) · `get_type_hints` (strips `Annotated`/`Required`/`NotRequired`/`ReadOnly` unless `include_extras=True`) · `IntVar` (legacy helper returning `TypeVar(name)`) · `is_protocol` · `is_typeddict` · `Literal` · `NewType` (runtime identity function; subclassing gives a guided `TypeError`) · `override` (PEP 698; sets `__override__`; no runtime enforcement) · `Protocol` (structural subtyping; non-instantiable; non-runtime protocols raise `TypeError` on `isinstance`/`issubclass`; protocols with non-method members reject `issubclass` listing the members) · `sentinel` / `Sentinel` (unique-sentinel factory; pickle-by-name singleton) · `reveal_type` (checker directive; backport prints runtime type to stderr and returns the object) · `runtime` (back-compat alias of `runtime_checkable`) · `runtime_checkable` (opts a Protocol into `isinstance`/`issubclass`; presence-only checks, **not signature checks**) · `Text` (legacy `str` alias) · `TypeAlias` (PEP 613 marker) · `TypeAliasType` (PEP 695 `type X[T] = ...`; immutable — attribute writes raise `AttributeError`; only generic aliases subscriptable) · `TypeForm` (PEP 747, type-of-a-type-expression) · `TypeGuard` (PEP 647; narrows to exactly the guarded type on `True`) · `TypeIs` (PEP 742; narrows to the *intersection* on `True`, safer for `else` branches) · `TYPE_CHECKING` · `type_repr` (STRING-format helper) · `Never` (bottom type) · `NoReturn` · `ReadOnly` (PEP 705 per-key TypedDict immutability; no runtime enforcement) · `Required` / `NotRequired` (PEP 655 per-key requiredness; only meaningful inside `TypedDict`) · `NoDefault` (PEP 696 "no default" singleton for type-param defaults) · `NoExtraItems` (PEP 728 sentinel for TypedDict `extra_items=`).

**Pure aliases, always in `typing` (36):** `AbstractSet` · `AnyStr` · `BinaryIO` · `Callable` · `Collection` · `Container` · `Dict` · `ForwardRef` · `FrozenSet` · `Generic` · `Hashable` · `IO` · `ItemsView` · `Iterable` · `Iterator` · `KeysView` · `List` · `Mapping` · `MappingView` · `Match` · `MutableMapping` · `MutableSequence` · `MutableSet` · `Optional` · `Pattern` · `Reversible` · `Sequence` · `Set` · `Sized` · `TextIO` · `Tuple` · `Union` · `ValuesView` · `cast` · `no_type_check`.

**Conditional appends, both active on 3.14 (2):** `CapsuleType` (from `types`; C-capsule type) · `no_type_check_decorator` (appended only when `sys.version_info < (3, 15)`).

**Explicitly absent** (asked, not present): `Signature`, `frozen_func` — neither exists in this package. (`NoExtraItems` exists but lives in the one-off group, and `CapsuleType` is a conditional append.)

## stdlib-vs-backport on Python 3.14

Ground truth below was verified at runtime on the project venv (`3.14.7`). Rule for this app (`requires-python = ">=3.14"` in `pyproject.toml`): import everything from stdlib; `typing_extensions` is a transitive dependency only.

**Native on 3.14 — import from stdlib, never the backport (all verified `hasattr(typing, …) is True` unless noted):**
`Annotated`, `Any`, `ClassVar`, `Concatenate`, `Final`, `Literal`, `LiteralString`, `NamedTuple`, `Never`, `NewType`, `NoDefault`, `NotRequired`, `NoReturn`, `Required`, `ReadOnly`, `Self`, `Type`, `TypeAlias`, `TypeAliasType` (in `typing` since 3.12), `TypeGuard`, `TypeIs`, `TypeVar`/`ParamSpec` (with native PEP 696 `default=`/`infer_variance` — the backport just re-exports them), `TypeVarTuple`, `TypedDict`, `Unpack`, `Protocol`, `runtime_checkable`, `is_protocol`, `get_protocol_members`, `get_type_hints`, `get_origin`, `get_args`, `overload`/`get_overloads`/`clear_overloads`, `assert_type`, `assert_never`, `reveal_type`, `override`, `dataclass_transform`, `evaluate_forward_ref`, plus all ABC/collection aliases. Also native outside `typing`: `Format`/`get_annotations`/`type_repr` (from `annotationlib`), `Reader`/`Writer` (from `io`), `Buffer` (from `collections.abc`), `get_original_bases`/`CapsuleType` (from `types`), `deprecated` (canonical home is `warnings.deprecated` — on ≥3.14.1 `te.deprecated` **is** that object; venv is 3.14.7).

**Still backport-only on 3.14 (import from `typing_extensions` only if ever needed):**
`TypeForm` (PEP 747, no stdlib home yet) · `Doc` (PEP 727 — `hasattr(typing, "Doc")` is `False` on this 3.14.7, backport class is used) · `NoExtraItems` + the `closed=`/`extra_items=` TypedDict knobs (PEP 728 targets 3.15) · `disjoint_base` (PEP 800, 3.15) · `sentinel`/`Sentinel` (preview of 3.15 `builtins.sentinel`) · `IntVar` (legacy helper, never in stdlib). Note the `TypedDict` implementation itself is always the backport's `_TypedDictMeta` in 4.16.0 (`_PEP_764_IMPLEMENTED = False`), with 3.14-aware branches (annotationlib `__annotate__` support) inside it.

**Version-sensitive behaviors that matter here:** `TypeVar`/`ParamSpec`/`TypeVarTuple` accept `default=` (PEP 696) natively on 3.14 — including the ordering rule (a required type-param after a defaulted one raises `TypeError`); `TypeAliasType` attribute writes raise `AttributeError`; `deprecated` on classes warns on instantiation *and* subclassing; `get_type_hints` on 3.14 is plain stdlib (the `Required`/`NotRequired`/`ReadOnly`-stripping shim only applies ≤3.12); no `typing._collect_parameters`/`_check_generic` monkeypatching is active on 3.14 (native PEP 696 path).

## App usage & correctness

**(a) Dependency chains (from installed METADATA `Requires-Dist` + `uv.lock`).** Only two real chains pull the package in, and only one is active on this interpreter:
- `anyio 4.15.1`: `Requires-Dist: typing_extensions>=4.16.0; python_version < "3.15"` — **active on 3.14** (reached via `httpx → anyio`; `httpx` itself declares no direct pin). `uv.lock` agrees: `typing-extensions` with marker `python_full_version < '3.15'`.
- `flet 1.0.0`: `Requires-Dist: typing-extensions; python_version < "3.11"` — **inactive marker on 3.14**; flet does not cause the install here.
- Non-chains (verified): `msgpack` has no `Requires-Dist` at all; `httpcore`/`qrcode`/`watchdog`/`charset_normalizer` METADATA hits for "typing" are changelog prose, not dependencies. `REQUESTED` is empty — nothing depends on it directly; it can never be removed while `anyio` needs it, but it is invisible to app code either way.

**(b) Misuse: none.** `grep -rn "typing_extensions" src tests tools` returns **zero hits** — no app file imports the backport. The 8 `from typing import Any` sites (`src/components/update_dialog.py:6`, `src/core/state.py:8`, `src/core/styles.py:5`, `src/services/update_service.py:6`, `src/state/service_ctx.py:6`, `src/state/controller_ctx.py:7`, `src/services/storage_service.py:10`, `src/services/ad_service.py:12`) all correctly use stdlib `typing`. Correct as-is for a py3.14-only app; keep it that way.

**(c) Correctness notes.** Because the app floor is 3.14, every typing construct it needs exists in stdlib. If a future dependency ever required a still-backport-only name (`TypeForm`, `Doc`, `disjoint_base`, `sentinel`), that import must live in the dependency, not in app code.

## Underused typing to adopt

All of the following are **stdlib on 3.14** — `from typing import …`, no new dependency. Ranked by payoff for v1:

1. **`Literal` for job states + `assert_never` exhaustiveness** (`src/core/state.py:96`, `src/components/job_card.py:23-222`). Today `Job.status` is a bare `str` with the union documented in a comment, and `job_card.py`/`job_queue.py`/`main.py:419` compare against raw strings — a typo (`"completd"`) passes silently.
   ```python
   from typing import Literal, assert_never

   JobStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
   # src/core/state.py
   status: JobStatus = "pending"
   # ...in any dispatcher:
   if job.status == "completed":
       ...
   elif job.status == "failed":
       ...
   else:
       assert_never(job.status)  # checker error the moment a new state is added
   ```
   Same treatment fits `AppState.active_view` (`"dashboard"`, `"convert"`, … in `state.py`) and `Job.op` (`"convert"`, `"compress"`, `"cut"`, …), plus the probe badges (`"checking"`/`"present"`/`"partial"` in `streams_screen.py:79-83`).
2. **`TypedDict` for the update-manifest payload** (`src/services/update_service.py:19`, schema in `version.json`). Today `check_for_updates()` returns `dict[str, Any] | None` and reads `data.get("build_number", 0)` — every key access is unchecked against the real manifest (`build_number`, `version`, `type`, `title`, `release_notes`, `mandatory`, `github_url`, `playstore_url`).
   ```python
   from typing import TypedDict, NotRequired


   class UpdateManifest(TypedDict):
       build_number: int
       version: str
       title: str
       release_notes: NotRequired[str]
       mandatory: NotRequired[bool]
       github_url: NotRequired[str]
       playstore_url: NotRequired[str]


   async def check_for_updates() -> UpdateManifest | None: ...
   ```
3. **`Protocol` for the service registry** (`src/state/service_ctx.py:11-24`). All nine `Services` fields are `Any = None`, so a misspelled service method fails only at runtime on-device. A narrow `Protocol` per service (checker-only, zero runtime cost) restores safety without importing concrete services into UI code:
   ```python
   from typing import Protocol
   from core.state import MediaInfo


   class EngineProtocol(Protocol):
       def probe(self, file_path: str) -> MediaInfo: ...
       def convert(self, *args, **kwargs) -> object: ...


   # Services.engine: EngineProtocol | None = None
   ```
   Add `@runtime_checkable` only if a call site ever needs `isinstance` filtering (remember: presence-only, never signature-checked). Related, lower-priority adoptions: `TypeIs`/`TypeGuard` for probe predicates (`_probe_protocol` in `engine_probe.py:287`, `_codec_mode_available:152`, `_as_name_set:137` — e.g. `def is_present(x: str | None) -> TypeIs[str]`); `ReadOnly` on shared manifest/config `TypedDict`s consumed across screens; `@override` if v1 introduces service subclasses (today `JobQueue`, `EngineService`, `StorageService` are standalone — nothing to annotate yet); `ParamSpec` only if app code gains its own decorators (none exist — `page.run_task` is flet's API, not a local decorator); `dataclass_transform` only if v1 builds a control-factory DSL (no such factory today).

## Gotchas

- `TypedDict` and non-`@runtime_checkable` `Protocol`s raise `TypeError` on `isinstance`/`issubclass` — they are checker-only. `is_typeddict()` is the runtime-safe test.
- `Literal`, `Required`/`NotRequired`/`ReadOnly`, `@final`, `@override` have **no runtime enforcement** (markers/attrs only: `__final__`, `__override__`, `__required_keys__`, …). A `ReadOnly` key is still writable at runtime.
- `@runtime_checkable` checks member *presence*, not signatures; protocols with data members reject `issubclass` outright (with the member list in the error).
- `TypeGuard` vs `TypeIs`: on `True` both narrow; on `False`, `TypeIs` keeps the *intersection* (safer `else` branches), `TypeGuard` falls back to the original type.
- `@deprecated` **does warn at runtime** (`DeprecationWarning`; `category=None` for checker-only deprecation). `assert_never` raises `AssertionError` if reached; `assert_type` is a pass-through; `NewType` is the identity function at runtime.
- `Required`/`NotRequired`/`ReadOnly` are meaningless outside `TypedDict` annotations (wrapping them elsewhere only confuses checkers).
- `TypeVar`/`ParamSpec`/`TypeVarTuple` default ordering is runtime-validated: required-after-default raises `TypeError` at class-creation time.
- `TypeAliasType` objects are immutable after naming; only generic aliases subscript. `Concatenate`'s last argument must be a `ParamSpec` or `...`.
- On 3.14 `typing_extensions` performs no stdlib monkeypatching (native PEP 696 path) — but on older interpreters it patches `typing._check_generic`/`_collect_parameters`; never rely on backport-specific runtime quirks in version-gated code.
