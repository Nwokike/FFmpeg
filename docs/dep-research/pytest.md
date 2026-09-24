# pytest 9.1.1 — Complete API Reference

> App: FFmpeg mobile (Flet 1.0, Python 3.14, uv venv). Suite: 20 test modules + `tests/conftest.py`, 168/168 passing.
> Ground truth: `.venv/Lib/site-packages/{pytest,_pytest,py.py}` + `pytest-9.1.1.dist-info/`. Static reading only; full suite not executed.

## Files

- **Count:** 82 `.py` files across `pytest/` + `_pytest/` (excludes `__pycache__`/`*.pyc`).
- `pytest/` (public surface, thin re-export layer): `__init__.py`, `__main__.py`, `py.typed`.
- `_pytest/` top level (42 modules): `__init__.py`, `_argcomplete.py`, `_version.py`, `assertion/` (11 files: `__init__`, `rewrite`, `util`, `truncate`, `compare_text`, `_compare_any/_mapping/_sequence/_set`, `_guards`, `_typing`, `highlight`), `cacheprovider.py`, `capture.py`, `compat.py`, `config/` (`__init__`, `argparsing`, `exceptions`, `findpaths`), `debugging.py`, `deprecated.py`, `doctest.py`, `faulthandler.py`, `fixtures.py`, `freeze_support.py`, `helpconfig.py`, `hookspec.py`, `junitxml.py`, `legacypath.py`, `logging.py`, `main.py`, `mark/` (`__init__`, `structures`, `expression`), `monkeypatch.py`, `nodes.py`, `outcomes.py`, `pastebin.py`, `pathlib.py`, `pytester.py`, `pytester_assertions.py`, `python.py`, `python_api.py`, `raises.py`, `recwarn.py`, `reports.py`, `runner.py`, `scope.py`, `setuponly.py`, `setupplan.py`, `skipping.py`, `stash.py`, `stepwise.py`, `subtests.py`, `terminal.py`, `terminalprogress.py`, `threadexception.py`, `timing.py`, `tmpdir.py`, `tracemalloc.py`, `unittest.py`, `unraisableexception.py`, `warning_types.py`, `warnings.py`, plus `_code/` (`__init__`, `code`, `source`), `_io/` (`__init__`, `pprint`, `saferepr`, `terminalwriter`, `wcwidth`), `_py/` (`__init__`, `error`, `path`), `py.typed`.
- `py.py` (top-level, 329 bytes): dead-pylib shim — `sys.modules["py.error"]/_pytest._py.error`, `sys.modules["py.path"]=_pytest._py.path`; `__all__ = ["error", "path"]`. Only relevant via legacy `py.path` usage.
- `pytest-9.1.1.dist-info/`: `METADATA`, `RECORD` (hashes every installed file + `Scripts/pytest.exe`, `Scripts/py.test.exe`), `entry_points.txt`, `top_level.txt` (`_pytest`, `py`, `pytest`), `INSTALLER` (uv), `WHEEL` (py3-none-any, setuptools 82.0.1), `REQUESTED`, `licenses/LICENSE`.

## Metadata

