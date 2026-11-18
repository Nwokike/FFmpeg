"""TLS trust for network inputs opened through PyAV/FFmpeg.

PyAV's bundled FFmpeg uses its own TLS backend (mbedTLS in the mobile wrap
build, GnuTLS on some desktop wheels). That backend does **not** read the
OS trust store and ignores ``SSL_CERT_FILE`` — verified on the pinned av
wheel: ``https://…m3u8`` fails with ``[tls] Peer certificate failed
verification`` until a ``ca_file`` is supplied. ``certifi`` ships a CA bundle
inside the same environment on every platform (httpx already depends on it),
so passing it as the ``ca_file`` AVOption is the portable fix.
"""

from __future__ import annotations

import certifi


def ca_file() -> str:
    """Path to the CA bundle FFmpeg's TLS backend should verify against."""
    return certifi.where()


def network_options() -> dict[str, str]:
    """``av.open`` options for http(s) URLs (TLS trust)."""
    return {"ca_file": ca_file()}
