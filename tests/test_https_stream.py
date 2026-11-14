"""HTTPS/HLS stream routing — the phone's ProtocolNotFoundError regression."""

from __future__ import annotations

from threading import Event
from unittest.mock import MagicMock

import av
import httpx
import pytest

from services.engine_service import EngineService, friendly_job_error


def test_https_routes_through_httpx_only_on_a_tls_less_wheel(monkeypatch):
    """A wheel without a TLS handler must not hand https to av.open.

    That is the stock bare-LGPL flet-libffmpeg (and the old Mobile Forge build);
    the capability probe decides, not the platform.
    """
    import services.engine_service as es

    sentinel = MagicMock()
    monkeypatch.setattr("services.engine_service.options._TLS_OK", False)
    monkeypatch.setattr(
        EngineService,
        "_open_https_via_httpx",
        staticmethod(
            lambda url, cancel_event=None, max_hls_download_mb=None: (sentinel, "/tmp/backing.dat")
        ),
    )

    def fail_open(*_args, **_kwargs):
        raise AssertionError("HTTPS must not reach av.open on a TLS-less wheel")

    monkeypatch.setattr(av, "open", fail_open)

    container, cleanup = EngineService._open_network_input("https://example.com/stream.m3u8")
    assert container is sentinel
    assert cleanup == "/tmp/backing.dat"


def test_http_routes_straight_to_native_av_open(monkeypatch):
    """Only HTTPS needs the httpx transport — HTTP keeps PyAV's own path."""
    container = MagicMock()
    monkeypatch.setattr(av, "open", lambda *a, **k: container)
    monkeypatch.setattr(
        EngineService,
        "_open_https_via_httpx",
        staticmethod(lambda *a, **k: pytest.fail("HTTP must not use the httpx path")),
    )

    got_container, cleanup = EngineService._open_network_input("http://example.com/stream")
    assert got_container is container
    assert cleanup is None


def test_https_uses_av_open_when_the_wheel_has_tls(monkeypatch):
    """Our wrap wheel ships TLS: https goes straight to av.open."""
    import services.engine_service as es

    container = MagicMock()
    monkeypatch.setattr("services.engine_service.options._TLS_OK", True)
    monkeypatch.setattr(av, "open", lambda *a, **k: container)
    monkeypatch.setattr(
        EngineService,
        "_open_https_via_httpx",
        staticmethod(
            lambda *a, **k: pytest.fail("a TLS-capable wheel must not use the httpx path")
        ),
    )

    got_container, cleanup = EngineService._open_network_input("https://example.com/stream.m3u8")
    assert got_container is container
    assert cleanup is None


def test_https_download_cancel_raises_interrupted(monkeypatch):
    """A cancelled download must raise rather than write a zero-byte output."""
    cancel = Event()
    cancel.set()

    class FakeClient:
        def __init__(self, **_kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, *_a, **_kw):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def raise_for_status(self):
                    pass

                def iter_bytes(self, chunk_size=None):
                    yield b"x" * 1024

            return Resp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    with pytest.raises(InterruptedError):
        EngineService._open_https_via_httpx("https://example.com/large.bin", cancel_event=cancel)


def test_https_protocol_error_message_is_friendly():
    exc = av.error.ProtocolNotFoundError("https", "Protocol not found")
    message = friendly_job_error(exc)
    assert "UnknownCodec" not in message
    assert "protocol" in message.lower()
