# certifi 2026.7.22 — Complete API Reference

TLS CA bundle: Mozilla's curated root-certificate collection, shipped as
`cacert.pem` plus a two-function Python API. Zero dependencies,
pure-Python wheel (`py3-none-any`), `py.typed` marked.

Package dir (read-only ground truth):
`<repo>\.venv\Lib\site-packages\certifi`
Dist-info:
`<repo>\.venv\Lib\site-packages\certifi-2026.7.22.dist-info\`

---

## Files

Package files (`__pycache__` skipped; sizes from installed wheel):

| File | Size | Role |
|---|---|---|
| `certifi/__init__.py` | 94 B | Public surface: `from .core import contents, where`; `__all__ = ["contents", "where"]`; `__version__ = "2026.07.22"` |
| `certifi/core.py` | 3,394 B | Entire implementation (`where()`, `contents()`, zipimport handling) |
| `certifi/__main__.py` | 243 B | CLI: `python -m certifi` / `python -m certifi --contents` |
| `certifi/cacert.pem` | 240,216 B, 3,959 lines | The actual trust store (PEM bundle) |
| `certifi/py.typed` | 0 B | PEP 561 marker: package ships inline types |
| `certifi/tests/__init__.py` | 0 B | Test package marker |
| `certifi/tests/test_certify.py` | 467 B | 3 upstream unit tests (see below) |

Dist-info files:

| File | Notes |
|---|---|
| `METADATA` (2,474 B) | Name/Version/Summary/License/classifiers + long-description usage notes |
| `RECORD` | 14 rows; SHA-256 per file; `REQUESTED` and `RECORD` itself have empty hash per spec |
| `WHEEL` | `Wheel-Version: 1.0`, `Generator: setuptools (83.0.0)`, `Root-Is-Purelib: true`, `Tag: py3-none-any` |
| `INSTALLER` | Content: `uv` (single line) — venv was built by uv |
| `REQUESTED` | **0 bytes (empty)** — proves certifi is **transitive**, not a direct app dependency |
| `top_level.txt` | Content: `certifi` |
| `licenses/LICENSE` | MPL-2.0 + Mozilla `certdata.txt` extraction provenance (see Metadata) |

### `cacert.pem` structure (sampled, not fully read)

- 3,959 lines / 240,216 bytes; `grep -c "BEGIN CERTIFICATE"` → **121 root certificates**.
- Repeating block layout per root:
  ```
  # Issuer: CN=... O=...
  # Subject: CN=... O=...
  # Label: "..."
  # Serial: <int>
  # MD5 Fingerprint: aa:bb:...
  # SHA1 Fingerprint: aa:bb:...
  # SHA256 Fingerprint: aa:bb:...
  -----BEGIN CERTIFICATE-----
  <base64 DER, ~25 lines>
  -----END CERTIFICATE-----
  ```
- First entry: `COMODO ECC Certification Authority`. Encoding is pure ASCII
  (hence `contents()` uses `encoding="ascii"`). Fingerprint comments are
  informational only — TLS validation uses the DER bytes.

### Bundled tests (`tests/test_certify.py`, 467 B, verbatim logic)

```python
class TestCertifi(unittest.TestCase):
    def test_cabundle_exists(self):
        assert os.path.exists(certifi.where())

    def test_read_contents(self):
        assert "-----BEGIN CERTIFICATE-----" in certifi.contents()

    def test_py_typed_exists(self):
        assert os.path.exists(... / py.typed)
