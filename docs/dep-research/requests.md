# requests 2.34.2 — Complete API Reference

> **Purpose:** "Python HTTP for Humans" — a sync, urllib3-backed HTTP/1.1 client library.
> Installed at `<repo>\.venv\Lib\site-packages\requests`.
> Dist-info at `...\requests-2.34.2.dist-info\` (METADATA, RECORD, WHEEL, INSTALLER,
> `licenses/LICENSE`, `licenses/NOTICE`, `top_level.txt`, `REQUESTED`).
> All 19 `.py` files were read in full for this report.

## Files

| File | Role |
|---|---|
| `__init__.py` | Public surface; re-exports api fns, models, Session, exceptions, `codes`; runs `check_compatibility()` on urllib3/chardet/charset_normalizer at import; silences urllib3 `DependencyWarning`; installs `NullHandler` logging |
| `__version__.py` | `__version__ = "2.34.2"`, `__build__ = 0x023402`, title/author/license constants, `__cake__` |
| `api.py` | Module-level one-shot verbs: `request/get/options/head/post/put/patch/delete` |
| `sessions.py` | `Session`, `SessionRedirectMixin`, `merge_setting`, `merge_hooks`, deprecated `session()` factory |
| `models.py` | `Request`, `PreparedRequest`, `Response`, `RequestEncodingMixin`, `RequestHooksMixin`; `REDIRECT_STATI`, `DEFAULT_REDIRECT_LIMIT = 30`, `CONTENT_CHUNK_SIZE = 10*1024`, `ITER_CHUNK_SIZE = 512` |
| `adapters.py` | `BaseAdapter`, `HTTPAdapter` (urllib3 PoolManager wrapper); `DEFAULT_POOLSIZE = 10`, `DEFAULT_POOLBLOCK = False`, `DEFAULT_RETRIES = 0`, `DEFAULT_POOL_TIMEOUT = None` |
| `auth.py` | `AuthBase`, `HTTPBasicAuth`, `HTTPProxyAuth`, `HTTPDigestAuth`, `_basic_auth_str` |
| `cookies.py` | `RequestsCookieJar`, `MockRequest/MockResponse` (cookiejar bridge), `extract_cookies_to_jar`, `get_cookie_header`, `cookiejar_from_dict`, `merge_cookies`, `create_cookie`, `morsel_to_cookie`, `remove_cookie_by_name`, `CookieConflictError` |
| `exceptions.py` | Full hierarchy (below) + `RequestsWarning`, `FileModeWarning`, `RequestsDependencyWarning` |
| `structures.py` | `CaseInsensitiveDict`, `LookupDict` |
| `utils.py` | ~30 public helpers (below); `DEFAULT_PORTS = {"http": 80, "https": 443}`, `DEFAULT_ACCEPT_ENCODING`, `DEFAULT_CA_BUNDLE_PATH = certs.where()` |
| `status_codes.py` | `codes` LookupDict, ~60 statuses incl. aliases (`ok/okay/\o/`, `teapot`, `too_many`…) |
| `hooks.py` | `HOOKS = ["response"]`, `default_hooks()`, `dispatch_hook()` — `response` is the ONLY hook event |
| `certs.py` | Re-exports `certifi.where()` — one line: the CA bundle *is* certifi's |
| `compat.py` | Legacy Py2/3 shim kept for backwards compat: re-exports urllib compat (`quote`, `urlparse`, `getproxies`, `proxy_bypass`…), `chardet` resolver (tries `chardet`, falls back to `charset_normalizer`), `is_py2/is_py3`, `JSONDecodeError` (simplejson if present else stdlib json), `is_urllib3_1` flag |
| `_internal_utils.py` | `to_native_string`, `unicode_is_ascii`, `HEADER_VALIDATORS` regexes (header name/value validation) |
| `_types.py` | Internal-only type aliases (`TimeoutType = float | tuple[float|None, float|None] | None`, `AuthType`, `FilesType`, `RequestKwargs/GetKwargs/PostKwargs/DataKwargs` TypedDicts…). Explicitly **not public API** |
| `packages.py` | Back-compat alias shim: maps `requests.packages.urllib3|idna|chardet` onto the real installed modules |
| `help.py` | `info()` / `main()` — bug-report helper dumping platform, SSL, urllib3/chardet/charset_normalizer/cryptography/idna/requests versions as JSON |
| `py.typed` | PEP 561 marker — the package ships inline types |

No `__pycache__` counted (bytecode only). No other legacy modules exist.

## Metadata

From `METADATA` (Metadata-Version 2.4):

- **Name / Version:** `requests 2.34.2` — Summary "Python HTTP for Humans."
- **License:** `Apache-2.0` (license files: `licenses/LICENSE`, `licenses/NOTICE` — note: there is
  **no top-level `LICENSE` file**; `RECORD` lists `licenses/LICENSE`, hash
  `sha256:CeipvOyAZxBGUsFoaFqwkx54aPnIKEtm9a5u2uXxEws`).
- **Requires-Python:** `>=3.10` (classifiers list 3.10–3.15, CPython + PyPy, free-threading Beta).
- **Hard pins (all satisfied by the installed venv):**

  | Requirement | Installed | Status |
  |---|---|---|
  | `charset_normalizer<4,>=2` | 3.5.1 | OK |
  | `idna<4,>=2.5` | 3.20 | OK |
  | `urllib3<3,>=1.26` | 2.8.0 | OK |
  | `certifi>=2023.5.7` | 2026.07.22 | OK |

- **Extras:** `security`, `socks` (`PySocks!=1.5.7,>=1.5.6`), `use-chardet-on-py3` (`chardet<8,>=3.0.2`).
  No chardet installed here — charset detection goes through `charset_normalizer`.
- **Description:** long README body (usage samples, install notes); no console scripts.
- **Reverse deps in this venv** (who pulls requests in): `cookiecutter 2.7.1`
  (`Requires-Dist: requests>=2.23.0`, hard dep); `markdown_it_py` and `pytest` reference it only
  under `dev`/`testing` extras. `qrcode 8.2` is installed but its METADATA does **not** require
  requests. Nothing under `flet*.dist-info` requires it.

## Module-by-module API

### `requests.api` — one-shot top-level functions

Every verb builds a throwaway `Session` in a `with` block (`api.py:70-71`) — **no connection reuse
across calls**. All return `Response`; all accept the same `**kwargs` (`params/data/json/headers/
cookies/files/auth/timeout/allow_redirects/proxies/hooks/stream/verify/cert`).

```python
requests.request(method, url, **kwargs) -> Response
requests.get(url, params=None, **kwargs) -> Response            # redirects ON (default)
requests.options(url, **kwargs) -> Response                    # redirects ON
requests.head(url, **kwargs) -> Response                       # allow_redirects defaults False (api.py:113)
requests.post(url, data=None, json=None, **kwargs) -> Response
requests.put(url, data=None, **kwargs) -> Response
requests.patch(url, data=None, **kwargs) -> Response
requests.delete(url, **kwargs) -> Response
```

Defaults that matter: `allow_redirects=True` (except `head`), `stream=False` (body downloaded
immediately), `verify=True`, `timeout=None` (**no timeout — can hang forever**).

### `requests.sessions.Session` — the object to prefer

```python
s = requests.Session()  # or: with requests.Session() as s: ...
s.headers  # CaseInsensitiveDict, defaults: User-Agent python-requests/2.34.2,
#   Accept-Encoding (gzip/deflate/br/zstd), Accept: */*, Connection: keep-alive
s.auth  # None | (user, pass) tuple | AuthBase instance — applied to every request
s.proxies  # {} e.g. {"http": "http://proxy:3128", "http://host": "http://p:4012"}
s.hooks  # {"response": [...]}
s.params  # {} — merged into every request's query string
s.stream = False
s.verify = True
s.cert = None
s.max_redirects = 30  # DEFAULT_REDIRECT_LIMIT; exceed -> TooManyRedirects
s.trust_env = True  # honor HTTP(S)_PROXY/NO_PROXY, REQUESTS_CA_BUNDLE/CURL_CA_BUNDLE, netrc
s.cookies  # RequestsCookieJar, persisted across requests
s.adapters  # OrderedDict {"https://": HTTPAdapter(), "http://": HTTPAdapter()}
```

Methods (all verbs mirror `api` but default `Session.get/options` to `allow_redirects=True`,
`Session.head` to `False`):

```python
s.request(method, url, params=None, data=None, headers=None, cookies=None, files=None,
          auth=None, timeout=None, allow_redirects=True, proxies=None, hooks=None,
          stream=None, verify=None, cert=None, json=None) -> Response