- **Version:** 9.1.1 (`_pytest/_version.py`: `__version__ = version = '9.1.1'`, tuple `(9, 1, 1)`). License MIT. `Requires-Python: >=3.10` (classifiers list 3.10–3.15).
- **Runtime deps (pins):** `colorama>=0.4` (win32 only), `exceptiongroup>=1` (py<3.11 only), `iniconfig>=1.0.1`, `packaging>=22`, `pluggy<2,>=1.5`, `pygments>=2.7.2`, `tomli>=1` (py<3.11 only). `dev` extra: argcomplete, attrs≥19.2, hypothesis≥3.56, mock, requests, setuptools, xmlschema.
- **Entry points** (`entry_points.txt`, `[console_scripts]` only): `pytest = _pytest.config:_console_main`, `py.test = _pytest.config:_console_main`. There are **no `pytest11` plugin entries shipped** — third-party plugins register their own `pytest11` group; the app currently has none installed.
- **Public namespace** (`pytest/__init__.py`, ~90 names): `fixture`, `yield_fixture` (deprecated), `register_fixture`, `FixtureDef/FixtureRequest/FixtureLookupError`, `mark`, `param`, `Mark/MarkDecorator/MarkGenerator`, `raises/RaisesExc/RaisesGroup`, `approx`, `warns/WarningsRecorder/deprecated_call`, `skip/fail/xfail/exit/importorskip`, `MonkeyPatch`, `CaptureFixture`, `LogCaptureFixture`, `TempPathFactory` (+ legacy `TempdirFactory/Testdir`), `Cache`, `Config/Parser/OptionGroup/ExitCode/UsageError/PytestPluginManager/hookimpl/hookspec/cmdline/main/console_main`, `ExceptionInfo`, `CallInfo`, `TestReport/CollectReport`, `Session/Dir/Directory/Collector/File/Item`, `Module/Package/Class/Function/Metafunc`, `DoctestItem`, `TerminalReporter/TestShortLogReport`, `Subtests/SubtestReport`, `Stash/StashKey`, `ScopeName`, `Pytester/RunResult/HookRecorder/LineMatcher/RecordedHookCall`, `set_trace`, all `Pytest*Warning` types, `freeze_includes`, `register_assert_rewrite`, `__version__/version_tuple`.

## Module-by-module API

### Fixture system (`_pytest/fixtures.py`, `scope.py`)

```python
@pytest.fixture(fixture_function=None, *, scope="function", params=None,
                autouse=False, ids=None, name=None)
```

- Three overloads: bare `@pytest.fixture`, `@pytest.fixture(...)`, direct `fixture(func, ...)`. Returns `FixtureFunctionMarker` / `FixtureFunctionDefinition`. `yield_fixture` = deprecated alias.
- **Scopes** (`Scope` enum, low→high): `function < class < module < package < session`. `ScopeName = Literal["session","package","module","class","function"]`. `scope=` also accepts `Callable[[str, Config], ScopeName]` (dynamic scope).
- `params=`: iterable → fixture runs once per value; current value at `request.param`; `ids=` customizes test IDs (sequence or callable). `autouse=True` injects without naming. `name=` registers under a different name.
- Yield fixtures: `yield` exactly once; code after `yield` is teardown, runs even on failure. `request.addfinalizer(fn)` is the return-style equivalent.
- **`FixtureRequest`** (injected as `request`): `request.param`, `request.scope` (`"function"|...`), `request.fixturename`, `request.fixturenames`, `getfixturevalue(name)`, `addfinalizer()`, `applymarker(mark)`, `getfixturedefs(name)`, `raiseerror()`, `config`, `session`, `node` (+ `module/cls/instance/function/path/keywords`). `SubRequest` (fixture-scoped) adds teardown context; `TopRequest` is test-scoped.
- **`FixtureDef`** (internal container, stable documented fields only): `argname`, `scope`, `params`, `func`, `baseid`, `cached_result`; `execute(request)`, `finish(request)`, `cache_key(request)`.
- `register_fixture(...)` (programmatic alt to the decorator), `getfixturemarker(obj)`, `FixtureManager` (resolution, `--fixtures` / `--fixtures-per-test` display), `FixtureLookupError`.
- Builtin fixtures available without import: `request`, `pytestconfig`, `tmp_path`, `tmp_path_factory`, `monkeypatch`, `capsys/capfd (+binary/capteesys)`, `caplog`, `recwarn`, `cache`, `record_property/record_xml_attribute/record_testsuite_property`, `doctest_namespace`, `subtests`, `capteesys`.

### Hooks (`_pytest/hookspec.py` — 52 hooks; pluggy `hookspec`/`hookimpl`)

