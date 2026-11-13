#!/usr/bin/env bash
# Install the wrap's FFmpeg external-library overlay into a ffmpeg-android-maker
# clone: new lib recipes + the parse-argument/configure wiring they need.
#
# Usage: apply.sh <path-to-ffmpeg-android-maker-clone>
set -euo pipefail

FORGE="${1:?usage: apply.sh <ffmpeg-android-maker-clone>}"
EXT="$(cd "$(dirname "$0")" && pwd)"

for lib in libogg libvorbis libsvtav1; do
    test -d "$FORGE/scripts/$lib" && { echo "overlay already applied ($lib)" >&2; exit 0; }
    cp -r "$EXT/$lib" "$FORGE/scripts/$lib"
done

python3 - "$FORGE" <<'PY'
import re
import sys
from pathlib import Path

forge = Path(sys.argv[1])

# 1) parse-arguments.sh: register the new libraries.
pa = forge / "scripts" / "parse-arguments.sh"
text = pa.read_text()
anchor = '    *)\n        echo "Unknown argument $argument"\n        ;;'
assert anchor in text, "parse-arguments anchor not found"
cases = """    --enable-libogg | -ogg)
      EXTERNAL_LIBRARIES+=("libogg")
      ;;
    --enable-libvorbis | -vorbis)
      EXTERNAL_LIBRARIES+=("libvorbis")
      ;;
    --enable-libsvtav1 | -svtav1)
      EXTERNAL_LIBRARIES+=("libsvtav1")
      ;;
"""
text = text.replace(anchor, cases + anchor, 1)
pa.write_text(text)

# 2) ffmpeg/build.sh: libogg is dependency-only (FFmpeg has no
#    --enable-libogg), and pkg-config must see the external .pc files.
fb = forge / "scripts" / "ffmpeg" / "build.sh"
text = fb.read_text()
old = """for LIBARY_NAME in ${FFMPEG_EXTERNAL_LIBRARIES[@]}
do
    ADDITIONAL_COMPONENTS+=" --enable-$LIBARY_NAME"
done"""
new = """for LIBARY_NAME in ${FFMPEG_EXTERNAL_LIBRARIES[@]}
do
    # libogg is a dependency of libvorbis (no FFmpeg enable flag).
    if [ "$LIBARY_NAME" != "libogg" ]; then
        ADDITIONAL_COMPONENTS+=" --enable-$LIBARY_NAME"
    fi
done"""
assert old in text, "ffmpeg build.sh loop anchor not found"
text = text.replace(old, new, 1)
old2 = 'export PKG_CONFIG_PATH="${PKG_CONFIG_PATH:-}"'
if old2 not in text:
    text = text.replace(
        "cd $TERMUX_PKG_BUILDDIR" if "cd $TERMUX_PKG_BUILDDIR" in text else "./configure \\",
        "./configure \\",
        1,
    )
    # Put the external pkgconfig dir on the search path right before configure.
    text = text.replace(
        "export PKG_CONFIG_PATH=\"${PKG_CONFIG_PATH:-}\"",
        "export PKG_CONFIG_PATH=\"${BUILD_DIR_EXTERNAL}/${ANDROID_ABI}/lib/pkgconfig:${PKG_CONFIG_PATH:-}\"",
        1,
    )
    if "PKG_CONFIG_PATH=\"${BUILD_DIR_EXTERNAL}" not in text:
        text = text.replace(
            "echo \"=== configure (android $ANDROID_ABI, arch $FF_ARCH) ===\"",
            "echo \"=== configure (android $ANDROID_ABI, arch $FF_ARCH) ===\"\nexport PKG_CONFIG_PATH=\"${BUILD_DIR_EXTERNAL}/${ANDROID_ABI}/lib/pkgconfig:${PKG_CONFIG_PATH:-}\"",
            1,
        )
fb.write_text(text)
print("overlay applied:", [p.name for p in (forge / "scripts").iterdir() if p.name in ("libogg", "libvorbis", "libsvtav1")])
PY
echo ">> overlay applied to $FORGE"