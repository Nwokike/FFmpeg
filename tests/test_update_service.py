"""UpdateService behavior across newer/same/missing/broken manifests."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from core.constants import BUILD_NUMBER, UPDATE_CONFIG_URL
from services.update_service import UpdateService


@pytest.fixture
def patch_client(monkeypatch):
    """Route every AsyncClient built by update_service through a MockTransport."""

    def _install(handler) -> None:
        real = httpx.AsyncClient

        class _Mocked(real):
            def __init__(self, **kwargs):
                kwargs["transport"] = httpx.MockTransport(handler)
                super().__init__(**kwargs)

        monkeypatch.setattr("services.update_service.httpx.AsyncClient", _Mocked)
        # The service pools ONE client per process — drop the cached one so
        # each test (and each event loop) gets its own mock transport.
        monkeypatch.setattr("services.update_service._CLIENT", None)

    return _install


def _check() -> dict | None:
    return asyncio.run(UpdateService.check_for_updates())


def test_newer_build_offers_update(patch_client):
    payload = {"build_number": BUILD_NUMBER + 1, "version": "9.9.9"}
    patch_client(lambda req: httpx.Response(200, json=payload))
    assert _check() == payload


def test_same_build_is_silent(patch_client):
    patch_client(lambda req: httpx.Response(200, json={"build_number": BUILD_NUMBER}))
    assert _check() is None


def test_404_is_silent(patch_client):
    patch_client(lambda req: httpx.Response(404))
    assert _check() is None


def test_timeout_is_silent(patch_client):
    def _raise(request):
        raise httpx.ConnectTimeout("boom", request=request)

    patch_client(_raise)
    assert _check() is None


def test_bad_json_is_silent(patch_client):
    patch_client(lambda req: httpx.Response(200, text="{not json"))
    assert _check() is None


def test_update_url_targets_canonical_repo():
    # Case guard: FFMPEG vs FFmpeg broke nothing on GitHub but must stay canonical
    assert UPDATE_CONFIG_URL.startswith("https://raw.githubusercontent.com/Nwokike/FFmpeg/")
    assert UPDATE_CONFIG_URL.endswith("/version.json")


def test_manifest_shape_when_present(patch_client):
    payload = json.loads(
        '{"build_number": 2, "version": "1.0.1", "release_notes": "x", "mandatory": false}'
    )
    patch_client(lambda req: httpx.Response(200, json=payload))
    data = _check()
    assert data is not None and data["build_number"] > BUILD_NUMBER


# ── version gate (build-only comparison missed version-only releases) ──────


def test_version_only_bump_offers_update(patch_client):
    payload = {"build_number": BUILD_NUMBER, "version": "9.0.0"}
    patch_client(lambda req: httpx.Response(200, json=payload))
    assert _check() == payload


def test_lexicographic_trap_is_not_hit(patch_client):
    # "1.10.0" > "1.9.0" numerically; any string compare gets this backwards.
    payload = {"build_number": BUILD_NUMBER, "version": "1.10.0"}
    patch_client(lambda req: httpx.Response(200, json=payload))
    assert _check() == payload


def test_older_version_same_build_is_silent(patch_client):
    patch_client(
        lambda req: httpx.Response(200, json={"build_number": BUILD_NUMBER, "version": "0.0.1"})
    )
    assert _check() is None


def test_garbage_version_does_not_crash(patch_client):
    patch_client(
        lambda req: httpx.Response(200, json={"build_number": BUILD_NUMBER, "version": "nightly"})
    )
    assert _check() is None


def test_non_dict_manifest_is_silent(patch_client):
    patch_client(lambda req: httpx.Response(200, json=[1, 2, 3]))
    assert _check() is None
