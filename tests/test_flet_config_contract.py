"""Guard the Flet CLI configuration keys that are easy to typo or mis-scope."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _flet() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["tool"]["flet"]


def test_boot_screen_uses_supported_nested_shape():
    boot = _flet()["boot_screen"]
    assert boot["name"] == "flet"
    assert boot["flet"]["startup_message"] == "Initializing FFmpeg Lite..."


def test_android_deep_link_is_platform_scoped():
    flet = _flet()
    assert "deep_linking" not in flet
    assert flet["android"]["deep_linking"] == {"scheme": "ffmpeg", "host": "app"}


def test_android_config_has_no_silently_ignored_keys():
    android = _flet()["android"]
    assert "min_sdk_version" not in android
    assert "manifest_application" not in android
    assert android["split_per_abi"] is True
    assert android["extract_packages"] == ["av"]
    # Flet's bundled Python and the Mobile Forge PyAV index publish all three
    # Android ABIs; the earlier arm64-only pin copied a sibling app's note
    # about an emulator-only split that is not a dependency constraint here.
    assert android["target_arch"] == ["arm64-v8a", "x86_64", "armeabi-v7a"]


def test_cross_platform_permission_groups_are_declared():
    flet = _flet()
    assert flet["permissions"] == ["camera", "microphone"]
    permissions = flet["android"]["permission"]
    assert permissions["android.permission.CAMERA"] is True
    assert permissions["android.permission.RECORD_AUDIO"] is True


def test_desktop_flavor_is_deterministic():
    assert _flet()["desktop_flavor"] == "full"
