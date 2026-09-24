# anyio 4.15.1 — Complete API Reference

> High-level concurrency and networking framework on top of asyncio or Trio.
> Trio-like structured concurrency (task groups, cancel scopes), happy-eyeballs
> TCP, async UDP/UNIX sockets, byte/object streams, locks/events/semaphores,
> worker threads/processes/subinterpreters, async file I/O, subprocesses,
> pytest plugin. Ground truth: installed source at
> `<repo>\.venv\Lib\site-packages\anyio`
> (46 `.py` files, every one read in full), metadata from
> `anyio-4.15.1.dist-info\METADATA` / `RECORD` / `entry_points.txt` /
> `licenses\LICENSE`.

---

## Files

Package dir `...\.venv\Lib\site-packages\anyio` (excludes `__pycache__`/`*.pyc`):

| File | Role |
|---|---|
| `__init__.py` | Public re-exports only (plus lazy-importer + one deprecated alias). Full export list = the reference below |
| `_lazyimport.py` | Lazy module importer (`install_lazy_importer`, `fix_package_names`, `set_deprecated_aliases`) |
| `_core/_eventloop.py` | `run`, `sleep`, `sleep_forever`, `sleep_until`, `current_time`, `get_all_backends`, `get_available_backends`, `get_cancelled_exc_class`, backend/sniffio plumbing |
| `_core/_tasks.py` | `CancelScope`, `fail_at`, `fail_after`, `move_on_at`, `move_on_after`, `current_effective_deadline`, `create_task_group`, `TaskHandle`, `TASK_STATUS_IGNORED` |
| `_core/_synchronization.py` | `Event` (+`EventAdapter`), `Lock` (+adapter), `Condition`, `Semaphore` (+adapter), `CapacityLimiter` (+adapter), `ResourceGuard`, `*Statistics` dataclasses |
| `_core/_streams.py` | `create_memory_object_stream` factory (tuple subclass) |
| `_core/_sockets.py` | `connect_tcp` (happy eyeballs), `connect_unix`, `create_tcp_listener`, `create_unix_listener`, `create_udp_socket`, `create_connected_udp_socket`, `create_unix_datagram_socket`, `create_connected_unix_datagram_socket`, `getaddrinfo`, `getnameinfo`, `wait_readable`/`wait_writable`, `notify_closing`, `TCPConnectable`, `UNIXConnectable`, `as_connectable` (+ deprecated `wait_socket_readable/writable`) |
| `_core/_subprocesses.py` | `run_process`, `open_process` (mirrors `subprocess.run`/`Popen` kwargs) |
| `_core/_fileio.py` | `AsyncFile`, `open_file`, `wrap_file`, `Path` (full async `pathlib.Path` mirror) |
| `_core/_futures.py` | `Future` (awaitable, `Status`, `return_value`/`exception` props) |
| `_core/_resources.py` | `aclose_forcefully` |
| `_core/_signals.py` | `open_signal_receiver` (POSIX only in practice) |
| `_core/_testing.py` | `TaskInfo`, `get_current_task`, `get_running_tasks`, `wait_all_tasks_blocked` |
| `_core/_tempfile.py` | Async `TemporaryFile`, `NamedTemporaryFile`, `SpooledTemporaryFile`, `TemporaryDirectory`, `mkstemp`, `mkdtemp`, `gettempdir`, `gettempdirb` |
| `_core/_typedattr.py` | `typed_attribute`, `TypedAttributeSet`, `TypedAttributeProvider` (+ `extra()` lookup) |
| `_core/_concurrency_utils.py` | `gather`, `as_completed`, `amap` |
| `_core/_contextmanagers.py` | `ContextManagerMixin`, `AsyncContextManagerMixin` (generator-based CM impl helpers) |
| `_core/_exceptions.py` | Full exception hierarchy (see below) |
| `_core/_asyncio_selector_thread.py` | Selector thread backing `wait_readable/writable` on proactor loops |
| `_core/__init__.py`, `_backends/__init__.py`, `streams/__init__.py` | Empty namespace packages |
| `_backends/_asyncio.py` | asyncio backend (~3100 lines): `CancelScope`, `TaskGroup`, `Event/Lock/Semaphore/CapacityLimiter`, sockets, `TestRunner`, `AsyncIOBackend` |
| `_backends/_trio.py` | Trio backend: same surface over native trio primitives |
| `abc/_tasks.py` | `TaskGroup` ABC (`create_task`, `start_soon`, `start`, `cancel`), `TaskStatus` protocol |
| `abc/_streams.py` | `ByteReceiveStream`, `ByteSendStream`, `ByteStream`, `ObjectReceive/SendStream`, `ObjectStream`, `UnreliableObject*`, `Listener`, `*Connectable`, `AnyByte*` aliases |
| `abc/_sockets.py` | `SocketStream`, `UNIXSocketStream` (+fd passing), `SocketListener` (`accept`, `serve`), `UDPSocket`, `ConnectedUDPSocket`, `UNIXDatagramSocket`, `SocketAttribute` |
| `abc/_resources.py` | `AsyncResource` (`aclose`) |
| `abc/_eventloop.py` | `AsyncBackend` interface (what each backend implements) |
| `abc/_subprocesses.py` | `Process` (`wait`, `returncode`, `stdin/stdout/stderr`, `kill/terminate`, `aclose`) |
| `abc/_testing.py` | `TestRunner` ABC |
| `abc/__init__.py` | Re-exports all ABCs |
| `from_thread.py` | `run`, `run_sync`, `check_cancelled`, `BlockingPortal`, `BlockingPortalProvider`, `start_blocking_portal` |
| `to_thread.py` | `run_sync`, `current_default_thread_limiter` |
| `to_process.py` | `run_sync`, `current_default_process_limiter`, `process_worker` |
| `to_interpreter.py` | `run_sync`, `current_default_interpreter_limiter` (subinterpreters, 3.13+) |
| `lowlevel.py` | `checkpoint`, `checkpoint_if_cancelled`, `cancel_shielded_checkpoint`, `RunVar`/`RunvarToken`, `EventLoopToken`, `current_token` |
| `streams/memory.py` | `MemoryObjectSendStream`, `MemoryObjectReceiveStream`, `MemoryObjectStreamStatistics` |
| `streams/buffered.py` | `BufferedByteReceiveStream` (`receive_exactly`, `receive_until`, `feed_data`, `buffer`), `BufferedByteStream`, `BufferedConnectable` |
| `streams/file.py` | `FileReadStream` (`from_path`, `seek`, `tell`), `FileWriteStream`, `FileStreamAttribute` |
| `streams/stapled.py` | `StapledByteStream`, `StapledObjectStream`, `MultiListener` (returned by `create_tcp_listener`) |
| `streams/text.py` | `TextReceiveStream`, `TextSendStream`, `TextStream`, `TextConnectable` |
| `streams/tls.py` | `TLSStream` (`wrap`, `unwrap`), `TLSListener`, `TLSConnectable`, `TLSAttribute` |
| `functools.py` | Async `cache`, `lru_cache`, `reduce` (+ `AsyncCacheInfo`) |
| `itertools.py` | Async `accumulate`, `batched`, `combinations`, `compress`, `count`, `cycle`, `dropwhile`, `filterfalse`, `groupby`, `islice`, `pairwise`, `permutations`, `product`, `repeat`, `starmap`, `takewhile`, `zip_longest`, `tee`, `Chain` |
| `pytest_plugin.py` | `anyio` pytest plugin (`anyio_backend` fixture, `@pytest.mark.anyio`, `--anyio-mode`) |
| `py.typed` | PEP 561 marker — fully type-annotated |