```

---

## Metadata

From `METADATA` (verbatim fields):

- `Name: certifi` · `Version: 2026.7.22` (note: `certifi.__version__`
  renders as `"2026.07.22"` — zero-padded month; same release, different
  string).
- `Summary: Python package for providing Mozilla's CA Bundle.`
- `Requires-Python: >=3.7` (classifiers list 3.7–3.14 explicitly, incl. 3.14 —
  matches this app's `requires-python = ">=3.14"`).
- **No `Requires-Dist` lines at all** — certifi depends on nothing (stdlib
  `importlib.resources` + `atexit` only).
- `License: MPL-2.0`, classifier
  `License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)`.
- Long description notes (paraphrased, load-bearing points kept exact):
  - "extracted from the `Requests` project" — historical provenance.
  - "Certifi does not support any addition/removal or other modification of
    the CA trust store content."
  - "intended to provide a reliable and highly portable root of trust."
- `licenses/LICENSE` data provenance: bundle is "a modified version of
  `ca-bundle.crt` … automatically extracted from Mozilla's root certificates
  file (`certdata.txt`)" at
  `https://hg.mozilla.org/mozilla-central/file/tip/security/nss/lib/ckfw/builtins/certdata.txt`,
  under the **Mozilla Public License v. 2.0** license block. Practical read:
  the *code* (`core.py`, ~80 lines) is MPL-2.0; the *data* (`cacert.pem`) is
  Mozilla's root list under the same MPL-2.0 header via `certdata.txt`.
- Versioning is **calendar-based** (`YYYY.M.DD`): this release = Mozilla sync
  of July 2026. Expect several releases per year as roots are added,
  removed, or distrusted upstream.

---

## Module-by-module API

### `certifi/__init__.py` (entire file, 4 lines)

```python
from .core import contents, where

__all__ = ["contents", "where"]
__version__ = "2026.07.22"
```

Public surface is exactly two functions plus a version string.

### `certifi/core.py` — `where() -> str`

```python
def where() -> str: ...
```

- **Returns:** absolute filesystem path to `cacert.pem`, e.g.
  `<repo>\.venv\Lib\site-packages\certifi\cacert.pem`
  (verified at runtime in this venv).
- **How:** on Python ≥ 3.11 (this app runs 3.14, so this is the live branch):
  `str(as_file(files("certifi").joinpath("cacert.pem")).__enter__())`.
  Normal installs return the in-place path (`__exit__` is a no-op); under
  **zipimport** (zipapp/pex-style) it extracts to a temp file once.
- **Caching:** result memoized in module globals `_CACERT_CTX`
  (the context manager, held so GC doesn't delete the temp file) and
  `_CACERT_PATH` (the string). First call does the work; later calls return
  the cached string. Cleanup registered via `atexit.register(exit_cacert_ctx)`.
- **Legacy branch** (`else`, `sys.version_info < (3, 11)`, using
  `importlib.resources.path`/`read_text`): dead code on this app's
  interpreter; kept for old Pythons. Same semantics.
- **Exceptions:** raises `FileNotFoundError` if `cacert.pem` is absent from
  the package (nothing catches it — callers see it raw). No other documented
  errors; never returns `None`.
- Example:
  ```python
  >>> import certifi, ssl
  >>> ctx = ssl.create_default_context(cafile=certifi.where())
  >>> ctx.verify_mode == ssl.CERT_REQUIRED
  True
  ```

### `certifi/core.py` — `contents() -> str`

```python
def contents() -> str: ...
```

- **Returns:** full text of `cacert.pem` as `str` (ASCII-decoded), ~240 KB.
  Not cached — re-reads from disk every call.
- **Use when:** you need the bundle inline (e.g. writing it into a
  frozen-app resource, comparing fingerprints). Prefer `where()` for TLS,
  which avoids a 240 KB string allocation per call.
- **Exceptions:** `FileNotFoundError` if the resource is missing.
- Example:
  ```python
  >>> import certifi
  >>> "-----BEGIN CERTIFICATE-----" in certifi.contents()
  True
  ```

### `certifi/__main__.py` — CLI (entire file, 11 lines)

```python
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--contents", action="store_true")
args = parser.parse_args()
print(contents() if args.contents else where())
```

- `python -m certifi` → prints the bundle path (one line).
- `python -m certifi -c` / `--contents` → dumps the whole PEM to stdout.
- No other flags; unknown flags → argparse `SystemExit(2)`. Useful in
  build scripts to locate the CA file without importing.

### Helpers / internals (not public)

- `exit_cacert_ctx() -> None` — atexit hook calling
  `_CACERT_CTX.__exit__(None, None, None)`; no-op for normal installs,
  deletes the extracted temp file for zipimport runs.
- `_CACERT_CTX`, `_CACERT_PATH` — module-global memo cells described above.

---

## App usage & correctness

### (a) Usage chain — certifi is transitive, httpx is the consumer

- **Zero direct references:** `grep -rn "certifi" src tests tools` returns
  nothing. The app never imports certifi. `REQUESTED` being empty corroborates:
  it entered the venv as a transitive dependency.
- **Dependents in the venv (from their METADATA):**
  - `httpx 0.28.1` → `Requires-Dist: certifi` (unpinned) + `httpcore==1.*`.
    This is the live consumer: `src/services/update_service.py` does
    `import httpx`.
  - `httpcore 1.0.9` → `Requires-Dist: certifi`.
  - `requests 2.34.2` → `Requires-Dist: certifi>=2023.5.7` (present in venv,
    but nothing in `src/` imports `requests` — likely a Flet-plugin
    transitive dep; not on the app's TLS path).
  - `urllib3 2.8.0` does **not** require certifi here.
- **The single TLS call site** — `src/services/update_service.py`
  (`UpdateService.check_for_updates`, lines 18–34):
  ```python
  async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
      resp = await client.get(
          UPDATE_CONFIG_URL
      )  # https://raw.githubusercontent.com/Nwokike/FFmpeg/main/version.json
  ```
  No `verify=`, no `cert=`, no custom `SSLContext` — httpx defaults apply:
  `httpx/_config.py::create_ssl_context(verify=True)` →
  `ssl.create_default_context(cafile=certifi.where())` (unless
  `SSL_CERT_FILE`/`SSL_CERT_DIR` env vars are set and `trust_env` is on).
  One layer down, `httpcore/_ssl.py::default_ssl_context()` does
  `ssl.create_default_context()` + `load_verify_locations(certifi.where())`.
  Runtime check in this venv confirmed `verify_mode == CERT_REQUIRED` and
  `check_hostname is True` for a context built from `certifi.where()`.
- **Tests** (`tests/test_update_service.py`): patch `httpx.AsyncClient` with
  `MockTransport` — TLS is bypassed by design in tests (no socket), covering
  newer/same/404/timeout/bad-JSON cases. Correct; nothing to change.
- Verdict: the update check — the app's only network call — is anchored by
  certifi's Mozilla bundle with full chain + hostname verification.

### (b) MISUSE sweep — clean

Searched `src/`, `tests/`, `tools/` for every standard TLS-bypass pattern:

```
verify=False | CERT_NONE | check_hostname=False | _create_unverified |
create_unverified | SSLContext | load_verify | cafile | capath | import ssl
```

**Zero hits** (grep exit 1 on both patterns). No `verify=False`, no
`ssl.CERT_NONE`, no `ssl._create_unverified_context()`, no `import ssl` at
all outside the venv. The app never opts out of verification and never
hand-rolls a context. Nothing to remediate before v1.

---

## Underused considerations

1. **Rotation discipline (the one real v1 action).** Mozilla adds/removes/
   distrusts roots several times a year and certifi re-releases each time
   (hence CalVer `2026.7.22`). A frozen `uv.lock` entry quietly ages: new
   sites chaining to a new root fail closed (good), and a distrusted root
   stays trusted until you update (bad). Recommendation: refresh the lock
   for `certifi`/`httpx`/`httpcore` on a cadence (e.g. quarterly, or whenever
   a certifi release lands — they are drop-in, data-only changes) and let
   the silent update-check failure log surface staleness. Do **not** add a
   direct `certifi==` pin to `pyproject.toml` — inherit it via
   `httpx>=0.28.1` so resolver upgrades stay frictionless; the lockfile is
   the pin.
2. **Prefer httpx defaults — deliberately.** `update_service.py` passes no
   `verify` argument, which is the correct posture: verification stays on,
   the bundle path resolves via `certifi.where()`, and `SSL_CERT_FILE` /
   `SSL_CERT_DIR` overrides keep working for enterprise users. Never pass
   `verify=certifi.where()` manually (deprecated `str` form in httpx) and
   never construct your own `SSLContext` here — both freeze behavior that
   currently tracks httpx/httpcore upgrades for free.
3. **certifi vs the OS store.** `ssl.create_default_context()` with no
   `cafile` uses the OS trust store; httpx/httpcore deliberately override it
   with certifi for a portable, deterministic root set. On desktop that is a
   wash; on **Android (Flet APK)** it matters: the bundled CPython has no
   useful system store, and the Java `KeyStore` is invisible to Python
   sockets — certifi *is* the trust store. Consequence: user-installed CAs
   (corporate MITM proxies, custom PKI) are **not** honored, and the update
   check fails closed with a logged warning. That is the safe default; if
   enterprise support is ever needed, honor `SSL_CERT_FILE` (already works
   via httpx `trust_env`) rather than weakening verification.
4. **Offline-update path needs no cert awareness.** The app is offline-first
   (local FFmpeg engine); the update check is best-effort, wrapped in
   `except Exception → None` with a one-line warning. A stale bundle, an
   expired system clock (common on fresh Android devices — fix the clock, not
   the code), or no connectivity all degrade to "silent, try next launch."
   No embedded certificate pinning exists, so Mozilla rotations can never
   brick the updater — worst case is a skipped prompt until the next certifi
   refresh. Keep the catch-all; optionally log `exc.__class__.__name__`
   alongside the message so TLS failures are distinguishable from HTTP 404s
   in bug reports.
5. **Unused API worth knowing:** `certifi.contents()` has no app use today —
   if a future self-contained/offline installer needs to embed the bundle
   (e.g. seeding a frozen APK asset), it is the supported accessor rather
   than reaching into `site-packages` by path.

---

## Gotchas

- **Two version strings:** dist-info says `2026.7.22`, `certifi.__version__`
  says `"2026.07.22"` (zero-padded). Normalize before comparing in scripts.
- **`where()` is memoized** in `_CACERT_PATH` — tests that relocate or mock
  the package must clear/reset the globals or reload the module; otherwise
  the first-resolved path sticks for the process lifetime.
- **`contents()` returns `str`, not `bytes`**, decoded as ASCII. Writing it
  back with a UTF-8/BOM writer changes the hash; use ASCII/plain mode.
- **No mutation API.** Adding a private CA means a custom `SSLContext` with
  `load_verify_locations(cafile=certifi.where())` *plus* your extra CA —
  certifi itself refuses modification by design.
- **certifi is a bundle, not a validator.** Hostname checks, expiry, and
  chain building are done by `ssl`/OpenSSL; certifi only supplies the roots.
  A current bundle with a wrong system clock still fails — on Android, tell
  users to enable automatic date/time.
- **`python -m certifi` prints exactly one line** (path + newline); with
  `-c` it prints ~240 KB — don't capture it accidentally in build logs.
- **`REQUESTED` empty + `INSTALLER: uv`** — if a future audit asks "is
  certifi a direct dependency?", the answer is no; it rides in via
  `httpx`/`httpcore`. Keep it that way.
