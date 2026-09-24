# httpcore 1.0.9 — Complete API Reference

> Scope: `httpcore` 1.0.9 as vendored in the app venv
> (`.venv/Lib/site-packages/httpcore`), the transport core under `httpx` 0.28.1.
> The app never imports `httpcore` directly; it reaches it as
> `update_service.py` → `httpx.AsyncClient` → `httpx.AsyncHTTPTransport` →
> `httpcore.AsyncConnectionPool`. There is **no `sse.py`** and **no `backoff.py`**
> in this version — backoff lives inline in `_sync/connection.py` and
> `_async/connection.py`. There is no top-level `interfaces.py` either; the
> interfaces live at `_sync/interfaces.py` and `_async/interfaces.py`.

## Files

32 `.py` files (excluding `__pycache__`), all read for this report:

```
httpcore/__init__.py            # public re-exports, __version__ = "1.0.9"
httpcore/_api.py                # top-level request() / stream() convenience helpers
httpcore/_exceptions.py         # full exception taxonomy + map_exceptions()
httpcore/_models.py             # URL, Origin, Request, Response, Proxy, ByteStream, enforce_*
httpcore/_ssl.py                # default_ssl_context()
httpcore/_utils.py              # is_socket_readable()
httpcore/_synchronization.py    # sync + async locks/events/semaphores/shields
httpcore/_trace.py              # Trace context manager (trace extension + DEBUG logging)
httpcore/_sync/__init__.py
httpcore/_sync/interfaces.py    # RequestInterface, ConnectionInterface (sync)
httpcore/_sync/connection_pool.py  # ConnectionPool + PoolByteStream
httpcore/_sync/connection.py    # HTTPConnection (origin dial + retry + ALPN dispatch)
httpcore/_sync/http11.py        # HTTP11Connection (h11 state machine)
httpcore/_sync/http2.py         # HTTP2Connection (h2, optional extra)
httpcore/_sync/http_proxy.py    # HTTPProxy, ForwardHTTPConnection, TunnelHTTPConnection
httpcore/_sync/socks_proxy.py   # SOCKSProxy, Socks5Connection (needs socksio extra)
httpcore/_async/__init__.py
httpcore/_async/interfaces.py   # AsyncRequestInterface, AsyncConnectionInterface
httpcore/_async/connection_pool.py # AsyncConnectionPool + PoolByteStream
httpcore/_async/connection.py   # AsyncHTTPConnection (mirror of sync)
httpcore/_async/http11.py       # AsyncHTTP11Connection
httpcore/_async/http2.py        # AsyncHTTP2Connection
httpcore/_async/http_proxy.py   # AsyncHTTPProxy, AsyncForward/TunnelHTTPConnection
httpcore/_async/socks_proxy.py  # AsyncSOCKSProxy, AsyncSocks5Connection
httpcore/_backends/__init__.py  # empty
httpcore/_backends/base.py      # NetworkStream/Backend, AsyncNetworkStream/Backend, SOCKET_OPTION
httpcore/_backends/sync.py      # SyncBackend (stdlib sockets)
httpcore/_backends/auto.py      # AutoBackend (sniffio → anyio/trio dispatch)
httpcore/_backends/anyio.py     # AnyIOBackend (asyncio path — what the app uses)
httpcore/_backends/trio.py      # TrioBackend
httpcore/_backends/mock.py      # MockBackend/MockStream, AsyncMockBackend/AsyncMockStream
```

Dist-info (`httpcore-1.0.9.dist-info/`): `METADATA`, `WHEEL`, `INSTALLER`,
`REQUESTED`, `RECORD` (38 entries), `licenses/LICENSE.md`.

## Metadata