Pytest entry point (`entry_points.txt`): `[pytest11] anyio = anyio.pytest_plugin`.

---

## Metadata

- **Name / version:** `anyio 4.15.1` — "High-level concurrency and networking
  framework on top of asyncio or Trio". Status: Production/Stable.
- **License:** MIT (`License-Expression: MIT`, `licenses\LICENSE`).
- **Requires-Python:** `>=3.10` (classifiers list 3.10–3.15 + free-threading beta).
  This app runs 3.14, so: `exceptiongroup` backport **not** needed (3.11+
  builtin), `typing_extensions` **is** required (`python_version < "3.15"`).
- **Hard pins (all satisfied in `.venv`):**
  - `exceptiongroup>=1.0.2; python_version < "3.11"` — not installed, not needed
  - `idna>=2.8` — installed 3.20 (used by `getaddrinfo` IDNA-2008 path)
  - `typing_extensions>=4.16.0; python_version < "3.15"` — installed 4.16.0
- **Extra:** `trio` → `trio>=0.32.0`. **NOT installed** — only the asyncio
  backend is usable here (`get_available_backends()` returns `("asyncio",)`).
- **`sniffio` is NOT installed** either. `_core/_eventloop.py` handles that:
  `current_async_library()` falls back to `asyncio.get_running_loop()` and
  assumes `"asyncio"` when a loop is running, `None` otherwise. Consequence:
  anyio works fine on asyncio here, but `sniffio.current_async_library()` calls
  by *other* libs raise `AsyncLibraryNotFoundError` outside a running loop —
  same as stock behaviour, just no trio detection possible.
