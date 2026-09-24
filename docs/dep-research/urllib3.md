# urllib3 2.8.0 — Complete API Reference

> Package: `urllib3` 2.8.0 — thread-safe HTTP connection pooling, TLS verification,
> multipart upload, retries/redirects. Ground truth: source files + METADATA read
> from `.venv/Lib/site-packages/urllib3` on Python 3.14 (Flet 1.0 app, `ffmpeg`).

---

## Files

All `.py` files enumerated from the installed package (`__pycache__` skipped).
Every file below was read in full (or, for the two largest, in all functionally
relevant ranges: `connectionpool.py` urlopen/redirect/retry paths, `response.py`
decoders + `BaseHTTPResponse` + full `HTTPResponse` streaming API, `connection.py`
`HTTPConnection.request/getresponse` + full `HTTPSConnection`).

| File | Role |
|---|---|
| `__init__.py` | Public exports, `urllib3.request()` top-level helper, warning filters, module-global `_DEFAULT_POOL` |
| `_version.py` | `__version__ = '2.8.0'`, `version_tuple = (2, 8, 0)` |
| `_base_connection.py` | Typing protocols `BaseHTTPConnection` / `BaseHTTPSConnection`, `ProxyConfig`, `_TYPE_BODY` |
| `_collections.py` | `HTTPHeaderDict`, `RecentlyUsedContainer` (LRU pool cache) |
| `_request_methods.py` | `RequestMethods` mixin: `request`, `request_encode_url`, `request_encode_body` |
| `poolmanager.py` | `PoolManager`, `ProxyManager`, `proxy_from_url`, `PoolKey` (29 fields), `key_fn_by_scheme` |
| `connectionpool.py` | `ConnectionPool`, `HTTPConnectionPool`, `HTTPSConnectionPool`, `connection_from_url`, `port_by_scheme` |
| `connection.py` | `HTTPConnection`, `HTTPSConnection`, `DummyConnection`, `port_by_scheme = {"http": 80, "https": 443}` |
| `response.py` | `BaseHTTPResponse`, `HTTPResponse`, decoders (gzip/deflate/brotli/zstd), `BytesQueueBuffer` |
| `fields.py` | `RequestField`, `guess_content_type`, `format_multipart_header_param` (+ 2 deprecated aliases) |
| `filepost.py` | `encode_multipart_formdata`, `choose_boundary`, `iter_field_objects` |
| `exceptions.py` | Full hierarchy (see below) |
| `util/__init__.py` | Re-exports (`Retry`, `Timeout`, `parse_url`, `make_headers`, ssl helpers…) |
| `util/retry.py` | `Retry`, `RequestHistory` |
| `util/timeout.py` | `Timeout`, `_DEFAULT_TIMEOUT` sentinel |
| `util/url.py` | `Url` NamedTuple, `parse_url`, `parse_host` |
| `util/request.py` | `make_headers`, `body_to_chunks`, `rewind_body`, `SKIP_HEADER` |
| `util/response.py` | `is_fp_closed`, `assert_header_parsing`, `is_response_to_head` |
| `util/ssl_.py` | `create_urllib3_context`, `ssl_wrap_socket`, `assert_fingerprint`, `resolve_cert_reqs`, `resolve_ssl_version` |
| `util/ssl_match_hostname.py` | `match_hostname`, `CertificateError` |
| `util/ssltransport.py` | `SSLTransport` (TLS-in-TLS, proxy tunnelling) |
| `util/connection.py` | `create_connection`, `is_connection_dropped`, `allowed_gai_family` |
| `util/proxy.py` | `connection_requires_http_tunnel` |
| `util/util.py` | `to_str`, `to_bytes`, `reraise` |
| `util/wait.py` | `wait_for_read`, `wait_for_write` (selector-based) |
| `contrib/pyopenssl.py` | PyOpenSSL injection — **deprecated, do not use** |
| `contrib/socks.py` | `SOCKSConnection`, `SOCKSHTTPSConnection`, `SOCKSProxyManager` — needs PySocks (**not installed here**) |
| `contrib/emscripten/` | Browser (Pyodide) fetch backend; auto-injected only when `sys.platform == "emscripten"` |
| `http2/__init__.py`, `http2/probe.py` | ALPN HTTP/2 probe cache only (`h2` package **not installed**; `http2/connection.py` exists but requires the `h2` extra) |

