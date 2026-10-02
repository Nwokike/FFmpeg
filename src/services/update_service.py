"""Update check service fetching remote version.json manifest."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from core.constants import APP_VERSION, BUILD_NUMBER, UPDATE_CONFIG_URL

logger = logging.getLogger("UpdateService")

# One pooled client per process — a client per check means every probe paid a
# cold TLS handshake. timeout= applies PER PHASE (connect/read/write/pool), so
# the split values below bound the worst case instead of multiplying it.
_TIMEOUT = httpx.Timeout(connect=3.0, read=4.0, write=4.0, pool=2.0)
_TRANSPORT = httpx.AsyncHTTPTransport(retries=2)
_CLIENT: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _CLIENT
    if _CLIENT is None or _CLIENT.is_closed:
        _CLIENT = httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            transport=_TRANSPORT,
        )
    return _CLIENT


async def close_client() -> None:
    """Release the pooled client (call from app shutdown)."""
    global _CLIENT
    if _CLIENT is not None and not _CLIENT.is_closed:
        await _CLIENT.aclose()
    _CLIENT = None


def _release_tuple(version: Any) -> tuple[int, ...] | None:
    """Dotted numeric release → comparable tuple ('1.10.0' → (1, 10, 0)).

    Hand-rolled deliberately: `packaging` is dev-transitive in this app and
    dev deps are stripped from release builds, so importing it at runtime
    would risk an ImportError in the shipped APK. Promote `packaging` to
    [project] dependencies first if full PEP 440 support is ever needed.
    """
    head = re.split(r"[-+]", str(version or "").strip(), maxsplit=1)[0]
    parts = head.split(".")
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def _gt_version(remote: Any, local: Any) -> bool:
    """True when `remote` > `local` for dotted numeric versions (1.10 > 1.9)."""
    a, b = _release_tuple(remote), _release_tuple(local)
    if a is None or b is None:
        return False
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def is_newer(remote_build: Any, remote_version: Any = None) -> bool:
    """True when the manifest is newer by build number OR by version.

    Build-only comparison missed releases that bumped the version string
    without the integer build number.
    """
    try:
        if int(remote_build) > BUILD_NUMBER:
            return True
    except (TypeError, ValueError):
        pass
    return _gt_version(remote_version, APP_VERSION)


class UpdateService:
    """Checks repository version.json for updates silently in the background."""

    @staticmethod
    async def check_for_updates() -> dict[str, Any] | None:
        """Fetch remote version.json and return data if a newer build/version exists."""
        try:
            resp = await _client().get(UPDATE_CONFIG_URL)
            resp.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            # Offline / flaky mobile link is normal — not a warning.
            logger.info("Update check unreachable: %s", exc)
            return None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                # Unpublished/private repo or the manifest isn't on the branch
                # yet — an expected pre-release state, not a failure.
                logger.info("Update manifest not reachable (HTTP %s)", exc.response.status_code)
            else:
                logger.warning("Update check rejected: %s", exc)
            return None
        except Exception as exc:
            logger.warning("Update check failed: %s", exc)
            return None

        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning("Update manifest is not valid JSON: %s", exc)
            return None
        if not isinstance(data, dict):
            logger.warning("Update manifest is not an object (%s)", type(data).__name__)
            return None

        if is_newer(data.get("build_number"), data.get("version")):
            logger.info(
                "New update discovered: build %s / version %s (local build %s / %s)",
                data.get("build_number"),
                data.get("version"),
                BUILD_NUMBER,
                APP_VERSION,
            )
            return data
        return None