- **Why it's in the tree:** transitive via `httpx 0.28.1`
  (`Requires-Dist: anyio`). `httpx.AsyncClient` uses anyio for backend
  sniffing/task-group internals. No other installed dist requires it.

---

## Module-by-module API

### Exceptions (`anyio.*`, from `_core/_exceptions.py`)

| Class | Base | When raised |
|---|---|---|
| `BrokenResourceError` | `Exception` | Resource unusable for external reasons (peer disconnect, rx-end closed) |
| `BrokenWorkerProcess` | `Exception` | `to_process.run_sync` worker died/misbehaved |
| `BrokenWorkerInterpreter` | `Exception` | `to_interpreter.run_sync` blew up (carries `.excinfo`) |
| `BusyResourceError(action)` | `Exception` | Two tasks using one resource concurrently; msg: `"Another task is already {action} this resource"` |
| `ClosedResourceError` | `Exception` | Using a resource after close |
| `ConnectionFailed` | `OSError` | `*Connectable.connect()` failed (kept as `OSError` for compat) |
| `DelimiterNotFound(max_bytes)` | `Exception` | `receive_until` hit cap without delimiter |
| `EndOfStream` | `Exception` | Read from a stream closed at the other end (also ends `async for`) |
| `IncompleteRead` | `Exception` | `receive_exactly`/`receive_until` cut short by close |
| `TypedAttributeLookupError` | `LookupError` | `extra()` miss with no default |
| `WouldBlock` | `Exception` | Any `*_nowait` call that would block |
| `NoEventLoopError` | `RuntimeError` | anyio call with no running loop (also `from_thread` without token / outside worker) |
| `RunFinishedError` | `RuntimeError` | `from_thread` call against a finished loop token |
| `TaskFailed` / `TaskCancelled(TaskFailed)` / `TaskNotFinished` | `Exception` | Awaiting/inspecting a `TaskHandle` in a terminal/pending state |
| `FutureFailed` / `FutureCancelled(FutureFailed)` / `FutureNotFinished` / `FutureAlreadyFinished` | `Exception` | Same quartet for `Future` |
| `get_cancelled_exc_class()` | — | Returns the backend's cancellation class (`asyncio.CancelledError` here). **Always** use this instead of hard-coding `asyncio.CancelledError` in backend-agnostic code |

Helper: `iterate_exceptions(exc)` yields leaves of a `BaseExceptionGroup`.

### Entry point & clock (`_core/_eventloop.py`)

```python
def run(func, *args, backend="asyncio", backend_options=None) -> T_Retval
async def sleep(delay: float) -> None
async def sleep_forever() -> None          # sleep(math.inf)
async def sleep_until(deadline: float) -> None   # monotonic clock of the loop
def current_time() -> float                # loop clock seconds; NoEventLoopError outside loop
def get_all_backends() -> tuple[str, ...]          # ("asyncio", "trio")
def get_available_backends() -> tuple[str, ...]    # import-probed; here ("asyncio",)
```

