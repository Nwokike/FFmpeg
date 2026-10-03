"""Capture helpers: permission mapping and platform gate.

The old PCM-streaming helpers (_write_wav/_pcm_rms) were deleted with the
direct-file rewrite — streaming was never wired, so they were dead code with
tests. What remains is the permission contract and the platform gate.
"""

from __future__ import annotations

from types import SimpleNamespace

from screens.capture_screen import _can_capture, next_permission_action

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


def test_permanently_denied_goes_to_settings():
    assert next_permission_action("permanentlyDenied") == "settings"


def test_restricted_is_unavailable_not_settings():
    # RESTRICTED (parental/MDM lock) forbids changes at OS level — a Settings
    # trip cannot help, so it gets its own action, not "settings".
    assert next_permission_action("restricted") == "unavailable"


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


def test_recorder_config_surface():
    """Config kwargs M5.3 passes must exist on the installed plugin model."""
    from flet_audio_recorder import AudioEncoder, AudioRecorderConfiguration

    cfg = AudioRecorderConfiguration(
        encoder=AudioEncoder.FLAC,
        channels=2,
        sample_rate=44100,
        bit_rate=0,
        suppress_noise=True,
        cancel_echo=True,
        auto_gain=True,
    )
    assert cfg.encoder == AudioEncoder.FLAC
    assert cfg.suppress_noise is True
    assert AudioEncoder.FLAC is not None


def test_camera_control_surface():
    """Camera methods M5.3 calls must exist on the installed plugin."""
    import flet_camera as ftc

    for method in (
        "set_flash_mode",
        "set_description",
        "set_zoom_level",
        "get_min_zoom_level",
        "get_max_zoom_level",
        "lock_capture_orientation",
        "unlock_capture_orientation",
        "resume_preview",
    ):
        assert hasattr(ftc.Camera, method), f"Camera.{method} missing"
    assert ftc.FlashMode.TORCH is not None
    assert ftc.FlashMode.OFF is not None


def test_shared_permission_helper_parity():
    from core.permissions import next_permission_action as shared
    from screens.capture_screen import next_permission_action as local

    for status in ("granted", "denied", "permanentlyDenied", "restricted", "limited", None):
        for asked in (False, True):
            assert shared(status, asked) == local(status, asked)
