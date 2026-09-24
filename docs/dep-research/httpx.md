# httpx 0.28.1 — Complete API Reference

> Next-generation HTTP client for Python. Sync + async APIs, connection pooling,
> HTTP/1.1 (plus optional HTTP/2), redirects, cookies, auth, proxies, streaming,
> multipart, timeouts, transports (incl. WSGI/ASGI/mock), and an integrated CLI.
> Ground truth: installed source at
> `<repo>\.venv\Lib\site-packages\httpx`
> (23 files, every `.py` read in full), metadata from
> `httpx-0.28.1.dist-info\METADATA` / `RECORD` / `entry_points.txt`.

---

## Files

Package dir `...\.venv\Lib\site-packages\httpx` (excludes `__pycache__`/`*.pyc`):

| File | Role |
|---|---|
| `__init__.py` | Public re-exports; sets `__module__ = "httpx"` on all public names |
| `__version__.py` | `__title__`, `__description__`, `__version__ = "0.28.1"` |
| `_api.py` | One-shot top-level functions: `request`, `stream`, `get`, `options`, `head`, `post`, `put`, `patch`, `delete` |
| `_auth.py` | `Auth`, `FunctionAuth`, `BasicAuth`, `NetRCAuth`, `DigestAuth` |
| `_client.py` | `Client`, `AsyncClient`, `BaseClient`, `USE_CLIENT_DEFAULT`, event hooks, redirect logic (2019 lines) |
| `_config.py` | `Timeout`, `Limits`, `Proxy`, `create_ssl_context`, defaults |
| `_content.py` | Request/response body encoders (`encode_*`), `ByteStream`, iterator streams |
| `_decoders.py` | Content-Encoding decoders (gzip/deflate/br/zstd), chunkers, `LineDecoder` |
| `_exceptions.py` | Full exception hierarchy (see below) |
| `_main.py` | `httpx` CLI (click + rich + pygments), `trace()` extension, download progress |
| `_models.py` | `Headers`, `Request`, `Response`, `Cookies` (1277 lines) |
| `_multipart.py` | `MultipartStream`, `DataField`, `FileField`, boundary parsing |
| `_status_codes.py` | `codes` IntEnum + `is_*` classifiers + lowercase aliases |
| `_transports/__init__.py` | Re-exports all transports |
| `_transports/base.py` | `BaseTransport`, `AsyncBaseTransport` interfaces |
| `_transports/default.py` | `HTTPTransport`, `AsyncHTTPTransport` over httpcore (pool/proxy/retries/uds) |
| `_transports/mock.py` | `MockTransport` for tests |
| `_transports/wsgi.py` | `WSGITransport` |
| `_transports/asgi.py` | `ASGITransport` |
| `_types.py` | Type aliases (`URLTypes`, `QueryParamTypes`, `HeaderTypes`, `CookieTypes`, `TimeoutTypes`, `ProxyTypes`, `CertTypes`, `AuthTypes`, `RequestContent`, …), `SyncByteStream`, `AsyncByteStream` |
| `_urlparse.py` | RFC 3986 URL parser/validator/normalizer (IDNA, percent-encoding sets) |
| `_urls.py` | `URL`, `QueryParams` (immutable multidict) |
| `_utils.py` | `URLPattern` (proxy/mount matching), `get_environment_proxies`, byte helpers |
| `py.typed` | PEP 561 marker — package is fully type-annotated |

Console script (`entry_points.txt`): `httpx = httpx:main` (installed as
`..\..\Scripts\httpx.exe` per RECORD — the `cli` extra deps *are* present).

---

## Metadata

- **Name / version:** `httpx 0.28.1` — "The next generation HTTP client."
- **License:** BSD-3-Clause (`Licenses: LICENSE.md`, Encode OSS Ltd).
- **Requires-Python:** `>=3.8`. **Status:** Beta. Pure-Python wheel.
- **Hard dependencies (all installed):**
  - `anyio` (installed 4.15.1) — async backend abstraction (asyncio/trio sniffing)
  - `certifi` (installed 2026.7.22) — default CA bundle for TLS
  - `httpcore==1.*` (installed 1.0.9; itself needs `certifi`, `h11>=0.16`) — the actual socket/HTTP engine; httpx maps every `httpcore` exception onto its own hierarchy
  - `idna` (installed 3.20) — internationalized domain names