`run()` raises `RuntimeError` if a loop already runs in this thread,
`LookupError` for unknown/uninstalled backends.

### Task groups & cancel scopes (`_core/_tasks.py`, `abc/_tasks.py`)

```python
def create_task_group() -> TaskGroup
async with create_task_group() as tg:
    handle: TaskHandle = tg.start_soon(func, *args, name=None)  # 4.14+: returns handle
    value = await tg.start(func, *args, name=None, return_handle=False)  # waits for task_status.started()
    tg.cancel(reason=None)                       # == tg.cancel_scope.cancel()
```

- Exiting the `async with` waits for **all** children; the first child
  exception cancels siblings and propagates (as `BaseExceptionGroup` on 3.11+).
- `TaskGroup.start` target must accept a `task_status: TaskStatus` kwarg and
  call `task_status.started(value)`; exiting without it → `RuntimeError`.
- `TASK_STATUS_IGNORED`: pass as `task_status` when calling such a function
  directly without a task group.

```python
CancelScope(*, deadline=math.inf, shield=False)   # sync CM; .cancel(reason?), .deadline rw, .cancel_called, .cancelled_caught, .shield rw
with fail_after(delay, shield=False, reason=None) as scope: ...    # raises TimeoutError on expiry
with fail_at(deadline, shield=False, reason=None) as scope: ...    # new in 4.15.0; absolute clock value
with move_on_after(delay, shield=False): ...       # silent expiry; NOTE timer starts at CALL, not __enter__ (fix slated for v5.0)
with move_on_at(deadline, shield=False): ...       # new in 4.15.0
def current_effective_deadline() -> float          # nearest scope deadline; inf = none, -inf = already cancelled
```

`fail_after(None)` / `move_on_after(None)` disable the timeout. Check
`scope.cancelled_caught` after `move_on_*` to detect expiry.

`TaskHandle` (new 4.14.0): `.status` (`PENDING/FINISHED/CANCELLING/CANCELLED/FAILED`),
`.return_value` (raises `TaskNotFinished`/`TaskCancelled`/`TaskFailed`),
`.exception`, `.start_value` (only for `tg.start(..., return_handle=True)`),
`await handle` → return value, `await handle.wait()`, `.cancel()`, `.coro`, `.name`.

### Concurrency helpers (`_core/_concurrency_utils.py`)

```python
async def gather(*coros) -> tuple[...]            # task-group fan-out, order-preserving (typed overloads to 6)
async def amap(func, args) -> list[R]             # concurrent map, order-preserving
@asynccontextmanager
async def as_completed(*awaitables) -> MemoryObjectReceiveStream[TaskHandle]  # yield handles in finish order; needs ≥1 arg
```

### Synchronization (`_core/_synchronization.py`)

```python
Event() -> set(), is_set(), await wait(), statistics() -> EventStatistics(tasks_waiting)
Lock(*, fast_acquire=False) -> await acquire(), acquire_nowait() [WouldBlock], release(), locked(), async CM, statistics()
Condition(lock=None) -> await acquire()/acquire_nowait()/wait()/wait_for(predicate), release(), locked(), notify(n=1), notify_all(), async CM
Semaphore(initial_value, *, max_value=None, fast_acquire=False) -> await acquire(), acquire_nowait(), release(), .value, .max_value, async CM
CapacityLimiter(total_tokens) -> await acquire()/acquire_on_behalf_of(borrower), *_nowait() [WouldBlock], release()/_on_behalf_of(), .total_tokens rw (0 allowed since 4.12), .borrowed_tokens, .available_tokens, statistics()
ResourceGuard(action="using")  # sync CM; re-entry raises BusyResourceError
```

All of `Event/Lock/Semaphore/CapacityLimiter` are loop-bound factories that
degrade to `*Adapter`s when constructed with no running loop (real backend
object is created lazily on first use) — so module-level construction is safe.
`Condition.wait()` re-acquires under a shielded scope; `wait_for()` added 4.11.0.

### Memory object streams (`_core/_streams.py`, `streams/memory.py`)