s.get(url, params=None, **kwargs) / s.options(url, **kwargs) / s.head(url, **kwargs)
s.post(url, data=None, json=None, **kwargs) / s.put(url, data=None, **kwargs)
s.patch(url, data=None, **kwargs) / s.delete(url, **kwargs)
s.prepare_request(req: Request) -> PreparedRequest  # merges session+request settings
s.send(prep: PreparedRequest, **kwargs) -> Response # sends; ONLY accepts PreparedRequest
                                                    # (passing Request raises ValueError, sessions.py:768)
s.merge_environment_settings(url, proxies, stream, verify, cert) -> dict
s.get_adapter(url) -> BaseAdapter   # longest-prefix match; unknown scheme -> InvalidSchema
s.mount(prefix, adapter)            # adapters sorted longest-prefix-first
s.close()                           # closes pools; also via context manager / __exit__
```

Merging rules (`merge_setting`): request-level wins; dicts merge with request winning; a request
key set to `None` **deletes** the session key. `merge_hooks` concatenates response hooks.
Redirect engine (`SessionRedirectMixin.resolve_redirects`): follows `REDIRECT_STATI`
(301/302/303/307/308); 303 → GET (non-HEAD), 302 → GET (non-HEAD), 301 POST → GET; strips
`Content-Length/Content-Type/Transfer-Encoding` + body except on 307/308; strips `Cookie` and
re-resolves the jar; **strips `Authorization` on cross-host/port/scheme change**
(`should_strip_auth`; http→https on standard ports is allowed); re-applies netrc + proxies;
`r.history` oldest→newest; with `allow_redirects=False`, `Response.next` holds the next
`PreparedRequest`.

### `requests.models` — `Request` / `PreparedRequest` / `Response`

```python
Request(method=None, url=None, headers=None, files=None, data=None, params=None,
        auth=None, cookies=None, hooks=None, json=None)