- **Optional extras (from METADATA):**
  - `brotli` → `brotli` (CPython) / `brotlicffi` — `br` responses. **NOT installed** (server `br` simply won't be advertised — graceful).
  - `cli` → `click==8.*`, `pygments==2.*`, `rich<14,>=10` — **installed** (click 8.5.0, pygments 2.21.0, rich 15.0.0), so the `httpx` CLI works.
  - `http2` → `h2<5,>=3` — **NOT installed**; passing `http2=True` raises `ImportError`.
  - `socks` → `socksio==1.*` — **NOT installed**; `socks5://` proxies raise `ImportError`.
  - `zstd` → `zstandard>=0.18.0` — **NOT installed**.
- **App pin:** `pyproject.toml` declares `"httpx>=0.28.1"` (floor pin, no ceiling).
- **Defaults baked into `_config.py`:** `DEFAULT_TIMEOUT_CONFIG = Timeout(5.0)`,
  `DEFAULT_LIMITS = Limits(max_connections=100, max_keepalive_connections=20)`,
  `DEFAULT_MAX_REDIRECTS = 20`. Client auto-headers: `Accept: */*`,
  `Accept-Encoding: gzip, deflate` (+ `br`/`zstd` only if installed),
  `Connection: keep-alive`, `User-Agent: python-httpx/0.28.1`.
- **httpx logging:** uses `logging.getLogger("httpx")` for one `INFO` line per
  request (`HTTP Request: GET <url> "HTTP/1.1 200 OK"`). App already quiets it
  (`src/main.py:92`).

---

## Module-by-module API

### 1. Top-level one-shot API (`_api.py`)

Each call builds a throwaway `Client`, sends one request, closes it. Convenient
but **no connection reuse** — fine for rare calls, bad in loops.

```python
httpx.request(method, url, *, params=None, content=None, data=None, files=None,
              json=None, headers=None, cookies=None, auth=None, proxy=None,
              timeout=Timeout(5.0), follow_redirects=False,
              verify=True, trust_env=True) -> Response
httpx.stream(method, url, *, <same as request>) -> Iterator[Response]  # context manager
httpx.get(url, *, params, headers, cookies, auth, proxy, follow_redirects, verify, timeout, trust_env) -> Response
httpx.options/head/delete(url, *, <same, no body params>) -> Response
httpx.post/put/patch(url, *, content, data, files, json, params, headers, cookies, auth, proxy, follow_redirects, verify, timeout, trust_env) -> Response
```

Defaults: `timeout=5.0` on **every** operation (connect/read/write/pool),
`follow_redirects=False`, `verify=True` (certifi bundle), `trust_env=True`
(env proxies honored).

### 2. `Client` / `AsyncClient` (`_client.py`)

```python
Client(*, auth=None, params=None, headers=None, cookies=None,
       verify=True, cert=None, trust_env=True,
       http1=True, http2=False,
       proxy=None, mounts=None,
       timeout=Timeout(5.0), follow_redirects=False,
       limits=Limits(100, 20), max_redirects=20,
       event_hooks=None, base_url="", transport=None,
       default_encoding="utf-8")
```

Same signature for `AsyncClient` (minus `cert`, plus async transport types).
`Client` is thread-shareable; `AsyncClient` is task-shareable. Both are
**single-use context managers** — reopening raises `RuntimeError`.

- `auth: AuthTypes` — `(user, pass)` tuple → `BasicAuth`, callable → `FunctionAuth`, or `Auth` instance. URL-embedded `user:pass@host` also becomes `BasicAuth` automatically.
- `params / headers / cookies` — client-level defaults **merged** into every request (`_merge_*`); per-request values win.
- `verify` — `True` (certifi) | `False` (**disables TLS verification — never in prod**) | `ssl.SSLContext` | (deprecated `str` path). Honors `SSL_CERT_FILE`/`SSL_CERT_DIR` env when `trust_env`.
- `cert` — deprecated; use `verify=<SSLContext>` + `load_cert_chain()`.
- `proxy` — URL str / `URL` / `Proxy`; `http(s)://` needs nothing extra, `socks5://` needs `httpx[socks]`. Env proxies (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`) auto-used when `trust_env=True` and no explicit transport.
- `mounts: Mapping[str, Transport | None]` — per-URL-pattern transports, e.g. `{"all://": HTTPTransport(http2=True), "all://*internal.local": HTTPTransport(verify=False)}`. Keys parsed by `URLPattern` (scheme/host/port wildcards), matched most-specific-first.
- `timeout` — `float | (c, r, w, p) tuple | Timeout | None`. `None` = no timeout. Per-request override via `client.get(url, timeout=...)`.
- `follow_redirects` — default `False`; per-request overridable. `max_redirects=20` default; exceeded → `TooManyRedirects`.
- `limits: Limits` — pool sizing (see §4).
- `event_hooks: {"request": [...], "response": [...]}` — sync callables for `Client`, **async** callables for `AsyncClient`. Basis for logging/metrics/auth-refresh.
- `base_url` — trailing slash enforced; relative request URLs append to it.
- `transport` — inject `MockTransport` (tests), `WSGITransport`/`ASGITransport`, or custom.
- `default_encoding` — `str` or callable `bytes -> str` (charset autodetection hook).
- `extensions={"trace": callable, "timeout": {...}, "sni_hostname": ...}` — per-request low-level hooks; the CLI uses `extensions={"trace": ...}` for verbose output. `sni_hostname` overrides TLS SNI.

Methods (sync shown; `AsyncClient` identical with `await` + `aclose`):

```python
client.request(method, url, *, content, data, files, json, params, headers,
               cookies, auth=USE_CLIENT_DEFAULT,
               follow_redirects=USE_CLIENT_DEFAULT, timeout=USE_CLIENT_DEFAULT,
               extensions=None) -> Response
client.get/options/head/delete(url, *, params, headers, cookies, auth, follow_redirects, timeout, extensions)
client.post/put/patch(url, *, content, data, files, json, params, headers, cookies, auth, follow_redirects, timeout, extensions)
client.stream(method, url, *, <same>) -> Iterator[Response]   # sync context manager
AsyncClient.stream(...) -> AsyncIterator[Response]            # async context manager
client.send(request, *, stream=False, auth=..., follow_redirects=...) -> Response
client.build_request(method, url, *, ...) -> Request          # merge + prep without sending
client.close() / AsyncClient.aclose()
client.cookies: Cookies        # persistent jar, auto extract/set per request
client.headers / .params / .auth / .base_url / .timeout / .event_hooks / .follow_redirects
client.max_redirects / .trust_env / .is_closed
```

`USE_CLIENT_DEFAULT` sentinel distinguishes "not passed → use client default"
from explicit `None` (= disable). Redirect semantics: 303 → GET (except HEAD);
302 → GET (browser behavior); 301 POST → GET; 307/308 keep method+body;
`Authorization` stripped on cross-origin redirects (kept on http→https upgrade);
`Host` rewritten; `Cookie` re-derived from jar; fragment preserved; redirect
chain in `response.history`; `response.next_request` set when *not* following.
`elapsed: timedelta` set when the response stream closes. Cookies deprecated at
per-request level (`DeprecationWarning` — set them on the client).

### 3. `Request` (`_models.py`)

```python
Request(method, url, *, params=None, headers=None, cookies=None,
        content=None, data=None, files=None, json=None,
        stream=None, extensions=None)
```

- `method` uppercased; auto `Host` header + `Content-Length: 0` for POST/PUT/PATCH.
- Body encoders: `content=<str|bytes|iter|aiter>` (chunked if length unknown);
  `data=<dict>` → `application/x-www-form-urlencoded` (`data=<bytes>` is
  **deprecated**, use `content=`); `files=` → multipart; `json=` → compact JSON
  (`separators=(",",":")`, `allow_nan=False`, utf-8).
- `.read() / .aread() -> bytes`, `.content` (raises `RequestNotRead` if unread),
  `.method`, `.url: URL`, `.headers: Headers`, `.extensions` (carries `timeout` dict).
- `Request(stream=...)` skips all auto-headers — transport/internal use only.
- Picklable (stream detached → `UnattachedStream`).

### 4. `Response` (`_models.py`)

```python
Response(status_code, *, headers=None, content=None, text=None, html=None, json=None,
         stream=None, request=None, extensions=None, history=None,
         default_encoding="utf-8")
```

Content (must `read()` first unless constructed with content; else
`ResponseNotRead`; a stream can be consumed only once → `StreamConsumed`):

```python
resp.read() -> bytes / await resp.aread() -> bytes
resp.iter_bytes(chunk_size=None) / aiter_bytes  # content-decoded (gzip/deflate/br/zstd)
resp.iter_text(chunk_size=None) / aiter_text    # + charset decode
resp.iter_lines() / aiter_lines                 # universal-newline aware, for SSE/NDJSON
resp.iter_raw(chunk_size=None) / aiter_raw      # raw wire bytes, updates num_bytes_downloaded
resp.close() / await resp.aclose()
resp.content: bytes / .text: str / .json(**kwargs)
```

Metadata: `.status_code: int`, `.reason_phrase`, `.http_version`
(from `extensions`, default `"HTTP/1.1"`), `.headers`, `.url` (via request),
`.request` (raises if unset), `.history: list[Response]`,
`.next_request: Request | None`, `.elapsed: timedelta` (only after read/close),
`.cookies: Cookies`, `.links: dict` (parsed `Link` header),
`.num_bytes_downloaded`, `.extensions`, `.is_closed`, `.is_stream_consumed`.

Status helpers: `.is_informational / .is_success / .is_redirect / .is_client_error / .is_server_error / .is_error`, `.has_redirect_location` (301/302/303/307/308 + `Location`).
`raise_for_status() -> Response` raises `HTTPStatusError` (with `request`+`response` attached; redirect message includes `Location`).
Encoding resolution: explicit `.encoding =` (raises `ValueError` if `.text`
already accessed) → `Content-Type` charset → `default_encoding` (str or
callable) → utf-8.

### 5. `Headers` / `QueryParams` / `URL` / `Cookies`

- **`Headers`** — case-insensitive multi-dict. Construct from dict / seq / `Headers`.
  `__getitem__` joins duplicates with `", "`; `.get_list(key, split_commas=False)`;
  `.multi_items()`; `.update()` replaces same-key entries; `in`/`del`; `.raw: list[(bytes,bytes)]`;
  auto encoding detection (ascii→utf-8→iso-8859-1); `repr` masks
  `authorization`/`proxy-authorization` as `[secure]`.
- **`QueryParams`** — **immutable** multidict (`q["a"]` first value; `.get_list()`;
  `.multi_items()`; `.set/.add/.remove/.merge` return **new** instances;
  `__setitem__`/`.update` raise `RuntimeError`). `str(q)` urlencodes; bools →
  `"true"/"false"`, `None` → `""`.
- **`URL`** — normalized (lowercased scheme/host, IDNA `raw_host`, default ports
  dropped so `:80` == bare host, dot-segment resolution, WHATWG percent-encode
  sets). Props: `.scheme/.raw_scheme/.username/.password/.userinfo/.host/.raw_host/.port/.netloc/.path/.query/.params/.raw_path/.fragment/.is_absolute_url/.is_relative_url`; `.copy_with(...)`, `.copy_set_param/.copy_add_param/.copy_remove_param/.copy_merge_params`, `.join(relative)`. `MAX_URL_LENGTH = 65536`; malformed → `InvalidURL`. `repr` masks passwords.
- **`Cookies`** — `MutableMapping` over `CookieJar`. `.extract_cookies(response)`,
  `.set_cookie_header(request)`, `.set(name, value, domain="", path="/")`,
  `.get(name, default, domain, path)` (raises `CookieConflict` on ambiguity),
  `.delete/.clear/.update`.

### 6. Exceptions (`_exceptions.py`)

```
HTTPError                                          # catch-all for request + raise_for_status
├── RequestError                                   # anything sending a request; has .request
│   ├── TransportError                             # transport layer
│   │   ├── TimeoutException                       # catch-all timeouts
│   │   │   ├── ConnectTimeout / ReadTimeout / WriteTimeout / PoolTimeout
│   │   ├── NetworkError
│   │   │   ├── ConnectError / ReadError / WriteError / CloseError
│   │   ├── ProtocolError → LocalProtocolError / RemoteProtocolError
│   │   ├── ProxyError / UnsupportedProtocol
│   ├── DecodingError                              # bad content-encoding / charset
│   └── TooManyRedirects
└── HTTPStatusError                                # from raise_for_status(); has .request + .response
InvalidURL(Exception) / CookieConflict(Exception)
StreamError(RuntimeError) → StreamConsumed / StreamClosed / ResponseNotRead / RequestNotRead
```

Practical catch ladder: `HTTPStatusError` (bad status) → `TimeoutException`
(retryable-ish) → `NetworkError` (offline/DNS/reset) → `RequestError`
(everything else incl. redirects/decoding). `json()` raises stdlib
`json.JSONDecodeError` (a `ValueError`, **not** an httpx error).

### 7. Timeouts / limits / proxies / SSL (`_config.py`)

```python
Timeout(timeout, *, connect=None, read=None, write=None, pool=None)
Timeout(5.0)                 # all four = 5s (the default)
Timeout(None)                # all disabled — use sparingly
Timeout(5.0, connect=10.0)   # per-op override
Timeout(5.0, pool=None)      # no pool-acquire timeout
t.as_dict()                  # {"connect":..,"read":..,"write":..,"pool":..}
Limits(*, max_connections=None, max_keepalive_connections=None, keepalive_expiry=5.0)
Proxy(url, *, ssl_context=None, auth=(user, pass), headers=None)  # creds stripped from URL
create_ssl_context(verify=True, cert=None, trust_env=True) -> ssl.SSLContext
```

`Timeout` also accepts a 4-tuple `(connect, read, write, pool)`.
`httpcore` maps pool timeouts → `PoolTimeout`; everything surfaces as the
httpx classes in §6.

### 8. Auth (`_auth.py`)

- `BasicAuth(username, password)` — preemptive `Authorization: Basic ...`.
- `DigestAuth(username, password)` — 401-challenge flow (MD5/MD5-SESS/SHA/SHA-SESS/SHA-256(-SESS)/SHA-512(-SESS)); caches last challenge; `auth-int` qop **not implemented**; stateful (`_nonce_count`) — one instance per client is fine, don't share across threads.
- `NetRCAuth(file=None)` — credentials from `~/.netrc` by host.
- Custom: subclass `Auth`, override `auth_flow(request)` generator
  (`response = yield request`, `return` ends flow). For I/O or locks, override
  `sync_auth_flow` / `async_auth_flow` instead. Set
  `requires_request_body / requires_response_body = True` if the flow needs bodies buffered.
- Shorthand: `auth=(user, pass)` tuple, or `auth=callable(request) -> request` (`FunctionAuth`, e.g. token injection).

### 9. Transports (`_transports/`)

```python
HTTPTransport(verify=True, cert=None, trust_env=True, http1=True, http2=False,
              limits=DEFAULT_LIMITS, proxy=None, uds=None, local_address=None,
              retries=0, socket_options=None)
AsyncHTTPTransport(<same>)
```

- `retries=N` — httpcore-level connection retries (covers connects, **not**
  status-code retries). `uds="socket.uds"` — Unix-domain sockets.
  `local_address` — bind source IP. `socket_options` — raw socket opts.
- `MockTransport(handler)` — `handler(request) -> Response` (may be `async`
  for `AsyncClient`; sync handler works for both; async handler under sync
  `Client` raises `TypeError`). Reads request body first. The unit-test seam.
- `WSGITransport(app, raise_app_exceptions=True, script_name="", remote_addr="127.0.0.1", wsgi_errors=None)` — or `Client(app=...)` shorthand (not in this version's `Client.__init__` params — pass explicit `transport=`).
- `ASGITransport(app, raise_app_exceptions=True, root_path="", client=("127.0.0.1", 123))` — async only; auto-detects trio vs asyncio via sniffio.
- Custom transports implement `handle_request(request) -> Response`
  (+ `close()`, context-manager support) or `handle_async_request` (+ `aclose()`).

### 10. Status codes (`_status_codes.py`)

`codes.OK == 200` etc. for all standard 1xx–5xx (+ `IM_A_TEAPOT`, `TOO_EARLY`,
`UNAVAILABLE_FOR_LEGAL_REASONS` …). Classifiers:
`codes.is_informational/is_success/is_redirect/is_client_error/is_server_error/is_error(value)`,
`codes.get_reason_phrase(value)`. Lowercase aliases (`codes.ok`, `codes.not_found`) for requests-compat.

### 11. Streaming / SSE pattern, multipart, decoders, logging/trace

- **Streaming download with progress** (the pattern a future in-app binary/media
  downloader should copy — also exactly what the CLI's `download_response` does):
  ```python
  async with httpx.AsyncClient(timeout=...) as client:
      async with client.stream("GET", url) as resp:
          resp.raise_for_status()
          total = int(resp.headers.get("Content-Length", 0))
          async for chunk in resp.aiter_bytes(chunk_size=65536):
              ...  # write chunk, update progress with resp.num_bytes_downloaded
  ```
- **SSE / NDJSON:** `async for line in resp.aiter_lines():` (handles split
  chunks, universal newlines); raw variant `aiter_raw()`; text variant
  `aiter_text(chunk_size=...)`.
- **Uploads:** `files={"f": open("a.bin","rb")}` / `("name", bytes, "mime")` /
  `("name", fh, "mime", {"X-..": ".."})` 4-tuple; text-mode or `StringIO` files
  raise `TypeError`; unknown lengths fall back to chunked transfer. `content=<generator>`
  streams with `Transfer-Encoding: chunked`.
- **Decoders:** gzip/deflate always; `br`/`zstd` only with extras (absent here,
  so `Accept-Encoding` omits them — no failure mode).
- **Logging/trace:** stdlib logger `"httpx"` (INFO per request); low-level
  `extensions={"trace": fn(name, info)}` hook receives
  `connection.connect_tcp.*`, `http11/2.send_request_headers.*`,
  `...receive_response_headers.complete` events (see `_main.trace`).

### 12. CLI (`_main.py`, `httpx = httpx:main`)

```
httpx <URL> [-m METHOD] [-p NAME VALUE...] [-c TEXT] [-d NAME VALUE...]
  [-f NAME FILENAME...] [-j JSON] [-h NAME VALUE...] [--cookies NAME VALUE...]
  [--auth USER PASS] [--proxy URL] [--timeout FLOAT=5.0] [--follow-redirects]
  [--no-verify] [--http2] [--download FILE] [-v] [--help]
```

Streams via `client.stream`, pretty-prints (JSON indented, syntax-highlighted),
binary shown as `<N bytes>`, `--download` renders a progress bar, `-v` prints
request/response headers + TLS/connection trace, exit code 1 on error or
non-2xx. Useful for manually probing `UPDATE_CONFIG_URL` and release assets.

---

## App usage & correctness

Single real consumer: `src/services/update_service.py` (8–34); tests in
`tests/test_update_service.py`; callers `src/main.py:650` (manual
`check_update`) and `:716` (`_silent_update_check` at startup, via
`page.run_task`); logger quieted at `src/main.py:92`.

**Correct usage (keep):**

- `AsyncClient` (not `Client`) inside `async def` — no event-loop blocking.
- Explicit `timeout=4.0` — no call can hang forever (beats the `#1 mobile bug).
- `follow_redirects=True` — required: `raw.githubusercontent.com` 302-redirects to CDN.
- `async with` — pool closed, no socket leaks.
- Broad `except Exception → warning + None` — deliberately silent background check; tests pin this (`test_timeout_is_silent`, `test_bad_json_is_silent`, `test_404_is_silent`).
- Tests use the idiomatic seam: `httpx.MockTransport(handler)` (+ `httpx.Response(200, json=...)`, raising `httpx.ConnectTimeout("boom", request=request)`) — correct signatures.

**Misuses / bugs (file:line):**

1. `update_service.py:24` — `resp.status_code == 200` instead of
   `resp.raise_for_status()` + `HTTPStatusError` handling. Any non-200
   (206, 304, 403 rate-limit, 500) collapses to the same `None` as "up to
   date" — the UI then reports "running the latest version" (`main.py:656`)
   when it actually *failed*. Check `resp.is_success` / `raise_for_status()`
   and distinguish failure from current.
2. `update_service.py:32` — blanket `except Exception` also swallows
   programming errors: `data.get` raises `AttributeError` if the JSON is a
   list/string (`:25`), `int(...)` raises `ValueError/TypeError` on
   `"build_number": "abc"` (`:26`). Catch `httpx.HTTPError` + `ValueError`
   (+ `KeyError`) explicitly; validate `isinstance(data, dict)` first.
3. `update_service.py:22` — fresh `AsyncClient` per check builds and tears
   down a connection pool each launch (and twice per session: manual +
   silent check). Hoist to a module-level shared `AsyncClient` (or at minimum
   `base_url` + shared `Limits`), or use one-shot `httpx.get` honestly.
4. `update_service.py:25` — `resp.json()` parses an **unbounded** body into
   memory with no `Content-Length`/`Content-Type` sanity check. A
   compromised/hijacked manifest path could feed megabytes of JSON. Guard
   size (e.g. reject `Content-Length` > 64 KiB) before parsing.
5. `update_service.py:22` — `timeout=4.0` is a blunt uniform value barely
   below the 5.0 default; prefer `httpx.Timeout(connect=4.0, read=10.0, …)`
   so slow-CDN reads don't fail while connects stay tight.
6. `update_service.py:22` — `follow_redirects=True` with default
   `max_redirects=20`: up to 20 chained fetches per check. Cap with
   `max_redirects=3` and optionally inspect `resp.history`.
7. `update_service.py:26` — `int(data.get("build_number", 0))` trusts schema;
   missing key → `0` → "no update" even on a 200 with garbage payload. Validate
   presence/type and log a distinct warning for malformed manifests.
8. No `User-Agent` / client `headers=` identifying the app — GitHub sees generic
   `python-httpx/0.28.1`; set e.g. `headers={"User-Agent": f"FFmpegApp/{v} ..."}`.
9. No conditional request — manifest re-downloaded in full every launch; send
   `If-None-Match`/`If-Modified-Since` and honor 304 (needs `raise_for_status`
   rework since 304 isn't 2xx — handle explicitly).
10. No retry on transient failure — one `TimeoutException`/5xx/429 misses the
    update notice for the whole session. Add 1–2 retries with backoff on
    `httpx.TimeoutException` + 5xx/429 (httpx has no status retry; hand-roll or
    `HTTPTransport(retries=1)` for connect-level only).
11. `tests/test_update_service.py:20-27` — subclassing `AsyncClient` to inject
    the transport works but is fragile; simpler and more precise is
    `httpx.AsyncClient(transport=httpx.MockTransport(handler))` directly, plus
    asserting on `request.url`/`headers` inside the handler.

No `verify=False`, no sync `Client` on the UI path, no `http2=True` (would
crash — `h2` absent), no SOCKS proxy use (would crash — `socksio` absent).

---

## Underused APIs to adopt

1. **`httpx.Timeout(connect/read/write/pool)`** — granular timeouts; tight
   connect, generous read for CDN stalls.
2. **`resp.raise_for_status()` + `HTTPStatusError`** — replace `status_code == 200`.
3. **Exception ladder** (`TimeoutException` → retry; `NetworkError` → offline;
   `DecodingError`; `TooManyRedirects`) instead of one `except Exception`.
4. **Shared client + `Limits`** — one module-level `AsyncClient` with tuned
   `Limits(max_connections=…, max_keepalive_connections=…)`; kills per-check
   pool churn.
5. **`max_redirects=3` + `resp.history`** — bounded redirects, auditable chain.
6. **Streaming + `Content-Length` guard + `aiter_bytes(chunk_size=…)`** —
   size-cap the manifest today; the exact pattern a future in-app APK/asset
   downloader with progress bar needs (`num_bytes_downloaded` for progress).
7. **`resp.elapsed` + `event_hooks={"request":…, "response":…}`** — timing and
   structured logging for diagnostics without touching call sites.
8. **Client-level `base_url` + `headers=` + `params=` merging** — e.g.
   `base_url="https://raw.githubusercontent.com/Nwokike/FFmpeg/main/"`,
   app `User-Agent` once instead of per call.
9. **`MockTransport` assertions on the request** — assert URL/headers/method in
   handlers; also drives offline UI tests without monkeypatching classes.
10. **`codes` / `is_success` / `QueryParams` / `URL`** — `codes.is_success`,
    `resp.is_error`, typed URL/param building instead of string
    concatenation; `BasicAuth`/token `FunctionAuth`, `Proxy`/`mounts`,
    `extensions={"trace": …}` for deep debugging; top-level `httpx.get` for
    genuine one-offs; the `httpx` CLI for manual endpoint probing.

---

## Gotchas

- One-shot `httpx.get()` opens **and closes a pool per call** — never in loops.
- `Client`/`AsyncClient` are **single-use**: re-entering `async with` on the
  same instance raises `RuntimeError`; create one long-lived instance.
- `follow_redirects` defaults to **`False`** everywhere (top-level and client).
- Default timeout is **5.0s on all four operations** — nothing hangs by default,
  but `Timeout(None)` disables everything (avoid).
- Per-request `cookies=` emits `DeprecationWarning` — set cookies on the client.
- `data=<bytes/str>` emits `DeprecationWarning` — use `content=`.
- `QueryParams` is **immutable** (`q.set()` returns a copy); `Headers` joins
  duplicates with commas (use `get_list`/`multi_items` for `Set-Cookie`-style headers).
- Must read before `.content/.text/.json()` (`ResponseNotRead`); streams are
  single-shot (`StreamConsumed`); setting `.encoding` after `.text` → `ValueError`.
- Redirects rewrite POST→GET on 301/302/303 and **strip `Authorization`
  cross-origin** — re-auth explicitly if needed; check `response.history`.
- `response.json()` raises stdlib `JSONDecodeError` (`ValueError`), not an
  httpx error — catch it separately.
- `verify=False` kills TLS verification; `trust_env=True` (default) means env
  `*_PROXY`/`NO_PROXY` and `SSL_CERT_*` silently affect behavior — set
  `trust_env=False` for hermetic behavior.
- `http2=True` / `socks5://` proxies / `br` / `zstd` need uninstalled extras
  (`h2`, `socksio`, `brotli`, `zstandard`) — first two raise `ImportError` on
  use; the decoders degrade gracefully (never advertised).
- `DigestAuth` keeps nonce state — don't share one instance across threads.
- Sync handler in `MockTransport` works for both clients; an `async` handler
  under sync `Client` raises `TypeError`.
- `URL("http://h:80/") == URL("http://h/")` (default-port normalization);
  passwords masked in `repr`; `InvalidURL` on hosts/ports/overlong (>65536) URLs.
- `AsyncClient` event hooks must be **async** callables (sync ones are never awaited).
- `Response(elapsed)` only exists after read/close — accessing earlier raises `RuntimeError`.
- CLI exit code is 1 on transport error **or** non-2xx — script accordingly.
