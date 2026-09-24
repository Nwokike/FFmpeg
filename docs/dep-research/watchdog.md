# watchdog 6.0.0 — Complete API Reference

> Installed wheel: `watchdog-6.0.0-py3-none-win_amd64` (pure-Python + `ctypes`; `py.typed` present).
> Package dir: `.venv/Lib/site-packages/watchdog`. Dist-info: `.venv/Lib/site-packages/watchdog-6.0.0.dist-info`.
> Layout correction vs. older docs: events live in single `watchdog/events.py` (there is **no** `events/api.py`);
> there is **no** `observers/observer.py`, **no** `decorators.py` (`@scheduled`/`@pattern`/`@exclude` do not exist
> in 6.0.0), **no** `main.py`/`cli.py` (CLI is `watchdog/watchmedo.py`), and **no** `utils/decorator.py`.

## Files

Enumerated (skipping `__pycache__`); all read:

| File | Contents |
|---|---|
| `watchdog/__init__.py` | Empty (0 bytes). No re-exports; import from submodules. |
| `watchdog/version.py` | `VERSION_MAJOR/MINOR/BUILD = 6/0/0`, `VERSION_INFO = (6, 0, 0)`, `VERSION_STRING = "6.0.0"`, `__version__ = VERSION_INFO` (note: a **tuple**, not a string). |
| `watchdog/events.py` | All event dataclasses + `FileSystemEventHandler`, `PatternMatchingEventHandler`, `RegexMatchingEventHandler`, `LoggingEventHandler`, `generate_sub_moved_events`, `generate_sub_created_events`. |
| `watchdog/observers/__init__.py` | Platform picker; `Observer = _get_observer_cls()`. Windows → `WindowsApiObserver`, Linux → `InotifyObserver`, macOS → `FSEventsObserver` (fallback `KqueueObserver`), BSD → `KqueueObserver`, else `PollingObserver` (with `warnings.warn` on fallback paths). |
| `watchdog/observers/api.py` | `EventQueue`, `ObservedWatch`, `EventEmitter`, `EventDispatcher`, `BaseObserver`; `DEFAULT_EMITTER_TIMEOUT = DEFAULT_OBSERVER_TIMEOUT = 1.0`. |
| `watchdog/observers/read_directory_changes.py` | `WindowsApiEmitter`, `WindowsApiObserver` (this host's backend). |
| `watchdog/observers/winapi.py` | Raw `ctypes` binding to `kernel32` (`ReadDirectoryChangesW`, `CreateFileW`, `CloseHandle`, `CancelIoEx`, …). Module docstring: *"removes dependency on `pywin32`"*. |
| `watchdog/observers/polling.py` | `PollingEmitter`, `PollingObserver`, `PollingObserverVFS` (snapshot-diff fallback, any platform). |
| `watchdog/observers/inotify.py` | `InotifyEmitter`, `InotifyFullEmitter`, `InotifyObserver(generate_full_events=False)`. |
| `watchdog/observers/inotify_buffer.py` | `InotifyBuffer(BaseThread)` — buffered `read_event()` layer over `Inotify`. |
| `watchdog/observers/inotify_c.py` | `InotifyConstants` (mask bits), `InotifyEventStruct` (ctypes), `Inotify` (libc wrapper), `InotifyEvent` (predicates: `is_create/is_modify/is_attrib/is_delete/is_delete_self/is_moved_from/is_moved_to/is_move/is_open/is_close_write/is_close_nowrite/is_directory`). |
| `watchdog/observers/kqueue.py` | `KeventDescriptorSet`, `KeventDescriptor`, `KqueueEmitter`, `KqueueObserver`; helpers `absolute_path/is_deleted/is_modified/is_attrib_modified/is_renamed`. Header warns kqueue is heavyweight (per-file fds, full dir re-scan per change). |
| `watchdog/observers/fsevents.py` | `FSEventsEmitter`, `FSEventsObserver` (native `_watchdog_fsevents` C extension; macOS only). |
| `watchdog/observers/fsevents2.py` | Deprecated PyObjC (`AppKit`/`FSEvents`) implementation. Do not use. |
| `watchdog/tricks/__init__.py` | `Trick`, `LoggerTrick`, `ShellCommandTrick`, `AutoRestartTrick`, `kill_process`. |
| `watchdog/watchmedo.py` | `watchmedo` CLI: `tricks-from` (alias `tricks`), `tricks-generate-yaml`, `log`, `shell-command`, `auto-restart`; `main()` entry point. |
| `watchdog/utils/__init__.py` | `BaseThread` (daemon stoppable thread), `UnsupportedLibcError`, `WatchdogShutdownError`, `load_module`, `load_class`. |
| `watchdog/utils/patterns.py` | `filter_paths`, `match_any_paths`, `_match_path`. |
| `watchdog/utils/dirsnapshot.py` | `DirectorySnapshot`, `DirectorySnapshotDiff` (+ `.ContextManager`), `EmptyDirectorySnapshot`. |
| `watchdog/utils/bricks.py` | `SkipRepeatsQueue` (drops consecutive-duplicate puts). |
| `watchdog/utils/delayed_queue.py` | `DelayedQueue(delay)` (`put(element, delay=False)`, `get()`, `remove(predicate)`, `close()`). Used by kqueue emitter. |
| `watchdog/utils/event_debouncer.py` | `EventDebouncer(debounce_interval_seconds, events_callback)` (`handle_event`, `stop`, `run`). Used by `AutoRestartTrick --debounce-interval`. |
| `watchdog/utils/process_watcher.py` | `ProcessWatcher(popen_obj, process_termination_callback)` — polls `poll()` every 0.1 s. |
| `watchdog/utils/echo.py` | `echo(fn, write=sys.stdout.write)` decorator + `format_arg_value`; used to log trick calls via `echo_events`. |
| `watchdog/utils/platform.py` | `get_platform_name()`, `is_linux/is_bsd/is_darwin/is_windows()` over `sys.platform`; constants `PLATFORM_WINDOWS/LINUX/BSD/DARWIN/UNKNOWN`. |

## Metadata

From `watchdog-6.0.0.dist-info/METADATA` (+ `entry_points.txt`, `WHEEL`, `RECORD`):

- `Name: watchdog`, `Version: 6.0.0`, `Summary: Filesystem events monitoring`, `License: Apache-2.0`
  (license files: `LICENSE`, `COPYING`, `AUTHORS`), `Requires-Python: >=3.9` (venv here is 3.14 — fine).
- **Runtime pins: none.** The only `Requires-Dist` is `PyYAML>=3.10; extra == "watchmedo"`.
  There is **no `pywin32` dependency — confirmed absent** (no `pywin32`/`win32`/`pythoncom` top-level
  dir in `site-packages`). Windows observation works because `observers/winapi.py` calls
  `ReadDirectoryChangesW`/`CreateFileW` directly through `ctypes.WinDLL("kernel32")`.
  Consequence: nothing extra to install on Windows; `PollingObserver` is the only fallback
  (used automatically if the `read_directory_changes` import ever fails, or forcibly via
  `--debug-force-polling` / `PollingObserver` import, e.g. for CIFS shares).
- Entry point (`entry_points.txt`): `[console_scripts] watchmedo = watchdog.watchmedo:main [watchmedo]`
  — i.e. the `watchmedo` exe (`Scripts/watchmedo.exe` is installed) requires the `watchmedo` extra
  for YAML-based commands. `PyYAML 6.0.3` **is** installed in this venv, so all subcommands work.
- `Provides-Extra: watchmedo`. `RECORD` lists all 20 package files above plus the exe.
  `REQUESTED` is empty (not a direct requirement — see § App usage).

## Module-by-module API

### Minimal observer snippet (canonical shape)

```python
import time
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class MyEventHandler(FileSystemEventHandler):
    def on_any_event(self, event: FileSystemEvent) -> None:
        print(event)


observer = Observer()  # WindowsApiObserver on this host
watch = observer.schedule(MyEventHandler(), ".", recursive=True)
observer.start()
try:
    while True:
        time.sleep(1)
finally:
    observer.stop()  # triggers unschedule_all via on_thread_stop
    observer.join()
```

### `watchdog.events` — events + handlers

Event-type constants: `EVENT_TYPE_MOVED/DELETED/CREATED/MODIFIED/CLOSED/CLOSED_NO_WRITE/OPENED`
(`"moved"`, `"deleted"`, `"created"`, `"modified"`, `"closed"`, `"closed_no_write"`, `"opened"`).

Base (a `@dataclass(unsafe_hash=True)`, immutable-by-convention, hashable → usable as dict keys):

```python
@dataclass(unsafe_hash=True)
class FileSystemEvent:
    src_path: bytes | str
    dest_path: bytes | str = ""
    event_type: str = field(default="", init=False)  # class attr on subclasses
    is_directory: bool = field(default=False, init=False)
    is_synthetic: bool = False  # True when synthesized (e.g. sub-events of a moved dir)
```

Hierarchy (`event_type` / `is_directory` are class attributes, so `event.event_type` reads them):

- `FileSystemMovedEvent(FileSystemEvent)` — `event_type = "moved"`.
- File: `FileDeletedEvent`, `FileModifiedEvent`, `FileCreatedEvent` (deleted/modified/created),
  `FileMovedEvent(FileSystemMovedEvent)` (`src_path` + `dest_path`),
  `FileClosedEvent` (`"closed"` — opened-for-write closed), `FileClosedNoWriteEvent`
  (`"closed_no_write"` — opened-for-read closed), `FileOpenedEvent` (`"opened"`).
- Dir (`is_directory = True`): `DirDeletedEvent`, `DirModifiedEvent`, `DirCreatedEvent`,
  `DirMovedEvent(FileSystemMovedEvent)` (`src_path` + `dest_path`).
- Only moved events carry a meaningful `dest_path`. `is_synthetic=True` marks events produced by
  `generate_sub_moved_events(src_dir, dest_dir)` / `generate_sub_created_events(src_dir)` (walk the
  moved/created tree and synthesize one event per child).

`FileSystemEventHandler.dispatch(event)` calls `on_any_event(event)` then
`getattr(self, f"on_{event.event_type}")(event)`. Override any of (all no-ops by default):

```python
def on_any_event(self, event: FileSystemEvent) -> None: ...
def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None: ...
def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None: ...
def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None: ...
def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None: ...
def on_closed(self, event: FileClosedEvent) -> None: ...
def on_closed_no_write(self, event: FileClosedNoWriteEvent) -> None: ...
def on_opened(self, event: FileOpenedEvent) -> None: ...
```

`PatternMatchingEventHandler` (subclass; **present** — use instead of the non-existent `@pattern` decorator):

```python
PatternMatchingEventHandler(*, patterns=None, ignore_patterns=None,
                            ignore_directories=False, case_sensitive=False)
# read-only properties: .patterns / .ignore_patterns / .ignore_directories / .case_sensitive
# dispatch(): skips dir events if ignore_directories; matches src_path AND dest_path
#   via match_any_paths(); calls super().dispatch() only on match.
```

`RegexMatchingEventHandler(*, regexes=None, ignore_regexes=None, ignore_directories=False, case_sensitive=False)` —
same shape; `regexes=None` → `[r".*"]`, a bare `str` is wrapped in a list, compiled with
`re.IGNORECASE` unless `case_sensitive=True`; matching uses `regex.match(path)` (**prefix** match,
not `search`/`fullmatch`). `LoggingEventHandler(*, logger=None)` (defaults to `logging.root`)
logs moved/created/deleted/modified/closed/closed-no-write/opened with file-vs-directory wording.

### `watchdog.utils.patterns` — glob matching semantics

```python
filter_paths(paths, *, included_patterns=None, excluded_patterns=None, case_sensitive=True) -> Iterator[str]
match_any_paths(paths, *, included_patterns=None, excluded_patterns=None, case_sensitive=True) -> bool
```

- Defaults: included `["*"]` (match all), excluded `[]`. Uses `pathlib` `PurePath.match()`
  (`"*.py"` matches the final component, so `PurePath("/a/b.py").match("*.py")` is `True`).
- Case handling: `case_sensitive=True` → `PurePosixPath`; `False` → patterns and path lowered and
  matched as `PureWindowsPath`. Note the asymmetry: `PatternMatchingEventHandler` defaults
  `case_sensitive=False` while the raw functions default `True`.
- A pattern appearing in **both** lists raises `ValueError("conflicting patterns ...")`.
- No hidden-file special-casing: dotfiles match like any other file unless your patterns exclude them.

### `watchdog.observers.api` — Observer / BaseObserver

```python
ObservedWatch(path: str | Path, *, recursive: bool, event_filter: list[type[FileSystemEvent]] | None = None)
# .path -> str; .is_recursive -> bool; .event_filter -> frozenset | None
# equality/hash/repr by (path, recursive, event_filter) key.

EventEmitter(event_queue, watch, *, timeout=1.0, event_filter=None)
# .timeout / .watch; .queue_event(event) (applies isinstance event_filter);
# .queue_events(timeout) (overridden per backend); .run() loops queue_events.

BaseObserver(emitter_class, *, timeout=1.0)   # subclass via e.g. WindowsApiObserver(timeout=...)
observer.schedule(event_handler, path: str, *, recursive=False, event_filter=None) -> ObservedWatch
observer.add_handler_for_watch(handler, watch) -> None
observer.remove_handler_for_watch(handler, watch) -> None
observer.unschedule(watch) -> None
observer.unschedule_all() -> None
observer.start() -> None      # starts pending emitters, then dispatcher thread
observer.stop() -> None       # signals stop; on_thread_stop() -> unschedule_all()
observer.join() / .is_alive() # threading.Thread
observer.emitters -> set[EventEmitter]
observer.event_queue -> EventQueue
observer.timeout -> float
```

Semantics that matter:

- **Threads are daemon** (`BaseThread`: `daemon=True`, `should_keep_running()`, `stop()` → `on_thread_stop()`).
  One emitter thread per scheduled watch + one dispatcher thread per observer.
- **Queue dedups consecutive repeats**: `EventQueue(SkipRepeatsQueue)` drops a `put` equal to the last item
  (items are `(event, watch)` tuples; events are hashable dataclasses). Bursts of identical events collapse —
  do not use event counts as a change counter; always re-`stat`/re-scan on receipt.
- `schedule()` before `start()` defers emitter start; after `start()` the emitter starts immediately.
  Same `(path, recursive, event_filter)` scheduled twice reuses one emitter with two handler entries.
- `event_filter` is applied twice: in `queue_event` (`isinstance` check) and, on inotify, as a kernel
  mask optimization (`get_event_mask_from_filter`). `dispatch_events` takes entries with blocking
  `queue.get(block=True)` and calls each still-registered handler (safe to `unschedule` inside a handler).
- Exceptions: no watchdog-specific exception on `schedule` for a missing path at schedule time on most
  backends — the emitter fails at `start()` (Windows: `CreateFileW` raises `ctypes.WinError`; polling:
  first snapshot raises `OSError` → queues `DirDeletedEvent(watch.path)` and stops). Guard with `os.path.isdir`.

### Backends — which runs where (this host: Windows)

- **Windows** (`read_directory_changes.WindowsApiObserver` / `WindowsApiEmitter`, via `winapi.py`):
  blocking `ReadDirectoryChangesW` on a `CreateFileW(path, FILE_LIST_DIRECTORY, share-all, OPEN_EXISTING,
  FILE_FLAG_BACKUP_SEMANTICS)` handle; notify filter covers file/dir names, attributes, size, last-write,
  security, last-access, creation. `BUFFER_SIZE = 64000` (capped: >64 KB fails over networks),
  `PATH_BUFFER_SIZE = 2048`. Rename pairing: `RENAMED_OLD_NAME` → remember src, `RENAMED_NEW_NAME` →
  emit `DirMovedEvent`/`FileMovedEvent` (+ synthesized sub-events when recursive). Added → created (+
  sub-created when recursive dir); modified → `Dir/FileModifiedEvent` via `os.path.isdir` check;
  removed → `FileDeletedEvent`; deleted-self → `DirDeletedEvent(watch.path)` + emitter stops
  (**you must reschedule after the watched root itself is deleted**). `timeout` is accepted but the read is
  effectively blocking; `close_directory_handle` uses `CancelIoEx` to unblock. No `FileOpened`/`FileClosed`
  events on Windows. **No pywin32 involved.**
- **Linux** (`InotifyObserver`; `InotifyFullEmitter` iff `generate_full_events=True`, which reports unmatched
  move halves as `MovedEvent("", path)`/`(path, "")` instead of created/deleted). Recursive watches are
  emulated by adding one inotify watch per subdirectory. Emits `FileOpenedEvent`/`FileClosedEvent`/
  `FileClosedNoWriteEvent` — the **only** backend that does. Watching the root dir's own deletion stops the emitter.
- **macOS** (`FSEventsObserver`, native `_watchdog_fsevents`; legacy `fsevents2` is deprecated/PyObjC).
  `KqueueObserver` is the fallback; kqueue needs one fd per watched file (raise `ulimit -n`) and re-scans
  on change — not scalable for big trees.
- **Polling** (`PollingObserver`, `PollingEmitter(timeout)`; `PollingObserverVFS(stat, listdir, polling_interval=1)`):
  `DirectorySnapshot` every `timeout` seconds → `DirectorySnapshotDiff` → created/deleted/modified/moved for
  files and dirs. `OSError` taking a snapshot → `DirDeletedEvent` + stop. Slow, CPU/disk-heavy, but the only
  choice for CIFS/network shares and exotic filesystems. `PollingObserverVFS` accepts custom `stat`/`listdir`
  (poll anything listdir-like, e.g. a remote listing).

### `watchdog.utils.dirsnapshot` — one-shot diffing (no thread needed)

```python
DirectorySnapshot(path, *, recursive=True, stat=os.stat, listdir=os.scandir)
# .paths, .path(uid)->path|None, .inode(path)->(st_ino, st_dev), .isdir/.mtime/.size/.stat_info(path)
# snapshot2 - snapshot1 -> DirectorySnapshotDiff; EmptyDirectorySnapshot() == "everything is new"
DirectorySnapshotDiff(ref, snapshot, *, ignore_device=False)
# .files_created/.files_deleted/.files_modified/.files_moved (pairs)
# .dirs_created/.dirs_deleted/.dirs_modified/.dirs_moved (pairs)
# move detection is inode-based: crossing partition boundaries degrades moves to created+deleted.
DirectorySnapshotDiff.ContextManager(path, *, recursive=True, stat=..., listdir=..., ignore_device=False)
# with cm: cm.__enter__ takes pre-snapshot; __exit__ takes post + sets cm.diff
```

### `watchdog.tricks` — ready-made handlers (also the `watchmedo` building blocks)

- `Trick(PatternMatchingEventHandler)` — base + `generate_yaml()` classmethod (emits a `tricks.yaml` stub).
- `LoggerTrick` — `@echo_events`-decorated `on_any_event` (logs the call signature at `INFO`).
- `ShellCommandTrick(shell_command, *, patterns=None, ignore_patterns=None, ignore_directories=False, wait_for_process=False, drop_during_process=False)` —
  ignores `opened`/`closed_no_write` events; interpolates `${watch_src_path} ${watch_dest_path} ${watch_event_type} ${watch_object}`
  via `string.Template.safe_substitute`; `None` command → default `echo ...`; `shell=True`; `wait_for_process`
  blocks the dispatcher thread, otherwise a `ProcessWatcher` reaps; `is_process_running()`.
- `AutoRestartTrick(command: list[str], *, patterns=None, ignore_patterns=None, ignore_directories=False, stop_signal=signal.SIGINT, kill_after=10, debounce_interval_seconds=0, restart_on_command_exit=True)` —
  `start()` launches (+ optional `EventDebouncer`), `stop()` terminates (`kill_process`: `os.kill` on
  Windows, `killpg` on POSIX; `kill_after` grace then signal 9), any non-ignored event restarts;
  `restart_count`. `ValueError` if `kill_after`/`debounce_interval_seconds` negative.
  `stop_signal` accepts `signal.Signals` or `int`.

### `watchmedo` CLI — full flags (`watchmedo --help`; `main() -> int`, `130` on Ctrl-C)

Global: `--version`; per-command `-q/--quiet` (once) / `-v/--verbose` (≤2) → ERROR/WARNING/INFO/DEBUG.

- `watchmedo tricks <file...> [--python-path .] [--interval|--timeout 1.0] [--recursive (default True)] [--debug-force-polling|--debug-force-kqueue|--debug-force-winapi|--debug-force-fsevents|--debug-force-inotify]` —
  loads YAML (`tricks:` + optional `python-path:` keys; `yaml.safe_load`), `load_class("dotted.Trick")(**kwargs)`,
  schedules each trick (`source_directory` attr or the YAML file's dir). Alias: `tricks`.
- `watchmedo tricks-generate-yaml <dotted.Trick...> [--python-path .] [--append-to-file F] [-a/--append-only]` —
  prints/appends `tricks.yaml` stubs. Alias: `generate-tricks-yaml`.
- `watchmedo log [dirs...=. ] [-p/--pattern(s) *] [-i/--ignore-pattern(s) ""] [-D/--ignore-directories] [-R/--recursive] [--interval|--timeout 1.0] [--debug-force-*]` —
  patterns separated by `;`. (6.0.0 removed the old `--trace` flag.)
- `watchmedo shell-command [dirs...] -c/--command 'echo "${watch_src_path}"' [-p *] [-i ""] [-D] [-R] [--interval 1.0] [-w/--wait] [-W/--drop] [--debug-force-polling]` —
  never double-quote the command string in a way your shell pre-interpolates.
- `watchmedo auto-restart <command> [args... --] [-d/--directory DIR (repeatable, default .)] [-p *] [-i ""] [-D] [-R] [--interval 1.0] [--signal SIGINT] [--kill-after 10.0] [--debounce-interval 0.0] [--no-restart-on-command-exit]` —
  restarts a long-running subprocess on match; SIGTERM/SIGINT/SIGHUP → `WatchdogShutdownError` unwind.

### Remaining utils

- `BaseThread`: daemon thread with `stopped_event`, `should_keep_running()`, `on_thread_start/stop`,
  `start()` → `on_thread_start()` + `Thread.start()`. `WatchdogShutdownError` = graceful-shutdown signal;
  `UnsupportedLibcError` = inotify unavailable. `load_module(name)` / `load_class("pkg.mod.Cls")`
  (`ValueError` if no dot, `AttributeError` if class missing) — powers `tricks-from`.
- `EventDebouncer(debounce_interval_seconds, events_callback)`: accumulates `handle_event(event)` calls,
  fires `events_callback(list)` after a quiet interval; `stop()` wakes + joins.
- `DelayedQueue(delay)`: `put(element, delay=False)`, `get()->T|None` (honors per-item delay; `None` once
  `close()`d), `remove(predicate)`, `close()`.
- `ProcessWatcher(popen_obj, cb)`: `run()` polls to exit, then calls `cb` once (exceptions logged).
- `platform`: `is_windows/is_linux/is_darwin/is_bsd()`, `get_platform_name()`.
- `echo.echo(fn, write=...)`: tracing decorator logging `fn(arg=repr, ...)` before delegating.

## App usage & correctness

- **App code does not import watchdog.** `grep -rn watchdog src/ tests/ tools/` → zero hits.
  No direct misuse possible; nothing to fix. This is a **transitive dev-tool dependency**:
  `flet_cli-1.0.0.dist-info/METADATA` → `Requires-Dist: watchdog>=4.0.0`; installed `6.0.0` satisfies it.
  `uv.lock` pins `watchdog 6.0.0` (sdist + 10 wheels incl. `win_amd64`) as a dependency of `flet-cli`.
- **Chain (verified in `flet_cli/commands/run.py`)**: `flet run` builds a `Handler(FileSystemEventHandler)`
  (restarts the user app subprocess on code change, opens/closes desktop view or browser/QR) and runs:
  `my_observer = Observer(); my_observer.schedule(my_event_handler, script_dir, recursive=options.recursive);
  my_observer.start(); ... my_event_handler.terminate.wait(1) ...; my_observer.stop(); my_observer.join()`.
  On this Windows dev machine that is `WindowsApiObserver` over `ReadDirectoryChangesW` — hot-reload only.
- **Correctness for v1.0**: watchdog never ships in the mobile bundle (flet-cli stays on the dev host), so
  it cannot break the Android/iOS/Web builds. Keep it out of any runtime import path; do not add it to
  the app's own dependencies. No action required.

## Underused APIs to adopt (with platform caveats)

Genuinely useful patterns for this FFmpeg app — but **almost all belong on desktop, not on-device**:

1. **Output-dir reconciliation (desktop): watch for externally deleted/modified results.**
   `PatternMatchingEventHandler(patterns=["*.mp4","*.mkv","*.mp3","*.wav","*.jpg","*.png"], ignore_directories=True)`
   + `Observer.schedule(h, output_dir, recursive=False)`; on `on_deleted`/`on_moved` mark the history row
   missing/stale, on `on_modified` refresh size/duration. Debounce bursts with `EventDebouncer` or the
   `--debounce-interval` trick pattern — encoders emit many modify events per second.
2. **Track save-as renames with `on_moved`.** `FileMovedEvent.src_path → dest_path` (and dir moves +
   synthesized children) let history follow a file the user renames in Explorer/Files instead of
   orphaning the row. Polling/dirsnapshot diffs also report moves, but only same-filesystem (inode-based).
3. **Probe-cache / jobs-history external edits.** A lightweight `PollingObserver(timeout=5–10)` (or a
   `DirectorySnapshotDiff.ContextManager` re-scan on window focus) reconciles JSON sidecars edited by
   external tools without a permanent thread per file.
4. **USB/OTG mount arrival (desktop).** Watching a stable mount-point parent with `DirCreatedEvent` works
   on Windows/Linux **if** the OS actually mounts the stick as a filesystem path the process can open.
5. **Dev workflow, not app code:** `watchmedo shell-command -R -p "*.py" -c ...` or `auto-restart` can
   re-run the slow test subset / restart a local probe server on save. Prefer this over hand-rolled watchers.

**Platform caveats — where watchdog actually works:**

| Target | Verdict | Reason |
|---|---|---|
| Windows / Linux / macOS (dev host, desktop builds) | ✅ Full support | Native `ReadDirectoryChangesW` / inotify / FSEvents; polling fallback for CIFS. |
| Android (SAF `content://`, MediaStore, scoped storage) | ❌ Mostly unusable | Watchers need real filesystem paths + `stat`/inode; SAF/MediaStore URIs are a database, not paths — external edits there raise **no** inotify events. App-private dirs technically watchable but pointless in production. |
| iOS | ❌ Not useful | Sandbox + no persistent watcher story; backgrounding kills threads. |
| Web | ❌ Impossible | No filesystem event source in the browser. |
| Network/CIFS shares, some USB stacks | ⚠️ Polling only | Native events unreliable — force `PollingObserver` (slow, battery/disk-heavy). |

**Recommendation:** do **not** adopt watchdog as an in-app runtime dependency for v1.0 mobile. The correct
mobile pattern is **re-scan on resume**: `DirectorySnapshot` at pause, diff at foreground (`snapshot2 - snapshot1`),
plus explicit refresh after share intents/picker returns. Reserve live `Observer` usage for the desktop/dev
host (history-folder reconciliation, `watchmedo` automation), guarded to `sys.platform` desktop + `PollingObserver`
fallback, with handlers that only enqueue work (dispatch runs on watcher threads — never touch Flet UI directly;
marshal to the UI thread) and always re-`stat` before acting (Vim-style atomic saves surface as
created/moved pairs, not modifies; `SkipRepeatsQueue` coalescing means events are hints, not a journal).

## Gotchas

1. **No pywin32 needed, ever** — `winapi.py` is pure `ctypes`. If you see pywin32 advice, it predates the rewrite.
2. **This host runs `WindowsApiObserver`, not polling** — don't tune `timeout` expecting poll-interval behavior;
   on Windows the read blocks in `ReadDirectoryChangesW`.
3. **Watching the watched root's own deletion stops that emitter** (`DirDeletedEvent(watch.path)` + `stop()`).
   Reschedule after delete; same for inotify `delete_self` and polling `OSError` path.
4. **`case_sensitive` defaults to `False`** on the matching handlers (but `True` in raw `patterns` functions).
   On Linux that can over-match (`*.MP4` ≡ `*.mp4`); pass `case_sensitive=True` explicitly for media globs.
5. **Regex handlers use `re.match` (prefix)** — anchor with `.*` or `$` deliberately; glob handlers use
   `PurePath.match` (final-component matching, no dotfile special-casing); overlapping include+exclude
   patterns raise `ValueError`.
6. **Events are hints, not a journal**: `SkipRepeatsQueue` drops consecutive duplicates; editors/Vim atomic-save
   as rename pairs; `FileOpened/Closed` exist **only** on Linux inotify; directory `modified` events are noisy
   (consider `ignore_directories=True` for media watches).
7. **`FileSystemEventHandler.dispatch` uses `getattr(on_<event_type>)`** — custom/unknown `event_type`
   strings raise `AttributeError`; keep to the eight known types.
8. **Threading**: handlers run on dispatcher threads (daemon). `observer.stop()` clears all watches;
   `schedule()` after `stop()` without `start()` leaves dead emitters. `ShellCommandTrick(wait_for_process=True)`
   blocks dispatch — prefer `drop_during_process` for bursty encoders.
9. **API drift from old tutorials**: `watchdog.events` is a module, not a package (`events.api` doesn't exist);
   `Observer` is a factory, not a class to subclass (subclass `BaseObserver` + `EventEmitter` if customizing);
   `watchmedo log` lost `--trace`; `PatternMatchingEventHandler`/`Trick` kwargs are **keyword-only** post-5.0;
   `version.__version__` is the tuple `(6, 0, 0)` — use `VERSION_STRING` for display.
10. **Mobile packaging**: adding watchdog to app deps would bloat Android/iOS bundles with zero SAF/MediaStore
    payoff — keep it a dev-host tool (`flet run` hot-reload already covers its one legitimate job).
