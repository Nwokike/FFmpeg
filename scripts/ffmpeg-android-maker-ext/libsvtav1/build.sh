#!/usr/bin/env bash
# SVT-AV1: static lib only (no app), installed into INSTALL_DIR.
cd "$SOURCE_DIR"
rm -rf build && mkdir build && cd build
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR}" \
    -DCMAKE_TOOLCHAIN_FILE="${SCRIPTS_DIR}/libaom/android.cmake" \
    -DBUILD_SHARED_LIBS=0 \
    -DENABLE_NASM=OFF \
    -DSVT_AV1_LTO=OFF \
    -DBUILD_APP=OFF \
    -DBUILD_TESTING=OFF
make -j"${HOST_NPROC}"
make install