---

## Metadata

From `urllib3-2.8.0.dist-info/METADATA` (+ `RECORD`, `licenses/LICENSE.txt`):

- **Name / Version:** `urllib3` **2.8.0** (`Metadata-Version: 2.5`).
- **Requires-Python:** `>=3.10`; classifiers explicitly list **3.10–3.15**
  (incl. free-threading beta, CPython + PyPy). **No issue on Python 3.14.**
- **Runtime pins: none.** Core install has zero mandatory dependencies
  (stdlib `ssl`, `http.client`, `socket` only). Verified: `Requires-Dist`
  entries exist **only** behind extras.
- **License:** `MIT` (`License-Expression: MIT`, text in `licenses/LICENSE.txt`,
  © 2008–2020 Andrey Petrov and contributors).
- **Extras (all optional, none installed in this venv — verified by listing
  `site-packages`: no `brotli`/`brotlicffi`, no `backports.zstd`, no `PySocks`,
  no `h2`):**
  - `brotli` → `brotli>=1.2.0` (CPython) or `brotlicffi>=1.2.0.0` (else).
    Absent ⇒ `ACCEPT_ENCODING = "gzip,deflate"`, no `br` decoder.
  - `h2` → `h2<5,>=4`. Absent ⇒ HTTP/1.1 only.
  - `socks` → `PySocks!=1.5.7,<2.0,>=1.5.6`. Absent ⇒ importing
    `urllib3.contrib.socks` raises with a `DependencyWarning`.
  - `zstd` → `backports-zstd>=1.0.0` **only when `python_version < '3.14'`**.
    On 3.14+ `util/request.py` tries stdlib `compression.zstd` instead
    (code path present; no backport package needed or installed).
  - *(Note: the brief mentions a `secure` extra — it does not exist in 2.8.0
    METADATA. TLS uses stdlib `ssl`; there is no `secure` extra to install.)*
- **Downstream pin:** `requests 2.34.2` requires `urllib3<3,>=1.26` —
  satisfied by 2.8.0.

---

## Module-by-module API

### Top level (`urllib3/__init__.py`)

```python
urllib3.request(method, url, *, body=None, fields=None, headers=None,
                preload_content=True, decode_content=True, redirect=True,
                retries=None, timeout=3, json=None) -> BaseHTTPResponse
```

- Uses a **module-global `PoolManager`** — side effects (pools, connections)
  are shared across all callers/dependencies. For isolation, construct your
  own `PoolManager`.
- `timeout=3` default (float seconds → applies to connect *and* read).
- `retries=None` → `Retry.DEFAULT` (= `Retry(3)`), i.e. 3 total retries.
- Helpers: `disable_warnings(category=HTTPWarning)`, `add_stderr_logger()`.
- Emits `SecurityWarning` (always) / `InsecurePlatformWarning` filters on import.
- **Requires OpenSSL 1.1.1+**: raises `ImportError` / `NotOpenSSLWarning`
  otherwise (non-OpenSSL TLS backends warn).

### `PoolManager` / `ProxyManager` (`poolmanager.py`)

```python
PoolManager(num_pools=10, headers=None, **connection_pool_kw)
ProxyManager(proxy_url, num_pools=10, headers=None, proxy_headers=None,
             proxy_ssl_context=None, use_forwarding_for_https=False,
             proxy_assert_hostname=None, proxy_assert_fingerprint=None,
             **connection_pool_kw)
proxy_from_url(url, **kw) -> ProxyManager
```

- `num_pools`: LRU cache size for per-host pools (`RecentlyUsedContainer`);
  least-recently-used pool is evicted past the limit.
- `**connection_pool_kw` is forwarded to every `HTTP(S)ConnectionPool` it
  creates (e.g. `timeout=`, `retries=`, `maxsize=`, `block=`, TLS kwargs…).
- Pool identity = 29-field `PoolKey` (scheme/host/port/timeout/retries/
  headers/proxy/TLS settings/socket options…); any differing kwarg ⇒ a
  **separate pool**. Scheme+host are lowercased before keying.
