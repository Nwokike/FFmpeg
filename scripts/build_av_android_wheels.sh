#!/usr/bin/env bash
# Build the `av` (PyAV) Android wheels via flet-dev/mobile-forge, against the
# wrap's own full flet-libffmpeg wheel.
#
# Stage two of the wrap pipeline. ffmpeg-android-maker built the FFmpeg
# libraries; forge compiles PyAV's 49 Cython extension modules against them for
# every ABI in the pinned Python support package's manifest.
#
# Usage: build_av_android_wheels.sh [wheel-src-dir]   (default: wheels/)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# ABSOLUTE, resolved before any cd: the script later cd's into the forge tree,
# and a relative "wheels" would then copy into .wrap-work/mobile-forge/wheels
# while the CI audit looks in <repo>/wheels (that mismatch cost two builds).
WHEELS="${1:-$ROOT/wheels}"
case "$WHEELS" in
    /*) ;;
    *) WHEELS="$PWD/$WHEELS" ;;
esac
WORK="${WRAP_WORK:-$ROOT/.wrap-work}"
PYVER=$(python3 "$ROOT/scripts/wrap_pins.py" --value PYTHON_VERSION)
FORGE_REPO=$(python3 "$ROOT/scripts/wrap_pins.py" --value FORGE_REPO)
FORGE_COMMIT=$(python3 "$ROOT/scripts/wrap_pins.py" --value FORGE_COMMIT)

FORGE_DIR="$WORK/mobile-forge"
if [ ! -d "$FORGE_DIR/.git" ]; then
    git clone --quiet "$FORGE_REPO" "$FORGE_DIR"
fi
git -C "$FORGE_DIR" checkout --quiet "$FORGE_COMMIT"

# ── NDK for the Cython extension build ──────────────────────────────────────
# The Python Android support package embeds compiler paths pointing at an NDK
# layout that only exists inside the package. Forge re-points those paths to a
# real NDK ONLY when NDK_HOME is set (src/forge/build.py: "If NDK_HOME is set,
# re-point missing compiler/binutils paths to that installed NDK toolchain").
# Without it the build dies with "No such file or directory: .../aarch64-...-clang".
if [ -z "${NDK_HOME:-}" ]; then
    if [ -n "${ANDROID_NDK_HOME:-}" ]; then
        NDK_HOME="$ANDROID_NDK_HOME"
    else
        SDK="${ANDROID_HOME:-${ANDROID_SDK_HOME:-/usr/local/lib/android/sdk}}"
        NDK_HOME=$(ls -d "$SDK"/ndk/* 2>/dev/null | sort -V | tail -1)
    fi
fi
export NDK_HOME
export ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-$NDK_HOME}"
echo ">> NDK_HOME=$NDK_HOME"

# ── Install the wrap's av recipe fork (version + host dep) ──────────────────
rm -rf "$FORGE_DIR/recipes/av"
cp -r "$ROOT/scripts/mobile-forge/recipes/av" "$FORGE_DIR/recipes/av"

# ── Seed the full flet-libffmpeg wheels so the host dep resolves ────────────
mkdir -p "$FORGE_DIR/dist"
ls "$WHEELS"/flet_libffmpeg-*.whl >/dev/null || {
    echo "no flet_libffmpeg wheels in $WHEELS — run build_ffmpeg_android.sh first" >&2
    exit 1
}
cp "$WHEELS"/flet_libffmpeg-*.whl "$FORGE_DIR/dist/"

# ── Forge environment (downloads the pinned python-build support package) ──
cd "$FORGE_DIR"
# shellcheck disable=SC1091
source ./setup.sh "$PYVER" android

# ── Build av for every Android ABI ──────────────────────────────────────────
forge android av

# ── Collect the produced wheels ─────────────────────────────────────────────
mkdir -p "$WHEELS"
ls -lh dist/av-*.whl
cp dist/av-*.whl "$WHEELS/"
echo ">> av wheels written to $WHEELS"
