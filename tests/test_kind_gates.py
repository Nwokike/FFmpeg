"""Kind gates: no tool opens on media it cannot process.

The load gate (main._load_path_into / capture handoff) consults the shared
map; the extract screen's mode availability is the pure decision under the
chips. Render-level presence is covered by the all-screens harness — these
tests pin the DECISIONS so a wrong-kind file is refused before any queue job
can fail late.
"""

from __future__ import annotations

from core.constants import TOOL_MEDIA_KINDS, kind_allowed, kind_refusal
from core.state import MediaInfo, MediaStreamInfo
from screens.extract_screen import extract_mode_availability


def _media(kind: str, *, subs: bool = False, muted: bool = False) -> MediaInfo:
    streams: list[MediaStreamInfo] = []
    if kind in ("video", "image"):
        streams.append(
            MediaStreamInfo(
                index=0,
                stream_type="video",
                codec_name="h264" if kind == "video" else "mjpeg",
                disposition={"attached_pic": True} if kind == "image" else {},
            )
        )
    if kind == "audio" or (kind == "video" and not muted):
        streams.append(MediaStreamInfo(index=1, stream_type="audio", codec_name="aac"))
    if subs:
        streams.append(MediaStreamInfo(index=2, stream_type="subtitle", codec_name="subrip"))
    dur = {"video": 60.0, "audio": 30.0, "image": 0.0, "unknown": 0.0}[kind]
    return MediaInfo(
        file_path="x.mp4",
        file_name="x.mp4",
        file_size_bytes=1000,
        duration_s=dur,
        bitrate=0,
        format_name="mp4",
        format_long_name="mp4",
        streams=streams,
    )


# ── Contract of the shared map ───────────────────────────────────────────────


def test_tool_kinds_cover_every_tool_with_media():
    from app_shell import ACTIVE_VIEWS

    for tool in ("convert", "compress", "cut", "extract", "filters", "audio", "probe", "join"):
        assert tool in ACTIVE_VIEWS, f"{tool} is not a view"
        assert tool in TOOL_MEDIA_KINDS, f"{tool} missing from the kind map"


def test_kind_allowed_matches_engine_truth():
    # The dossier accepts anything probed.
    assert kind_allowed("probe", "unknown")
    # Convert adapts by kind — all three.
    assert kind_allowed("convert", "video")
    assert kind_allowed("convert", "audio")
    assert kind_allowed("convert", "image")
    # Video-only tools refuse audio and image.
    for tool in ("compress", "filters"):
        assert kind_allowed(tool, "video")
        assert not kind_allowed(tool, "audio")
        assert not kind_allowed(tool, "image")
    # Cut genuinely handles audio (engine truth) but not a photo.
    assert kind_allowed("cut", "audio")
    assert not kind_allowed("cut", "image")


def test_refusal_message_names_tool_and_kind():
    msg = kind_refusal("compress", "audio")
    assert "Compress" in msg and "audio" in msg


# ── Extract mode availability (engine truth per mode) ────────────────────────


def test_audio_file_cannot_offer_frames_or_gif():
    ok = extract_mode_availability(_media("audio"))
    assert ok["audio"] is True
    assert ok["frames"] is False and ok["gif"] is False, "engine raises for missing video"
    assert ok["subtitles"] is False


def test_video_without_audio_blocks_the_audio_mode():
    ok = extract_mode_availability(_media("video", muted=True))
    assert ok["audio"] is False, "extract_audio raises 'No audio stream' mid-job"
    assert ok["frames"] is True and ok["gif"] is True


def test_subtitles_mode_needs_subtitle_streams():
    assert extract_mode_availability(_media("video", subs=True))["subtitles"] is True
    assert extract_mode_availability(_media("video"))["subtitles"] is False


def test_unprobed_stays_permissive():
    ok = extract_mode_availability(None)
    assert ok["audio"] and ok["frames"] and ok["gif"]
    assert not ok["subtitles"], "no probe, no subtitle claims"