| Field | Value |
|---|---|
| Name / Version | `httpcore` / `1.0.9` (also `__version__` in `__init__.py:134`) |
| License | `BSD-3-Clause` (`License-Expression`, license file `licenses/LICENSE.md`) |
| Summary | "A minimal low-level HTTP client." |
| Requires-Python | `>=3.8` |
| Hard deps (`Requires-Dist`, unconditional) | `certifi`, `h11>=0.16` (installed: `certifi-2026.7.22`, `h11-0.16.0`). **No `typing_extensions` pin.** No `anyio` pin in base install. |
| Extra `asyncio` | `anyio<5.0,>=4.0` (installed `anyio-4.15.1` — satisfies) |
| Extra `http2` | `h2<5,>=3` — **not installed** in this venv, so `http2=True` paths are unavailable |
| Extra `socks` | `socksio==1.*` — **not installed**, so SOCKS proxy classes unusable |
| Extra `trio` | `trio<1.0,>=0.22.0` — **not installed**; `TrioBackend` import raises `RuntimeError` |
| Changelog highlights | 1.0.9: h11 bump for GHSA-vqfr-h8mv-ghfj (#1008). 1.0.8: fix `AttributeError` on Python 3.14 (#1005 — the `SOCKET_OPTION` `__module__` guard still visible in `__init__.py:137-141`). 1.0.7: `proxy=…` on `ConnectionPool()` (#974). |

## Module-by-module API

### `_api.py` — top-level helpers

```python
httpcore.request(method, url, *, headers=None, content=None, extensions=None) -> Response
httpcore.stream(method, url, *, headers=None, content=None, extensions=None)  # contextmanager yielding Response
```

Both build a throwaway `ConnectionPool()` (default settings, no keepalive reuse
across calls) and delegate to `pool.request()` / `pool.stream()`. `stream()`
does **not** read the body; caller must `response.read()` / iterate, else
`response.content` raises `RuntimeError`.

### `ConnectionPool` / `AsyncConnectionPool` (`_sync/connection_pool.py:48`, `_async/connection_pool.py:43`)

Identical signatures (sync shown):

```python
ConnectionPool(
    ssl_context: ssl.SSLContext | None = None,   # default: httpcore.default_ssl_context()
    proxy: Proxy | None = None,                  # added 1.0.7 — pool-level proxy routing
    max_connections: int | None = 10,            # None → sys.maxsize (unbounded)
    max_keepalive_connections: int | None = None,# None → sys.maxsize, then min() with max_connections
    keepalive_expiry: float | None = None,       # None → idle conns NEVER expire
    http1: bool = True,
    http2: bool = False,                         # needs h2 extra (absent here)
    retries: int = 0,                            # connect-attempt retries, see below
    local_address: str | None = None,            # "0.0.0.0" → IPv4, "::" → IPv6
    uds: str | None = None,                      # Unix-domain-socket path (raises on Windows)
    network_backend: NetworkBackend | None = None,  # default SyncBackend / AutoBackend
    socket_options: Iterable[SOCKET_OPTION] | None = None,
)
```

Key methods:

- `handle_request(request: Request) -> Response` (sync) /
  `handle_async_request(request: Request) -> Response` (async) — core entry point.
  Validates scheme (`http/https/ws/wss`, else `UnsupportedProtocol`), reads
  `request.extensions["timeout"]["pool"]` as the pool-acquire budget, queues a
  `PoolRequest`, loops `assign → wait_for_connection → connection.handle_request`,
  retrying the loop only on `ConnectionNotAvailable`. Wraps the body in
  `PoolByteStream` so closing the response returns the connection to the pool.
- `request(...)` / `stream(...)` (from `RequestInterface`) — build `Request`,
  inject `Host` / `Content-Length` / `Transfer-Encoding`, then `handle_request`
  + `read()` + `close()` (`request`) or yield-and-close (`stream`).
- `.connections` property — live list snapshot for introspection.
- `close()` / `aclose()` + sync/async context-manager support.
- Pool assignment (`_assign_requests_to_connections`): evict closed/expired/
  surplus-idle connections first, then (1) reuse an available same-origin
  connection, (2) create new if under `max_connections`, else (3) evict an idle
  connection to make room; otherwise the request stays queued until `pool`
  timeout raises `PoolTimeout`.

### `HTTPConnection` / `AsyncHTTPConnection` (`_sync/connection.py:38`, `_async/connection.py:38`)

```python
HTTPConnection(
    origin: Origin, ssl_context=None, keepalive_expiry=None,
    http1=True, http2=False, retries=0, local_address=None, uds=None,
    network_backend=None, socket_options=None,
)
```

- `_connect(request)`: TCP dial (`connect_tcp(host, port, local_address, timeout, socket_options)`)
  or `connect_unix_socket(path, …)`; then TLS via `start_tls(ssl_context, server_hostname, timeout)`
  for `https`/`wss`, with `server_hostname` overridable by the `sni_hostname` extension.
  `timeout` here is strictly `extensions["timeout"]["connect"]`.
- **Retries & backoff** (`connection.py:19,25-35,105-165` both sides):
  `RETRIES_BACKOFF_FACTOR = 0.5`; `exponential_backoff()` yields `0, 0.5, 1, 2, 4, …`
  seconds; each failed attempt sleeps via `network_backend.sleep(delay)`.
  Only `ConnectError` / `ConnectTimeout` are retried, at most `retries` times
  (default `0` = single attempt). Read/write/pool timeouts, HTTP error statuses,
  and mid-request disconnects are **never** retried. SSL-handshake failures
  mapped to `ConnectError` are retryable (since 0.17.1). A failed connect sets
  `_connect_failed = True`, permanently poisoning that connection object
  (`is_closed()`/`has_expired()`/`is_idle()` all report unusable).
- ALPN dispatch: `set_alpn_protocols(["http/1.1", "h2"] if http2 else ["http/1.1"])`
  — note this **mutates the caller's `ssl_context` object**. `h2` negotiated via
  `selected_alpn_protocol() == "h2"` (or `http1=False, http2=True` for prior
  knowledge) selects the HTTP/2 connection class, else HTTP/1.1.
- State delegates (`can_handle_request` = strict `origin ==` match,
  `is_available/is_idle/is_closed/has_expired/info`) forward to the inner
  protocol connection once established.
- Example:

```python
import httpcore

origin = httpcore.URL("https://example.com").origin
conn = httpcore.HTTPConnection(origin, retries=2)
req = httpcore.Request("GET", "https://example.com/", extensions={"timeout": {"connect": 5.0}})
resp = conn.handle_request(req)
resp.read()
```

### `HTTP11Connection` / `AsyncHTTP11Connection` (`_sync/http11.py:43`)

```python
HTTP11Connection(origin: Origin, stream: NetworkStream, keepalive_expiry: float | None = None)
```

- `h11`-driven state machine `NEW → ACTIVE → IDLE → CLOSED`; only an
  `IDLE`/`NEW` connection `is_available()` (one request at a time).
- Constants: `READ_NUM_BYTES = 64*1024`, `MAX_INCOMPLETE_EVENT_SIZE = 100*1024`
  (oversize response head → `RemoteProtocolError`).
- Timeout keys consumed: `extensions["timeout"]["write"]` for request headers
  (`http11.py:142`) and body (`:154`); `["read"]` for response headers (`:174`)
  and body (`:200`). A `WriteError` while sending is swallowed so a server
  error response can still be read (`http11.py:89-95`).
- `101` / `CONNECT 2xx` responses upgrade to `HTTP11UpgradeStream` exposing the
  raw network stream via the `network_stream` extension.

### `HTTP2Connection` / `AsyncHTTP2Connection` (`_sync/http2.py:42`)

```python
HTTP2Connection(origin, stream, keepalive_expiry=None)
```

- Requires `h2` (absent in this venv). `H2Configuration(validate_inbound_headers=False)`,
  multiplexed (available while stream IDs remain), separate read/write locks,
  `["read"]` on receive (`http2.py:435`), `["write"]` on send (`:463`),
  honors server `max_concurrent_streams` and `GoAway` (retried on a fresh connection).

### Proxies (`_sync/http_proxy.py`, `_sync/socks_proxy.py`, async mirrors)

```python
HTTPProxy(
    proxy_url,
    proxy_auth=None,
    proxy_headers=None,
    ssl_context=None,
    proxy_ssl_context=None,
    max_connections=10,
    max_keepalive_connections=None,
    keepalive_expiry=None,
    http1=True,
    http2=False,
    retries=0,
    local_address=None,
    uds=None,
    network_backend=None,
    socket_options=None,
)
SOCKSProxy(
    proxy_url,
    proxy_auth=None,
    ssl_context=None,
    max_connections=10,
    max_keepalive_connections=None,
    keepalive_expiry=None,
    http1=True,
    http2=False,
    retries=0,
    network_backend=None,
)
# NOTE: SOCKS constructors take NO local_address / uds / socket_options.
```

- `ConnectionPool(..., proxy=Proxy(...))` (1.0.7+) routes per-origin:
  `socks5/socks5h` → `Socks5Connection`; `http` origin → `ForwardHTTPConnection`
  (absolute-URI request to the proxy); otherwise → `TunnelHTTPConnection`
  (`CONNECT` + TLS-in-TLS). Direct `HTTPProxy`/`SOCKSProxy` subclasses exist but
  are marked `# pragma: nocover` (httpx drives the `proxy=` path instead).
- `Proxy(url, auth=None, headers=None, ssl_context=None)` (`_models.py:496`):
  `auth=(user, pw)` is encoded to a `Proxy-Authorization: Basic …` header.
- CONNECT-tunnel setup honors `extensions["timeout"]["connect"]`
  (`http_proxy.py:267`, `socks_proxy.py:219`).
- SOCKS needs `socksio` — not installed here; importing the path raises.

### Interfaces (`_sync/interfaces.py`, `_async/interfaces.py`)

- `RequestInterface.request/stream/handle_request`; async mirror uses
  `handle_async_request`. They enforce types (`enforce_bytes/url/headers`),
  auto-add `Host` and `Content-Length`/`Transfer-Encoding: chunked`
  (`include_request_headers`, `_models.py:109`).
- `ConnectionInterface`: `close/info/can_handle_request/is_available/
  has_expired/is_idle/is_closed` (+ `aclose` async). `is_available` on an
  unconnected `HTTPConnection` is `True` only when HTTP/2 is plausible.

### Models (`_models.py`)

- `URL(url="", *, scheme, host, port, target)` — string-parsed or pre-parsed;
  `.origin` (default ports incl. `ws/wss/socks5*`), byte-exact `__bytes__`/`__repr__`.
- `Origin(scheme, host, port)` — pool/connection affinity key (equality-based).
- `Request(method, url, *, headers, content, extensions)` — `content` may be
  bytes / sync iterable / async iterable; `extensions["target"]` rewrites target
  (enables `OPTIONS *` and proxy absolute-URIs).
- `Response(status, *, headers, content, extensions)` — `read()/iter_stream()/
  close()` sync vs `aread()/aiter_stream()/aclose()` async; body is
  **single-consumption** (`_stream_consumed` guard); `.content` before read raises.
- `ByteStream(bytes)` — dual sync/async iterable. `Extensions = MutableMapping[str, Any]`.
- Standard extension keys: `timeout={connect,read,write,pool}`,
  `trace=callable`, `sni_hostname=str`, `target=bytes`,
  response-side `http_version, reason_phrase, network_stream`.

### Exceptions (`_exceptions.py`)

```
Exception
├── ConnectionNotAvailable   # transient pool race → pool retries internally
├── ProxyError
├── UnsupportedProtocol      # bad/missing scheme
├── ProtocolError
│   ├── RemoteProtocolError  # server disconnect, bad bytes, oversize head
│   └── LocalProtocolError
├── TimeoutException
│   ├── PoolTimeout          # waiting for a pooled connection
│   ├── ConnectTimeout       # TCP/TLS establish
│   ├── ReadTimeout          # response wait/read
│   └── WriteTimeout         # request send
└── NetworkError
    ├── ConnectError         # DNS/refused/TLS mapped failures
    ├── ReadError
    └── WriteError
```

`map_exceptions({from: to})` context manager chains (`raise to_exc(exc) from exc`).
httpx maps each 1:1 to its own hierarchy
(`httpx/_transports/default.py:74-92`), most-specific match wins.

### TLS (`_ssl.py`)

```python
httpcore.default_ssl_context() -> ssl.SSLContext  # create_default_context() + certifi.where()
```

Used whenever `ssl_context=None`. System-trust equivalent only if certifi is
current (it is: `2026.7.22`). Caveat: pool/connection code calls
`ssl_context.set_alpn_protocols(...)` on the passed object — never share one
context between an http2 and an http1-only pool.

### Network backends (`_backends/`)

- `NetworkStream.read/write/close/start_tls/get_extra_info` and
  `AsyncNetworkStream.read/write/aclose/start_tls/get_extra_info`;
  `NetworkBackend.connect_tcp/connect_unix_socket/sleep` (+ async).
- `SOCKET_OPTION = tuple[int,int,int] | tuple[int,int,bytes|bytearray] | tuple[int,int,None,int]`.
- `SyncBackend` (stdlib sockets, `TCP_NODELAY` on), `AnyIOBackend` (the app's
  asyncio path), `TrioBackend` (needs trio — absent), `AutoBackend` (sniffio
  dispatch), `MockBackend/MockStream` + async twins for tests (public API).
- `sleep()` on the backend is what spaces connect retries.

### Synchronization (`_synchronization.py`) & trace (`_trace.py`) & utils

- Sync: `Lock/ThreadLock/Event/Semaphore/ShieldCancellation` (threading-based;
  shield is a no-op). Async: `AsyncLock/AsyncThreadLock(no-op)/AsyncEvent/
  AsyncSemaphore/AsyncShieldCancellation`, backend chosen by
  `current_async_library()` (sniffio; raises without `anyio`/`trio` installed).
  `AsyncEvent.wait(timeout)` maps `trio.TooSlowError` / anyio `TimeoutError` →
  `PoolTimeout`; sync `Event.wait` likewise raises `PoolTimeout`.
- `Trace(name, logger, request, kwargs)`: emits `"<prefix>.<name>.started/
  complete/failed"` to `request.extensions["trace"]` **and/or** DEBUG logging on
  `httpcore.connection`, `httpcore.http11`, `httpcore.http2`, `httpcore.proxy`.
  Sync interface + async callback (or vice versa) raises `TypeError`.
  The app silences these loggers to WARNING (`src/main.py:92`) — correct.
- `_utils.is_socket_readable(sock)` — `select` on Windows, `poll` elsewhere.

## App usage & correctness

**(a) Usage chain.** Single call site: `src/services/update_service.py:22`:

```python
async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
    resp = await client.get(UPDATE_CONFIG_URL)  # constants.py:52
```

`UPDATE_CONFIG_URL = "https://raw.githubusercontent.com/Nwokike/FFmpeg/main/version.json"`.
httpx (`0.28.1`) builds `AsyncHTTPTransport` → `httpcore.AsyncConnectionPool(
ssl_context=<httpx-created certifi context>, max_connections=100,
max_keepalive_connections=20, keepalive_expiry=5.0, http1=True, http2=False,
retries=0, …)` (httpx `_transports/default.py:279+`, `_config.py:159-181,246-247`:
`DEFAULT_LIMITS = Limits(100, 20)` with `keepalive_expiry=5.0`,
`DEFAULT_TIMEOUT_CONFIG = Timeout(5.0)` overridden to `4.0` by the app).
`follow_redirects=True` is required and correct (raw.githubusercontent.com
redirects). No test references httpx/httpcore. `httpcore` is otherwise only
named in the log-silencer (`src/main.py:92`).

**(b) Misuse? No transport-level bug, but three soft spots.**
`timeout=4.0` becomes `httpx.Timeout(4.0)` → `.as_dict()` →
`{connect: 4.0, read: 4.0, write: 4.0, pool: 4.0}` → `request.extensions["timeout"]`,
consumed per-phase: `pool` in `_async/connection_pool.py:216,232`
(acquire wait); `connect` for TCP+TLS in `_async/connection.py:105-158`;
`write`/`read` for send/receive in `_async/http11.py:142,154,174,200`.
So 4.0 s is **four independent per-phase budgets, not a 4 s total deadline**
(worst case ≈ 16 s + backoff sleeps before `check_for_updates` gives up).
That is safe (always finite) but sluggish on the app-start path over a dying
connection — read/connect stall the full 4 s each. Second, `retries=0`
(httpx default, app never overrides) means one connect attempt and **zero**
retries — expected single-shot failures on flaky mobile data, and httpcore
retries would not help read-time drops anyway. Third, the per-check
`async with AsyncClient(...)` builds and closes a pool per call, so
`max_connections=100 / max_keepalive=20 / keepalive_expiry=5.0` never get used —
every update check pays a cold TCP+TLS handshake, and the broad
`except Exception → logger.warning → return None` (`update_service.py:32-34`)
conflates "no update" with "network down". Also note `update_service.py` never
consults the existing connectivity state (`src/main.py:206-229`,
`components/offline_banner.py`, `state.is_online`) before waking the radio.

**(c) Timeout propagation (exact).** `AsyncClient(timeout=4.0)` →
`httpx.Timeout.__init__` (`httpx/_config.py:86`) fans out to all four fields →
each request carries `extensions={"timeout": {"connect":4.0,"read":4.0,
"write":4.0,"pool":4.0}}` → httpcore async pool/connection/http11 consume
exactly the keys listed above; `PoolTimeout/ConnectTimeout/ReadTimeout/
WriteTimeout` map 1:1 to `httpx.PoolTimeout/...` (`httpx/_transports/default.py:74-92`)
and surface inside the app's `except Exception` as a silent skip.

## Underused APIs to adopt

1. **Connect retries for flaky mobile** (v1, smallest change, scoped to the
   update host so nothing else changes semantics):
   ```python
   transport = httpx.AsyncHTTPTransport(
       retries=2
   )  # 0s, 0.5s, 1s backoff on ConnectError/ConnectTimeout only
   limits = httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=5.0)
   async with httpx.AsyncClient(
       transport=transport,
       limits=limits,
       timeout=httpx.Timeout(4.0, connect=3.0, pool=2.0),
       follow_redirects=True,
   ) as client:
       ...
   ```
   Or per-host via `mounts={"https://raw.githubusercontent.com": transport}`.
   Do **not** expect retries to cover read stalls — add app-level "retry the
   whole check once" if that matters.
2. **Split the timeout**: `httpx.Timeout(4.0, connect=3.0, pool=2.0)` keeps the
   total feel but fails fast on queue/connect, the dominant mobile failure.
3. **Share one `AsyncClient`** (module-level, closed on app exit) instead of a
   pool-per-check: makes keepalive actually work and removes a handshake per
   check. If sharing, add network-switch hygiene — on the existing
   `connectivity.on_change` handler (`src/main.py:226`), `await client.aclose()`
   or drop `keepalive_expiry` to ~2–5 s so stale idle connections to the old
   interface are reaped instead of reused against the new route.
4. **Skip when offline**: gate `check_for_updates()` on `state.is_online`
   (already tracked for the banner) to avoid radio wake + log noise.
5. **Distinguish errors**: catch `httpx.TimeoutException / httpx.NetworkError`
   separately from `ValueError` on `resp.json()`/`int(...)` so a corrupt
   manifest is visible instead of silently "no update".
6. **Diagnostics**: pass `extensions={"trace": async_cb}` on a debug build to
   log `connection.connect_tcp.started/complete`, negotiated HTTP version, and
   TLS info without touching packaging. `pool.connections` / `info()` give the
   same post-mortem cheaply.

## Gotchas

- `retries` covers **connect only** (`ConnectError/ConnectTimeout` during dial +
  TLS handshake). Nothing retries pool/read/write failures or HTTP 5xx.
- `keepalive_expiry=None` (httpcore default; httpx sets 5.0 s) means idle
  connections **never expire** — after a Wi-Fi→cellular handoff the pool will
  happily reuse a dead-route socket until the server or a read timeout kills it.
  Always set it on mobile, and close the pool on connectivity change.
- `max_keepalive_connections=None` is **unbounded** (capped only by
  `max_connections`); httpx's `Limits(100, 20)` saves the app from this, but any
  hand-rolled `httpcore` pool must set it explicitly.
- Per-phase timeouts are independent — `timeout=4.0` can spend up to ~4 s in
  *each* of pool/connect/read/write. There is no total-deadline concept in 1.0.9.
- `ssl_context` objects are mutated (`set_alpn_protocols`); do not share one
  across http1-only and http2 pools.
- `trace` callbacks must match sync/async flavor or `handle_request` raises
  `TypeError`; `Response` bodies are single-consumption (`read()` then
  `content`, never iterate twice).
- `uds` raises on Windows; `local_address` selects address family
  (`"0.0.0.0"` vs `"::"`); `Socks5Connection`/`HTTPProxy` constructors lack some
  `ConnectionPool` params (SOCKS: no `local_address/uds/socket_options`).
- `http2=True` and any SOCKS proxy are **uninstallable here** (`h2`, `socksio`,
  `trio` all absent) — attempting them raises `ImportError`/`RuntimeError`, not
  a fallback. `ws/wss` schemes are accepted at pool level (websocket upgrades).
- Python 3.14: `SOCKET_OPTION` is deliberately excluded from the `__module__`
  rewrite (`__init__.py:137-141`, cf. 1.0.8 #1005) — cosmetic, but a reminder
  this 1.0.9 predates 3.14 hardening; keep `h11>=0.16` pinned for the GHSA fix.