- Key methods: `request(...)` (via `RequestMethods`), `urlopen(method, url,
  redirect=True, **kw)`, `connection_from_url(url)`,
  `connection_from_host(host, port, scheme)`, `clear()` (closes all pools;
  also a context manager). Cross-host redirect logic lives here:
  - Follows 301/302/303/307/308 using `urljoin` (relative `Location` OK).
  - **303 ⇒ method forced to `GET`, body dropped**, content headers stripped
    (`_prepare_for_method_change`).
  - `Cookie` / `Authorization` / `Proxy-Authorization` stripped on
    cross-host redirect (`Retry.remove_headers_on_redirect`).
  - Each redirect consumes one `Retry.increment`; exhausted +
    `raise_on_redirect=True` ⇒ `MaxRetryError`, else the 3xx response is returned.
- `ProxyManager`: plain-HTTP destinations are forwarded (absolute URI);
  HTTPS destinations use `CONNECT` tunnel by default. `use_forwarding_for_https=True`
  forwards instead of tunnelling (**proxy then sees headers + body**).
  HTTPS-proxy + HTTPS-destination tunnelling is supported; fetching HTTPS
  resources through an HTTPS *forwarding* proxy raises `ProxySchemeUnsupported`
  in the underlying layer.

### `HTTPConnectionPool` / `HTTPSConnectionPool` (`connectionpool.py`)

```python
HTTPConnectionPool(host, port=None, timeout=_DEFAULT_TIMEOUT, maxsize=1,
    block=False, headers=None, retries=None, _proxy=None,
    _proxy_headers=None, _proxy_config=None, **conn_kw)
HTTPSConnectionPool(host, port=None, ..., key_file=None, cert_file=None,
    cert_reqs=None, key_password=None, ca_certs=None, ssl_version=None,      # ssl_version deprecated
    ssl_minimum_version=None, ssl_maximum_version=None,
    assert_hostname=None, assert_fingerprint=None, ca_cert_dir=None, **conn_kw)
connection_from_url(url, **kw) -> HTTPConnectionPool | HTTPSConnectionPool
```

- `maxsize=1` default; `block=True` ⇒ checkout blocks, else creates a fresh
  (non-pooled) connection past the limit; `pool_timeout=` bounds the wait
  (`EmptyPoolError` on expiry). Full pool in blocking mode ⇒ `FullPoolError`.
- `retries=None` ⇒ `Retry.DEFAULT` (`Retry(3)`). `False`/`0`/int accepted.
- Core call — lowest level, all details explicit:

```python
pool.urlopen(
    method,
    url,
    body=None,
    headers=None,
    retries=None,
    redirect=True,
    assert_same_host=True,
    timeout=_DEFAULT_TIMEOUT,
    pool_timeout=None,
    release_conn=None,
    chunked=False,
    body_pos=None,
    preload_content=True,
    decode_content=True,
    **response_kw,
)
```

- `release_conn=None` defaults to the value of `preload_content`. With
  `preload_content=False` you **must** call `resp.release_conn()` (or fully
  read / `drain_conn()`) or the connection leaks out of the pool.
- Retries on `TimeoutError, HTTPException, OSError, ProtocolError, SSLError,
  CertificateError, ProxyError`; dead connection discarded, `retries.sleep()`
  (backoff + `Retry-After`) between attempts, then recursion.
- Per-pool redirect handling mirrors `PoolManager` (status retry via
  `retries.is_retry(method, status, has_retry_after)`).
- `is_same_host(url)` guards against cross-host use (`HostChangedError`
  unless `assert_same_host=False`, e.g. proxies).
- `close()` disables the pool; further checkouts raise `ClosedPoolError`.
- `HTTPSConnectionPool._prepare_proxy` establishes the `CONNECT` tunnel;
  HTTPS-through-HTTPS-proxy without tunnelling (forwarding) is unsupported.

### `HTTPConnection` / `HTTPSConnection` (`connection.py`)