- **Bootstrap/config:** `pytest_addhooks`, `pytest_plugin_registered`, `pytest_addoption(parser, pluginmanager)`, `pytest_configure(config)`, `pytest_cmdline_parse(pluginmanager, args)`, `pytest_load_initial_conftests(early_config, args, parser)`, `pytest_cmdline_main(config) -> ExitCode|int|None`, `pytest_unconfigure(config)`, `pytest_sessionstart/sessionfinish(session, exitstatus)`.
- **Collection:** `pytest_collection(session)`, `pytest_collection_modifyitems(session, config, items)`, `pytest_collection_finish(session)`, `pytest_ignore_collect(collection_path, config)`, `pytest_collect_directory(path, parent)`, `pytest_collect_file(file_path, parent)`, `pytest_collectstart(collector)`, `pytest_itemcollected(item)`, `pytest_collectreport(report)`, `pytest_deselected(items)`, `pytest_make_collect_report(collector)`, `pytest_pycollect_makemodule(module_path, parent)`, `pytest_pycollect_makeitem(pycollector, name, obj)`, `pytest_generate_tests(metafunc)`, `pytest_make_parametrize_id(config, val, argname)`.
- **Run:** `pytest_runtestloop(session)`, `pytest_runtest_protocol(item, nextitem)`, `pytest_runtest_logstart(nodeid, location)`, `pytest_runtest_setup/call/teardown(item[, nextitem])`, `pytest_runtest_logfinish(nodeid, location)`, `pytest_runtest_makereport(item, call)`, `pytest_runtest_logreport(report)`, `pytest_pyfunc_call(pyfuncitem)`, `pytest_report_to_serializable/report_from_serializable`.
- **Fixtures:** `pytest_fixture_setup(fixturedef, request)`, `pytest_fixture_post_finalizer(fixturedef, request)`.
- **Reporting/misc:** `pytest_assertrepr_compare(config, op, left, right)`, `pytest_assertion_pass(item, lineno, orig, expl)`, `pytest_report_header(config, start_path)`, `pytest_report_collectionfinish(config, start_path, items)`, `pytest_report_teststatus(report, config)`, `pytest_terminal_summary(terminalreporter, exitstatus, config)`, `pytest_warning_recorded(warning_message, when, nodeid, location)`, `pytest_markeval_namespace(config)`, `pytest_internalerror(excrepr, excinfo)`, `pytest_keyboard_interrupt(excinfo)`, `pytest_exception_interact(node, call, report)`, `pytest_enter_pdb/pytest_leave_pdb(config, pdb)`.
- Plugin writing = implement any hook + `@pytest.hookimpl` (pluggy options `tryfirst/trylast/hookwrapper/optionalhook`); declare in a `conftest.py` or register a `pytest11` entry point; add CLI/ini via `pytest_addoption`.

### Marks (`_pytest/mark/`, `_pytest/skipping.py`)

- `@pytest.mark.parametrize(argnames, argvalues, indirect=False, ids=None, scope=None, marks=None)`: comma-string or list argnames; values as list or list-of-tuples; `indirect=True|["fixture"]` routes values through fixtures of the same name; `ids=` list/callable; stacked decorators = cartesian product; `pytest.param(..., marks=..., id=...)` for per-case marks/ids; empty-values behavior via `empty_parameter_set_mark` ini (`skip|xfail|fail_at_collect`).
- Builtin markers: `skip(reason)`, `skipif(condition, reason=...)`, `xfail(condition, reason=..., run=True, raises=None, strict=...)`, `filterwarnings(...)`, `usefixtures("a", "b")`; unknown marks warn (`PytestUnknownMarkWarning`) unless registered via `markers` ini + `--strict-markers` errors on them.
- `Mark(name, args, kwargs)` / `MarkDecorator(mark)` (`.with_args()`, `.markname`, callable onto functions/classes) / `MarkGenerator` (`pytest.mark`); `-m EXPR` (boolean mark expression) and `-k EXPR` (name-substring) select; `pytest_collection_modifyitems` sees all items for custom deselect.
- xfail semantics: `run=True` still executes and expects failure; `strict=True` (or `xfail_strict` ini) turns XPASS into failure.

