"""Capture helpers: permission mapping, WAV wrapping, RMS meter, platform gate."""

from __future__ import annotations

import struct
from pathlib import Path
from types import SimpleNamespace

from screens.capture_screen import _can_capture, _pcm_rms, _write_wav, next_permission_action

# ── Permission status → action mapping ───────────────────────────────────


def test_granted_statuses_are_ok():
    for status in ("granted", "limited", "provisional", "GRANTED", "Granted"):
        assert next_permission_action(status) == "ok"


def test_enumerated_member_with_value_attr():
    member = SimpleNamespace(value="granted")
    assert next_permission_action(member) == "ok"
    member = SimpleNamespace(value="permanentlyDenied")
    assert next_permission_action(member, just_requested=True) == "settings"


def test_unknown_status_asks():
    assert next_permission_action(None) == "ask"
    assert next_permission_action(None, just_requested=True) == "explain"


def test_denied_first_asks_then_explains():
    assert next_permission_action("denied") == "ask"
    assert next_permission_action("denied", just_requested=True) == "explain"


def test_permanently_denied_and_restricted_go_to_settings():
    assert next_permission_action("permanentlyDenied") == "settings"
    assert next_permission_action("restricted") == "settings"


# ── WAV wrapper ──────────────────────────────────────────────────────────


def test_write_wav_header(tmp_path: Path):
    data = struct.pack("<4h", 0, 1000, -1000, 0)
    out = tmp_path / "t.wav"
    _write_wav(str(out), data, sample_rate=44100, channels=2)

    raw = out.read_bytes()
    assert raw[:4] == b"RIFF"
    assert raw[8:12] == b"WAVE"
    assert raw[12:16] == b"fmt "
    riff_size = struct.unpack("<I", raw[4:8])[0]
    assert riff_size == 36 + len(data)
    channels, rate = struct.unpack("<H", raw[22:24])[0], struct.unpack("<I", raw[24:28])[0]
    assert (channels, rate) == (2, 44100)
    assert raw[36:40] == b"data"
    data_len = struct.unpack("<I", raw[40:44])[0]
    assert data_len == len(data)
    assert raw[44:] == data


def test_write_wav_mono_voice_preset(tmp_path: Path):
    out = tmp_path / "v.wav"
    _write_wav(str(out), b"\x00\x00" * 16, sample_rate=16000, channels=1)
    raw = out.read_bytes()
    assert struct.unpack("<H", raw[22:24])[0] == 1
    assert struct.unpack("<I", raw[24:28])[0] == 16000


# ── PCM RMS meter ────────────────────────────────────────────────────────


def test_rms_of_silence_is_zero():
    assert _pcm_rms(b"\x00\x00" * 512) == 0.0


def test_rms_of_loud_signal_is_high():
    loud = struct.pack("<h", 30000) * 512
    assert _pcm_rms(loud) > 0.5


def test_rms_of_empty_or_odd_chunk():
    assert _pcm_rms(b"") == 0.0
    assert _pcm_rms(b"\x00") == 0.0  # odd trailing byte is ignored


# ── Platform gate ────────────────────────────────────────────────────────


def test_can_capture_web_and_mobile():
    assert _can_capture(SimpleNamespace(web=True, platform=None))
    mobile = SimpleNamespace(web=False, platform=SimpleNamespace(is_mobile=lambda: True))
    assert _can_capture(mobile)


def test_can_capture_rejects_desktop_and_broken_platform():
    desktop = SimpleNamespace(web=False, platform=SimpleNamespace(is_mobile=lambda: False))
    assert not _can_capture(desktop)
    assert not _can_capture(SimpleNamespace(web=False, platform=None))

    class ExplodingPlatform:
        @property
        def is_mobile(self):
            raise RuntimeError("no platform")

    assert not _can_capture(SimpleNamespace(web=False, platform=ExplodingPlatform()))