```python
HTTPConnection(host, port=None, *, timeout=_DEFAULT_TIMEOUT, source_address=None,
    blocksize=16384, socket_options=[(IPPROTO_TCP, TCP_NODELAY, 1)],
    proxy=None, proxy_config=None)
HTTPSConnection(host, port=None, *, timeout=..., ..., cert_reqs=None,
    assert_hostname=None, assert_fingerprint=None, server_hostname=None,
    ssl_context=None, ca_certs=None, ca_cert_dir=None, ca_cert_data=None,
    ssl_minimum_version=None, ssl_maximum_version=None,
    ssl_version=None,            # deprecated, use min/maximum
    cert_file=None, key_file=None, key_password=None)
```

- Subclasses `http.client` connections; `host` property strips trailing-dot
  FQDN for TLS/SNI while DNS still uses the original.
- `request(method, url, body=None, headers=None, *, chunked=False,
  preload_content=True, decode_content=True, enforce_content_length=True)`.
  `request_chunked()` and `HTTPSConnection.set_cert()` are **deprecated**
  (FutureWarning, removal in v3).
- Default `User-Agent: python-urllib3/<version>`; skippable via
  `SKIP_HEADER` for `Accept-Encoding`/`Host`/`User-Agent`.
- TLS: hostname verification via `match_hostname`, optional
  `assert_fingerprint`, `create_urllib3_context()` defaults
  (TLS 1.2+, `CERT_REQUIRED`, system CAs via `certifi`-independent stdlib
  paths unless overridden). Unverified HTTPS warns `InsecureRequestWarning`.
- `DummyConnection` is substituted when `ssl` is unavailable ⇒ HTTPS raises
  `ImportError` on connect.

### `Retry` (`util/retry.py`) — full signature

```python
Retry(
    total=10,
    connect=None,
    read=None,
    redirect=None,
    status=None,
    other=None,
    allowed_methods=frozenset({"HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"}),
    status_forcelist=None,
    backoff_factor=0,
    backoff_max=120,
    raise_on_redirect=True,
    raise_on_status=True,
    history=None,
    respect_retry_after_header=True,
    remove_headers_on_redirect=frozenset({"Cookie", "Authorization", "Proxy-Authorization"}),
    backoff_jitter=0.0,
    retry_after_max=21600,
)
```

- `total=10` default cap across all kinds; `None` removes the cap;
  `0` fails on first retry; `False` disables retries (implies
  `raise_on_redirect=False`).
- `connect`: pre-send errors (safe). `read`: post-send errors (may have
  side effects). `redirect`: max redirects (301/302/303/307/308).
  `status`: retries when response status ∈ `status_forcelist` **and** method ∈
  `allowed_methods`. `other`: everything else.
- `allowed_methods=None` ⇒ retry any verb (empty collection is deprecated).
  Default excludes POST/PUT-body methods — **non-idempotent methods are not
  retried on read/status by default**.
- Backoff: `backoff_factor * 2**(consecutive_errors-1)` after the 2nd try,
  capped at `backoff_max` (default 120 s), plus `uniform(0, backoff_jitter)`;
  e.g. factor 0.1 ⇒ sleeps `[0, 0.2, 0.4, 0.8, …]`.
- `respect_retry_after_header=True`: honors `Retry-After` (delta-seconds or
  HTTP-date, capped at `retry_after_max` = 6 h) on **413/429/503**
  (`RETRY_AFTER_STATUS_CODES`); invalid header ⇒ `InvalidHeader`.
- Key methods: `increment(method, url, response, error, _pool)` → new `Retry`
  (immutable style) or `MaxRetryError`; `sleep(response)`; `is_retry(...)`;
  `is_exhausted()`; `from_int(n)` (int ⇒ connect-retries only);
  `Retry.DEFAULT = Retry(3)`.
- Example:

```python
from urllib3 import PoolManager
from urllib3.util import Retry, Timeout

r = Retry(
    total=5,
    connect=3,
    read=3,
    redirect=3,
    status=3,
    status_forcelist={429, 500, 502, 503, 504},
    allowed_methods={"HEAD", "GET", "OPTIONS", "TRACE"},
    backoff_factor=0.3,
    backoff_max=10.0,
)
http = PoolManager(retries=r, timeout=Timeout(connect=2.0, read=7.0))
resp = http.request("GET", "https://example.com/", retries=r)  # per-request override
```

### `Timeout` (`util/timeout.py`) — all modes

