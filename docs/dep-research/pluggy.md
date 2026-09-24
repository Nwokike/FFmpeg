# pluggy 1.6.0 — Complete API Reference

> Plugin/hook framework (pytest's engine). Zero runtime dependencies, MIT, typed (`py.typed`).
> Ground truth: `.venv/Lib/site-packages/pluggy/` + `pluggy-1.6.0.dist-info/` (read 2026-09-23).
> venv total: 1,663 lines across 8 `.py` files.

## Files

| File | Lines | Role |
|---|---|---|
| `__init__.py` | 30 | Public re-exports only |
| `_hooks.py` | 714 | Markers, `HookCaller`/`HookRelay`/`HookImpl`/`HookSpec`, ordering, history |
| `_manager.py` | 523 | `PluginManager`, validation, entry points, tracing hooks |
| `_callers.py` | 169 | `_multicall` loop, old/new wrapper adapters, teardown discipline |
| `_result.py` | 107 | `Result`, `HookCallError` |
| `_tracing.py` | 72 | `TagTracer` / `TagTracerSub` |
| `_warnings.py` | 27 | `PluggyWarning`, `PluggyTeardownRaisedWarning` |
| `_version.py` | 21 | `__version__ = "1.6.0"`, `version_tuple = (1, 6, 0)` (setuptools-scm generated) |
| `py.typed` | 0 | PEP 561 typed-package marker |

`__pycache__/` (8× `cpython-314.pyc`) skipped — build artifacts, no API.

Public surface (`__init__.__all__`, 15 names):

```python
(
    __version__,
    PluginManager,
    PluginValidationError,
)
(
    HookCaller,
    HookCallError,
    HookspecOpts,
    HookimplOpts,
    HookImpl,
)
(
    HookRelay,
    HookspecMarker,
    HookimplMarker,
    Result,
)
PluggyWarning, PluggyTeardownRaisedWarning
```

Backward-compat aliases (pluggy ≤ 1.2, still importable): `_HookRelay`, `_HookCaller`, `_Result`.

## Metadata

From `pluggy-1.6.0.dist-info/METADATA` (+ `WHEEL`/`RECORD`/licenses):

- **Name / Version:** `pluggy 1.6.0` (sdist+wheel uploaded 2025-05-15; uv.lock pins wheel
  `sha256:e920276d…` / sdist `sha256:7dcc130b…`, registry `https://pypi.org/simple`).
- **Summary:** "plugin and hook calling mechanisms for python".
- **License:** MIT (`License: MIT` + classifier `OSI Approved :: MIT License`;
  text at `dist-info/licenses/LICENSE`, © 2015 holger krekel).
- **`Requires-Python: >=3.9`** — no version friction on this repo (app requires `>=3.14`).
- **Runtime pins: NONE.** No `Requires-Dist` outside extras — notably **no `typing_extensions`**
  dependency (uses stdlib `typing` only). Extras: `dev: pre-commit, tox`;
  `testing: pytest, pytest-benchmark, coverage`.
- **Artifact:** `py3-none-any` purelib wheel (`Root-Is-Purelib: true`, setuptools 80.7.1).
- This repo's pull chain: `pyproject [dev] pytest>=9.1.1` → pytest 9.1.1
  `Requires-Dist: pluggy<2,>=1.5` → pluggy 1.6.0 satisfies it. Indirect-only dependency.

## Module-by-module API

### Markers — `_hooks.HookspecMarker` / `HookimplMarker` (both `@final`)

```python
HookspecMarker(project_name: str)
HookspecMarker.__call__(function=None, *, firstresult=False, historic=False,
                        warn_on_impl: Warning | None = None,
                        warn_on_impl_args: Mapping[str, Warning] | None = None)
HookimplMarker(project_name: str)
HookimplMarker.__call__(function=None, *, hookwrapper=False, optionalhook=False,
                        tryfirst=False, trylast=False,
                        specname: str | None = None, wrapper=False)
```

- Usable bare (`@marker`) or with kwargs (`@marker(tryfirst=True)`); sets
  `{project}_spec` / `{project}_impl` attrs holding a `HookspecOpts` / `HookimplOpts` TypedDict.
- **Spec kwargs:** `firstresult=True` — 1:N call stops at first non-`None` impl result and
  returns the scalar (not a list). `historic=True` — every call is memorized and replayed to
  plugins registered later (via `call_historic` only; direct `__call__` asserts). The two are
  mutually exclusive (`ValueError: cannot have a historic firstresult hook`, raised at decoration
  time). `warn_on_impl` / `warn_on_impl_args` (latter added 1.5) emit the given warning at
  registration for matching impls, pinpointed with `warnings.warn_explicit` at the impl's
  file:lineno.
- **Impl kwargs:** `tryfirst` / `trylast` — ordering hints (see ordering below).
  `optionalhook=True` — skip validation when no spec exists (otherwise `check_pending` raises).
  `specname="real_hook"` — register this function under a different hook name.
  `wrapper` (new-style, added 1.2.0) vs `hookwrapper` (old-style) — both require exactly one
  `yield` in a generator function (else `PluginValidationError`, or `RuntimeError: wrap_controller
  … did not yield / has second yield` at call time), and are mutually exclusive.
  - New `wrapper=True`: `result = yield` gives the inner result value (or **raises** the inner
    exception into you); `return x` / `raise y` becomes the hook's outcome.
  - Old `hookwrapper=True`: `outcome = yield` gives a `Result` object; inspect
    `outcome.get_result()` / `.exception`; prefer `force_result` / `force_exception` over raising
    in teardown (raising warns `PluggyTeardownRaisedWarning`, see Gotchas).
- `normalize_hookimpl_opts(opts)` fills all six impl keys with defaults
  (`False`…`None`); called by `register`, **not** needed by hand.

### `PluginManager` — `_manager.PluginManager`

```python
PluginManager(project_name: str)          # .project_name, .hook: HookRelay,
                                          # .trace: TagTracerSub("pluginmanage")
pm.add_hookspecs(module_or_class) -> None
pm.register(plugin, name: str | None = None) -> str | None
pm.parse_hookimpl_opts(plugin, name) -> HookimplOpts | None
pm.parse_hookspec_opts(module_or_class, name) -> HookspecOpts | None
pm.unregister(plugin=None, name=None) -> plugin | None
pm.set_blocked(name) -> None;  pm.is_blocked(name) -> bool;  pm.unblock(name) -> bool
pm.check_pending() -> None
pm.load_setuptools_entrypoints(group: str, name: str | None = None) -> int
pm.list_plugin_distinfo() -> list[(plugin, DistFacade)]
pm.list_name_plugin() -> list[(name, plugin)]
pm.get_hookcallers(plugin) -> list[HookCaller] | None
pm.get_plugins() -> set;  pm.is_registered(p) -> bool
pm.get_canonical_name(p) -> str;  pm.get_plugin(n);  pm.has_plugin(n) -> bool;  pm.get_name(p)
pm.add_hookcall_monitoring(before, after) -> undo()
pm.enable_tracing() -> undo()
pm.subset_hook_caller(name, remove_plugins) -> HookCaller
```

- `register`: name defaults to `get_canonical_name` (`__name__` or `id()`); `ValueError` on
  duplicate name **or** same object under another name; returns `None` for blocked names.
  Only `inspect.isroutine` members carrying `{project}_impl` are picked up; `specname` remaps the
  hook name; unknown hooks get a spec-less `HookCaller` created on the fly (verified later when
  the spec arrives, or flagged by `check_pending` unless `optionalhook`).
- `_verify_hook` (raises `PluginValidationError`, with `.plugin` attr): impl arg names must be a
  subset of spec args; wrapper/hookwrapper impls must be generator functions; historic hooks
  reject wrappers; `warn_on_impl[_args]` warn at impl location.
- `unregister` removes all impls via `HookCaller._remove_plugin` (which raises `ValueError` if
  absent) and drops the name — except blocked names (`None` entries) are kept.
- `load_setuptools_entrypoints(group, name=None)` scans `importlib.metadata.distributions()`,
  skips already-registered/blocked names, `ep.load()`s + registers under `ep.name`, records
  `(plugin, DistFacade)` (`DistFacade.project_name` emulates pkg_resources). Returns count.
- `add_hookcall_monitoring(before(hook_name, hook_impls, kwargs),
  after(outcome: Result, hook_name, hook_impls, kwargs))` wraps `_inner_hookexec` with
  `Result.from_call` capture; returns `undo()`. `enable_tracing()` is this pre-wired to the
  `pluginmanage → hook` tracer with an indent counter.
- `subset_hook_caller(name, remove_plugins)` returns a lightweight `_SubsetHookCaller` **proxy**
  (no copy — avoids the #346 leak / #347 history bugs); if no removed plugin implements the hook,
  returns the original caller. Both parse methods are documented subclass-customization points.
- `PluginValidationError(plugin, message)` — `str(exc)` is the message; offending plugin on
  `.plugin`.

### `HookCaller` call semantics — `_hooks.HookCaller` (+ `HookRelay`)

```python
pm.hook.<name>(**kwargs) -> list | scalar   # __call__; kwargs-ONLY, must match spec
hc.call_historic(result_callback=None, kwargs=None) -> None
hc.call_extra(methods: Sequence[callable], kwargs) -> Any
hc.get_hookimpls() -> list[HookImpl];  hc.has_spec() -> bool;  hc.is_historic() -> bool
```

- `pm.hook` is a `HookRelay` — an empty holder whose attributes are `HookCaller`s created at
  spec/plugin registration (dynamic namespace; static type-checkers see `HookCaller` via
  `__getattr__` in `TYPE_CHECKING`).
- **Ordering (LIFO):** the impl list is iterated **in reverse**, so the **last-registered plain
  impl runs first**. Layout: `[trylast nonwrappers, plain nonwrappers, tryfirst nonwrappers,
  trylast wrappers, plain wrappers, tryfirst wrappers]`; wrappers' pre-yield runs outermost-first,
  post-yield teardown runs in reverse. Within a band, registration order decides (later = earlier
  run), `tryfirst` sinks to the end of its band, `trylast` floats to the start.
- **Results:** non-`firstresult` returns a **list of non-`None` results in call order** (`None`
  returns are dropped — a hook cannot broadcast `None`). `firstresult` stops after the first
  non-`None` impl and returns that **scalar** (`None` if all returned `None`).
- **Args:** keyword-only; each impl receives only the subset it names
  (`args = [kwargs[a] for a in impl.argnames]`). Missing spec args at call time are a
  **warning** (not error); an impl needing an arg the caller didn't pass raises `HookCallError`.
- **Historic:** `call_historic(result_callback, kwargs)` executes + memoizes `(kwargs, callback)`;
  late `register` replays history per-impl via `_maybe_apply_history` (non-`None` list items fan
  out to the callback). Direct `pm.hook.h(...)` on a historic hook **asserts** — must use
  `call_historic`. Returns nothing (results go to the callback).
- **`call_extra`:** ad-hoc call with extra temp impls spliced as plain nonwrappers (after trylast,
  before tryfirst bands); historic forbidden (asserts). Used by pytest for one-off contributors.
- Impl list is `.copy()`ied before each execution, so plugins registering plugins mid-call
  (#438) are safe.

### `Result` + exception rules — `_result.Result`, `_callers._multicall`

```python
Result(result, exception)            # :meta private: constructor
Result.from_call(func) -> Result      # captures BaseException (incl. KeyboardInterrupt/SystemExit)
res.force_result(value) -> None       # clears exception; firstresult→scalar, else→list
res.force_exception(exc) -> None      # (1.1.0) clears result, keeps __traceback__
res.get_result()                      # returns value or `raise exc.with_traceback(tb)`
res.exception -> BaseException | None # :meta private:  res.excinfo -> tuple | None
```

- **Plain impl exceptions propagate** to the hook caller after all wrapper teardowns run —
  pluggy never swallows them (contrast `JobQueue._notify_finished`, which logs-and-continues).
- New-style wrapper: exception thrown **into** the generator at the `yield`; whatever it returns
  or raises replaces the outcome (`StopIteration.value` becomes the new result).
- Old-style wrapper teardown raising: pluggy emits `PluggyTeardownRaisedWarning` (stacklevel 6,
  with plugin/hook/exception + docs link) and re-raises — later teardowns may run at unexpected
  times or be skipped. Fix: migrate to `wrapper=True` or use `force_exception`.
- Setup-phase (pre-yield) exceptions skip remaining setups and go straight to teardown of already
  entered wrappers. Generator protocol violations raise `RuntimeError` naming
  `co_name filename:lineno`. `StopIteration` as the *inner* exception gets a dedicated
  `RuntimeError`-cause guard (#544).

### Tracing & typing

- `TagTracer().get(name) -> TagTracerSub`; `pm.trace` is `.get("pluginmanage")`,
  `enable_tracing` nests `.root.get("hook")`. `setwriter(w)` / `setprocessor("a:b", fn)` /
  `.root.indent += 1` protocol; message format `"<indent>content [tag:sub]\n    key: value\n"`
  (trailing-dict arg rendered as extra lines). Message example:
  `pm.trace.root.setwriter(print); pm.enable_tracing()`.
- Typing: `py.typed` present; `HookspecOpts` / `HookimplOpts` are `TypedDict`s;
  `HookImpl`/`HookSpec` expose `function/argnames/kwargnames/plugin/plugin_name/opts(+namespace/name)`;
  impl functions type as `_HookImplFunction[T] = Callable[..., T | Generator[None, Result[T], None]]`.

Minimal end-to-end (from METADATA docs, verified against this source):

```python
import pluggy

hookspec = pluggy.HookspecMarker("myproject")
hookimpl = pluggy.HookimplMarker("myproject")


class MySpec:
    @hookspec
    def myhook(self, arg1, arg2): ...


class P1:
    @hookimpl
    def myhook(self, arg1, arg2):
        return arg1 + arg2


pm = pluggy.PluginManager("myproject")
pm.add_hookspecs(MySpec)
pm.register(P1())
pm.hook.myhook(arg1=1, arg2=2)  # -> [3]
```

## App usage & correctness

- **Direct usage: NONE — correct.** `grep -ri pluggy src tests tools pyproject.toml` hits nothing;
  no `import pluggy`, no markers, no `PluginManager` in app code. (Name-collision note:
  `tests/test_pause.py` + `src/services/engine_service.py::_pause_hook(cancel_event)` is a plain
  blocking function for the pause `Event`, **not** a pluggy hook — no rename needed, just don't
  confuse the two in reviews.)
- **Chain (verified):** dev-group `pytest>=9.1.1` → installed pytest 9.1.1
  `Requires-Dist: pluggy<2,>=1.5` → pluggy 1.6.0. `_pytest/` imports pluggy in `hookspec.py`,
  `main.py`, `config/__init__.py`, `nodes.py`, `terminal.py`, etc.; `config/__init__.py`
  drives `load_setuptools_entrypoints("pytest11")` — **every pytest hook in this repo is a pluggy
  hook call**. `uv.lock` records both directions (`pytest.dependencies` ∋ `pluggy`;
  `pluggy` package pinned 1.6.0 with hash).
- **How the suite rides on it:** `tests/conftest.py::synthetic_media` (session fixture building a
  2 s 96×64 h264 + 440 Hz AAC clip) and `::fake_page`, plus per-file fixtures
  (`test_all_screens_render`, `test_crossfade`, `test_remux_dossier`, …), `@parametrize`,
  `usefixtures("_isolated_state")` — all dispatched through pytest's pluggy `PluginManager`
  (`pytest_plugins` / entry-point loading in `_pytest/config`). No custom `conftest` hookspecs;
  standard fixture/mark usage, no misuse.
- **Misuse: none found.** No hand-rolled hook dispatch that duplicates pluggy, no version-pin
  conflict (`Requires-Python >=3.9` vs app `>=3.14`), no `hookwrapper` legacy code to migrate.

## Underused APIs to adopt

**Opportunity (warranted, small, post-v1 or late-v1): use pluggy as the in-app job-lifecycle
plugin bus.** Today `JobQueue(runner, on_started, on_finished)` takes single callbacks and
`_notify_finished` try/excepts each — fine for one UI listener, but a second consumer (analytics,
notifier, export-target fan-out, custom-filter registry) means editing core. A `PluginManager`
makes lifecycle 1:N with ordering, isolation-ready semantics, and third-party entry points.

Concrete minimal design (no core rewrite — wrap existing callbacks):

```python
# src/state/job_hooks.py  (new; ~40 lines)
import pluggy

hookspec = pluggy.HookspecMarker("ffmpeg")
hookimpl = pluggy.HookimplMarker("ffmpeg")


class JobSpec:
    @hookspec
    def on_job_start(self, job): ...
    @hookspec
    def on_job_progress(self, job, fraction): ...  # plain, non-historic; keep off hot paths
    @hookspec
    def on_job_done(self, job, ok, error): ...


_pm = pluggy.PluginManager("ffmpeg")
_pm.add_hookspecs(JobSpec)
pm = _pm  # singleton; register builtins at startup, e.g. pm.register(UiBridge())

# in JobQueue._loop / _notify_finished: keep existing callbacks, then
#   pm.hook.on_job_start(job=job)
#   pm.hook.on_job_done(job=job, ok=True, error=None)
```

- **Registration:** singleton in `state/` (e.g. `state/job_hooks.py` or `service_ctx.py`);
  `add_hookspecs` once at import, `register()` builtin bridges at startup, `pm.check_pending()`
  in debug to catch typo'd hook names. Future out-of-tree extensions via
  `pm.load_setuptools_entrypoints("ffmpeg_app")` (distinct group; never `"pytest11"`).
- **Ordering rules:** default LIFO is fine (last-registered notifier runs first — harmless);
  `@hookimpl(tryfirst=True)` for a guard (e.g. pause/cancel gate), `trylast=True` for logging;
  `tryfirst` on the *wrapper* band for timing wrappers (`wrapper=True`, `t0=yield`-style).
  Future selectors (e.g. per-screen muting) → `pm.subset_hook_caller("on_job_progress",
  remove_plugins=[...])`.
- **Future impl ideas (don't build for v1):** custom-filter packs, export targets (Save to
  Files/Share sheet), notifiers (toast/log/upload), each a class with `@hookimpl` methods.
- **When NOT to use it:** (1) single-consumer UI wiring — keep the plain `on_started/on_finished`
  args; (2) hot paths — `on_job_progress` per packet/frame would pay list+copy overhead per call,
  keep the current throttle/poll; (3) anything needing aggregated returns — `None` is dropped and
  multi-results come back as a list, so don't model request/response; (4) crash-critical paths —
  pluggy **propagates** impl exceptions (unlike `_notify_finished`'s log-and-continue), so wrap
  `pm.hook.*` calls in try/except at the dispatch site until per-plugin isolation is designed.
  Cost is ~20 KB wheel, zero runtime deps — the decision is architectural, not footprint.

## Gotchas

1. **LIFO, not FIFO:** last `register()`ed plain impl runs **first**; results list follows call
   order (METADATA toy example prints `[-1, 3]` for P1-then-P2). Don't assume definition order.
2. **`None` is invisible:** returned `None`s are dropped from result lists; a hook has no way to
   broadcast `None`. `firstresult` stops at first non-`None` and returns the scalar.
3. **Wrappers ≠ impls in ordering:** all wrappers run outside all plain impls regardless of
   registration order; `tryfirst/trylast` apply *within* the wrapper/nonwrapper bands.
4. **Old vs new wrappers:** `hookwrapper=True` yields a `Result` (legacy, teardown-raise warns);
   `wrapper=True` yields the value and gets exceptions thrown in (preferred since 1.2.0). Both must
   `yield` exactly once and be generator functions — else `RuntimeError` naming file:line.
5. **Historic is one-way:** no `firstresult`, no wrappers, no direct call (asserts), no return
   value — late plugins get replays, early results go only to `result_callback`. Don't make
   `on_job_progress` historic (unbounded memory + replay storms).
6. **Validation asymmetry:** extra impl args = hard `PluginValidationError`; missing call args =
   mere warning; unknown hooks without spec = error only via `check_pending()` (or silenced by
   `optionalhook=True`). Call `check_pending()` in tests/debug startup.
7. **Exceptions propagate:** any impl/wrapper exception (after teardowns) fails the whole
   `pm.hook.*` call — wrap dispatch sites; `BaseException` (even `KeyboardInterrupt`) is captured
   into `Result` for monitor `after()` hooks and re-raised by `get_result()`.
8. **No thread-safety:** no locks in `PluginManager`/`HookCaller` — register all plugins at startup;
   concurrent `register`/`unregister` from job threads races. Calling hooks from the worker thread
   is fine once registration is frozen.
9. **Name traps:** blocked names make `register` return `None` (not raise); `get_canonical_name`
   falls back to `str(id(plugin))` for anonymous objects (reuse-after-GC can collide — always pass
   explicit `name=` for dynamic plugins); `specname` silently remaps — grep for it when a hook
   "never fires". `subset_hook_caller` returns the *original* caller when nothing is excluded —
   don't mutate the result expecting isolation.
10. **Version note:** 1.6.0 is current-stable for `pytest<2,>=1.5`; `Requires-Python >=3.9` keeps it
   installable everywhere the app runs. No `typing_extensions` pin to track.
