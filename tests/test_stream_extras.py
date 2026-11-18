"""Device enumeration and the honest DASH preflight (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.engine_probe import input_devices, output_devices  # noqa: E402
from services.engine_service.ops_network import estimate_hls_segments  # noqa: E402


def test_device_enumeration_returns_a_list():
    assert isinstance(input_devices(), list)
    assert isinstance(output_devices(), list)
    for dev in input_devices():
        assert "name" in dev and "description" in dev


def test_dash_preflight_is_refused_with_a_reason():
    with pytest.raises(ValueError, match="DASH"):
        estimate_hls_segments(None, "https://example.com/manifest.mpd")