### Collection: `python.py`, `main.py`, `nodes.py`

- Node tree: `Session > Dir/Package > Module > Class > Function`; base `Node` (`.nodeid`, `.name`, `.path`, `.stash`, `.keywords`, `.iter_markers()`), `Collector` vs `Item`. `FSCollector`/`File`/`Directory` for path-backed nodes.
- Default discovery: `testpaths` rooted files matching `python_files = test_*.py|*_test.py`, classes `Test*` (no `__init__`), functions `test*`; `__init__.py` presence toggles package mode. `Metafunc.parametrize()` is what `parametrize` lowers to; `pytest_generate_tests(metafunc)` hook for custom generation (`metafunc.fixturenames`, `metafunc.parametrize(...)`).
- `ImportMode`: `prepend` (default) / `importlib` / `append` — controls sys.path insertion; mismatch raises `ImportPathMismatchError`.
- Key CLI: `--collect-only/-co`, `--continue-on-collection-errors`, `--ignore/--ignore-glob`, `--confcutdir`, `--co -q`, `--pyargs`, `--import-mode`.

### Runner & reports (`runner.py`, `reports.py`, `_code/`)

- Protocol per item: `setup → call → teardown`, each a `CallInfo[T]` (`.when`, `.result`, `.excinfo`, `.from_call()`); failures in setup/teardown still produce reports. `runtestprotocol(item, nextitem)` drives it; `--setup-only/--setup-plan` short-circuit setup display.
- `TestReport`: `.when` (`setup|call|teardown`), `.outcome` (`passed|failed|skipped`), `.longrepr` (traceback/skip reason), `.sections` (captured stdout/stderr/log per phase), `.nodeid`, `.keywords`; `CollectReport` analogous for collectors. JSON-serializable via `pytest_report_to/from_serializable` (powers xdist/JUnit).
- `ExceptionInfo`: `.type/.value/.tb/.match(pattern)`, `.getrepr(style)`, `.traceback` entries with source context; assertion rewrite enriches `assert` introspection (see below).
- Exit codes (`ExitCode` IntEnum): 0 OK, 1 tests failed, 2 interrupted, 3 internal error, 4 usage error, 5 no tests collected.

### Config (`config/__init__.py`, `argparsing.py`, `findpaths.py`)

- `Config`: `.option` (parsed CLI namespace), `.getini(name)`, `.getoption(name)`, `.addinivalue_line()`, `.rootpath/.invocation_params/.pluginmanager/.stash`, `.get_cache()`.
- `Parser.addoption(*names, action/store_true/append/...)`, `addini(name, help, type, default)`; `OptionGroup` groups help. `UsageError` for bad CLI/ini. `PytestPluginManager` = pluggy manager + `register/check_pending`; compat `pytest.config` global removed — use `pytestconfig` fixture.
- Rootdir detection (`findpaths.py`): `pytest.ini` > `pyproject.toml [tool.pytest.ini_options]` > `tox.ini [pytest]` > `setup.cfg [tool:pytest]`; `--rootdir/--config-file/-c` override; `--noconftest` skips conftest loading.
- **ini options registered in-tree:** `addopts`, `cache_dir`, `faulthandler_timeout`, `markers`, `minversion`, `empty_parameter_set_mark` (+ doctest/logging/junit/python `python_files/python_classes/python_functions`, `testpaths`, `norecursedirs`, `console_output_style`, `log_*`, `junit_*`, `xfail_strict`, `filterwarnings`, `pythonpath`). **This app sets only `pythonpath=["src"]`, `testpaths=["tests"]`** (pyproject `[tool.pytest.ini_options]`).
- High-value CLI flags: `-x/--exitfirst`, `--maxfail=N`, `-k/-m`, `--lf/--ff/--nf` (last-failed cache), `--deselect`, `-q/-v`, `--pdb`, `-W`, `--capture=fd|sys|no|tee-sys`, `-s` (= `--capture=no`), `--junit-xml=`, `--durations=N`, `--stepwise`, `-p no:NAME` (disable plugin), `--trace-config`, `--fixtures(-per-test)`, `--markers`, `--collect-only`.