```python
send, receive = create_memory_object_stream[T](max_buffer_size=0)  # 0 = rendezvous; math.inf = unbounded
await send.send(item) / send.send_nowait(item)      # BrokenResourceError if rx closed; WouldBlock if full
await receive.receive() / receive.receive_nowait()  # EndOfStream if tx closed+empty; WouldBlock if empty
.send.clone() / .close() / await .aclose() / .statistics() -> MemoryObjectStreamStatistics(current_buffer_used, max_buffer_size, open_send_streams, open_receive_streams, tasks_waiting_send, tasks_waiting_receive)
```

Both ends support sync `close()` (for callbacks) and `with` blocks; unclosed
streams warn `ResourceWarning`. `async for item in receive:` stops on
`EndOfStream`. Statistics make queue-depth/lag UIs trivial.

### Byte/object stream ABCs (`abc/_streams.py`)

- `ByteReceiveStream.receive(max_bytes=65536) -> bytes` (never empty on
  success); `ByteSendStream.send(bytes)`; `ByteStream.send_eof()` (idempotent).
- `ObjectReceiveStream/ObjectSendStream/ObjectStream.send_eof()`;
  unreliable (UDP) variants skip ordering guarantees.
- `Listener.serve(handler, task_group=None)`.
- Type aliases: `AnyByteStream`, `AnyByteReceiveStream`, `AnyByteSendStream`,
  `AnyUnreliableByte*`, `AnyByteStreamConnectable`.

### Concrete streams (`streams/`)

- **buffered**: `BufferedByteReceiveStream(stream)` — `.receive_exactly(nbytes)`
  [IncompleteRead], `.receive_until(delimiter, max_bytes)`
  [DelimiterNotFound/IncompleteRead], `.feed_data(...)`, `.buffer`;
  `BufferedByteStream` (+send); `BufferedConnectable`.
- **file**: `await FileReadStream.from_path(path)`; `.receive()`
  [EndOfStream/BrokenResourceError], `.seek()`, `.tell()`; `FileWriteStream.send()`.
- **stapled**: `StapledByteStream(send_stream, receive_stream)`,
  `StapledObjectStream(...)` (+`send_nowait`), `MultiListener([...])` with
  `.serve(handler, task_group)` fan-out.
- **text**: `TextReceiveStream/SendStream/Stream(transport_stream, encoding="utf-8", errors="strict")`,
  `TextConnectable(connectable)`.
- **tls**: `await TLSStream.wrap(transport, *, server_side=False, hostname=None, ssl_context=None, standard_compatible=True)`;
  `.unwrap() -> (raw_stream, leftover)`; `TLSListener`; `TLSConnectable`.
  `standard_compatible=False` skips the closing handshake (needed for HTTP-style
  servers or `ssl.SSLEOFError` appears).

### Sockets (`_core/_sockets.py`, `abc/_sockets.py`)

```python
await connect_tcp(remote_host, remote_port, *, local_host=None, local_port=None, tls=False, ssl_context=None, tls_standard_compatible=True, tls_hostname=None, happy_eyeballs_delay=0.25) -> SocketStream | TLSStream
await connect_unix(path) -> UNIXSocketStream                       # not on Windows
await create_tcp_listener(*, local_host=None, local_port=0, family=AF_UNSPEC, backlog=65536, reuse_port=False) -> MultiListener[SocketStream]
await create_unix_listener(path, *, mode=None, backlog=65536)      # not on Windows; unlinks stale socket
await create_udp_socket(family, *, local_host=None, local_port=0, reuse_port=False) -> UDPSocket
await create_connected_udp_socket(remote_host, remote_port, *, family=..., local_host=None, local_port=0, reuse_port=False)
# + UNIX datagram variants (not on Windows)
await getaddrinfo(host, port, *, family=0, type=0, proto=0, flags=0)  # IDNA-2008; IPv6 4-tuples collapsed to 2-tuples
getnameinfo(sockaddr, flags=0) -> Awaitable[(host, service)]
wait_readable(obj) / wait_writable(obj) -> Awaitable[None]   # fd or .fileno(); ClosedResourceError/BusyResourceError; selector-thread fallback on proactor
notify_closing(obj) -> None                                  # wake waiters before YOU close the fd
TCPConnectable(host, port) / UNIXConnectable(path)           # .connect(); port validated 1..65535
as_connectable(remote, /, *, tls=False, ssl_context=None, tls_hostname=None, tls_standard_compatible=True)
SocketListener.accept() -> SocketStream; .serve(handler, task_group=None)
UDPSocket.sendto(data, host, port) / .receive() -> (data, (host, port)); IDNA via idna>=2.8
UNIXSocketStream.send_fds(message, fds) / .receive_fds(msglen, maxfds)
```

