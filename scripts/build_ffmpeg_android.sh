#!/usr/bin/env bash
# Build full FFmpeg shared libraries for Android via ffmpeg-android-maker.
#
# The wrap pipeline's first stage: produces a per-ABI `make install` prefix
# (lib/*.so + include/ + lib/pkgconfig/*.pc) that
# scripts/build_flet_libffmpeg_wheel.py packages into `flet-libffmpeg` wheels.
# All versions/commits are pinned in scripts/wrap_pins.py.
#
# Usage: build_ffmpeg_android.sh [abi,abi,...]   (default: all pinned ABIs)
# Env:   ANDROID_NDK_HOME (downloaded + cached when unset)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ABIS="${1:-$(python3 "$ROOT/scripts/wrap_pins.py" --abis)}"
WORK="${WRAP_WORK:-$ROOT/.wrap-work}"
mkdir -p "$WORK"

# ── Android NDK (pinned; downloaded + cached when unset) ────────────────────
if [ -z "${ANDROID_NDK_HOME:-}" ]; then
    NDK_DIR="$WORK/android-ndk"
    if [ ! -d "$NDK_DIR" ]; then
        NDK_URL=$(python3 "$ROOT/scripts/wrap_pins.py" --value NDK_URL)
        echo ">> downloading $NDK_URL"
        curl -sL --retry 3 -o "$WORK/ndk.zip" "$NDK_URL"
        mkdir -p "$NDK_DIR"
        unzip -q "$WORK/ndk.zip" -d "$NDK_DIR"
    fi
    export ANDROID_NDK_HOME="$NDK_DIR/$(ls "$NDK_DIR" | head -1)"
fi
echo ">> ANDROID_NDK_HOME=$ANDROID_NDK_HOME"
# ffmpeg-android-maker's host checks expect the SDK too (GitHub runners have it
# preinstalled at ANDROID_HOME).
export ANDROID_SDK_HOME="${ANDROID_SDK_HOME:-${ANDROID_HOME:-/usr/local/lib/android/sdk}}"

# ── ffmpeg-android-maker (pinned commit) ────────────────────────────────────
FAM_DIR="$WORK/ffmpeg-android-maker"
FAM_REPO=$(python3 "$ROOT/scripts/wrap_pins.py" --value FAM_REPO)
FAM_COMMIT=$(python3 "$ROOT/scripts/wrap_pins.py" --value FAM_COMMIT)
if [ ! -d "$FAM_DIR/.git" ]; then
    git clone --quiet "$FAM_REPO" "$FAM_DIR"
fi
git -C "$FAM_DIR" checkout --quiet "$FAM_COMMIT"

# CMake 4.x removed compatibility with cmake_minimum_required < 3.5, and
# libx265 still declares 3.2. This env var (supported since CMake 4.0) tells
# every cmake in the tree to treat 3.5 as the floor; a no-op for the libs that
# already require more.
export CMAKE_POLICY_VERSION_MINIMUM=3.5

# ── Overlay: extra external codec libraries (ogg/vorbis/svtav1) ────────────
"$ROOT/scripts/ffmpeg-android-maker-ext/apply.sh" "$FAM_DIR"

# ── Build every requested ABI ───────────────────────────────────────────────
FAM_ARGS=$(python3 "$ROOT/scripts/wrap_pins.py" --args)
cd "$FAM_DIR"
# shellcheck disable=SC2086
./ffmpeg-android-maker.sh $FAM_ARGS --target-abis="$ABIS"

echo ">> ffmpeg prefixes:"
for abi in ${ABIS//,/ }; do
    prefix="$FAM_DIR/build/ffmpeg/$abi"
    test -d "$prefix/lib" || { echo "missing $prefix" >&2; exit 1; }
    ls -lh "$prefix"/lib/*.so
done
echo ">> done. Pass --ffmpeg-prefix $FAM_DIR/build/ffmpeg to build_flet_libffmpeg_wheel.py"