### Assertion rewriting (`assertion/rewrite.py`)

- AST import hook rewrites `assert` in test modules + registered plugins (`register_assert_rewrite("pkg")` / `--assert=rewrite|plain`): decomposes expressions into `where`-clauses, rich diffs for sequences/mappings/sets/strings (`_compare_*`), truncation (`assertion_cutoff_lines`), terminal color (`--code-highlight`). Raises `PytestAssertRewriteWarning` on conflicts. Plain `assert x == y` is the house style — never `self.assert*`.

### Builtin fixtures & helpers

- **`tmp_path: Path` / `tmp_path_factory: TempPathFactory`**: per-test dir (auto-cleaned, 3-deep numbered `test_name0/`); `factory.mktemp(basename, numbered=True)`, `factory.getbasetemp()`; retention via `--basetemp`, `--keep-duplicates`; cleanup keeps last 3 basetemps. Legacy `tmpdir` (py.path) still available — don't use.
- **Capture** (`capture.py`): `capsys` (sys-level), `capfd` (fd-level, sees subprocess/C output), `capteesys/capfd` tee variants, `capsysbinary/capfdbinary` (bytes). `CaptureFixture.readouterr() -> CaptureResult(out, err)` (consumes buffer), `.close()` disables. `--capture=no/-s` disables globally.
- **Logging** (`logging.py`): `caplog: LogCaptureFixture` — `.records`, `.record_tuples`, `.messages`, `.text`, `.handler`, `.set_level(level, logger=None)`, `.at_level(level, logger=None)` ctx, `.clear()`, `.filtering(filter)`; ini `log_cli/log_level/log_format/log_date_format/log_file*`; `--log-cli-level`.
- **Warnings** (`recwarn.py`, `warnings.py`): `recwarn: WarningsRecorder` (`.list` of `WarningMessage`, `.pop()/.clear()`), `pytest.warns(Expected, match=<regex>) -> WarningsChecker` (also callable form `warns(E, func, *a, **k)`), `pytest.deprecated_call(...)`, `@pytest.mark.filterwarnings("error::DeprecationWarning")`, `-W` flag, `filterwarnings` ini.
- **`monkeypatch: MonkeyPatch`**: `.setattr(target|obj, name, value, raising=True)`, `.delattr()`, `.setitem/.delitem(mapping, k, v)`, `.setenv/.delenv(name, value, prepend=None)`, `.syspath_prepend(path)`, `.chdir(path)`, `.undo()`, `.context()` classmethod ctx manager. All undone at test end — the sanctioned replacement for manual save/restore.
- **`approx(expected, rel=None, abs=None, nan_ok=False)`**: scalar/sequence/mapping/numpy/Decimal/timedelta aware; default `rel=1e-6`; pass explicit `abs=` for near-zero comparisons; `nan_ok=True` to treat NaN as equal.
- **`raises(expected, match=<regex>, check=<fn>) -> RaisesExc`**: `.value` (the exception), `.match(regex)` (also asserts post-hoc), `.fail_reason`; classic form `raises(E, func, *args)` returns `ExceptionInfo`; `RaisesGroup` for `ExceptionGroup`; `match` is `re.search` on `str(exc)` + PEP 678 notes — escape dots/brackets.
- **`Cache`** (`cache` fixture / `--cache-show/--clear`): `.get(key, default)/.set(key, value)/.mkdir(name)` under `.pytest_cache`; backs `--lf/--ff`.
- **JUnit XML** (`junitxml.py`): `--junit-xml=path` (+ `--junit-prefix`, `--junit-duration-report`), `record_property(name, value)`, `record_xml_attribute(name, value)`, `record_testsuite_property(name, value)` fixtures.
- **`skip/fail/xfail/exit/importorskip`** (`outcomes.py`): `pytest.skip(reason, allow_module_level=False)`, `pytest.fail(reason, pytrace=True)`, `pytest.xfail(reason)` (imperative), `pytest.exit(reason, returncode=None)`, `pytest.importorskip(modname, minversion, reason, exc_type=None)`.
- **`Stash`/`StashKey[T]`**: type-safe heterogeneous map on `Config`/nodes (`key = StashKey[str](); config.stash[key] = v`).
- **`Subtests`** (`subtests` fixture): `with subtests.test(msg=...)` — soft multi-assert within one test (JUnit-friendly `SubtestReport`).
- **`stepwise`** (`--stepwise/--stepwise-skip`): stop at first failure, resume from last failure next run (cache-backed).
- **Debugging** (`debugging.py`): `--pdb` (drop into pdb on failure), `--trace`, `pytest.set_trace()`, `--pdbcls`.
- **Doctest** (`doctest.py`): `--doctest-modules`, `--doctest-glob`, `--doctest-report=none/short`, `doctest_namespace` fixture.
- **unittest compat** (`unittest.py`): `TestCase` subclasses collected; `setUp/tearDown` honored; skips mapped.
- **terminal/cache extras**: `--durations=N`, `--durations-min`, `-rfEsxX` summary chars, `--tb=short|line|no`, `-q/-v`, `--color=yes|no|auto`, `--max-warnings`, `--disable-warnings`.
- **Warning types** (`warning_types.py`): `PytestWarning` base + `PytestAssertRewriteWarning`, `PytestCacheWarning`, `PytestCollectionWarning`, `PytestConfigWarning`, `PytestDeprecationWarning`, `PytestExperimentalApiWarning`, `PytestFDWarning`, `PytestRemovedIn10Warning`, `PytestReturnNotNoneWarning` (tests must return None), `PytestUnhandledThreadExceptionWarning`, `PytestUnknownMarkWarning`, `PytestUnraisableExceptionWarning`.