`connect_tcp` implements stateless Happy Eyeballs (RFC 6555): IPv6 first,
next attempt after 250 ms; all-fail → `OSError("All connection attempts failed")`.
`create_tcp_listener` dual-stacks `::` w/ `v6only=False` when host is omitted.
Deprecated: `wait_socket_readable/writable(sock)` → use `wait_readable/writable`.

### Threads / processes / interpreters

```python
await to_thread.run_sync(func, *args, abandon_on_cancel=False, limiter=None) -> T   # (cancellable= deprecated alias)
to_thread.current_default_thread_limiter() -> CapacityLimiter   # default cap: 40 threads
from_thread.run(func, *args, token=None)       # coro fn from worker thread -> result; needs token outside anyio workers
from_thread.run_sync(func, *args, token=None)  # plain fn on the loop thread
from_thread.check_cancelled()                  # raise backend cancel exc if host scope cancelled (worker threads only)
class BlockingPortal:  # async CM
    .call(func, *args)                         # run fn/corofn on loop, block for result (never from loop thread)
    .start_task_soon(func, *args, name=None) -> concurrent.futures.Future
    .start_task(func, *args, name=None) -> (Future, started_value)
    .wrap_async_context_manager(cm) -> sync CM
    .stop(cancel_remaining=False) / .sleep_until_stopped()
with start_blocking_portal(backend="asyncio", backend_options=None, *, name=None) as portal: ...
BlockingPortalProvider(backend="asyncio", backend_options=None)  # ref-counted shared portal
await to_process.run_sync(func, *args, cancellable=False, limiter=None)   # SIGKILL/terminate on cancel
await to_interpreter.run_sync(func, *args, limiter=None)                  # subinterpreters; 3.13 private-API caveat
```

`abandon_on_cancel=True` lets the thread run on while the waiter is cancelled
(result discarded) — the right default for UI teardown paths.

### Files, paths, tempfiles, subprocesses, misc

```python
await open_file(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None, *, limiter=None) -> AsyncFile
wrap_file(fp, *, limiter=None) -> AsyncFile     # async read/read1/readline/readlines/readinto/readinto1/write/writelines/truncate/seek/tell/flush; async iteration; async CM closes
Path(*args, limiter=None)                       # async pathlib.Path: stat/exists/mkdir/open/read_bytes/read_text/write_*/rename/replace/unlink/glob/iterdir/rglob/walk(3.12+)/copy/move(3.14+) all awaited; pure ops sync
await run_process(cmd, *, input=None, stdin=None, stdout=PIPE, stderr=PIPE, check=True, cwd=None, env=None, ...) -> CompletedProcess[bytes]
await open_process(cmd, *, stdin=PIPE, stdout=PIPE, stderr=PIPE, ...) -> Process  # async CM; .wait()/.kill()/.terminate()/.send_signal()
async TemporaryFile/NamedTemporaryFile/SpooledTemporaryFile/TemporaryDirectory(...)  # async CMs mirroring tempfile
await mkstemp(...)/mkdtemp(...)/gettempdir()/gettempdirb()
async def aclose_forcefully(resource)           # aclose() inside an already-cancelled scope
def open_signal_receiver(*signals) -> CM[AsyncIterator[Signals]]  # POSIX; replaces asyncio handlers
async def wait_all_tasks_blocked() -> None; get_current_task() -> TaskInfo; get_running_tasks() -> list[TaskInfo]
async def checkpoint() / checkpoint_if_cancelled() / cancel_shielded_checkpoint()  # lowlevel
RunVar(name, default) — loop-scoped ContextVar-like (.get/.set->RunvarToken/.reset; usable as CM via token)
EventLoopToken/current_token()  # opaque loop handle for from_thread token= (new 4.11.0)
AsyncLRU/async functools: cache/lru_cache/reduce; async itertools: full list in Files table
TypedAttributeProvider.extra(attr, default) / TypedAttributeSet / typed_attribute()
```

