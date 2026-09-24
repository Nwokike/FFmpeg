# oauthlib 3.3.1 — Complete API Reference

> A generic, spec-compliant, thorough implementation of the OAuth request-signing
> logic for Python. Framework-agnostic: implements OAuth1 (RFC 5849), OAuth2
> (RFC 6749), Device flow (RFC 8628) and OpenID Connect (core) client + server
> logic without assuming any HTTP library or web framework. Thin veneers
> (`requests-oauthlib`, `flet/auth`, `django-oauth-toolkit`, …) graft it onto
> real transports.

---

## Files

75 `.py` files (excluding `__pycache__`) under
`.venv/Lib/site-packages/oauthlib/`, plus dist-info with 82 RECORD entries.

**Top level (4)**

| File | Contents |
|---|---|
| `__init__.py` | `__version__ = '3.3.1'`, `set_debug(bool)`, `get_debug()` |
| `common.py` | Shared utils + `Request` + `CaseInsensitiveDict` |
| `signals.py` | `scope_changed` signal (blinker or noop fallback) |
| `uri_validate.py` | RFC 3986 regexes: `is_uri`, `is_uri_reference`, `is_absolute_uri` |

**OAuth1 — RFC 5849 (16)**

```
oauth1/__init__.py                      # re-exports Client, SIGNATURE_*, endpoints, errors
oauth1/rfc5849/__init__.py              # Client + SIGNATURE_* constants
oauth1/rfc5849/signature.py             # base-string, HMAC/RSA/PLAINTEXT sign+verify
oauth1/rfc5849/parameters.py            # prepare_headers / form body / URI query
oauth1/rfc5849/utils.py                 # escape, parse_authorization_header, filters
oauth1/rfc5849/errors.py                # OAuth1Error + 4 subclasses
oauth1/rfc5849/request_validator.py     # server-side RequestValidator (dummy_* helpers)
oauth1/rfc5849/endpoints/__init__.py
oauth1/rfc5849/endpoints/base.py        # BaseEndpoint (_create_request, _check_* )
oauth1/rfc5849/endpoints/request_token.py
oauth1/rfc5849/endpoints/authorization.py
oauth1/rfc5849/endpoints/access_token.py
oauth1/rfc5849/endpoints/resource.py
oauth1/rfc5849/endpoints/signature_only.py
oauth1/rfc5849/endpoints/pre_configured.py  # WebApplicationServer (all-in-one)
```

**OAuth2 — RFC 6749 (28)**

```
oauth2/__init__.py                      # public façade: clients, servers, errors, grants
oauth2/rfc6749/__init__.py              # (consuming-logic docstring module)
oauth2/rfc6749/clients/__init__.py
oauth2/rfc6749/clients/base.py          # Client (token mgmt, PKCE helpers)
oauth2/rfc6749/clients/web_application.py      # authorization-code flow
oauth2/rfc6749/clients/mobile_application.py   # implicit flow
oauth2/rfc6749/clients/legacy_application.py   # resource-owner password flow
oauth2/rfc6749/clients/backend_application.py  # client-credentials flow
oauth2/rfc6749/clients/service_application.py  # JWT-bearer flow
oauth2/rfc6749/parameters.py            # prepare/parse grant, token, revocation
oauth2/rfc6749/tokens.py                # OAuth2Token, BearerToken, bearer/MAC helpers
oauth2/rfc6749/errors.py                # OAuth2Error + ~25 subclasses + raise_from_error
oauth2/rfc6749/utils.py                 # list_to_scope, scope_to_list, is_secure_transport …
oauth2/rfc6749/request_validator.py     # server-side RequestValidator (~25 methods)
oauth2/rfc6749/grant_types/__init__.py
oauth2/rfc6749/grant_types/base.py      # GrantTypeBase, ValidatorsContainer
oauth2/rfc6749/grant_types/authorization_code.py  # + PKCE S256/plain helpers
oauth2/rfc6749/grant_types/implicit.py
oauth2/rfc6749/grant_types/refresh_token.py
oauth2/rfc6749/grant_types/client_credentials.py
oauth2/rfc6749/grant_types/resource_owner_password_credentials.py
oauth2/rfc6749/endpoints/__init__.py
oauth2/rfc6749/endpoints/base.py        # BaseEndpoint + catch_errors_and_unavailability
oauth2/rfc6749/endpoints/authorization.py
oauth2/rfc6749/endpoints/token.py
oauth2/rfc6749/endpoints/resource.py
oauth2/rfc6749/endpoints/revocation.py  # RFC 7009
oauth2/rfc6749/endpoints/introspect.py  # RFC 7662
oauth2/rfc6749/endpoints/metadata.py    # RFC 8414 discovery
oauth2/rfc6749/endpoints/pre_configured.py  # Server + 4 single-grant servers
```

**OAuth2 Device flow — RFC 8628 (7)**

```
oauth2/rfc8628/__init__.py
oauth2/rfc8628/clients/__init__.py
oauth2/rfc8628/clients/device.py        # DeviceClient
oauth2/rfc8628/grant_types/__init__.py
oauth2/rfc8628/grant_types/device_code.py
oauth2/rfc8628/endpoints/__init__.py
oauth2/rfc8628/endpoints/device_authorization.py  # DeviceAuthorizationEndpoint
oauth2/rfc8628/endpoints/pre_configured.py        # DeviceApplicationServer
oauth2/rfc8628/request_validator.py     # thin OAuth2RequestValidator subclass
oauth2/rfc8628/errors.py                # authorization_pending / slow_down / expired_token / access_denied
```

**OpenID Connect core (14)**