## App usage & correctness

### (a) Correct usage — keep

- Session media factory done right: `tests/conftest.py:61-62` — `@pytest.fixture(scope="session") def synthetic_media(tmp_path_factory)` + `mktemp("engine_media")`; single 2 s H264/AAC encode amortized over 168 tests; `import av` fail-fast inside.
- `caplog.at_level("WARNING")` + record scan (`tests/test_crossfade.py:127-136`, `:142-150`) is the canonical log-assertion idiom.
- `monkeypatch.setattr("services.engine_service.available_filters", ...)` (`tests/test_crossfade.py:142-146`, `tests/test_update_service.py:16-27`) correctly avoids real-network/real-codec coupling.
- Per-test `tmp_path` isolation for outputs (`test_concat.py`, `test_subtitles.py`, `test_command_parser.py:media`), `pytest.raises(..., match=...)` with loud refusal messages (`test_command_parser.py:75,155,182,188,196,201,207`), one good `pytest.approx` (`test_command_parser.py:135`), module-level `pytestmark = pytest.mark.usefixtures(...)` (`test_all_screens_render.py:37`, `test_tab_crashes.py:26`), parametrized atempo table + screen-render matrix (`test_engine_params.py:19`, `test_all_screens_render.py:92` with `ids=`).

### (b) Misuse / weaknesses (file:line)