```python
Timeout(total=None, connect=_DEFAULT_TIMEOUT, read=_DEFAULT_TIMEOUT)
Timeout.DEFAULT_TIMEOUT  # sentinel meaning "system default"
```

- `_DEFAULT_TIMEOUT` resolves via `socket.getdefaulttimeout()` — **omitted
  timeouts inherit the global socket default, not infinity**.
- `total`: budget covering connect+read; read allowance = leftover.
  Shorter of total/specific wins.
- `None` per-leg = infinite (e.g. `Timeout(connect=None, read=None)` disables).
- Validation: bools rejected, `<= 0` rejected (`ValueError`).
- `Timeout.from_float(x)` sets both legs; `clone()` per-request copies;
  `start_connect()` / `get_connect_duration()` misuse ⇒ `TimeoutStateError`.
- Timeout errors surface as `ConnectTimeoutError` / `ReadTimeoutError`
  (both subclass `urllib3.exceptions.TimeoutError`), wrapped in
  `MaxRetryError` when retries remain.

### `Response` streaming (`response.py`)

```python
HTTPResponse(
    body="",
    headers=None,
    status=0,
    version=0,
    version_string="HTTP/?",
    reason=None,
    preload_content=True,
    decode_content=True,
    original_response=None,
    pool=None,
    connection=None,
    msg=None,
    retries=None,
    enforce_content_length=True,
    request_method=None,
    request_url=None,
    auto_close=True,
    sock_shutdown=None,
)
```

- `.data` (bytes, cached), `.json()` (UTF-8 per RFC 8259),
  `.status/.headers/.reason/.version`, `.url`, `.retries`,
  `.length_remaining`, `.tell()`.
- `read(amt=None, decode_content=None, cache_content=False)` — `amt` set ⇒
  caching silently disabled. `read1(...)`, `stream(amt=65536)` generator,
  `read_chunked(amt=None)` (requires `Transfer-Encoding: chunked`, else
  `ResponseNotChunked`).
- Decoders: gzip/x-gzip, deflate (zlib + raw fallback), `br` (if brotli
  installed — **not installed here**), `zstd` (if available — 3.14 stdlib
  path attempted). Failures ⇒ `DecodeError`.
- **Gotcha:** `read(decode_content=False)` after any decoded read raises
  `RuntimeError`. Length mismatch ⇒ `IncompleteRead`/`ProtocolError`
  (when `enforce_content_length=True`, the default).
- Connection discipline: `release_conn()`, `drain_conn()` (discard remainder
  so the socket is reusable — used internally before redirects/retries),
  `close()`, context-manager support.
- `get_redirect_location()` → `Location` header for 301/302/303/307/308,
  else `False`.

### Redirect logic (summary)

Handled at **both** `PoolManager.urlopen` and `HTTPConnectionPool.urlopen`:
status ∈ {301,302,303,307,308} + `Location` header. 303 ⇒ rewrite to GET and
drop body/chunked state/content headers. Auth-sensitive headers stripped
cross-host. Retry-After slept. Exhausted budget ⇒ `MaxRetryError` (if
`raise_on_redirect`) else the 3xx response is returned. Non-rewindable bodies
across a redirect/retry ⇒ `UnrewindableBodyError`.

### Multipart / form encoding (`filepost.py`, `fields.py`, `_request_methods.py`)

```python
encode_multipart_formdata(fields, boundary=None) -> (body: bytes, content_type: str)
RequestField(name, data, filename=None, headers=None)   # header_formatter deprecated
RequestField.from_tuples(fieldname, value)              # value | (filename, data) | (filename, data, mime)
```

- Field value shapes: `'foo': 'bar'`, `'f': ('name.txt', data)`,
  `'t': ('b.bin', data, 'image/jpeg')`; MIME guessed via `mimetypes`.
- `RequestMethods.request(method, url, body, fields, headers, json, **urlopen_kw)`:
  GET/HEAD/DELETE/OPTIONS ⇒ fields URL-encoded into query string;
  otherwise `request_encode_body` ⇒ multipart (default) or
  `application/x-www-form-urlencoded` (`encode_multipart=False`).
  `json=` sets `Content-Type: application/json` unless already present;
  `body` + `json`, or `fields` + `body`, ⇒ `TypeError`.
