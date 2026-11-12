#!/usr/bin/env bash
# Build the `av` (PyAV) Android wheels via flet-dev/mobile-forge, against the
# wrap's own full flet-libffmpeg wheel.
#
# Stage two of the wrap pipeline. ffmpeg-android-master built the FFmpeg
# libraries; forge compiles PyAV's 49 Cython extension modules against them for
# every ABI in the pinned Python support package's manifest.
#
# Usage: build_av_android_wheels.sh [wheel-src-dir]   (default: wheels/)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WHEELS="${1:-$ROOT/wheels}"
WORK="${WRAP_WORK:-$ROOT/.wrap-work}"
PYVER=$(python3 "$ROOT/scripts/wrap_pins.py" --value PYTHON_VERSION)
FORGE_REPO=$(python3 "$ROOT/scripts/wrap_pins.py" --value FORGE_REPO)
FORGE_COMMIT=$(python3 "$ROOT/scripts/wrap_pins.py" --value FORGE_COMMIT)

FORGE_DIR="$WORK/mobile-forge"
if [ ! -d "$FORGE_DIR/.git" ]; then
    git clone --quiet "$FORGE_REPO" "$FORGE_DIR"
fi
git -C "$FORGE_DIR" checkout --quiet "$FORGE_COMMIT"

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
