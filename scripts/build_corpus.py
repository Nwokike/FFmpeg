#!/usr/bin/env python3
"""Build the media corpus the ability matrix runs against.

Assets are generated with **av itself** wherever possible — the same wheel the
app ships — so the corpus is deterministic, offline and cannot rot when a
download URL moves. The one thing PyAV cannot produce from Python (subtitle
*encoding*) comes from an ``ffmpeg`` binary when one is on PATH; those assets
are recorded as such and the matrix skips their tests when missing.

Usage: uv run python scripts/build_corpus.py [--out DIR] [--force]
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import av

DEFAULT_OUT = Path.home() / ".cache" / "ffmpeg-av" / "corpus"

# A moving 2 s clip at a small size: cheap to encode, deterministic, and the
# motion gives the encoders something to spend bits on.
CLIP_SECONDS = 2
CLIP_FPS = 25
CLIP_SIZE = (320, 180)


# ── frame builders ───────────────────────────────────────────────────────────


def _video_frames(width: int, height: int, pix_fmt: str, count: int, fps: int):
    for i in range(count):
        frame = av.VideoFrame(width, height, pix_fmt)
        plane = frame.planes[0]
        rows = bytearray()
        for y in range(height):
            rows.extend(bytes(((x + y * 3 + i * 9) & 0xFF) for x in range(plane.line_size)))
        plane.update(bytes(rows[: plane.buffer_size]))
        frame.pts = i
        frame.time_base = Fraction(1, fps)
        yield frame


def _audio_frames(rate: int, layout: str, seconds: float):
    total = int(rate * seconds)
    done = 0
    channels = 2 if layout == "stereo" else 1
    while total - done >= 1024:
        chunk = 1024
        frame = av.AudioFrame("s16", layout, chunk)
        frame.sample_rate = rate
        frame.pts = done
        frame.time_base = Fraction(1, rate)
        samples = bytearray()
        for k in range(chunk):
            value = int(12000 * math.sin(2 * math.pi * 440 * (done + k) / rate)).to_bytes(
                2, "little", signed=True
            )
            samples.extend(value * channels)
        frame.planes[0].update(bytes(samples))
        done += chunk
        yield frame


def _encoder_pix_fmt(codec: str) -> str:
    """The codec's first declared format (the wheel's own answer)."""
    try:
        formats = av.Codec(codec, "w").video_formats or []
    except Exception:
        return "yuv420p"
    names = [str(fmt.name) for fmt in formats]
    for candidate in ("yuv420p", "yuv422p", "rgb24", "gray"):
        if candidate in names:
            return candidate
    return names[0] if names else "yuv420p"


# ── one asset ────────────────────────────────────────────────────────────────


def _encode(
    path: Path,
    *,
    video: dict | None = None,
    audio: list[dict] | None = None,
    mux: str | None = None,
    chapters: list[dict] | None = None,
    attach: tuple[str, str, bytes] | None = None,
    data: str | None = None,
) -> None:
    """Write one asset: any mix of video, audio tracks, chapters, attachment, data.

    ``video`` keys: codec, width, height, pix_fmt, fps, seconds, sar, rotate,
    field_order, color (primaries, trc, space), options, bit_rate.
    """
    container = av.open(str(path), "w", format=mux)
    try:
        # ── create EVERY stream before the first mux ─────────────────────
        # The muxer writes its header on the first packet; a stream added
        # afterwards never gets a proper time base (0/1), and muxing into it
        # then crashes libavformat's interleaver with a division by zero.
        video_stream = None
        if video:
            fps = int(video.get("fps", CLIP_FPS))
            codec = str(video["codec"])
            video_stream = container.add_stream(codec, rate=fps, options=video.get("options"))
            video_stream.width = int(video.get("width", CLIP_SIZE[0]))
            video_stream.height = int(video.get("height", CLIP_SIZE[1]))
            video_stream.pix_fmt = str(video.get("pix_fmt") or _encoder_pix_fmt(codec))
            video_stream.time_base = Fraction(1, fps)
            if video.get("bit_rate"):
                video_stream.bit_rate = int(video["bit_rate"])
            context = video_stream.codec_context
            if video.get("color"):
                # FFmpeg enum ints: AVCOL_PRI_BT2020 = 9,
                # AVCOL_TRC_SMPTE2084 = 16, AVCOL_SPC_BT2020NCL = 9.
                primaries, trc, space = video["color"]
                context.color_primaries = int(primaries)
                context.color_trc = int(trc)
                context.colorspace = int(space)
            if video.get("field_order"):
                # av 19 exposes these as the FFmpeg enum ints:
                # AV_FIELD_TT = 2 (top-field-first).
                context.field_order = int(video["field_order"])
            if video.get("sar"):
                context.sample_aspect_ratio = Fraction(*video["sar"])
            if video.get("rotate"):
                video_stream.set_display_rotation(int(video["rotate"]))

        audio_streams: list[tuple[object, dict]] = []
        for spec in audio or []:
            rate = int(spec.get("rate", 44100))
            if str(spec["codec"]) == "libopus" and rate not in (8000, 12000, 16000, 24000, 48000):
                rate = 48000  # libopus refuses every other rate
            stream = container.add_stream(str(spec["codec"]), rate=rate)
            stream.layout = str(spec.get("layout", "stereo"))
            if spec.get("bit_rate"):
                stream.bit_rate = int(spec["bit_rate"])
            if spec.get("language"):
                # av 19 exposes language as stream metadata, not a settable
                # codec-context attribute.
                stream.metadata["language"] = str(spec["language"])
            audio_streams.append((stream, spec))

        if data:
            container.add_data_stream(data)
        if attach:
            container.add_attachment(*attach)
        if chapters:
            container.set_chapters(chapters)

        # ── encode ────────────────────────────────────────────────────────
        if video_stream is not None:
            fps = int(video.get("fps", CLIP_FPS))  # type: ignore[union-attr]
            for frame in _video_frames(
                video_stream.width,
                video_stream.height,
                video_stream.pix_fmt,
                int(video.get("seconds", CLIP_SECONDS) * fps),  # type: ignore[union-attr]
                fps,
            ):
                for packet in video_stream.encode(frame):
                    container.mux(packet)
            for packet in video_stream.encode(None):
                container.mux(packet)

        for stream, spec in audio_streams:
            rate = int(spec.get("rate", 44100))
            for frame in _audio_frames(
                rate, str(spec.get("layout", "stereo")), float(spec.get("seconds", CLIP_SECONDS))
            ):
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode(None):
                container.mux(packet)
    finally:
        container.close()


# ── ffmpeg-backed helpers (subtitles only) ──────────────────────────────────


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def _run_ffmpeg(args: list[str]) -> bool:
    binary = _ffmpeg()
    if binary is None:
        return False
    result = subprocess.run(
        [binary, "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ffmpeg: {result.stderr.strip()[:200]}")
    return result.returncode == 0


def _cover_mp3(out: Path) -> bool:
    """MP3 + attached cover art (ffmpeg: av's attachment lacks attached_pic)."""
    art = out / "cover_art.jpg"
    art.write_bytes(_jpeg_bytes())
    return _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=2",
            "-i",
            str(art),
            "-map",
            "0:a",
            "-map",
            "1:v",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "96k",
            "-c:v",
            "mjpeg",
            "-disposition:v",
            "attached_pic",
            str(out / "cover.mp3"),
        ]
    )