req.prepare() -> PreparedRequest
req.register_hook(event, hook) / req.deregister_hook(event, hook) -> bool
# event must be "response" else ValueError
```

`PreparedRequest.prepare(method, url, headers, files, data, params, auth, cookies, hooks, json)` —
order matters, `prepare_auth` runs last so auth schemes see the full request. URL prep:
bytes→utf-8, strips leading whitespace, non-`http` schemes (`mailto:`, `data:`) pass through
untouched, IDNA-encodes unicode hosts (`*.`/`.foo` hosts → `InvalidURL`), missing scheme →
`MissingSchema` ("Perhaps you meant https://…?"), missing host → `InvalidURL`, `params` merged
into query, full URL re-quoted via `requote_uri`. Body rules: `json=` serializes with
`allow_nan=False` (`InvalidJSONError` on NaN — strict) + `Content-Type: application/json`;
dict/list data → url-encoded + `Content-Type: application/x-www-form-urlencoded`;
`files=` → multipart (`_encode_files`; 2/3/4-tuples `(filename, fp[, content_type[, headers]])`),
and **`files` + streamed body raises `NotImplementedError`**; non-GET/HEAD with empty body gets
`Content-Length: 0`; text-mode file bodies trigger `FileModeWarning` length caveats.
`prepare_auth`: tuple → `HTTPBasicAuth`; URL-embedded `user:pass@` used when no explicit auth.
`prepare_cookies` fires once — Cookie header is not regenerated while one exists.

`Response` attributes: `status_code: int`, `headers: CaseInsensitiveDict`, `raw`, `url`,
`encoding` (from headers; `None` → auto-detect on `.text`), `history: list[Response]`,
`reason`, `cookies: RequestsCookieJar`, `elapsed: timedelta` (send→headers only, not content),
`request: PreparedRequest`, `connection: HTTPAdapter`. Key members:

```python
r.ok / bool(r)            # status_code < 400 — NOT "== 200"
r.is_redirect             # "location" in headers and status in REDIRECT_STATI
r.is_permanent_redirect   # 301 or 308 with location
r.next                    # next PreparedRequest when redirects not followed
r.content -> bytes        # downloads + caches; consumed-stream re-access raises RuntimeError
r.text -> str             # headers charset, else apparent_encoding, errors="replace"
r.json(**kwargs) -> Any   # BOM-aware (utf-8-sig/16/32); raises requests.JSONDecodeError
r.links                   # parsed Link header -> {rel|url: {...}}
r.raise_for_status()      # 4xx -> "N Client Error…", 5xx -> "N Server Error…", raises HTTPError
r.apparent_encoding       # charset_normalizer/chardet guess, else "utf-8"
r.iter_content(chunk_size=1, decode_unicode=False)  # stream=True friendly; chunk_size=None:
                          # as-arrived if streaming else single chunk; StreamConsumedError if
                          # raw consumed and _content is bool; TypeError on non-int chunk_size
