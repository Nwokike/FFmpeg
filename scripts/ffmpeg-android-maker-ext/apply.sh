#!/usr/bin/env bash
# Install the wrap's FFmpeg external-library overlay into a ffmpeg-android-maker
# clone: new lib recipes + the parse-argument/configure wiring they need.
#
# Usage: apply.sh <path-to-ffmpeg-android-maker-clone>
#
# Idempotent: re-running against an already-patched clone changes nothing.
set -euo pipefail

FORGE="${1:?usage: apply.sh <ffmpeg-android-maker-clone>}"
EXT="$(cd "$(dirname "$0")" && pwd)"

for lib in libogg libvorbis libsvtav1; do
    if [ ! -d "$FORGE/scripts/$lib" ]; then
        cp -r "$EXT/$lib" "$FORGE/scripts/$lib"
    fi
done

python3 - "$FORGE" <<'PY'
import re
import sys
from pathlib import Path

forge = Path(sys.argv[1])

# 1) parse-arguments.sh: register the new libraries.
#    Anchor on the catch-all case (the `*)` + "Unknown argument" echo),
#    indentation-tolerant so an upstream reformat can't silently unwire this.
pa = forge / "scripts" / "parse-arguments.sh"
text = pa.read_text()
if "--enable-libogg | -ogg)" not in text:
    m = re.search(r'\n(  \*\)\n[ \t]+echo "Unknown argument)', text)
    assert m, "parse-arguments catch-all not found"
    cases = (
        '  --enable-libogg | -ogg)\n'
        '    EXTERNAL_LIBRARIES+=("libogg")\n'
        '    ;;\n'
        '  --enable-libvorbis | -vorbis)\n'
        '    EXTERNAL_LIBRARIES+=("libvorbis")\n'
        '    ;;\n'
        '  --enable-libsvtav1 | -svtav1)\n'
        '    EXTERNAL_LIBRARIES+=("libsvtav1")\n'
        '    ;;\n'
    )
    text = text[: m.start() + 1] + cases + text[m.start() + 1 :]
    pa.write_text(text)

# 2) ffmpeg/build.sh: libogg is dependency-only (FFmpeg has no
#    --enable-libogg). No pkg-config wiring is needed here:
#    export-build-variables.sh already exports
#    PKG_CONFIG_LIBDIR=<prefix>/lib/pkgconfig — the directory the external
#    .pc files install into — and pkg-config searches it.
fb = forge / "scripts" / "ffmpeg" / "build.sh"
text = fb.read_text()
old = (
    "for LIBARY_NAME in ${FFMPEG_EXTERNAL_LIBRARIES[@]}\n"
    "do\n"
    '  ADDITIONAL_COMPONENTS+=" --enable-$LIBARY_NAME"\n'
    "done"
)
if "libogg is a dependency" not in text:
    assert old in text, "ffmpeg build.sh loop anchor not found"
    new = (
        "for LIBARY_NAME in ${FFMPEG_EXTERNAL_LIBRARIES[@]}\n"
        "do\n"
        "  # libogg is a dependency of libvorbis (no FFmpeg enable flag).\n"
        '  if [ "$LIBARY_NAME" != "libogg" ]; then\n'
        '    ADDITIONAL_COMPONENTS+=" --enable-$LIBARY_NAME"\n'
        "  fi\n"
        "done"
    )
    fb.write_text(text.replace(old, new, 1))

# 3) mbedtls/build.sh: download.sh clones the tag into ${MBEDTLS_VERSION}
#    (v3.6.3) but build.sh cd's into mbedtls-${MBEDTLS_VERSION} — a directory
#    that never exists. Upstream bug at the pin; without set -e the failing
#    cd is swallowed and mbedtls is silently skipped.
mb = forge / "scripts" / "mbedtls" / "build.sh"
text = mb.read_text()
if "cd mbedtls-${MBEDTLS_VERSION}" in text:
    mb.write_text(text.replace("cd mbedtls-${MBEDTLS_VERSION}", "cd ${MBEDTLS_VERSION}", 1))
print("overlay applied:", [p.name for p in (forge / "scripts").iterdir() if p.name in ("libogg", "libvorbis", "libsvtav1")])
PY
echo ">> overlay applied to $FORGE"