"""Audio effect-chain ordering (pure; no media needed)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.engine_service.ops_audio import _audio_effect_nodes  # noqa: E402


def test_loudness_gain_fades_and_caller_nodes_keep_order():
    nodes = _audio_effect_nodes(
        loudnorm_args="i=-14",
        gain_db=-6.0,
        fade_in_s=0.5,
        fade_out_s=1.0,
        duration_s=10.0,
        extra=[("highpass", "f=80"), ("volume", "")],
    )
    assert [name for name, _ in nodes] == [
        "loudnorm",
        "volume",
        "afade",
        "afade",
        "highpass",
        "volume",
    ]
    assert nodes[1][1] == "-6.00dB"
    assert nodes[2][1] == "t=in:st=0:d=0.500"
    assert nodes[3][1] == "t=out:st=9.000:d=1.000"
    assert nodes[4][1] == "f=80"
    assert nodes[5][1] is None


def test_no_effects_means_no_chain():
    assert (
        _audio_effect_nodes(
            loudnorm_args=None, gain_db=0.0, fade_in_s=0, fade_out_s=0, duration_s=10, extra=None
        )
        == []
    )


def test_out_fade_without_duration_is_skipped():
    nodes = _audio_effect_nodes(
        loudnorm_args=None, gain_db=0.0, fade_in_s=0, fade_out_s=1.0, duration_s=0.0, extra=None
    )
    assert nodes == []
