"""MediaInfo.kind — image/audio/video detection that drives screen gating."""

from __future__ import annotations

from core.state import MediaInfo, MediaStreamInfo


def _media(fmt: str, dur: float, codec: str | None, *, audio: bool = False, disposition=None):
    streams: list[MediaStreamInfo] = []
    if codec is not None:
        streams.append(
            MediaStreamInfo(
                index=0,
                stream_type="video",
                codec_name=codec,
                disposition=disposition or {},
            )
        )
    if audio:
        streams.append(MediaStreamInfo(index=1, stream_type="audio", codec_name="aac"))
    return MediaInfo(
        file_path="x",
        file_name="x",
        file_size_bytes=1,
        duration_s=dur,
        bitrate=0,
        format_name=fmt,
        format_long_name=fmt,
        streams=streams,
    )


def test_still_image_is_detected_as_image():
    assert _media("image2", 0.0, "png").kind == "image"
    assert _media("jpeg_pipe", 0.0, "mjpeg").kind == "image"


def test_real_video_is_detected_as_video():
    assert _media("mov,mp4,m4a,3gp,3g2,mj2", 10.0, "h264").kind == "video"
    # A long still with no audio is still a video if the container says so.
    assert _media("matroska", 10.0, "ffv1").kind == "video"


def test_cover_art_does_not_turn_an_audio_file_into_a_video():
    """An MP3's attached_pic video stream must not classify it as video."""
    kind = _media("mp3", 180.0, "mjpeg", audio=True, disposition={"attached_pic": True}).kind
    assert kind == "audio"


def test_audio_only_is_detected_as_audio():
    assert _media("wav", 60.0, None, audio=True).kind == "audio"


def test_unrecognized_is_unknown():
    assert _media("xyz", 0.0, None).kind == "unknown"