### Testing / pytest plugin

`pytest_plugin.py` (entry point `anyio`): `@pytest.mark.anyio` marks async
tests/fixtures; `anyio_backend` fixture (string or `(name, options)` tuple;
`params` to run both backends); `--anyio-mode=strict|auto`; async fixtures
(incl. async generators) supported; `free_tcp_port` / `free_udp_port`
(`_factory`) fixtures. **Not installed here** (no `pytest-asyncio`-style
auto mode available) — plain `pytest 9.1.1` only, and the repo's
`tests/conftest.py` builds its own synthetic-media + FakePage harness.

---

## App usage & correctness

**Status: transitive-only.** No `import anyio` (or `sniffio`) exists anywhere
in `src/` or `tests/`. The single live path is:

- `src/services/update_service.py:22` —
  `async with httpx.AsyncClient(timeout=4.0, follow_redirects=True)` then
  `await client.get(UPDATE_CONFIG_URL)`. httpx 0.28.1 drives this over anyio
  internally (backend sniffing + task groups inside httpcore's async pool).
  Usage is correct: bounded timeout, closed via `async with`, broad
  `except Exception` keeps the silent check silent, `None` on any failure.

**No misuse of anyio semantics exists** (nothing to mix: no task groups, no
`asyncio.gather`, no `asyncio.wait_for` in the codebase). The neighbouring
patterns that were audited:

- `asyncio.to_thread` for blocking PyAV work (the anyio-equivalent would be
  `anyio.to_thread.run_sync`) — 10 correct call sites, all awaited, none
  capturing loop state unsafely:
  `src/main.py:392` (`engine.probe`), `src/screens/capture_screen.py:346`
  (`EngineService.probe`), `src/screens/join_screen.py:52`
  (`available_filters`), `src/screens/join_screen.py:123` (`_probe_sync`),
  `src/screens/filters_screen.py:72` (`available_filters`),
  `src/screens/engine_info_screen.py:45` (`_load_sync`),
  `src/screens/streams_screen.py:71` (`_check_protocols_sync`),
  `src/screens/settings_screen.py:55`, `src/screens/settings_screen.py:118`
  (`probe`), `src/screens/cut_screen.py:116-117` (`thumbnail_strip` +
  `keyframe_times`, currently sequential — see below).
- `src/screens/capture_screen.py:327` catches `asyncio.CancelledError` around
  the record ticker and swallows it. Harmless today (asyncio-only runtime via
  Flet), but any anyio-scope migration must re-raise or use
  `get_cancelled_exc_class()` — swallowing backend cancellation breaks
  structured-teardown propagation.
- `src/services/job_queue.py:1-60` rolls its own serial queue on
  `threading.Thread` + `threading.Event` (`_wake.wait(timeout=0.5)` polling at
  `:162,167`). Correct but anyio-native primitives would remove the poll loop.
- Timeouts on network/engine ops are ad-hoc, not structured:
  httpx `timeout=4.0` (`update_service.py:22`), `av.open(url, timeout=(1, 2))`
  (`core/engine_probe.py:294`), `av.open(input_url, "r", timeout=(10.0, 30.0))`
  (`services/engine_service.py:2574`). No `asyncio.wait_for`/`TimeoutError`
  handling around UI-triggered probes — a wedged `to_thread` probe blocks the
  awaiting screen task indefinitely.
- No structured cancellation on navigate-away: screens fire coroutines via
  `page.run_task(...)` (`src/main.py:712`) with no scope handle, so leaving a
  screen mid-probe leaves the work running.

## Underused APIs to adopt

1. **`move_on_after` around every engine probe/thumbnail op** — wrap the
   `asyncio.to_thread` calls (`main.py:392`, `cut_screen.py:116-117`,
   `join_screen.py:123`, `settings_screen.py:55,118`) so a wedged native call
   degrades to "unavailable" UI instead of a hung screen:
   `with anyio.move_on_after(15) as scope: info = await ...; if scope.cancelled_caught: show_snack(...)`.
   Prefer `fail_after` where the caller already has `try/except TimeoutError`.
2. **`CapacityLimiter(1 or 2)` for PyAV work** — phones OOM when
   `thumbnail_strip` + `keyframe_times` + a probe overlap; a module-level
   limiter (`limiter = anyio.CapacityLimiter(2)`, constructible with no running
   loop thanks to the Adapter) passed as `limiter=` bounds concurrency without
   the bespoke `job_queue.py` thread for new code paths.
3. **`to_thread.run_sync(..., abandon_on_cancel=True)`** instead of bare
   `asyncio.to_thread` on teardown-able screens — navigate-away cancels the
   waiter while the native call finishes harmlessly in the background.
4. **`create_task_group` + `gather` in `cut_screen.py:116-117`** — the two
   `await asyncio.to_thread(...)` calls are independent; one task group halves
   strip-load latency and gives a single cancellation point.
5. **Memory object streams for progress events** — replace callback/threading
   plumbing between engine callbacks and Flet UI with
   `create_memory_object_stream[ProgressEvent](max_buffer_size=64)`; the UI
   task `async for`s updates, `.statistics()` feeds a lag/debug indicator, and
   closing the receive end surfaces `BrokenResourceError` to producers instead
   of dead callbacks.
6. **`Event` instead of `threading.Event` polling** in `job_queue.py:162,167` —
   an `anyio.Event` set by `set_paused(False)`/enqueue removes the 500 ms
   wake latency and spurious wakeups (adopt incrementally; queue core can stay
   threaded via `BlockingPortal`).
7. **`open_file`/`Path` for media I/O helpers** — dossier/history JSON
   reads-writes currently ride the loop thread; the async path API keeps large
   writes off the UI loop with one-line changes.

## Gotchas

- **No trio, no sniffio in this venv.** `get_available_backends()` →
  `("asyncio",)`; backend must stay `"asyncio"`. `sniffio` absence is handled
  internally, but do not add trio-only idioms (e.g. `trio` imports in tests).
- **`move_on_after` timer starts at call time, not `__enter__`** (documented,
  fix planned for v5.0). Construct it immediately before the `with` block.
- **Cancel-scope shielding for `finally:` UI updates**: code that must run
  during teardown (dialog close, `page.update()`) needs
  `with CancelScope(shield=True)` or a cancelled probe can abort the cleanup.
- **Never swallow the backend's cancellation exception** (`capture_screen.py:327`
  pattern): always `raise` after local cleanup, or `get_cancelled_exc_class()`
  checks, or enclosing scopes misreport `cancelled_caught`.
- **`create_memory_object_stream` default `max_buffer_size=0` is a rendezvous**
  — `send()` blocks until a receiver waits. Size buffers explicitly (`64`)
  for progress fan-out or producers stall.
- **Unclosed memory streams warn `ResourceWarning`** — always `aclose()`/use
  `async with` on both ends, especially in tests.
- **`wait_readable/writable` + `notify_closing` ordering**: mark-closed →
  `notify_closing(fd)` → real `close()`, with no checkpoints between, or
  waiters raise `ClosedResourceError` spuriously / new waiters sneak in.
- **`to_process.run_sync` pickles the callable** — engine closures over Flet
  `page` objects will fail to pickle; keep worker payloads to plain data.
- **IDNA**: `getaddrinfo` transliterates per IDNA-2008 via `idna>=2.8` — stream
  URLs with unicode hosts resolve without extra code, but raw `socket`
  fallbacks in `engine_probe.py` would not.
- **Windows**: `connect_unix`, UNIX listeners/datagram sockets, and
  `open_signal_receiver` are unavailable/degenerate — the app targets Android
  + desktop, so guard any future server-socket debug tooling accordingly.
