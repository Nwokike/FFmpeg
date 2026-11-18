"""Fetch a real-media test corpus (deterministic, public URLs).

The ability matrix runs against synthetic assets produced by
``scripts/build_corpus.py``; this set is the *real-world* companion: actual
camera-style H.264/HEVC/VP9 video, MP3/WAV/FLAC/Opus audio and JPEG/PNG
images, downloaded once into ``testdata/media/`` with a sha256 manifest.

Usage:
    uv run python scripts/fetch_testmedia.py [--out DIR] [--force]

The live suites read this directory when ``~/Videos`` has nothing
(``FFMPEG_TEST_MEDIA`` overrides the location).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "testdata" / "media"
UA = "ffmpeg-av-testmedia/1.0"

SOURCES = {
    # Real encodes from the public test-videos set (10 s, ~1 MB each).
    "bbb_h264.mp4": "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4",
    "jellyfish_hevc.mp4": "https://test-videos.co.uk/vids/jellyfish/mp4/h265/360/Jellyfish_360_10s_1MB.mp4",
    "bbb_vp9.webm": "https://test-videos.co.uk/vids/bigbuckbunny/webm/vp9/360/Big_Buck_Bunny_360_10s_1MB.webm",
    "sample_15s.mp3": "https://download.samplelib.com/mp3/sample-15s.mp3",
    "sample_15s.wav": "https://download.samplelib.com/wav/sample-15s.wav",
    "photo_640x480.jpg": "https://picsum.photos/id/237/640/480.jpg",
    "image_640x480.png": "https://dummyimage.com/640x480/336699/fff.png",
}

# Real content, repackaged locally so FLAC/Opus have real-world audio in them
# (both source only as WAV upstream).
DERIVED = {
    "sample_15s.flac": ("sample_15s.wav", ["-c:a", "flac"]),
    "sample_15s.opus": ("sample_15s.wav", ["-c:a", "libopus", "-b:a", "96k"]),
}

# The upstream test clips are video-only. Mux the real WAV audio in so the
# audio assertions exercise a genuine A/V file — this is what a phone
# gallery file looks like.
COMPOSITES = {
    "bbb_h264_aac.mp4": (
        ("bbb_h264.mp4", "sample_15s.wav"),
        ["-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest"],
    ),
    "jellyfish_hevc_aac.mp4": (
        ("jellyfish_hevc.mp4", "sample_15s.wav"),
        ["-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest"],
    ),
}


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict] = {}
    for name, url in SOURCES.items():
        path = out / name
        if path.exists() and not args.force:
            blob = path.read_bytes()
            print(f"= {name} (cached, {len(blob) // 1024} KiB)")
        else:
            print(f"> {name} <- {url}")
            blob = _fetch(url)
            path.write_bytes(blob)
            print(f"  {len(blob) // 1024} KiB")
        manifest[name] = {
            "url": url,
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }

    ffmpeg = shutil.which("ffmpeg")
    for name, (src, codec_args) in DERIVED.items():
        path = out / name
        if path.exists() and not args.force:
            print(f"= {name} (cached, {path.stat().st_size // 1024} KiB)")
        elif ffmpeg is None:
            print(f"! {name}: ffmpeg not on PATH — skipped")
            continue
        else:
            print(f"> {name} (from {src})")
            subprocess.run(
                [ffmpeg, "-y", "-v", "error", "-i", str(out / src), *codec_args, str(path)],
                check=True,
            )
        blob = path.read_bytes()
        manifest[name] = {
            "source": src,
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }

    for name, (sources, codec_args) in COMPOSITES.items():
        path = out / name
        if path.exists() and not args.force:
            print(f"= {name} (cached, {path.stat().st_size // 1024} KiB)")
        elif ffmpeg is None:
            print(f"! {name}: ffmpeg not on PATH — skipped")
            continue
        else:
            print(f"> {name} (from {', '.join(sources)})")
            cmd = [ffmpeg, "-y", "-v", "error"]
            for s in sources:
                cmd += ["-i", str(out / s)]
            subprocess.run(
                [*cmd, *codec_args, "-map", "0:v:0", "-map", "1:a:0", str(path)], check=True
            )
        blob = path.read_bytes()
        manifest[name] = {
            "sources": list(sources),
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    total = sum(m["bytes"] for m in manifest.values())
    print(f"\ncorpus: {len(manifest)} files, {total / 1_048_576:.1f} MiB in {out}")
    print("live HLS URL (not downloaded): https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