1. **Tests coupled to private APIs** — any underscore rename breaks the suite with zero app breakage: `tests/test_routes.py:10` (`flet.components.router._match_routes/_normalize_path`) + `:12` (`app_shell._ROUTES`); `tests/test_previews.py:6` (`_mjpeg_bytes`), `:5` (`screens.result_screen._fmt_ms`); `tests/test_remux_dossier.py:15` (`screens.probe_screen._fmt_ct`); `tests/test_engine_params.py:14` (`_atempo_factors`); `tests/test_pause.py:10` (`_pause_hook`); `tests/test_subtitles.py:18-28` (`_fmt_srt_time/_write_*`); `tests/test_capture_helpers.py:9` (`_can_capture/_pcm_rms/_write_wav`); `tests/test_tab_crashes.py:21` (`app_shell._build_navigation_bar/_dashboard_view`). Worst case is `test_routes.py:32-54`: five tests iterate `_ROUTES` directly — prefer a public `resolve_route(path)` helper and test through it.
2. **Duplicated fixture/helper logic across modules** — the two `_isolated_state` fixtures differ in snapshot width (`tests/test_all_screens_render.py:61` snapshots jobs/history/terms/tab/settings vs `tests/test_tab_crashes.py:30` which omits `settings`), so settings leak in one file but not the other; `_render()` is copy-pasted (`test_all_screens_render.py:86`, `test_tab_crashes.py:43`, plus a third inline variant via `mock_ctx` in `tests/test_render.py:31`); clip builders are quadrupled (`_build_synthetic` in conftest, `_make_clip` in `test_concat.py`, `_gray_clip` in `test_crossfade.py`, `_rich_source` in `test_remux_dossier.py`). Move all four into `conftest.py`.
3. **Over-broad / bare exception assertions**: `tests/test_concat.py:112` `pytest.raises(Exception)` (with a `noqa: B017` apology — narrow to `(FileNotFoundError, FFmpegError)` or assert the message); `test_bare_invocation_lists_help` in `test_command_parser.py` uses bare `pytest.raises(CommandError)` with no `match`, unlike every sibling refusal test.
4. **Hand-rolled float tolerance instead of `approx`**: `tests/test_concat.py:78,97`, `tests/test_engine_params.py:55,66` (and the crossfade/remux duration checks) use `abs(a-b) < 0.35`-style asserts — `pytest.approx` diffs read better on failure.
5. **`tempfile` instead of `tmp_path`**: `tests/test_engine.py:23` and `tests/test_storage.py:11` use `tempfile.TemporaryDirectory()` — loses pytest's auto-cleanup/numbering/`--basetemp` integration; `test_storage.py` additionally crams an entire lifecycle (get/set/flush/remove/re-read) into one test function.
6. **Thread-timing-dependent queue tests** (`tests/test_job_queue.py` sleeps 0.05–0.3 s; `tests/test_pause.py` similar) — no `pytest-timeout`/`pytest-repeat`/`pytest-rerunfailures` installed; a slow CI worker can flake these. `tests/test_update_service.py:33` wraps async code in `asyncio.run()` per test — fine today, but an `anyio`-style async-test plugin would remove the boilerplate if async coverage grows.
7. **`pyproject.toml [tool.pytest.ini_options]` sets only `pythonpath` + `testpaths`** — no `filterwarnings`, no `xfail_strict`, no `markers` registration, no `addopts`; unknown-mark typos are currently silent warnings.

### (c) Coverage gaps (no test exercises these paths)

Zero usage of `pytest.warns`/`recwarn` (warning regressions untestable), `capsys`/`capfd` (CLI/helper stdout untested), `skip`/`skipif`/`xfail` markers (no platform-gated tests — e.g. codec-absent paths), `tmp_path_factory` beyond conftest, `monkeypatch.setenv/chdir` (env-dependent code untested), `cache` fixture, JUnit XML output, `--lf/--ff` workflow, `subtests`, `doctest-modules`.

## Underused APIs to adopt

