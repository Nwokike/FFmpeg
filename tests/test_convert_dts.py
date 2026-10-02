"""Convert duplicate-DTS regression: encoder-emitted packets with identical
DTS must be bumped at mux time (device log: ``12800 >= 12800`` EINVAL).

``_monotonic_video_pts`` keeps *frame* PTS strictly increasing, but on a
coarse output time base the encoder can still emit two packets with the same
DTS. The MP4 muxer rejects those, so every re-encode path muxes through the
module-level ``_MuxClamp`` (pts+dts floor per stream).
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from services.engine_service import EngineService, _crop_dims


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


def _assert_strict_dts(path: str) -> None:
    import av

    with av.open(path) as c:
        kinds = ["video"] if c.streams.video else []
        kinds += ["audio"] if c.streams.audio else []
    assert kinds, f"expected A/V streams in {path}"
    for kind in kinds:
        # Fresh open per stream: a second demux() pass on one container
        # does not reliably re-yield the other stream's packets.
        with av.open(path) as c:
            stream = getattr(c.streams, kind)[0]
            stamps = [p.dts for p in c.demux(stream) if p.dts is not None]
        assert len(stamps) > 1, f"expected stamped packets on {kind} in {path}"
        assert all(b > a for a, b in pairwise(stamps)), f"DTS must be strictly increasing on {kind}"


def test_compress_mux_stamps_strictly_increasing(synthetic_media, tmp_path):
    out = str(tmp_path / "compress_strict.mp4")
    EngineService.compress_to_target(
        input_path=synthetic_media.path, output_path=out, target_size_mb=8.0
    )
    assert Path(out).exists()
    _assert_strict_dts(out)


def test_cut_reencode_mux_stamps_strictly_increasing(synthetic_media, tmp_path):
    out = str(tmp_path / "cut_strict.mp4")
    EngineService.cut_trim(
        input_path=synthetic_media.path,
        output_path=out,
        start_seconds=0.0,
        end_seconds=1.5,
        stream_copy=False,
    )
    assert Path(out).exists()
    _assert_strict_dts(out)


def test_concat_reencode_mux_stamps_strictly_increasing(synthetic_media, tmp_path):
    out = str(tmp_path / "concat_strict.mp4")
    EngineService.concat(
        paths=[synthetic_media.path, synthetic_media.path],
        output_path=out,
        transition="cut",
    )
    assert Path(out).exists()
    _assert_strict_dts(out)


def test_cancel_skips_drain_and_flush(synthetic_media, tmp_path):
    """A cancelled convert must not mux drained/flushed packets afterwards."""
    import threading
    from contextlib import suppress

    out = str(tmp_path / "cancelled.mp4")
    evt = threading.Event()
    evt.set()  # cancelled before the first packet
    with suppress(InterruptedError):
        EngineService.convert(
            input_path=synthetic_media.path,
            output_path=out,
            video_codec="mpeg4",
            audio_codec="aac",
            cancel_event=evt,
        )
    assert not Path(out).exists(), "cancelled output must be discarded"


def test_crop_dims_even_after_clamp():
    # Odd source dim must not come back through min() still odd — the crop
    # filter rejects odd dims for yuv420p.
    cw, ch = _crop_dims(853, 480, "16:9")
    assert cw % 2 == 0 and ch % 2 == 0
    cw, ch = _crop_dims(640, 481, "1:1")
    assert cw % 2 == 0 and ch % 2 == 0