r.iter_lines(chunk_size=512, decode_unicode=False, delimiter=None)  # not reentrant-safe
r.close()                 # release conn to pool; with-statement supported
iter(r) == r.iter_content(128)
```

### Auth (`auth.py`)

```python
requests.auth.HTTPBasicAuth(username, password)   # sets Authorization: Basic <b64(user:pass)> (latin-1)
requests.auth.HTTPProxyAuth(username, password)   # sets Proxy-Authorization instead
requests.auth.HTTPDigestAuth(username, password)  # RFC-2617 digest, MD5/MD5-SESS/SHA/SHA-256/SHA-512;
                                                  # per-thread state (nonce_count, chal); auto-retries
                                                  # the 401 handshake (max 2), rewinds seekable bodies;
                                                  # qop=auth-int NOT implemented (returns None)
class AuthBase:  def __call__(self, r: PreparedRequest) -> PreparedRequest  # subclass hook
```

Shorthands: `auth=("user", "pass")` tuple ≡ Basic; any callable `(PreparedRequest)->PreparedRequest`
works as custom auth. `http://user:pass@host/` URLs also authenticate. Netrc (`~/.netrc`/`~/_netrc`
or `$NETRC`) is consulted when `trust_env` and no explicit auth.

### Timeouts & `HTTPAdapter` (`adapters.py`)

`timeout` accepts `float` (both phases), `(connect, read)` tuple with either `None`, or a urllib3
`Timeout` object; a malformed tuple raises `ValueError`. Maps to `ConnectTimeout` (safe to retry)
vs `ReadTimeout`. **urllib3 retries (`max_retries`) cover only DNS/connect/timeouts — never
requests whose data reached the server** (`DEFAULT_RETRIES = 0` → `Retry(0, read=False)`).

```python
HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0, pool_block=False)
a = HTTPAdapter(max_retries=3)
s.mount("https://", a)
s.mount("https://api.example.com/", HTTPAdapter(pool_connections=20, pool_maxsize=20))
# or urllib3 Retry for granular control:
from urllib3.util.retry import Retry

Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
```

Custom-adapter seams: `init_poolmanager`, `proxy_manager_for`, `cert_verify`, `build_response`,
`build_connection_pool_key_attributes`, `get_connection_with_tls_context`
(`get_connection` is **deprecated** since 2.32.2), `request_url`, `add_headers`, `proxy_headers`.
`verify`: `True` (certifi bundle) | `False` (**disables TLS verification — MitM-vulnerable, test
only**) | path to CA bundle/dir; `REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` env override when
`trust_env`. `cert`: path or `(cert, key)` tuple for mTLS. SOCKS proxies need the `socks` extra;
malformed proxy URL → `InvalidProxyURL`.

### Cookies (`cookies.py`)

`RequestsCookieJar(CookieJar, MutableMapping)`: dict-style `jar["name"]`, `.get/.set` (with
`domain=`/`path=` to disambiguate), `.keys/.values/.items`, `get_dict(domain, path)`,
`list_domains/list_paths/multiple_domains`, pickleable (unlike stdlib jars).
`jar["dup"]` with duplicates → `CookieConflictError` (use `.get(name, domain=…, path=…)`).
Helpers: `cookiejar_from_dict(d, jar=None, overwrite=True)`, `merge_cookies(jar, cookies)`,
`create_cookie(name, value, **kwargs)` (defaults: domain `""`, path `/`, discardable
"supercookie"), `dict_from_cookiejar`, `add_dict_to_cookiejar`, `morsel_to_cookie`,
`remove_cookie_by_name`. Session jars persist + auto-update from `Set-Cookie` on every response
(including redirect hops).

### Exceptions (`exceptions.py`) — catch order matters

