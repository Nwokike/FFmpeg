# Transitive dependencies — audit reference

Pinned only via `flet`/`httpx`; none in `pyproject.toml` direct deps.
None should be promoted to direct unless app code imports it.

## msgpack 1.2.2

Binary serializer (C ext + pure-Python fallback): `pack/packb/unpack/
unpackb`, `Packer/Unpacker`, `ExtType/Timestamp`. Flet hard-requires
`msgpack>=1.1.0`. Role: Python↔Dart wire-protocol codec
(`flet/messaging/protocol.py`: `packb` with dataclass/enum/datetime/
Duration handler, `ExtType(1/2/3)` for date/time/Duration,
`MessageAction` 1–7, `Message=[action,body]`; transports
`flet_socket_server/dart_bridge/pyodide_connection`: `[u32LE][0x00]
[msgpack body]`). App direct use: NONE (grep zero). App JSON stays
JSON: probe `caps3.json` (keep — debuggable, tiny, probe dominates),
`storage.json` (must stay JSON — user-debuggable), ffprobe stdout
(must stay JSON — FFmpeg's format), thumbnails already binary.
Recommendation: keep as transitive, do not promote.

## oauthlib 3.3.1

OAuth1 (RFC5849) + OAuth2 (RFC6749 clients/endpoints/grants, RFC8628
device flow) + OpenID. Parent: `flet==1.0.3` only
(`Requires-Dist: oauthlib>=3.2.2; sys_platform != 'emscripten'`).
Flet consumes in `auth/authorization_service.py`
(`WebApplicationClient`: authorize URLs, callback parse, token
exchange); providers: github/google/azure/auth0. App use: IDLE —
no `flet.auth`/`page.login`/OAuth imports anywhere; GitHub links are
plain browser URLs; update manifest is anonymous raw-json poll.
Retention: cannot prune (non-optional outside Emscripten); ~160KB
disk only, `WebApplicationClient` imported lazily (no import-time
cost). Future (not now): authenticated `api.github.com` checks
(60→5000/hr) if rate limits ever bite; no accounts/server today so
no bearer-token story.

## repath 0.9.0 (+ six)

Single-module Express-style route compiler (`parse/pattern/compile/
match/template`, grammar `/:id/*/:slug*/(\d+)/?/+`). Flet hard-requires
`repath>=0.9.0`. Used by `flet/components/router.py` (index exact,
recursive prefix, child/leaf matching → `re.match` + `groupdict`) and
`flet/controls/template_route.py`. App direct use: NONE — single-view
by design, `test_routes.py:66-70` forbids `ft.Router`. Route-like
strings (`/blank` underlay, `?back=` suffix) are manual split/format,
never `repath`. One plausible use: `ffmpeg://app/...` deep-link param
parsing (`scheme=ffmpeg host=app` declared, no parameterized matching
today) — but that means adopting the Router just removed. Cost: ~8KB,
cannot trim. Hygiene: stale upstream (Py2-era six, beta classifier,
docstring typo) but stable.

## anyio 4.15.1 / httpcore 1.0.9 / h11 0.16.0 / certifi 2026.7.22 / idna 3.20

All transitive via `httpx==0.28.1`. Roles: anyio = async backend for
AsyncClient (asyncio loop here; no trio in venv); httpcore = pooled
connections/TLS/retries under httpx; h11 = HTTP/1.1 state machine;
certifi = Mozilla CA bundle (`verify=True` default both call sites);
idna = IDNA2008/UTS-46 host encoding (automatic, no app code).
App: never imported directly; async path = update_service AsyncClient
(manifest probe — all five engage invisibly); sync path =
engine_service Client (HLS — anyio idle, rest work synchronously).
Notes: certifi ~2 months old (fresh); both HTTPS sites rely on implicit
`verify=True` — if TLS starts failing while desktop passes, suspect the
packaged `cacert.pem` on Mobile Forge first. anyio ready for async HLS
(update path shares one transport — second AsyncClient consumer needs
its own lifecycle). idna covers Unicode HLS hosts via urljoin'd
absolute segment URLs with no app code.
