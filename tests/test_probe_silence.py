"""Protocol probe stays quiet: the dead-port open must not emit native
ERROR lines (device log showed ``tcp://127.0.0.1:9 Connection refused`` as
an [ERROR] on every boot), while results stay identical."""

from __future__ import annotations

import logging

import av

from core.engine_probe import (
    _ffmpeg_build_identity,
    _find_attr,
    _probe_cache_path,
    _probe_protocol,
    probe,
)


def test_probe_protocol_returns_present_for_dead_port(caplog):
    """tcp/9 is always closed — the handler exists, so result is present."""
    with caplog.at_level(logging.DEBUG):
        assert _probe_protocol("tcp") == "present"


def test_probe_protocol_results_unchanged():
    """Silencing must not change present/missing verdicts."""
    assert _probe_protocol("tcp") == "present"
    assert _probe_protocol("http") == "present"
    # tcp and rtmp both ride the dead-port path — same verdict shape.
    assert _probe_protocol("rtmp") == "present"


def test_hwdevices_uses_hwaccel_path():
    """The hwaccel module (not a dead getattr) reports this machine's backends."""
    from av.codec.hwaccel import hwdevices_available

    expected = set(hwdevices_available())
    assert expected, "this dev machine must have HW backends to pin the path"
    assert probe().hw_devices == expected


def test_cache_key_includes_ffmpeg_build_identity():
    identity = _ffmpeg_build_identity()
    assert len(identity) == 12 and all(c in "0123456789abcdef" for c in identity)
    name = _probe_cache_path().name
    assert identity in name, "same-PyAV FFmpeg rebuilds must re-measure"
    assert av.__version__ in name
    assert "caps3" not in name, "stale caps3 files must be ignored"


def test_hls_and_dash_are_formats_only():
    p = probe()
    assert ("hls" in p.formats) == p.hls_ok
    assert ("dash" in p.formats) == p.dash_ok


def test_to_text_labels_preferred_tier_counts():
    text = probe().to_text()
    assert "preferred encoders verified" in text
    assert "preferred decoders verified" in text


def test_find_attr_resolves_dotted_module_path():
    assert _find_attr(av, "formats_available", "av.format.formats_available")
    assert _find_attr(av, "no_such_attr", "av.format.no_such_attr") == set()