def _subtitle_asset(path: Path, *, codec: str, mux: str | None = None) -> bool:
    """A video file with a subtitle track (PyAV cannot encode subtitles)."""
    cues = path.with_suffix(".srt")
    cues.write_text(
        "1\n00:00:00,000 --> 00:00:01,500\nHello from the corpus\n\n"
        "2\n00:00:01,500 --> 00:00:02,000\nSecond cue\n",
        encoding="utf-8",
    )
    args = ["-i", str(cues)]
    if mux:
        args += ["-f", mux]
    return _run_ffmpeg([*args, "-c:s", codec, str(path)])


def _jpeg_bytes() -> bytes:
    """A tiny JPEG payload for the cover-art asset (no external file needed)."""
    cache = Path(DEFAULT_OUT).parent / "corpus_cover_src.jpg"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        frame = av.VideoFrame(64, 64, "rgb24")
        frame.planes[0].update(bytes([200, 40, 40]) * (64 * 64))
        frame.save(str(cache))
    return cache.read_bytes()


# ── the asset table ─────────────────────────────────────────────────────────


def build(out: Path, force: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}

    def add(name: str, builder, *, by: str = "av", note: str = "") -> None:
        path = out / name
        if path.exists() and not force:
            manifest[name] = {"path": str(path), "by": by, "note": note}
            return
        ok = False
        try:
            builder()
            ok = path.exists() and path.stat().st_size > 0
        except Exception as exc:
            print(f"  build error: {type(exc).__name__}: {exc}")
        manifest[name] = {
            "path": str(path) if ok else "",
            "by": by,
            "note": note if ok else (note or "build failed"),
        }
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")

    audio = [{"codec": "aac", "layout": "stereo", "language": "eng"}]
    print(f"building corpus in {out}")

    # ── the baseline every test starts from ───────────────────────────────
    add(
        "h264_mp4.mp4",
        lambda: _encode(out / "h264_mp4.mp4", video={"codec": "libx264"}, audio=audio),
        note="H.264 + AAC in MP4",
    )

    # ── encoders / containers ─────────────────────────────────────────────
    add(
        "hevc_mp4.mp4",
        lambda: _encode(out / "hevc_mp4.mp4", video={"codec": "libx265"}, audio=audio, mux="mp4"),
        note="HEVC",
    )
    add(
        "vp9_webm.webm",
        lambda: _encode(
            out / "vp9_webm.webm",
            video={"codec": "libvpx-vp9"},
            audio=[{"codec": "libopus"}],
            mux="webm",
        ),
        note="VP9 + Opus",
    )
    add(
        "av1_mkv.mkv",
        lambda: _encode(
            out / "av1_mkv.mkv",
            video={"codec": "libsvtav1"},
            audio=[{"codec": "libopus"}],
            mux="matroska",
        ),
        note="AV1 (SVT)",
    )
    add(
        "mpeg4_avi.avi",
        lambda: _encode(out / "mpeg4_avi.avi", video={"codec": "mpeg4"}, audio=audio, mux="avi"),
        note="MPEG-4 Part 2",
    )
    add(
        "ffv1_mkv.mkv",
        lambda: _encode(
            out / "ffv1_mkv.mkv", video={"codec": "ffv1"}, audio=[{"codec": "flac"}], mux="matroska"
        ),
        note="FFV1 lossless",
    )
    add(
        "prores_mov.mov",
        lambda: _encode(
            out / "prores_mov.mov",
            video={"codec": "prores"},
            audio=[{"codec": "pcm_s16le"}],
            mux="mov",
        ),
        note="ProRes",
    )
    add(
        "mjpeg_avi.avi",
        lambda: _encode(
            out / "mjpeg_avi.avi",
            video={"codec": "mjpeg", "pix_fmt": "yuvj420p"},
            audio=[{"codec": "pcm_s16le"}],
            mux="avi",
        ),
        note="MJPEG",
    )

    # ── pixel formats ─────────────────────────────────────────────────────
    add(
        "h264_10bit.mp4",
        lambda: _encode(
            out / "h264_10bit.mp4",
            video={"codec": "libx264", "pix_fmt": "yuv420p10le"},
            audio=audio,
        ),
        note="10-bit",
    )
    add(
        "h264_422.mp4",
        lambda: _encode(
            out / "h264_422.mp4", video={"codec": "libx264", "pix_fmt": "yuv422p"}, audio=audio
        ),
        note="4:2:2",
    )
    add(
        "h264_gray.mp4",
        lambda: _encode(
            out / "h264_gray.mp4", video={"codec": "libx264", "pix_fmt": "gray"}, audio=audio
        ),
        note="grayscale",
    )

    # ── geometry / timing / colour ────────────────────────────────────────
    add(
        "h264_1080p.mp4",
        lambda: _encode(
            out / "h264_1080p.mp4",
            video={"codec": "libx264", "width": 1920, "height": 1080, "seconds": 1},
            audio=audio,
        ),
        note="1080p",
    )
    add(
        "h264_60fps.mp4",
        lambda: _encode(
            out / "h264_60fps.mp4", video={"codec": "libx264", "fps": 60, "seconds": 1}, audio=audio
        ),
        note="60 fps",
    )
    add(
        "h264_sar.mp4",
        lambda: _encode(
            out / "h264_sar.mp4", video={"codec": "libx264", "sar": (4, 3)}, audio=audio
        ),
        note="non-square pixels",
    )
    add(
        "h264_rot90.mkv",
        lambda: _encode(
            out / "h264_rot90.mkv",
            video={"codec": "libx264", "rotate": 90},
            audio=audio,
            mux="matroska",
        ),
        note="90° display rotation",
    )
    add(
        "h264_interlaced.mp4",
        lambda: _encode(
            out / "h264_interlaced.mp4",
            video={"codec": "libx264", "field_order": 2},
            audio=audio,
        ),
        note="interlaced (tff)",
    )
    add(
        "h264_color.mp4",
        lambda: _encode(
            out / "h264_color.mp4",
            video={"codec": "libx264", "color": (9, 16, 9)},
            audio=audio,
        ),
        note="HDR-ish colour tags",
    )
    add(
        "h264_slow.mkv",
        lambda: _encode(
            out / "h264_slow.mkv",
            video={"codec": "libx264", "fps": 12},
            audio=audio,
            mux="matroska",
        ),
        note="reduced-rate timeline",
    )

    # ── containers with extras ────────────────────────────────────────────
    chapters = [
        {
            "id": 0,
            "start": 0,
            "end": 1000,
            "time_base": Fraction(1, 1000),
            "metadata": {"title": "First"},
        },
        {
            "id": 1,
            "start": 1000,
            "end": 2000,
            "time_base": Fraction(1, 1000),
            "metadata": {"title": "Second"},
        },
    ]
    add(
        "chapters.mkv",
        lambda: _encode(
            out / "chapters.mkv",
            video={"codec": "libx264"},
            audio=audio,
            chapters=chapters,
            mux="matroska",
        ),
        note="chapters",
    )
    add(
        "multi_audio.mkv",
        lambda: _encode(
            out / "multi_audio.mkv",
            video={"codec": "libx264"},
            audio=[{"codec": "aac", "language": "eng"}, {"codec": "aac", "language": "deu"}],
            mux="matroska",
        ),
        note="two audio tracks",
    )
    add(
        "cover.mp3",
        # MP3 cover art needs the picture stream marked attached_pic in the mp3
        # muxer, which av's add_attachment does not do (the mp3 muxer refuses
        # the attachment as "not a picture") — ffmpeg builds this one asset.
        lambda: _cover_mp3(out),
        by="ffmpeg",
        note="attached cover art",
    )
    add(
        "data_stream.mkv",
        lambda: _encode(
            out / "data_stream.mkv",
            video={"codec": "libx264"},
            audio=audio,
            data=None,
            mux="matroska",
        ),
        note="data stream",
    )

    # ── subtitles (ffmpeg: PyAV cannot encode subtitle frames) ────────────
    add(
        "subs_movtext.mp4",
        lambda: _subtitle_asset(out / "subs_movtext.mp4", codec="mov_text", mux="mp4"),
        by="ffmpeg",
        note="mov_text subtitles",
    )
    add(
        "subs_ass.mkv",
        lambda: _subtitle_asset(out / "subs_ass.mkv", codec="ass", mux="matroska"),
        by="ffmpeg",
        note="ASS subtitles",
    )
    add(
        "cues.srt",
        lambda: (
            (out / "cues.srt").write_text(
                "1\n00:00:00,000 --> 00:00:01,000\ncue one\n", encoding="utf-8"
            )
            or True
        ),
        note="standalone SRT",
    )

    # ── audio-only targets ────────────────────────────────────────────────
    for name, codec, mux, note in (
        ("audio_mp3.mp3", "libmp3lame", "mp3", "MP3"),
        ("audio_m4a.m4a", "aac", "ipod", "AAC in MP4"),
        ("audio_flac.flac", "flac", "flac", "FLAC"),
        ("audio_opus.ogg", "libopus", "opus", "Opus"),
        ("audio_alac.m4a", "alac", "ipod", "ALAC"),
        ("audio_wav.wav", "pcm_s16le", "wav", "PCM"),
    ):
        add(
            name,
            (lambda n=name, c=codec, m=mux: _encode(out / n, audio=[{"codec": c}], mux=m)),
            note=note,
        )

    # ── still images and a GIF ────────────────────────────────────────────
    for name, codec, note in (
        ("frame.png", "png", "PNG still"),
        ("frame.jpg", "mjpeg", "JPEG still"),
        ("frame.webp", "libwebp", "WebP still"),
    ):
        add(
            name,
            (
                lambda n=name, c=codec: _encode(
                    out / n,
                    video={
                        "codec": c,
                        "width": 320,
                        "height": 180,
                        "seconds": 1,
                        "fps": 1,
                        "pix_fmt": "yuvj420p" if c == "mjpeg" else None,
                    },
                )
            ),
            note=note,
        )
    add(
        "anim.gif",
        lambda: _encode(
            out / "anim.gif",
            video={
                "codec": "gif",
                "width": 160,
                "height": 90,
                "fps": 10,
                "seconds": 1,
                "pix_fmt": "rgb8",
            },
        ),
        note="animated GIF",
    )

    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    missing = sorted(name for name, meta in manifest.items() if not meta["path"])
    print(f"\n{len(manifest) - len(missing)}/{len(manifest)} assets built")
    if missing:
        print("missing: " + ", ".join(missing))
    return manifest


def main() -> int:
    # The corpus build is not a diagnostic: keep the encoders' native chatter
    # out of the log.
    av.logging.set_level(av.logging.PANIC)
    parser = argparse.ArgumentParser(description="build the ability-matrix corpus")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    manifest = build(Path(args.out), force=args.force)
    missing = [name for name, meta in manifest.items() if not meta["path"]]
    if missing and _ffmpeg() is None:
        print(f"\nffmpeg not on PATH — {len(missing)} subtitle assets skipped")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
