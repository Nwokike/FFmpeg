# httpx 0.28.1 + transport stack — audit reference

## httpx relevant surface

Streaming/request: `Client.stream/AsyncClient.stream`,
`request/send/get/head/post/put/patch/delete` (all take
headers/params/auth/timeout/follow_redirects). Response:
`iter_bytes(chunk_size)/iter_text/iter_lines/iter_raw` + async mirrors,
`read/aread`, `raise_for_status`, `.text/.json/.content`. No
HLS/Range helper — Range is just `headers={"Range": ...}` + 206
handling. Timeouts: `Timeout(connect/read/write/pool)`; tuple form
maps (connect,read,write,pool), missing → None (no timeout);
`DEFAULT_TIMEOUT_CONFIG=Timeout(5.0)`. Hierarchy
`TimeoutException→Connect/Read/Write/PoolTimeout`. Retries/pool:
`HTTPTransport/AsyncHTTPTransport(retries=0)` (transport-level
idempotent only, no backoff); `Limits(max_connections/
max_keepalive/keepalive_expiry)`, `DEFAULT_LIMITS=Limits(100,20)`,
`DEFAULT_MAX_REDIRECTS=20`, `http1=True,http2=False`. Proxy/TLS/auth:
`Proxy(url/ssl_context/auth/headers)` (http/https/socks5);
`Client(proxy/verify=True/cert/trust_env=True)`; `BasicAuth/DigestAuth/
NetRCAuth`. Exceptions: `NetworkError→Connect/Read/Write/CloseError`,
`ProxyError/UnsupportedProtocol/ProtocolError/DecodingError/
TooManyRedirects/HTTPStatusError/StreamConsumed/Closed`.

## Used by app

HLS fetch (engine_service): `_hls_fetch_text` (get + raise + .text);
`_hls_download_segment` (stream + raise + iter_bytes + HTML sniff);
`_download_hls_segments` (sequential, 256K chunks, 32K min guard,
master→media recursion); `_open_https_via_httpx` (fresh Client per
download, probe stream + 512B `#EXTM3U` sniff, second stream for
non-HLS body — double-GET); record maps Timeout→ValueError,
HTTPStatus→ValueError, HTTPError→ValueError (no NetworkError/
TooManyRedirects/DecodingError branches). Update check
(update_service): explicit 4-phase `Timeout(3/4/4/2)`,
`AsyncHTTPTransport(retries=2)`, pooled singleton AsyncClient,
`get(UPDATE_CONFIG_URL)` + raise; catches Timeout/NetworkError/
HTTPStatusError. main.py:118 silences httpx/httpcore loggers.

## Unused

Range resume (zero `Range`/206 usage; failed segment restarts at 0).
Pooling asymmetry (update pooled; HLS fresh Client per call, default
limits, no http2, sequential segments). HEAD preflight (full GET +
sniff + discard + re-GET). Retries (HLS `retries=0`; one transient
ReadError aborts playlist; TooManyRedirects/DecodingError/RemoteProtocol
unhandled despite follow_redirects). Timeout inconsistency (engine
tuple leaves write/pool unbounded; PoolTimeout never caught).
Proxy/auth/TLS (Proxy/trust_env/verify/Basic/Digest/NetRC never
instantiated; authed/private HLS + GitHub-token manifest unexercised).
