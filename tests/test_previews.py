"""Preview helpers: thumbnail strip, keyframe index, result time label, cut snap."""

from __future__ import annotations

from screens.result_screen import _fmt_ms
from services.engine_service import EngineService, _mjpeg_bytes

# ── Result screen time label ─────────────────────────────────────────────


def test_fmt_ms():
    assert _fmt_ms(0) == "00:00"
    assert _fmt_ms(999) == "00:00"
    assert _fmt_ms(61_000) == "01:01"
    assert _fmt_ms(59_999) == "00:59"
    assert _fmt_ms(-5) == "00:00"


# ── Thumbnail strip (in-memory JPEGs, single decode pass) ────────────────


def test_thumbnail_strip_returns_jpegs(synthetic_media):
    thumbs = EngineService.thumbnail_strip(synthetic_media.path, [0.5, 1.0, 1.5], width=64)
    assert len(thumbs) == 3
    for t in thumbs:
        assert t[:2] == b"\xff\xd8"  # JPEG SOI magic
        assert len(t) > 100


def test_thumbnail_strip_empty_and_no_video(synthetic_media, tmp_path):
    assert EngineService.thumbnail_strip(synthetic_media.path, []) == []

    srt = tmp_path / "only.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n", encoding="utf-8")
    assert EngineService.thumbnail_strip(str(srt), [0.5]) == []


def test_mjpeg_bytes_rejects_nothing(synthetic_media):
    import av

    with av.open(synthetic_media.path) as inp:
        for pkt in inp.demux([inp.streams.video[0]]):
            frames = pkt.decode()
            if frames:
                data = _mjpeg_bytes(frames[0], 48)
                assert data[:2] == b"\xff\xd8"
                break


# ── Keyframe index ───────────────────────────────────────────────────────


def test_keyframe_times_sorted_and_bounded(synthetic_media):
    from services.engine_service import EngineService as E

    dur = E.probe(synthetic_media.path).duration_s
    kfs = E.keyframe_times(synthetic_media.path)
    assert kfs, "fixture uses keyint=10 — must expose keyframes"
    assert kfs == sorted(kfs)
    assert kfs[0] <= 0.1
    assert all(0.0 <= k <= dur + 0.1 for k in kfs)


def test_keyframe_times_respects_limit(synthetic_media):
    kfs = EngineService.keyframe_times(synthetic_media.path, limit=2)
    assert len(kfs) <= 2


def test_keyframe_times_no_video(synthetic_media, tmp_path):

    srt = tmp_path / "only.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n", encoding="utf-8")
    assert EngineService.keyframe_times(str(srt)) == []


# ── Keyframe snap (instant cuts) ─────────────────────────────────────────


def test_stream_copy_snaps_start_to_keyframe(synthetic_media):
    """Cut from a mid-GOP point must begin at the prior keyframe, not 1.05s."""
    out = str(synthetic_media.dir / "snapped.mp4")
    events: list[str] = []

    EngineService.cut_trim(
        synthetic_media.path,
        out,
        1.05,
        2.0,
        stream_copy=True,
        on_progress=lambda p, m: events.append(m),
    )

    assert any("snapped" in m for m in events), events
    dur = EngineService.probe(out).duration_s
    # Snap pulls start back to the ~1.0s keyframe → ~1.0s of output, not 0.95
    assert dur > 0.97, f"expected ~1.0s after snap, got {dur:.3f}s"


def test_reencode_cut_is_not_snapped(synthetic_media):
    """Exact (re-encode) mode honors the requested start precisely."""
    out = str(synthetic_media.dir / "exact.mp4")
    events: list[str] = []

    EngineService.cut_trim(
        synthetic_media.path,
        out,
        1.05,
        2.0,
        stream_copy=False,
        on_progress=lambda p, m: events.append(m),
    )

    assert not any("snapped" in m for m in events), events
    dur = EngineService.probe(out).duration_s
    assert dur < 1.0, f"re-encode must keep exact start, got {dur:.3f}s"


def test_cut_player_carries_title_and_playlist_mode():
    import flet_video as ftv

    src = "C:/x/in.mp4"
    player = ftv.Video(
        playlist=[ftv.VideoMedia(src)],
        autoplay=False,
        title="Trim preview: in.mp4",
        controls=None,
        playlist_mode=ftv.PlaylistMode.NONE,
    )
    assert player.title == "Trim preview: in.mp4"
    assert player.playlist_mode == ftv.PlaylistMode.NONE
    assert len(player.playlist) == 1


def test_result_player_title_and_subtitle_track():
    import flet_video as ftv

    player = ftv.Video(
        playlist=[ftv.VideoMedia("C:/x/out.mp4")],
        autoplay=False,
        title="Result: out.mp4",
        playlist_mode=ftv.PlaylistMode.NONE,
        subtitle_track=ftv.VideoSubtitleTrack(src="C:/x/out.srt", title="out.srt", language="en"),
    )
    assert player.title == "Result: out.mp4"
    assert player.subtitle_track is not None


def test_audio_loop_and_balance_fields_exist():
    from flet_audio import Audio, ReleaseMode

    player = Audio(src="C:/x/out.mp3", release_mode=ReleaseMode.STOP)
    player.release_mode = ReleaseMode.LOOP
    assert player.release_mode == ReleaseMode.LOOP
    player.balance = -1.0
    assert player.balance == -1.0
    player.playback_rate = 1.5
    assert player.playback_rate == 1.5