```
RequestException(IOError)  [has .response / .request attrs]
├── InvalidJSONError
│   └── JSONDecodeError(InvalidJSONError, json.JSONDecodeError)  # from Response.json()
├── HTTPError                       # from raise_for_status()
├── ConnectionError
│   ├── ProxyError
│   ├── SSLError
│   └── ConnectTimeout(ConnectionError, Timeout)   # safe to retry
├── Timeout
│   ├── ConnectTimeout (see above)
│   └── ReadTimeout
├── URLRequired
├── TooManyRedirects
├── MissingSchema(ValueError) / InvalidSchema(ValueError) / InvalidURL(ValueError)
│   └── InvalidProxyURL(InvalidURL)
├── InvalidHeader(ValueError)
├── ChunkedEncodingError / ContentDecodingError / StreamConsumedError(TypeError)
├── RetryError / UnrewindableBodyError
└── warnings: RequestsWarning → FileModeWarning, RequestsDependencyWarning
```

Catch `requests.RequestException` to cover all network failures; put `ConnectTimeout`/`ReadTimeout`
before `Timeout`/`ConnectionError` (a bare `except Timeout` swallows both). Note
`MissingSchema/InvalidSchema/InvalidURL/InvalidHeader` also subclass `ValueError`.

### Hooks (`hooks.py`)

Only event: `"response"`. `hooks={"response": fn_or_list}` per request, merged with session hooks;
each `fn(response, **kwargs) -> response|None` (return value replaces it when not `None`).
`HTTPDigestAuth` itself is implemented as response hooks (`handle_401`, `handle_redirect`).

### `utils.py` helpers worth knowing

