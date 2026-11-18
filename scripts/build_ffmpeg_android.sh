#!/usr/bin/env bash
# Build FFmpeg shared libraries for Android via ffmpeg-android-maker.
#
# The wrap pipeline's first stage: produces a per-ABI `make install` prefix
# (lib/*.so + include/ + lib/pkgconfig/*.pc) that
# scripts/build_flet_libffmpeg_wheel.py packages into `flet-libffmpeg` wheels.
# All versions/commits are pinned in scripts/wrap_pins.py.
#
# Every external codec is linked STATIC and folded into the seven libav*.so,
# so the wheels ship no companion .so closure (that is what keeps the APK
# lean). The component set lives in wrap_pins.FAM_ARGS.
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

# ── Deterministic repairs for upstream bugs at the pin (idempotent) ────────
python3 "$ROOT/scripts/fam_fixes.py" "$FAM_DIR"

# ── CMake 3.31.x (pinned in wrap_pins.py) ───────────────────────────────────
# CMake 4 refuses libx265's cmake_minimum_required 3.2 and the CMP0025/CMP0054
# OLD policies x265 4.1 still sets (removed in CMake 4.0) — no env override
# exists for the policies, so the toolchain itself is pinned. `which cmake`
# inside ffmpeg-android-maker resolves through PATH.
CMAKE_VENV="$WORK/cmake-venv"
if [ ! -x "$CMAKE_VENV/bin/cmake" ]; then
    uv venv --quiet "$CMAKE_VENV"
    uv pip install --python "$CMAKE_VENV/bin/python" --quiet \
        "$(python3 "$ROOT/scripts/wrap_pins.py" --value CMAKE_PIP_SPEC)"
fi
export PATH="$CMAKE_VENV/bin:$PATH"
echo ">> cmake: $(cmake --version | head -1)"

# ── Build every requested ABI (skipped when the pin set is unchanged) ──────
FAM_ARGS=$(python3 "$ROOT/scripts/wrap_pins.py" --args)
PINS_HASH=$(python3 "$ROOT/scripts/wrap_pins.py")
STAMP="$FAM_DIR/build/ffmpeg/.build-stamp"
if [ "${WRAP_FORCE_BUILD:-0}" != "1" ] && [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$PINS_HASH" ]; then
    echo ">> cached FFmpeg prefixes for pin set $PINS_HASH — skipping build"
else
    cd "$FAM_DIR"
    # shellcheck disable=SC2086
    ./ffmpeg-android-maker.sh $FAM_ARGS --target-abis="$ABIS"
    mkdir -p "$FAM_DIR/build/ffmpeg"
    echo "$PINS_HASH" > "$STAMP"
fi

echo ">> ffmpeg prefixes:"
for abi in ${ABIS//,/ }; do
    prefix="$FAM_DIR/build/ffmpeg/$abi"
    test -d "$prefix/lib" || { echo "missing $prefix" >&2; exit 1; }
    ls -lh "$prefix"/lib/*.so
done
echo ">> done. Pass --ffmpeg-prefix $FAM_DIR/build/ffmpeg to build_flet_libffmpeg_wheel.py"
