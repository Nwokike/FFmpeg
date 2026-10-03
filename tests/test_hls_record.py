"""HLS master-variant + segment validation (device log job 930dc4d5).

The failing URL was a MASTER variant playlist: the old parser treated the
two variant URLs as media segments, downloaded two more playlists as bytes,
and av.open failed EOF on text. These tests pin the fixed behavior with
fixtures (no network).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.engine_service import EngineService

MASTER = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
https://cdn.example.com/hi/chunks.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
https://cdn.example.com/lo/chunks.m3u8
"""

MEDIA = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXTINF:6,
seg1.ts
#EXTINF:6,
seg2.ts
"""

ENCRYPTED = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-KEY:METHOD=AES-128,URI="key.bin"
#EXTINF:6,
seg1.ts
"""


def test_parse_master_picks_highest_bandwidth():
    from urllib.parse import urljoin

    segs, is_master, key_err = EngineService._parse_hls_playlist(
        MASTER, urljoin("https://x.example.com/a.m3u8", ".")
    )
    assert is_master is True
    assert key_err is None
    assert segs == ["https://cdn.example.com/hi/chunks.m3u8"]


def test_parse_media_lists_segments():
    segs, is_master, key_err = EngineService._parse_hls_playlist(MEDIA, "https://x.example.com/")
    assert is_master is False
    assert key_err is None
    assert segs == ["https://x.example.com/seg1.ts", "https://x.example.com/seg2.ts"]


def test_parse_encrypted_reports_key_error():
    _segs, _master, key_err = EngineService._parse_hls_playlist(ENCRYPTED, "https://x.example.com/")
    assert key_err is not None and "encrypted" in key_err.lower()


def test_master_variant_resolves_to_media_segments(monkeypatch, tmp_path):
    """Full path with mocked httpx: master -> media -> 2 TS segments."""
    import httpx

    bodies = {
        "https://alb.example.com/live.m3u8": (
            "#EXTM3U\n#EXT-X-VERSION:3\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080\n"
            "hi/chunks.m3u8\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360\n"
            "lo/chunks.m3u8\n"
        ),
        "https://alb.example.com/hi/chunks.m3u8": MEDIA,
        "https://alb.example.com/lo/chunks.m3u8": MEDIA,
        "https://alb.example.com/hi/seg1.ts": "TSBYTES1" * 20000,
        "https://alb.example.com/hi/seg2.ts": "TSBYTES2" * 20000,
    }

    class Resp:
        def __init__(self, url):
            self.url = url
            self._body = bodies[url].encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=None):
            yield self._body

    class GetResp:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url, timeout=None):
            return Resp(url)

        def get(self, url, timeout=None):
            return GetResp(bodies[url])

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("services.engine_service.get_temp_dir", lambda: tmp_path)
    import av

    opened = {}

    def fake_open(path, *a, **k):
        opened["path"] = path
        with Path(path).open("rb") as fh:
            data = fh.read()
        assert b"TSBYTES1" in data and b"TSBYTES2" in data
        assert b"#EXTM3U" not in data, "variant playlists must never land in the media bytes"

        class FakeContainer:
            def close(self):
                pass

        return FakeContainer()

    monkeypatch.setattr(av, "open", fake_open)
    _c, cleanup = EngineService._open_https_via_httpx("https://alb.example.com/live.m3u8")
    assert cleanup.endswith(".dat") or "https_dl_" in cleanup


def test_html_error_segment_fails_loud(monkeypatch, tmp_path):
    """A segment answering HTML must raise naming the cause, not blind EOF."""
    import httpx

    class Resp:
        def __init__(self, payload: bytes):
            self._p = payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=None):
            yield self._p

    class GetResp:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url, timeout=None):
            if url.endswith(".m3u8"):
                return Resp(b"#EXTM3U\nseg1.ts\n")
            return Resp(b"<html><body>403 Forbidden</body></html>" * 100)

        def get(self, url, timeout=None):
            return GetResp("#EXTM3U\nseg1.ts\n")

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("services.engine_service.get_temp_dir", lambda: tmp_path)
    with pytest.raises(ValueError, match="error page"):
        EngineService._open_https_via_httpx("https://x.example.com/live.m3u8")


def test_encrypted_playlist_refused_loud(monkeypatch, tmp_path):
    import httpx

    class GetResp:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url, timeout=None):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def raise_for_status(self):
                    pass

                def iter_bytes(self, chunk_size=None):
                    yield b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="k"\nseg.ts\n'

            return Resp()

        def get(self, url, timeout=None):
            return GetResp(ENCRYPTED)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("services.engine_service.get_temp_dir", lambda: tmp_path)
    with pytest.raises(ValueError, match="encrypted"):
        EngineService._open_https_via_httpx("https://x.example.com/live.m3u8")


