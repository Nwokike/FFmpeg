"""Declared chain geometry (scale/crop/pad) used to open the encoder."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.engine_service.sizing import _chain_declared_size  # noqa: E402


def test_pad_declares_the_output_size():
    nodes = [("pad", "800:500:(ow-iw)/2:(oh-ih)/2:black")]
    assert _chain_declared_size(nodes, (640, 360)) == (800, 500)


def test_crop_rect_declares_the_cropped_size():
    nodes = [("crop", "320:180:10:10")]
    assert _chain_declared_size(nodes, (640, 360)) == (320, 180)


def test_transpose_swaps_the_declared_axes():
    nodes = [("transpose", "clock")]
    assert _chain_declared_size(nodes, (640, 360)) == (360, 640)


def test_expression_geometry_stays_unknown():
    assert _chain_declared_size([("scale", "-2:720")], (640, 360)) is None