```
openid/__init__.py
openid/connect/__init__.py
openid/connect/core/__init__.py
openid/connect/core/request_validator.py  # adds get_id_token, finalize_id_token, validate_jwt_bearer_token …
openid/connect/core/exceptions.py         # OpenIDClientError family + raise_from_error
openid/connect/core/tokens.py             # JWTToken(TokenBase)
openid/connect/core/grant_types/__init__.py
openid/connect/core/grant_types/base.py   # OpenIDConnectBase proxy (add_id_token, id_token_hash)
openid/connect/core/grant_types/authorization_code.py
openid/connect/core/grant_types/implicit.py
openid/connect/core/grant_types/hybrid.py         # HybridGrant (code+token/id_token combos)
openid/connect/core/grant_types/refresh_token.py
openid/connect/core/grant_types/dispatchers.py    # AuthorizationCode/Implicit/AuthorizationToken dispatchers
openid/connect/core/endpoints/__init__.py
openid/connect/core/endpoints/userinfo.py         # UserInfoEndpoint
openid/connect/core/endpoints/pre_configured.py   # OIDC Server
```

---

## Metadata

From `oauthlib-3.3.1.dist-info/METADATA` (+ `WHEEL`, `INSTALLER`, `licenses/LICENSE`):

| Field | Value |
|---|---|
| Name / Version | `oauthlib` / `3.3.1` |
| Summary | "A generic, spec-compliant, thorough implementation of the OAuth request-signing logic" |
| License | **BSD-3-Clause** (`License-File: LICENSE`, `licenses/LICENSE` present) |
| Requires-Python | `>=3.8` (classifiers list 3.8–3.13; runs on the app's Python 3.14) |
| Platform | `any`; pure-Python wheel (`py3-none-any`) |
| Hard runtime deps | **none** — zero `Requires-Dist` outside extras |
| Extra `rsa` | `cryptography>=3.0.0` |
| Extra `signedtoken` | `cryptography>=3.0.0`, `pyjwt<3,>=2.0.0` |
| Extra `signals` | `blinker>=1.4.0` |
| `REQUESTED` | absent/empty → **not a direct dependency** (purely transitive) |
| Installed size | ~160 kB wheel; sdist 2025-06-19 |

None of the three extras is installed in this venv (no `cryptography`, no
`pyjwt`/`jwt`, no `blinker`). Consequence: RSA-SHA1/256/512 signing, JWT
`signed_token_generator` / `ServiceApplicationClient`, and real blinker
signals all degrade (ImportError at call time, or silent noop for signals).

---

## Module-by-module API

### 1. `oauthlib` top level

```python
__version__: str  # '3.3.1'
def set_debug(debug_val: bool) -> None
def get_debug() -> bool
```

`Request.__repr__` is sanitized unless `set_debug(True)` (tokens/passwords
redacted otherwise). Logging goes to the `oauthlib` logger with a
`NullHandler` attached.

### 2. `oauthlib.common` — shared primitives

```python
UNICODE_ASCII_CHARACTER_SET: str   # a-zA-Z0-9
CLIENT_ID_CHARACTER_SET: str       # RFC 6749 Appendix A printable range
SANITIZE_PATTERN, INVALID_HEX_PATTERN  # compiled regexes

def quote(s, safe=b'/') -> str
def unquote(s) -> str
def urlencode(params) -> str
def encode_params_utf8(params: list[tuple]) -> list[tuple[bytes, bytes]]
def decode_params_utf8(params) -> list[tuple[str, str]]
def urldecode(query: str) -> list[tuple[str, str]]   # raises ValueError on bad encoding
def extract_params(raw) -> list[tuple] | None        # str|dict|2-tuples → 2-tuples
def generate_nonce() -> str                          # 64-bit rand + timestamp
def generate_timestamp() -> str                      # int(time.time())
def generate_token(length=30, chars=UNICODE_ASCII_CHARACTER_SET) -> str  # SystemRandom
def generate_signed_token(private_pem, request) -> str   # needs pyjwt (signedtoken extra)
def verify_signed_token(public_pem, token) -> dict       # needs pyjwt
def generate_client_id(length=30, chars=CLIENT_ID_CHARACTER_SET) -> str
def add_params_to_qs(query: str, params) -> str
def add_params_to_uri(uri: str, params, fragment=False) -> str
def safe_string_equals(a: str, b: str) -> bool           # near-constant-time compare
def to_unicode(data, encoding='UTF-8')

class CaseInsensitiveDict(dict): ...   # proxy-based; get/__getitem__/__setitem__/__delitem__/update
class Request:
    def __init__(self, uri, http_method='GET', body=None, headers=None, encoding='utf-8')
    # .uri, .http_method, .headers (CaseInsensitiveDict), .body, .decoded_body,
    # .oauth_params, .validator_log; dynamic attrs via __getattr__:
    # access_token, client, client_id, client_secret, code, code_challenge(_method),
    # code_verifier, grant_type, redirect_uri, refresh_token, response_type,
    # scope/scopes, state, token, user, nonce, claims, max_age, ui_locales,
    # id_token_hint, login_hint, acr_values, response_mode, display, prompt …
    @property uri_query -> str
    @property uri_query_params -> list[tuple]
    @property duplicate_params -> list[str]
```

Example:

```python
from oauthlib.common import Request, generate_token

req = Request(
    "https://api.example.com/r?a=1", "POST", body="grant_type=client_credentials", headers={}
)
req.decoded_body  # [('grant_type', 'client_credentials')]
generate_token()  # e.g. 'k2f9Q…'(30 chars)
```

### 3. `oauthlib.signals` and `oauthlib.uri_validate`

```python
# signals.py
scope_changed = _signals.signal('scope-changed')  # blinker if installed else _FakeSignal
signals_available: bool
# usage: scope_changed.send(message=..., old=[...], new=[...])
# Without blinker, .send() is a noop; .connect() raises RuntimeError.

# uri_validate.py  (RFC 3986 ABNF-derived regexes, use with re.VERBOSE)
def is_uri(uri) -> re.Match | None
def is_uri_reference(uri) -> re.Match | None
def is_absolute_uri(uri) -> re.Match | None
```

### 4. OAuth1 (RFC 5849) — `oauthlib.oauth1`

Constants:

```python
SIGNATURE_HMAC_SHA1 = "HMAC-SHA1"
SIGNATURE_HMAC_SHA256 = "HMAC-SHA256"
SIGNATURE_HMAC_SHA512 = "HMAC-SHA512"
SIGNATURE_HMAC = SIGNATURE_HMAC_SHA1              # deprecated alias
SIGNATURE_RSA_SHA1 = "RSA-SHA1"
SIGNATURE_RSA_SHA256 = "RSA-SHA256"
SIGNATURE_RSA_SHA512 = "RSA-SHA512"
SIGNATURE_RSA = SIGNATURE_RSA_SHA1                # deprecated alias
SIGNATURE_PLAINTEXT = "PLAINTEXT"
SIGNATURE_METHODS = (all seven above)
SIGNATURE_TYPE_AUTH_HEADER = 'AUTH_HEADER'
SIGNATURE_TYPE_QUERY = 'QUERY'
SIGNATURE_TYPE_BODY = 'BODY'
```

**`Client`** (`oauth1/rfc5849/__init__.py`) — signs client requests:

```python
class Client:
    SIGNATURE_METHODS: dict[str, callable]  # 7 methods → sign_*_with_client
    @classmethod
    def register_signature_method(cls, method_name, method_callback) -> None
    def __init__(self, client_key, client_secret=None,
                 resource_owner_key=None, resource_owner_secret=None,
                 callback_uri=None, signature_method=SIGNATURE_HMAC_SHA1,
                 signature_type=SIGNATURE_TYPE_AUTH_HEADER,
                 rsa_key=None, verifier=None, realm=None,
                 encoding='utf-8', decoding=None, nonce=None, timestamp=None)
    def get_oauth_signature(self, request: Request) -> str
    def get_oauth_params(self, request: Request) -> list[tuple]  # nonce, timestamp, version, method, consumer key, token/callback/verifier/body-hash
    def sign(self, uri, http_method='GET', body=None, headers=None, realm=None
             ) -> tuple[str, dict, str]   # (signed_uri, signed_headers, signed_body)
```

`sign()` raises `ValueError` for: multipart body with params, declared
formencoded body that is not decodable, params without formencoded
content-type, `BODY` signature type without formencoded content, or body
params on GET/HEAD. RSA methods need the `rsa` extra (`cryptography`).

Example:

```python
from oauthlib.oauth1 import Client

c = Client(
    "consumer_key",
    client_secret="secret",
    resource_owner_key="tok",
    resource_owner_secret="tok_secret",
)
uri, headers, body = c.sign("https://api.example.com/resource", "GET")
# headers → {'Authorization': 'OAuth oauth_nonce="…", oauth_timestamp="…", …'}
```

**Signature primitives** (`oauth1/rfc5849/signature.py`):

```python
def signature_base_string(http_method: str, base_str_uri: str, normalized_encoded_request_parameters: str) -> str
def base_string_uri(uri: str, host: str = None) -> str   # lowercase scheme/host, strip default ports
def collect_parameters(uri_query='', body=None, headers=None,
                       exclude_oauth_signature=True, with_realm=False) -> list[tuple]
def normalize_parameters(params) -> str                 # sort + percent-encode + join
def sign_hmac_sha1(base_string, client_secret, resource_owner_secret) -> str
def sign_hmac_sha256(base_string, client_secret, resource_owner_secret) -> str
def sign_hmac_sha512(base_string, client_secret, resource_owner_secret) -> str
def sign_hmac_sha1_with_client(sig_base_str, client) -> str       # + sha256/sha512 variants
def verify_hmac_sha1(request, client_secret=None, resource_owner_secret=None) -> bool  # + sha256/sha512
def sign_rsa_sha1(base_string, rsa_private_key) -> str            # needs cryptography
def sign_rsa_sha256_with_client / sign_rsa_sha512_with_client / verify_rsa_sha1 / verify_rsa_sha256 / verify_rsa_sha512 / sign_rsa_sha1_with_client(...)
def sign_plaintext(client_secret, resource_owner_secret) -> str   # "secret&owner_secret"
def sign_plaintext_with_client(_signature_base_string, client) -> str
def verify_plaintext(request, client_secret=None, resource_owner_secret=None) -> bool
```

**Parameter placement** (`oauth1/rfc5849/parameters.py`):

```python
def prepare_headers(oauth_params, headers=None, realm=None) -> dict      # §3.5.1
def prepare_form_encoded_body(oauth_params, body) -> list[tuple]         # §3.5.2
def prepare_request_uri_query(oauth_params, uri) -> str                  # §3.5.3
```

**utils** (`oauth1/rfc5849/utils.py`):

```python
def filter_params(target) -> callable     # decorator: strip non-oauth_* params
def filter_oauth_params(params) -> list
def escape(u: str) -> str                 # RFC 5849 §3.6 (adds '~' to safe set)
def unescape(u: str) -> str
def parse_keqv_list(l) -> dict
def parse_http_list(u) -> list
def parse_authorization_header(authorization_header) -> list[tuple]  # raises ValueError if malformed
```

**OAuth1 errors** (`oauth1/rfc5849/errors.py`) — all derive `OAuth1Error`
(`.error`, `.description`, `.uri`, `.status_code=400`, `.in_uri(uri)`,
`.twotuples`, `.urlencoded`):

| Class | `.error` |
|---|---|
| `InsecureTransportError` | `insecure_transport_protocol` ("Only HTTPS…") |
| `InvalidSignatureMethodError` | `invalid_signature_method` |
| `InvalidRequestError` | `invalid_request` |
| `InvalidClientError` | `invalid_client` |

**OAuth1 server endpoints** (`oauth1/rfc5849/endpoints/`):

```python
class RequestTokenEndpoint(BaseEndpoint):
    def create_request_token(self, request, credentials) -> tuple[dict, str, int]
    def create_request_token_response(self, uri, http_method='GET', body=None, headers=None, credentials=None)
    def validate_request_token_request(self, request)
class AuthorizationEndpoint(BaseEndpoint):
    def create_verifier(self, request, credentials)
    def create_authorization_response(self, uri, http_method='GET', body=None, headers=None, realms=None, credentials=None)
    def get_realms_and_credentials(self, uri, http_method='GET', body=None, headers=None)
class AccessTokenEndpoint(BaseEndpoint):
    def create_access_token(self, request, credentials)
    def create_access_token_response(self, uri, http_method='GET', body=None, headers=None, credentials=None)
    def validate_access_token_request(self, request)
class ResourceEndpoint(BaseEndpoint):
    def validate_protected_resource_request(self, uri, http_method='GET', body=None, headers=None, realms=None)
class SignatureOnlyEndpoint(BaseEndpoint):
    def validate_request(self, uri, http_method='GET', body=None, headers=None) -> tuple[bool, Request|None]
class WebApplicationServer(RequestTokenEndpoint, AuthorizationEndpoint, AccessTokenEndpoint, ResourceEndpoint):
    def __init__(self, request_validator)
```

`RequestValidator` (server side) exposes tunables (`allowed_signature_methods`,
`timestamp_lifetime`, `client_key_length`, `enforce_ssl`, …) plus
`validate_client_key / validate_request_token / validate_access_token /
validate_timestamp_and_nonce / validate_redirect_uri / validate_realms /
validate_verifier`, getters (`get_client_secret`, `get_rsa_key`, …) and
savers (`save_request_token`, `save_verifier`, `save_access_token`), with
`dummy_client / dummy_request_token / dummy_access_token` for
timing-attack-resistant verification.

### 5. OAuth2 clients (RFC 6749) — `oauthlib.oauth2`

Base client (`rfc6749/clients/base.py`):

```python
AUTH_HEADER = 'auth_header'; URI_QUERY = 'query'; BODY = 'body'
FORM_ENC_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

class Client:
    refresh_token_key = 'refresh_token'
    def __init__(self, client_id, default_token_placement=AUTH_HEADER,
                 token_type='Bearer', access_token=None, refresh_token=None,
                 mac_key=None, mac_algorithm=None, token=None, scope=None,
                 state=None, redirect_url=None, state_generator=generate_token,
                 code_verifier=None, code_challenge=None, code_challenge_method=None, **kwargs)
    @property token_types -> {'Bearer': _add_bearer_token, 'MAC': _add_mac_token}
    def add_token(self, uri, http_method='GET', body=None, headers=None, token_placement=None, **kwargs)
        # raises InsecureTransportError / ValueError(missing token) / TokenExpiredError
    def prepare_authorization_request(self, authorization_url, state=None, redirect_url=None, scope=None, **kwargs
        ) -> tuple[str, dict, str]
    def prepare_token_request(self, token_url, authorization_response=None, redirect_url=None,
                              state=None, body='', **kwargs) -> tuple[str, dict, str]
    def prepare_refresh_token_request(self, token_url, refresh_token=None, body='', scope=None, **kwargs)
    def prepare_token_revocation_request(self, revocation_url, token, token_type_hint="access_token",
                                         body='', callback=None, **kwargs)
    def parse_request_body_response(self, body, scope=None, **kwargs) -> OAuth2Token
    def prepare_refresh_body(self, body='', refresh_token=None, scope=None, **kwargs) -> str
    def create_code_verifier(self, length) -> str          # PKCE RFC 7636 §4.1, 43 ≤ length ≤ 128
    def create_code_challenge(self, code_verifier, code_challenge_method=None) -> str  # 'plain' | 'S256'
    def populate_code_attributes(self, response) -> None
    def populate_token_attributes(self, response) -> None  # access/refresh/token_type/expires/mac_*
```

Concrete grant clients:

```python
class WebApplicationClient(Client):          # authorization code (confidential web app)
    grant_type = 'authorization_code'
    def __init__(self, client_id, code=None, **kwargs)
    def prepare_request_uri(self, uri, redirect_uri=None, scope=None, state=None,
                            code_challenge=None, code_challenge_method='plain', **kwargs) -> str
    def prepare_request_body(self, code=None, redirect_uri=None, body='',
                             include_client_id=True, code_verifier=None, **kwargs) -> str
    def parse_request_uri_response(self, uri, state=None) -> dict  # raises MismatchingStateError

class MobileApplicationClient(Client):       # implicit (public UA app; no refresh tokens)
    response_type = 'token'
    def prepare_request_uri(self, uri, redirect_uri=None, scope=None, state=None, **kwargs) -> str
    def parse_request_uri_response(self, uri, state=None, scope=None) -> OAuth2Token  # fragment

class LegacyApplicationClient(Client):       # resource-owner password (trusted first-party only)
    grant_type = 'password'
    def __init__(self, client_id, **kwargs)
    def prepare_request_body(self, username, password, body='', scope=None,
                             include_client_id=False, **kwargs) -> str

class BackendApplicationClient(Client):      # client credentials (machine-to-machine)
    grant_type = 'client_credentials'
    def prepare_request_body(self, body='', scope=None, include_client_id=False, **kwargs) -> str

class ServiceApplicationClient(Client):      # JWT bearer assertion (RFC 7523 style)
    grant_type = 'urn:ietf:params:oauth:grant-type:jwt-bearer'
    def __init__(self, client_id, private_key=None, subject=None, issuer=None, audience=None, **kwargs)
    def prepare_request_body(self, private_key=None, subject=None, issuer=None, audience=None,
                             expires_at=None, issued_at=None, extra_claims=None, body='',
                             scope=None, include_client_id=False, **kwargs) -> str
        # needs pyjwt; raises ValueError if key/iss/aud/sub missing
```

Examples (the flows the flet integration actually uses):

```python
from oauthlib.oauth2 import WebApplicationClient

c = WebApplicationClient("my_client_id")
auth_url, headers, body = c.prepare_authorization_request(
    "https://provider.example/authorize",
    redirect_url="https://app/cb",
    scope=["profile"],
    state="csrf123",
)
# → 'https://provider.example/authorize?response_type=code&client_id=…&…'
token_body = c.prepare_request_body(
    code="authcode", redirect_uri="https://app/cb", client_secret="s3cr3t"
)
t = c.parse_request_body_response('{"access_token":"…","token_type":"Bearer","expires_in":3600}')
refresh_body = c.prepare_refresh_body(refresh_token="…")
```

### 6. OAuth2 parameters & tokens

`rfc6749/parameters.py`:

```python
def prepare_grant_uri(uri, client_id, response_type, redirect_uri=None, scope=None,
                      state=None, code_challenge=None, code_challenge_method='plain', **kwargs) -> str
def prepare_token_request(grant_type, body='', include_client_id=True, code_verifier=None, **kwargs) -> str
def prepare_token_revocation_request(url, token, token_type_hint="access_token", callback=None, body='', **kwargs
    ) -> tuple[str, dict, str]                    # RFC 7009; callback → JSONP GET form
def parse_authorization_code_response(uri, state=None) -> dict   # raises MismatchingStateError / MissingCodeError
def parse_implicit_response(uri, state=None, scope=None) -> OAuth2Token
def parse_token_response(body, scope=None) -> OAuth2Token        # JSON, falls back to urlencoded (Facebook quirk)
def validate_token_parameters(params) -> None    # raises MissingTokenError / error mapping / scope-change Warning
def parse_expires(params) -> tuple[expires_in, expires_at, _expires_at]
```

`rfc6749/tokens.py`:

```python
class OAuth2Token(dict):
    def __init__(self, params, old_scope=None)
    @property scope_changed -> bool
    @property scope / scopes / old_scope / old_scopes
    @property missing_scopes / additional_scopes -> list
def prepare_bearer_headers(token, headers=None) -> dict   # Authorization: Bearer … (recommended)
def prepare_bearer_uri(token, uri) -> str                 # ?access_token=… (discouraged)
def prepare_bearer_body(token, body='') -> str
def prepare_mac_header(token, uri, key, http_method, nonce=None, headers=None, body=None,
                       ext='', hash_algorithm='hmac-sha-1', issue_time=None, draft=0) -> dict  # experimental
def random_token_generator(request, refresh_token=False) -> str
def signed_token_generator(private_pem, **kwargs) -> callable   # needs pyjwt
def get_token_from_header(request) -> str | None
class BearerToken(TokenBase):
    def __init__(self, request_validator=None, token_generator=None, expires_in=None,
                 refresh_token_generator=None)   # default expires_in=3600
    def create_token(self, request, refresh_token=False, **kwargs) -> OAuth2Token
    def validate_request(self, request)
    def estimate_type(self, request) -> int      # 9 = header Bearer, 5 = query/body, 0 = none
```

`rfc6749/utils.py`:

```python
def list_to_scope(scope) -> str | None
def scope_to_list(scope) -> list | None
def params_from_uri(uri) -> dict
def host_from_uri(uri) -> tuple[str, str]   # defaults 80/443
def escape(u: str) -> str
def generate_age(issue_time) -> str
def is_secure_transport(uri) -> bool        # False on http:// unless OAUTHLIB_INSECURE_TRANSPORT set
```

### 7. OAuth2 error hierarchy (`rfc6749/errors.py`)

Base `OAuth2Error(description, uri, state, status_code, request)` with
`.error`, `.status_code=400`, `.twotuples`, `.urlencoded`, `.json`,
`.in_uri(uri)`, `.headers` (401 → `WWW-Authenticate: Bearer …`), and
`raise_from_error(error, params)` factory (+ `CustomOAuth2Error` fallback).

| Class | `.error` | HTTP |
|---|---|---|
| `TokenExpiredError` | `token_expired` | 400 |
| `InsecureTransportError` | `insecure_transport` | 400 |
| `MismatchingStateError` | `mismatching_state` | 400 |
| `MissingCodeError` / `MissingTokenError` / `MissingTokenTypeError` | `missing_*` | 400 |
| `FatalClientError` (+ `InvalidRequestFatalError` → `InvalidRedirectURIError`, `MissingRedirectURIError`, `MismatchingRedirectURIError`, `InvalidClientIdError`, `MissingClientIdError`) | `invalid_request` etc. | 400 — never redirect |
| `InvalidRequestError` (+ `MissingResponseTypeError`, `MissingCodeChallengeError`, `MissingCodeVerifierError`, `UnsupportedCodeChallengeMethodError`) | `invalid_request` | 400 |
| `AccessDeniedError` | `access_denied` | 400 |
| `UnsupportedResponseTypeError` | `unsupported_response_type` | 400 |
| `InvalidScopeError` | `invalid_scope` | 400 |
| `ServerError` / `TemporarilyUnavailableError` | `server_error` / `temporarily_unavailable` | 400 |
| `InvalidClientError` (Fatal) | `invalid_client` | **401** |
| `InvalidGrantError` | `invalid_grant` | 400 |
| `UnauthorizedClientError` | `unauthorized_client` | 400 |
| `UnsupportedGrantTypeError` | `unsupported_grant_type` | 400 |
| `UnsupportedTokenTypeError` | `unsupported_token_type` | 400 |
| `InvalidTokenError` | `invalid_token` | **401** |
| `InsufficientScopeError` | `insufficient_scope` | **403** |
| `ConsentRequired` / `LoginRequired` | `consent_required` / `login_required` | 400 |

### 8. OAuth2 server side — grant types + endpoints

`grant_types/base.py`: `GrantTypeBase(request_validator, pre_auth/post_auth/
pre_token/post_token, …)` with `ValidatorsContainer`, `register_response_type/
register_code_modifier/register_token_modifier`, `create_authorization_response/
create_token_response`, `validate_grant_type/validate_scopes`,
`prepare_authorization_response` (query vs fragment placement).

| Grant class | Flow | Key methods |
|---|---|---|
| `AuthorizationCodeGrant` | code (+PKCE) | `create_authorization_code`, `create_authorization_response`, `create_token_response`, `validate_authorization_request`, `validate_token_request`, `validate_code_challenge`; helpers `code_challenge_method_s256/plain` |
| `ImplicitGrant` | token | same auth-response shape, `grant_allows_refresh_token=False` |
| `RefreshTokenGrant(issue_new_refresh_tokens=True)` | refresh | `create_token_response`, `validate_token_request` |
| `ClientCredentialsGrant` | 2-legged | `create_token_response`, `validate_token_request` |
| `ResourceOwnerPasswordCredentialsGrant` | password | `create_token_response`, `validate_token_request` |

Endpoints return `(headers, body, status)` triples:

```python
class AuthorizationEndpoint(BaseEndpoint):
    def __init__(self, default_response_type, default_token_type, response_types)
    def create_authorization_response(self, uri, http_method='GET', body=None, headers=None, ...)
    def validate_authorization_request(self, uri, http_method='GET', body=None, headers=None)
class TokenEndpoint(BaseEndpoint):
    def __init__(self, default_grant_type, default_token_type, grant_types)
    def create_token_response(self, uri, http_method='POST', body=None, headers=None, ...)
    def validate_token_request(self, request)
class ResourceEndpoint(BaseEndpoint):
    def __init__(self, default_token, token_types)
    def verify_request(self, uri, http_method='GET', body=None, headers=None, scopes=None) -> tuple[bool, Request]
class RevocationEndpoint(BaseEndpoint):      # RFC 7009
    def create_revocation_response(self, uri, http_method='POST', body=None, headers=None, ...)
class IntrospectEndpoint(BaseEndpoint):      # RFC 7662
    def create_introspect_response(self, uri, http_method='POST', body=None, headers=None, ...)
class MetadataEndpoint(BaseEndpoint):        # RFC 8414 discovery
    def __init__(self, endpoints, claims={}, raise_errors=True)
    def create_metadata_response(self, uri, http_method='GET', ...)  # + validate_metadata_* helpers
class Server(AuthorizationEndpoint, IntrospectEndpoint, TokenEndpoint, ResourceEndpoint, RevocationEndpoint)
    # all grants: code, implicit, password, credentials, refresh, device_code
class WebApplicationServer(...)    # code + refresh only
class MobileApplicationServer(...) # implicit only
class LegacyApplicationServer(...) # password + refresh
class BackendApplicationServer(...)# client_credentials only
# each __init__(self, request_validator, token_expires_in=None, token_generator=None, refresh_token_generator=None, **kwargs)
```

`RequestValidator` (server implementors subclass ~25 hooks):
`client_authentication_required`, `authenticate_client`,
`authenticate_client_id`, `validate_client_id`, `validate_grant_type`,
`validate_scopes`, `validate_user`, `validate_code`, `validate_redirect_uri`,
`validate_response_type`, `validate_refresh_token`, `save_authorization_code`,
`save_token`, `save_bearer_token`, `validate_bearer_token`,
`revoke_token`, `introspect_token`, `rotate_refresh_token`,
`is_pkce_required`, `get_code_challenge(_method)`, `is_origin_allowed`, …

### 9. Device flow (RFC 8628) — `oauthlib.oauth2.rfc8628`

```python
class DeviceClient(Client):
    grant_type = 'urn:ietf:params:oauth:grant-type:device_code'
    def __init__(self, client_id, **kwargs)          # client_secret via kwargs
    def prepare_request_uri(self, uri, scope=None, **kwargs) -> str
    def prepare_request_body(self, device_code, body='', scope=None, include_client_id=False, **kwargs) -> str
class DeviceCodeGrant(GrantTypeBase):
    def create_authorization_response(self, request, token_handler)
    def create_token_response(self, request, token_handler)
    def validate_token_request(self, request: Request) -> None
class DeviceAuthorizationEndpoint(BaseEndpoint):
    def __init__(self, request_validator, verification_uri, verification_uri_complete=None,
                 interval=5, expires_in=1800, **kwargs)
    def create_device_authorization_response(self, uri, http_method='POST', body=None, headers=None, ...)
    def validate_device_authorization_request(self, request)
class DeviceApplicationServer(...)  # pre-configured device server
# errors (all OAuth2Error): AuthorizationPendingError, SlowDownError, ExpiredTokenError, AccessDenied
```

### 10. OpenID Connect — `oauthlib.openid.connect.core`

Exceptions (`exceptions.py`): `OpenIDClientError(OAuth2Error)`,
`FatalOpenIDClientError(FatalClientError)`, `InteractionRequired`,
`LoginRequired`, `AccountSelectionRequired`, `ConsentRequired`,
`InvalidRequestURI`, `InvalidRequestObject`, `RequestNotSupported`,
`RequestURINotSupported`, `RegistrationNotSupported`, plus OIDC-flavoured
`InvalidTokenError` (401) / `InsufficientScopeError` (403) and
`raise_from_error`.

```python
class JWTToken(TokenBase):   # tokens.py
    def __init__(self, request_validator=None, token_generator=None, expires_in=None, refresh_token_generator=None)
    def create_token(self, request, refresh_token=False)   # delegates to validator.get_jwt_bearer_token
    def validate_request(self, request)                    # validator.validate_jwt_bearer_token
    def estimate_type(self, request) -> int                # 10 if looks like JWT (ey… + dots)

class OpenIDConnectBase / GrantTypeBase:     # grant_types/base.py (proxy to AuthorizationCode/Implicit grant)
    def validate_authorization_request(self, request)
    def id_token_hash(self, value, hashfunc=hashlib.sha256) -> str   # at_hash / c_hash left-half b64url
    def add_id_token(self, token, token_handler, request, nonce=None) -> dict
    def openid_authorization_validator(self, request)   # nonce/max_age/prompt/display/ui_locales/claims checks
class AuthorizationCodeGrant / ImplicitGrant / RefreshTokenGrant / HybridGrant(GrantTypeBase): ...
class AuthorizationCodeGrantDispatcher / ImplicitTokenGrantDispatcher / AuthorizationTokenGrantDispatcher(Dispatcher)
class UserInfoEndpoint(BaseEndpoint):
    def create_userinfo_response(self, uri, http_method='GET', body=None, headers=None, ...)
class Server(AuthorizationEndpoint, TokenEndpoint, ResourceEndpoint, UserInfoEndpoint, RevocationEndpoint, IntrospectEndpoint)
class RequestValidator(OAuth2RequestValidator):  # + get_id_token, finalize_id_token,
    # get_jwt_bearer_token, validate_jwt_bearer_token, validate_id_token, get_userinfo_claims …
```

---

## App usage & correctness

**Grep result: zero hits.** `grep -rin "oauthlib|oauth"` over
`<repo>\src`,
`tests`, `tools/` returns nothing — the app never imports oauthlib
directly. (The `src` tree contains `app_shell.py`, `main.py`,
`components/`, `core/`, `screens/`, `services/`, `state/`, `assets/`.)

**(a) Who requires it.** `flet 1.0.0` declares it unconditionally
(non-Emscripten):

```
# flet-1.0.0.dist-info/METADATA
Requires-Dist: oauthlib>=3.2.2; platform_system != "Emscripten"
```

Chain evidence: `uv.lock` pins `oauthlib 3.3.1` under the `flet` package
entry (`sys_platform != 'emscripten'` marker); `deps-tree.txt` shows
`flet → oauthlib v3.3.1`; `pinned-deps.txt:56` records
`oauthlib==3.3.1 ; sys_platform != 'emscripten'`;
`oauthlib-3.3.1.dist-info/REQUESTED` is absent (never directly requested).
`requests` does **not** pull it (no `requests-oauthlib` installed).

The consumer inside flet is the optional desktop/web login flow:
`flet/auth/authorization_service.py` lazily imports it in three places —

```python
from oauthlib.oauth2 import WebApplicationClient  # get_authorization_data()

client.prepare_request_uri(
    provider.authorization_endpoint,
    provider.redirect_url,
    scope=...,
    state=...,
    code_challenge=...,
    code_challenge_method=...,
)
client.prepare_request_body(
    code=...,
    redirect_uri=...,
    client_secret=...,  # request_token()
    include_client_id=True,
    code_verifier=...,
)
client.parse_request_body_response(resp.text)  # → OAuth2Token
client.prepare_refresh_body(...)  # __refresh_token()
```

Transport is `httpx` (`httpx.Request`/`AsyncClient`); token mapping is
converted to `flet.auth.OAuthToken`; userinfo uses a plain Bearer header.
Only `WebApplicationClient` (authorization-code + PKCE + refresh) is
exercised — no OAuth1, device, or OIDC paths.

**(b) Misuse.** None in app code (no usage at all). Within flet's usage:
correct — HTTPS enforced by oauthlib, random `secrets.token_urlsafe(16)`
state, PKCE verifier/challenge threaded through, refresh token preserved
when the provider omits a new one. One latent quirk inherited from oauthlib:
`parse_request_body_response` raises a scope-change `Warning` as an
exception unless `OAUTHLIB_RELAX_TOKEN_SCOPE` is set — a provider that
narrows scopes would surface as a crash, not a warning, in flet's refresh
path. Not app-actionable.

**(c) v1 relevance.** The FFmpeg mobile app (media conversion UI, AdMob,
camera/mic/file permissions) performs **no OAuth today** and v1 needs none:
AdMob monetisation is SDK-key/config based (`flet-ads`), Play publishing
uses service-account JSON via the Play Console/CLI (server-side
`google-auth`, not an in-app OAuth dance), and there is no cloud-sync or
user-account feature. oauthlib is therefore **intentionally-transitive dead
weight for v1**: required at install time by `flet`, dormant at runtime
unless `page.login()` is ever called. Do not add it to direct dependencies,
do not pin it independently, and do not remove it (removal breaks
`flet[auth]` imports and `uv sync`).

---

## Considerations for v1

- **Keep as transitive.** Let the `flet>=1.0.0` requirement float it
  (`oauthlib>=3.2.2`). The lockfile already pins 3.3.1 reproducibly.
- **If v1 ever needs auth**, the realistic candidates and what each stack
  layer gives you:
  - *In-app user login (Google/GitHub/Apple via flet `page.login()`)* →
    already wired: oauthlib's `WebApplicationClient` builds the
    authorize URL / token exchange / refresh; you only supply an
    `OAuthProvider` config. No new dependency.
  - *AdMob / Play Developer REST reporting from a backend script* →
    use `google-auth` + service accounts (JWT bearer), **not** oauthlib;
    the closest oauthlib analogue (`ServiceApplicationClient`) needs manual
    JWT plumbing and is the wrong tool for Google APIs.
  - *First-party cloud sync with username+password* → prefer
    `LegacyApplicationClient`/password grant only against your own backend,
    over TLS; never embed third-party passwords in the mobile client.
  - *TV/STB-style sign-in* → `DeviceClient` + polling on
    `authorization_pending`/`slow_down` is the only sane oauthlib path for
    input-constrained devices.
- **oauthlib vs `httpx` auth.** `httpx 0.28.1` (`_auth.py`) ships only
  `BasicAuth`, `DigestAuth`, `NetRCAuth`, `FunctionAuth` — no OAuth, no
  token refresh, no PKCE, no scope handling. oauthlib is the piece that
  *constructs and parses* OAuth messages; httpx is the piece that *sends*
  them. They compose (as flet demonstrates); neither replaces the other.
- **Mobile-packaging note.** oauthlib is pure Python with no native
  modules, so it adds negligible weight to the Android bundle and needs no
  recipe/patch. The `platform_system != "Emscripten"` marker means web
  builds skip it — harmless asymmetry, no action.
- **Security posture for later.** Enforce HTTPS (default), always verify
  `state` on callback, prefer `S256` PKCE over `plain`, send bearer tokens
  in the `Authorization` header (never query), and treat the implicit grant
  as legacy (authorization-code + PKCE instead).

---

## Gotchas

1. **HTTPS is mandatory.** Every client `prepare_*` and response parser
   raises `InsecureTransportError` on `http://`. Escape hatch
   `OAUTHLIB_INSECURE_TRANSPORT=1` exists for local testing only — never
   ship it.
2. **Scope-change `Warning` is raised, not warned.** `parse_token_response`
   / `parse_implicit_response` raise a `Warning` instance as an exception
   when granted scopes differ; set `OAUTHLIB_RELAX_TOKEN_SCOPE=1` to
   tolerate it, and optionally listen on `scope_changed` (needs blinker).
3. **`token_type` strictness is opt-in.** Missing `token_type` only raises
   `MissingTokenTypeError` when `OAUTHLIB_STRICT_TOKEN_SCOPE`…
   (`OAUTHLIB_STRICT_TOKEN_TYPE`) is set in the environment.
4. **`expires_in` must be int-like.** Non-numeric strings raise
   `ValueError("expires_in must be an int")`; floats are truncated.
   `parse_expires` synthesises `expires_at`/`_expires_at` from
   `time.time() + expires_in` when absent.
5. **Extras are NOT installed here.** `cryptography` and `pyjwt` are
   missing, so RSA-SHA1/256/512 signing/verification, `sign_plaintext`'s
   JWT cousins (`generate_signed_token`, `signed_token_generator`,
   `ServiceApplicationClient.prepare_request_body`) raise `ImportError` at
   call time. `blinker` is missing, so `signals.scope_changed.send()` is a
   silent noop and `.connect()` raises `RuntimeError`.
6. **MAC tokens are experimental** (draft-00 only, `hmac-sha-1`/`hmac-sha-256`).
   Prefer Bearer.
7. **OAuth1 PLAINTEXT sends secrets almost in clear** (`client_secret&token_secret`);
   only viable over TLS. HMAC-SHA1 is the RFC default; prefer SHA-256/512 variants.
8. **State/CSRF is caller-managed.** `prepare_*` helpers accept `state` but
   `WebApplicationClient` auto-generates it only via
   `prepare_authorization_request`; low-level `prepare_request_uri` sends
   none unless you pass it. Always verify on callback
   (`MismatchingStateError` / `ValueError` on mismatch).
9. **`client_secret` placement matters.** `WebApplicationClient.
   prepare_request_body(..., include_client_id=True)` puts the secret in the
   POST body; confidential clients talking to strict servers may need a
   Basic-auth header instead — oauthlib will not add it for you.
10. **Duplicate parameters are rejected server-side** (`InvalidRequestError`
    on duplicated `grant_type`/`scope`), and `Request.duplicate_params`
    surfaces them client-side — useful when merging query + body params.
11. **`Request` attribute access is permissive.** Unknown attributes raise
    `AttributeError`, but any recognised OAuth/OpenID field returns `None`
    when absent — check for `None` rather than catching.
12. **Refresh-token rotation is opt-out server-side**
    (`RefreshTokenGrant(issue_new_refresh_tokens=True)`); clients must
    replace the stored refresh token whenever the response contains a new one
    (flet already does this).
13. **Implicit grant has no refresh** by design; `MobileApplicationClient`
    tokens from the URL fragment expire without renewal — plan refresh via
    code flow instead.
14. **`is_secure_transport` lowercases the URI** before the `https://`
    check; custom schemes (`myapp://callback`) fail it — parse callbacks
    with `parse_*_response` only on the `https://` redirect endpoints, and
    handle the final custom-scheme hop yourself.
