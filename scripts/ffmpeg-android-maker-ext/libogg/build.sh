#!/usr/bin/env bash
# libogg: static, PIC, no programs — installed into INSTALL_DIR so
# libvorbis's pkg-config Requires.private finds it.
cd "$SOURCE_DIR"
./configure \
    --prefix="${INSTALL_DIR}" \
    --host="${TARGET}" \
    --sysroot="${SYSROOT_PATH}" \
    --disable-shared \
    --enable-static \
    --disable-examples \
    --disable-docs
make -j"${HOST_NPROC}"
make install