- `make_headers(keep_alive, accept_encoding, user_agent, basic_auth,
  proxy_basic_auth, disable_cache, *, *_encoding="latin-1")` builds auth/
  keep-alive/cache headers. `body_to_chunks()` maps body types to
  `(chunks, content_length)`; unknown-length bodies use chunked framing.

### `HTTPHeaderDict` / `RecentlyUsedContainer` (`_collections.py`)

Case-insensitive multi-value header dict: `add(key, val, *, combine=False)`,
`getlist(key)`, `extend(...)`, `iteritems()` (all duplicates) vs
`itermerged()` (comma-joined), `discard()`, `copy()`, `|`/`|=` merge,
`_prepare_for_method_change()`. `RecentlyUsedContainer(maxsize=10,
dispose_func)` — thread-safe LRU (`RLock`); iteration deliberately unsupported.

### URL (`util/url.py`)

`parse_url(url) -> Url(scheme, auth, host, port, path, query, fragment)` —
scheme/host lowercased, IDNA-aware, strict validation (`LocationParseError`,
`URLSchemeUnknown`). FutureWarning for scheme-less URLs (error in v3).

### Exceptions hierarchy (`exceptions.py`)

```
HTTPError (base)
├── PoolError (pool, message)
│   ├── RequestError (pool, url, message)
│   │   ├── MaxRetryError (pool, url, reason)
│   │   └── HostChangedError (pool, url, retries)
│   ├── EmptyPoolError, FullPoolError, ClosedPoolError
├── SSLError
├── ProxyError (message, original_error)
├── DecodeError, ProtocolError (= ConnectionError, alias),
│   ResponseError, InvalidHeader, InvalidChunkLength,
│   BodyNotHttplibCompatible, IncompleteRead, UnrewindableBodyError,
│   HeaderParsingError
├── TimeoutError
│   ├── ReadTimeoutError (TimeoutError + RequestError)
│   └── ConnectTimeoutError
│       └── NewConnectionError (conn, message)
│           └── NameResolutionError (host, conn, reason)
├── LocationValueError (ValueError + HTTPError)
│   ├── LocationParseError (location)
│   └── URLSchemeUnknown (scheme) → ProxySchemeUnknown (+ AssertionError)
├── TimeoutStateError
└── ProxySchemeUnsupported (ValueError)
HTTPWarning (base)
├── SecurityWarning → InsecureRequestWarning, NotOpenSSLWarning,
│   SystemTimeWarning, InsecurePlatformWarning
├── DependencyWarning
└── ResponseNotChunked (ProtocolError + ValueError)
```

### `contrib.*` / `http2` / `util/ssl_*`

- `contrib/pyopenssl.py`: `inject_into_urllib3()` — legacy; superseded by
  stdlib `ssl` SNI support. **Not recommended.**
- `contrib/socks.py`: `SOCKSProxyManager`, `SOCKSConnection`,
  `SOCKSHTTPSConnection`; schemes `socks4/4a/5/5h` — **unusable here,
  PySocks not installed**.
- `contrib/emscripten/`: fetch-based backend, browser only.
- `http2/probe.py`: ALPN probe result cache (`acquire_and_get` /
  `set_and_release`); real H2 needs the missing `h2` extra.
- `util/ssl_.py`: `create_urllib3_context(ssl_version, cert_reqs, options,
  ciphers, ssl_minimum/maximum_version, verify_flags, cert_reqs)`,
  `ssl_wrap_socket(...)`, `assert_fingerprint(cert, fingerprint)`.

---

## App usage & correctness

Dependency chain (verified in `uv.lock`, `pyproject.toml`, `src/`, `tests/`):

```
flet 1.0.0 (runtime) ──uses──▶ httpx 0.28.1 ──uses──▶ httpcore 1.0.9   (NO urllib3)
flet-cli 1.0.0 (dev-only) ──uses──▶ cookiecutter 2.7.1 ──uses──▶ requests 2.34.2
        ──uses──▶ urllib3 2.8.0  (+ certifi, charset-normalizer, idna)
```

- `pyproject.toml` production deps: `av`, `flet*`, `httpx` — **neither
  `requests` nor `urllib3` is a declared dependency**. The entire
  `flet-cli → cookiecutter → requests → urllib3` chain is **dev-only**
  (scaffolding/cookiecutter templating); it should not ship in the mobile
  artifact.