def test_hls_cap_refuses_oversize_with_loud_message(monkeypatch):
    """Totals past the cap refuse naming size, cap, setting, and override."""

    class FakeClient:
        def get(self, url, timeout=None):
            class R:
                text = MEDIA

                def raise_for_status(self):
                    pass

            return R()

        def stream(self, method, url, timeout=None):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def raise_for_status(self):
                    pass

                def iter_bytes(self, chunk_size=None):
                    yield b"X" * (256 * 1024)

            return Resp()

    client = FakeClient()
    with pytest.raises(ValueError, match="download cap") as exc_info:
        EngineService._download_hls_segments(
            client, "https://x.example.com/live.m3u8", lambda: None, max_hls_download_mb=0.001
        )
    msg = str(exc_info.value)
    assert "Download anyway" in msg


def test_hls_cap_override_bypasses(monkeypatch):
    """ignore_hls_cap (None cap) lets the take through."""

    class FakeClient:
        def get(self, url, timeout=None):
            class R:
                text = MEDIA

                def raise_for_status(self):
                    pass

            return R()

        def stream(self, method, url, timeout=None):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def raise_for_status(self):
                    pass

                def iter_bytes(self, chunk_size=None):
                    yield b"X" * (64 * 1024)

            return Resp()

    out = EngineService._download_hls_segments(
        FakeClient(), "https://x.example.com/live.m3u8", lambda: None, max_hls_download_mb=None
    )
    assert len(out) == 2


def test_plain_file_single_get(monkeypatch, tmp_path):
    """Non-HLS bodies stream through ONE GET (no sniff-discard-reGET)."""
    import httpx

    calls: list[str] = []

    class Resp:
        def __init__(self):
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=None):
            yield b"BINARY-MEDIA-BYTES" * 4000

    class FakeClient:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url, timeout=None):
            calls.append(url)
            return Resp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("services.engine_service.get_temp_dir", lambda: tmp_path)
    import av

    class FakeContainer:
        def close(self):
            pass

    monkeypatch.setattr(av, "open", lambda *a, **k: FakeContainer())
    EngineService._open_https_via_httpx("https://x.example.com/file.mp4")
    assert calls == ["https://x.example.com/file.mp4"], "exactly one GET per plain file"


def test_estimate_hls_segments_sums_lengths(monkeypatch):
    class Head:
        def __init__(self, n):
            self.headers = {"content-length": str(n)}

        def raise_for_status(self):
            pass

    class FakeClient:
        def get(self, url, timeout=None):
            class R:
                text = MEDIA

                def raise_for_status(self):
                    pass

            return R()

        def head(self, url, timeout=None):
            return Head(100_000)

    segs, total = EngineService.estimate_hls_segments(
        FakeClient(), "https://x.example.com/live.m3u8"
    )
    assert len(segs) == 2
    assert total == 200_000


def test_estimate_hls_segments_none_when_length_missing(monkeypatch):
    class Head:
        def __init__(self):
            self.headers = {}

        def raise_for_status(self):
            pass

    class FakeClient:
        def get(self, url, timeout=None):
            class R:
                text = MEDIA

                def raise_for_status(self):
                    pass

            return R()

        def head(self, url, timeout=None):
            return Head()

    segs, total = EngineService.estimate_hls_segments(
        FakeClient(), "https://x.example.com/live.m3u8"
    )
    assert len(segs) == 2
    assert total is None


def test_segment_retry_succeeds_after_transient_failure():
    """One ReadError must not abort the playlist (bounded retries)."""
    import httpx

    attempts: list[str] = []

    class Resp:
        def __init__(self, payload: bytes):
            self._p = payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=None):
            yield self._p

    class FakeClient:
        def stream(self, method, url, timeout=None):
            attempts.append(url)
            if len([a for a in attempts if a == url]) == 1:
                raise httpx.ReadError("transient", request=None)
            return Resp(b"X" * (64 * 1024))

    out = EngineService._hls_download_segment(
        FakeClient(), "https://x.example.com/s.ts", 1, lambda: None
    )
    assert len(out) == 64 * 1024
    assert len(attempts) == 2


def test_segment_retry_gives_up_loud():
    import httpx

    class FakeClient:
        def stream(self, method, url, timeout=None):
            raise httpx.ConnectError("down", request=None)

    import pytest as _pytest

    with _pytest.raises(ValueError, match="after retries"):
        EngineService._hls_download_segment(
            FakeClient(), "https://x.example.com/s.ts", 1, lambda: None
        )


def test_hls_timeout_is_four_phase():
    assert EngineService._HLS_TIMEOUT == (10.0, 30.0, 30.0, 10.0)