`get_encoding_from_headers` (charset → text/*→ISO-8859-1 → application/json→utf-8),
`get_encodings_from_content` + `get_unicode_from_response` (**deprecated**, warn for 3.0 removal),
`requote_uri` / `unquote_unreserved`, `prepend_scheme_if_needed`, `urldefragauth` (strip
fragment + `user:pass@`), `get_auth_from_url`, `select_proxy` / `resolve_proxies` /
`should_bypass_proxies` (NO_PROXY incl. CIDR) / `get_environ_proxies`, `default_headers`,
`default_user_agent`, `parse_header_links` (backs `Response.links`), `parse_list_header` /
`parse_dict_header` / `unquote_header_value`, `guess_json_utf` (BOM sniffer),
`iter_slices`, `stream_decode_response_unicode`, `super_len`, `to_key_val_list` /
`from_key_val_list` / `dict_to_sequence`, `guess_filename`, `extract_zipped_paths`,
`atomic_open`, `set_environ` (ctx manager), `check_header_validity` (bad headers →
`InvalidHeader`), `rewind_body`, `dotted_netmask` / `address_in_network` / `is_ipv4_address` /
`is_valid_cidr`, `get_netrc_auth`, `dict_from_cookiejar` / `add_dict_to_cookiejar`.

### Status codes (`status_codes.py`)

`requests.codes.ok == codes.okay == 200`, `codes.teapot == 418`, `codes.temporary_redirect == 307`,
`codes.too_many_requests == 429`, `codes.not_found == 404`, `codes.moved_permanently == 301`,
`codes.found == 302`, `codes.see_other == 303`, `codes.gateway_timeout == 504`… attribute
(case-insensitive: `codes.OK`) or item (`codes["temporary_redirect"]`) access; unknown names
return `None` (LookupDict fall-through — **no KeyError**, so typos fail silently).

## App usage & correctness

Grep over `src/` and `tests/` for `import requests|from requests` returns **zero hits** — the app
never imports requests directly. The only HTTP client in app code is **httpx**:

- `src/services/update_service.py:8,22` — `httpx.AsyncClient(timeout=4.0, follow_redirects=True)`
  fetching `UPDATE_CONFIG_URL`, `status_code == 200` check, `.json()`, broad `except Exception`
  → silent skip with `logger.warning`. Correct async usage for a Flet (async UI loop) app.
- `src/main.py:92` — only silences `httpx/httpcore/urllib3` loggers.
- `tests/test_update_service.py` — mocks via `httpx.MockTransport`; `httpx.ConnectTimeout`,
  `httpx.Response(404)`, malformed-JSON cases covered.

Dependency facts: `pyproject.toml` declares `httpx>=0.28.1` and **does not declare requests**.
requests 2.34.2 is present **transitively** — hard-required by `cookiecutter>=2.23.0`
(`cookiecutter-2.7.1.dist-info/METADATA:35`); `markdown_it_py`/`pytest` reference it only via
`dev`/`testing` extras. So the brief's "via qrcode/cookiecutter" is half-right: cookiecutter is
the carrier; qrcode 8.2 does not require it.

**(a) Correct usage:** no direct requests usage, so nothing to praise or blame; the httpx call
site sets an explicit timeout and follows redirects — both correct.

**(b) MISUSE:** none involving requests — no file:line to flag, and crucially **no
requests+httpx mixing** (the design smell does not exist here). Adjacent non-requests nits, for
the rewrite pass only: `update_service.py:24` checks `status_code == 200` instead of
`raise_for_status()`/2xx-range (a 204/304 manifest would be silently ignored); `:32` catches
bare `Exception`, which also swallows programming errors (e.g. `int()` on a non-numeric
`build_number`).

**(c) Recommendation:** keep it that way — **do not adopt requests for app code**. It is a *sync*
urllib3 client with no async support; every call would block Flet's event loop on mobile, while
httpx already provides `AsyncClient`, connection pooling, timeouts, and `MockTransport`
testability. Leave requests as an undeclared transitive dep (via cookiecutter); do **not** add it
to `pyproject.toml` unless app code actually imports it. If a future sync context ever needs it,
the only APIs that would matter are: one shared `Session` (never top-level `api.*` in a loop),
always pass `timeout=`, `raise_for_status()`, and `stream=True` + `iter_content` for downloads.

## Underused APIs to adopt

Nothing to adopt — adoption itself is the anti-goal (see above). For the record, the highest-value
requests APIs *if the package were ever used directly* would be: `Session` reuse + `mount()` with
a tuned `HTTPAdapter` (pool sizes/retries), explicit `(connect, read)` timeout tuples,
`Response.raise_for_status()`, `stream=True` with `iter_content`/`iter_lines` for large payloads,
`requests.codes.*` symbolic statuses, `auth=(user, pass)` shorthand, per-request
`hooks={"response": …}`, and `RequestsCookieJar.get_dict()`. Their httpx equivalents are already
in play.

## Gotchas

1. **No timeout by default** — `timeout=None` hangs forever; always pass `timeout=` (float or
   `(connect, read)`; either leg may be `None`).
2. **Top-level `requests.get(…)` opens a new Session per call** — no pooling; reuse one `Session`
   for repeated hosts, `close()` it (or use `with`).
3. **`head()` disables redirects by default** (`allow_redirects=False`) — unlike every other verb.
4. **`Response.ok` / `bool(r)` means `< 400`, not `== 200`.** 3xx counts as "ok".
5. **`codes.anything_typo` returns `None`**, never raises — silent failures on misspelled names.
6. **`Response.json()` raises `requests.JSONDecodeError`** (subclasses both `InvalidJSONError` and
   stdlib `json.JSONDecodeError`) — catch that, not `ValueError` alone… though note the Invalid*
   URL/header errors *are* `ValueError`s, so broad `except ValueError` catches URL bugs too.
7. **`json=` rejects NaN** (`allow_nan=False` → `InvalidJSONError`); `data=` dicts become
   form-encoded, not JSON.
8. **`files=` + streamed/generator body → `NotImplementedError`**; open files in **binary** mode
   or risk wrong `Content-Length` (`FileModeWarning`).
9. **Auth is stripped on cross-host/port/scheme redirects** — multi-host flows need re-auth or a
   custom `rebuild_auth`.
10. **`verify=False` disables TLS verification** (MitM risk); `REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE`
    env vars silently override `verify=True` when `trust_env`.
11. **`Session.send()` accepts ONLY `PreparedRequest`** (`ValueError` otherwise); `Session` instances
    are not safe to mutate concurrently across threads — share via one session per thread or lock.
12. **Compat/import traps:** `requests.packages.*` are mere aliases of the real urllib3/idna;
    `compat.is_urllib3_1` is `False` here (urllib3 2.8.0) which changes `super_len` str handling;
    `get_encodings_from_content` / `get_unicode_from_response` are deprecated (3.0 removal);
    `HTTPAdapter.get_connection` is deprecated in favor of `get_connection_with_tls_context`.
