"""Pin set for the mobile FFmpeg/av wrap pipeline — single source of truth.

The app's `av` requirement is flat; these pins are the wrap's internal contract
(the proot-distro `_PINNED_SOURCES` pattern). `build_ffmpeg_android.sh` and
`build_av_android_wheels.sh` read them via this module; CI caches the produced
wheels keyed on a hash of this file.
"""

from __future__ import annotations

import hashlib
import json

# FFmpeg 9.0.2 — the version PyAV 19.0.x is built against (libavcodec 63).
FFMPEG_VERSION = "9.0.2"
FFMPEG_SHA256 = "8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e"
FFMPEG_URL = f"https://www.ffmpeg.org/releases/ffmpeg-{FFMPEG_VERSION}.tar.xz"

# ffmpeg-android-maker: the cross-build harness for the external codec libs.
FAM_REPO = "https://github.com/Javernaut/ffmpeg-android-maker"
FAM_COMMIT = "dd72b161ae5c759fd25a5cab971a3ff710f0bdba"

# Android NDK used for the whole chain.
NDK_R = "r27c"
NDK_URL = f"https://dl.google.com/android/repository/android-ndk-{NDK_R}-linux.zip"

# mobile-forge — the PyAV Android wheel builder.
FORGE_REPO = "https://github.com/flet-dev/mobile-forge"
FORGE_COMMIT = "d2cb18b58226d958a2efa25bcbe126ce7a8ab19c"

# Python the Android wheels are built for (matches [project].requires-python).
PYTHON_VERSION = "3.14"

# Android API level (floor of the Flet/av wheel lineage).
ANDROID_API_LEVEL = 24

# ffmpeg-android-maker flag set: every library it supports, free + GPL.
# Pending (harness lacks recipes): libvorbis+ogg, libass(+harfbuzz), svt-av1,
# rav1e, openssl — tracked in docs/full-ffmpeg-plan.md Phase 2.
FAM_ARGS = [
    "--source-tar=" + FFMPEG_VERSION,
    f"--android-api-level={ANDROID_API_LEVEL}",
    "--enable-all-free",
    "--enable-all-gpl",
    # External libs beyond ffmpeg-android-maker's built-in set, built by the
    # overlay in scripts/ffmpeg-android-maker-ext/ (libogg is a dependency of
    # libvorbis; FFmpeg has no --enable-libogg, so apply.sh wires it as
    # build-only and adds the external pkg-config path).
    "--enable-libogg",
    "--enable-libvorbis",
    "--enable-libsvtav1",
]

ABIS = ("arm64-v8a", "armeabi-v7a", "x86_64")

# External encoders/protocols that must appear in the built libav* configure
# string before a wheel is accepted.
REQUIRED_CONFIGURE_TOKENS = (
    "libx264",
    "libx265",
    "libvpx",
    "libaom",
    "libmp3lame",
    "libopus",
    "libdav1d",
    "libwebp",
    "libxml2",
    "libbluray",
    "mbedtls",
    "libvorbis",
    "libsvtav1",
)

WHEEL_BUILD_TAG = "1"

# Third-party payload components → (license, upstream URL).
PAYLOAD_COMPONENTS = {
    "FFmpeg": ("GPL-3.0-or-later", "https://ffmpeg.org"),
    "x264": ("GPL-2.0-or-later", "https://code.videolan.org/videolan/x264"),
    "x265": ("GPL-2.0-or-later", "https://bitbucket.org/multicoreware/x265_git"),
    "libvpx": ("BSD-3-Clause", "https://chromium.googlesource.com/webm/libvpx"),
    "libaom": ("BSD-3-Clause", "https://aomedia.googlesource.com/aom"),
    "libdav1d": ("BSD-2-Clause", "https://code.videolan.org/videolan/dav1d"),
    "libmp3lame": ("LGPL-2.0-or-later", "https://lame.sourceforge.net"),
    "libopus": ("BSD-3-Clause", "https://opus-codec.org"),
    "libspeex": ("BSD-3-Clause", "https://speex.org"),
    "libtwolame": ("LGPL-2.1-or-later", "https://www.twolame.org"),
    "libwebp": ("BSD-3-Clause", "https://developers.google.com/speed/webp"),
    "libfreetype": ("FTL / GPL-2.0-or-later", "https://freetype.org"),
    "libfribidi": ("LGPL-2.1-or-later", "https://github.com/fribidi/fribidi"),
    "mbedtls": (
        "Apache-2.0 / GPL-2.0-or-later",
        "https://www.trustedfirmware.org/projects/mbed-tls",
    ),
    "libbluray": ("LGPL-2.1-or-later", "https://www.videolan.org/developers/libbluray.html"),
    "libxml2": ("MIT", "https://gitlab.gnome.org/GNOME/libxml2"),
}


def pins_hash() -> str:
    """Stable cache key for the produced wheels."""
    payload = {
        k: v
        for k, v in globals().items()
        if k.isupper() and isinstance(v, (str, int, tuple, list, dict))
    }
    blob = json.dumps(payload, sort_keys=True, default=list)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def main() -> int:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--args":
        # Space-joined ffmpeg-android-maker argument list for shell callers.
        print(" ".join(FAM_ARGS))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "--abis":
        print(",".join(ABIS))
        return 0
    if len(sys.argv) > 2 and sys.argv[1] == "--value":
        print(globals()[sys.argv[2]])
        return 0
    print(pins_hash())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
