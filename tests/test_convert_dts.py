"""Convert duplicate-DTS regression: encoder-emitted packets with identical
DTS must be bumped at mux time (device log: ``12800 >= 12800`` EINVAL).

``_monotonic_video_pts`` keeps *frame* PTS strictly increasing, but on a
coarse output time base the encoder can still emit two packets with the same
DTS. The MP4 muxer rejects those, so ``convert()`` clamps at ``mux`` time.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from services.engine_service import EngineService


def test_convert_survives_duplicate_dts_source(synthetic_media, tmp_path):
    """A source whose decoder yields duplicate-DTS frames still muxes clean."""
    import av

    src = synthetic_media.path
    out = str(tmp_path / "dts_fixed.mp4")
    # Baseline convert must succeed and produce a playable file.
    EngineService.convert(
        input_path=src,
        output_path=out,
        video_codec="mpeg4",
        audio_codec="aac",
        crf=30,
    )
    assert Path(out).exists() and Path(out).stat().st_size > 0
    with av.open(out) as c:
        assert c.duration is not None and c.duration > 0


def test_convert_mux_dts_is_strictly_increasing(synthetic_media, tmp_path):
    """Every muxed video packet DTS in the output is strictly increasing."""
    import av

    src = synthetic_media.path
    out = str(tmp_path / "dts_strict.mp4")
    EngineService.convert(
        input_path=src,
        output_path=out,
        video_codec="mpeg4",
        audio_codec="aac",
        crf=30,
    )
    with av.open(out) as c:
        v = c.streams.video[0]
        dts_list = [p.dts for p in c.demux(v) if p.dts is not None]
    assert len(dts_list) > 1
    assert all(b > a for a, b in pairwise(dts_list)), "DTS must be strictly increasing"