- (a) **Live HTTP path bypasses urllib3 entirely.** `src/services/update_service.py`
  uses `httpx.AsyncClient(timeout=4.0, follow_redirects=True)`; httpx rides on
  `httpcore`, never urllib3. `tests/test_update_service.py` mocks at the
  `httpx.AsyncClient`/`httpx.MockTransport` layer. The sole mention of urllib3
  in app code is log-silencing in `src/main.py:92`
  (`for noisy in ("httpx", "httpcore", "urllib3")`), which is harmless —
  the `urllib3` logger simply never emits.
- (b) **Misuse: none found.** No `import urllib3` / `import requests` anywhere
  under `src/` or `tests/` (grep-verified). No `Retry`/`Timeout` misconfiguration,
  no unverified-TLS, no leaked-pool patterns — because urllib3 is never called.
- (c) Correctness note: `timeout=4.0` in `UpdateService` is a single total-ish
  budget at the httpx layer; fine for a silent background check. Tests cover
  200-newer/200-same/404/timeout/bad-JSON — reasonable.

## Considerations for v1

1. **Recommend: httpx-only. Do not adopt urllib3/requests in app code.**
   The live path (`httpx.AsyncClient`) is async-native (matches the Flet
   event loop), already tested with `MockTransport`, and has no urllib3
   footprint. Introducing `requests` (sync, thread-blocking) on mobile —
   especially on the UI thread — risks ANRs; urllib3 sync pools add nothing
   httpx/`httpcore` doesn't already provide (pooling, TLS, redirects).
2. **urllib3 becomes load-bearing only if `requests` is ever imported**
   (directly or via a new dep). `requests` pins `urllib3<3,>=1.26`, so a
   future urllib3 3.x would break `requests 2.34.2` — keep the `<3` constraint
   in mind when running `uv lock --upgrade`.
3. **If urllib3 is ever used** (e.g. a sync download worker), the patterns
   worth copying from this reference: `PoolManager(retries=Retry(total=5,
   status_forcelist={429,500,502,503,504}, backoff_factor=0.3), timeout=
   Timeout(connect=2.0, read=7.0))`; stream large files with
   `preload_content=False` + `resp.stream(65536)` + `release_conn()`; reuse one
   `PoolManager` for the process; never use module-global `urllib3.request()`
   in library code.
4. **Keep the `main.py:92` silencer as-is** — it covers the transitive urllib3
   logger in dev (`flet build` plugin runs) at zero cost.
5. Optional extras (`brotli`, `h2`, `socks`, `zstd`-backport) are absent and
   unnecessary for v1; on Python 3.14 zstd-via-stdlib is attempted
   automatically if the server offers it.

## Gotchas

1. `Retry` default `total=10` (pool default `Retry(3)`); POST etc. are **not**
   retried on read/status unless added to `allowed_methods`.
2. `Timeout` omitted legs inherit `socket.getdefaulttimeout()`, not infinity;
   `True`/`False`/`<=0` raise `ValueError`.
3. `read(decode_content=False)` after any decoded read ⇒ `RuntimeError`;
   `read(amt=…)` silently disables `cache_content`.
4. `preload_content=False` without `release_conn()`/full-read/`drain_conn()`
   leaks the connection out of the pool (pool starvation under `block=True`).
5. Non-seekable bodies + redirect/retry ⇒ `UnrewindableBodyError`.
6. 303 rewrites to GET and drops the body; auth headers are stripped
   cross-host — can surprise signed-URL flows.
7. `urllib3.request()` shares one global `PoolManager` across all libraries
   in the process — prefer an instance.
8. Scheme-less URLs, `strict=`, `request_chunked()`, `set_cert()`,
   `ssl_version=` are deprecated (FutureWarning → removal/error in v3).
9. `MaxRetryError.reason` holds the real error (`ConnectTimeoutError`,
   `SSLError`, `ResponseError`…) — catch via `reason`, don't string-match.
10. SOCKS/H2/brotli code paths exist but their third-party packages are **not
    installed** — those imports fail loudly; don't reference them in v1 code.