1. **`@pytest.mark.parametrize` to collapse duplicated cases** — biggest win. `test_capture_helpers.py` has five sequential `next_permission_action` tests and `test_previews.py:fmt_ms`/subtitle time-format tests are assert-lists begging for tables (the `test_atempo_factors` table at `test_engine_params.py:19` is the template). Also parametrize `test_concat_to_mkv` over containers and the `record_unknown_protocol` refusal over bad schemes.
2. **`monkeypatch` (setenv/chdir/syspath)** — replace any future env manipulation; already proven in-repo (`test_crossfade.py:142`, `test_update_service.py:16`).
3. **`tmp_path` everywhere** — migrate `test_engine.py:23`, `test_storage.py:11` off `tempfile`; use `tmp_path_factory` for any new session asset.
4. **`pytest.warns` / `recwarn`** — pin the deprecation/fallback warnings the engine already emits ("falling back to instant" is currently asserted via `caplog`; a `pytest.warns` counterpart covers the warnings-channel callers).
5. **Custom markers + `--strict-markers`** — register `slow`, `needs_gpu`, `needs_network`, `engine` in the `markers` ini, mark the engine-heavy modules, allow `pytest -m "not slow"` for fast local loops and a full gate in CI.
6. **`capsys`/`capfd`** — assert CLI/helper stdout-stderr contracts (`help_text()`, dossier report printing) instead of only return values.
7. **`filterwarnings = ["error::DeprecationWarning"]`** in ini — turn warning regressions into failures pre-v1.0.
8. **JUnit XML in CI** — `--junit-xml=reports/junit.xml` + `record_property` (build number, codec set) needs zero test changes.
9. **`--lf/--ff`, `--stepwise`, `--durations=10`** — free workflow upgrades for the 2.5-minute suite; `--durations` identifies the slowest engine tests to split or mark `slow`.
10. **`subtests`** (`with subtests.test(...)`) — for the multi-assert render/probe tests where one failing assert currently hides the rest.
11. **`pytest.importorskip`** — guard optional-dependency tests (e.g. codec-specific paths) instead of hard imports.

## Gotchas

- `match=` is `re.search`, not `re.fullmatch` — escape `.`, `(`, `[` in messages (the suite's `match=r"\.mkv"` and `match=r"protocol|Couldn't|read"` get this right; bare-string matches like `match="duration"` are substring checks).
- `pytest.raises` needs the code *inside* the `with` block; returning the plan then asserting outside (as some tests do with `plan = parse_command(...)`) only works for the non-raising path.
- `approx` default `rel=1e-6` fails near zero — media timestamps/durations near 0.0 need explicit `abs=`; never nest `approx` inside `==` chains with `and`.
- `tmp_path` is per-test and deleted after; anything the session fixture must share belongs under `tmp_path_factory` (as `synthetic_media` correctly does). Never write into the repo tree from tests.
- `capsys` misses C-level/fd output (ffmpeg logs) — use `capfd` there; `caplog` needs `at_level()` because the default level swallows WARNING-adjacent records depending on root config.
- `monkeypatch` undoes at teardown — assigning module globals without it (e.g. mutating `state.settings` directly) leaks between tests; that's exactly why the two `_isolated_state` fixtures exist, and why they should be one fixture in `conftest.py`.
- `xfail(strict=True)` / `xfail_strict=true` turns XPASS into FAILURE — set it before v1.0 so fixed bugs can't hide as unexpected passes.
- Tests must return `None` (`PytestReturnNotNoneWarning` otherwise) — watch the `asyncio.run()` wrapper in `test_update_service.py:33` swallowing coroutine tracebacks; prefer `await`-native tests if async coverage grows.
- `--lf` cache lives in `.pytest_cache/` — never commit it; `cache_dir` ini can relocate it for CI hygiene.
- Assertion rewrite only applies to test modules and `register_assert_rewrite` packages — asserts inside `src/` helpers show plain tracebacks unless `pythonpath` + `consider_namespace_packages` cooperate; keep behavior asserts in `tests/`.
- `scope="session"` fixtures can't see function-scoped fixtures (`tmp_path` inside `synthetic_media` would error — it correctly uses `tmp_path_factory`).
- Class/module-scoped fixtures with `params` multiply the whole downstream closure — prefer function scope for parametrized media variants.
