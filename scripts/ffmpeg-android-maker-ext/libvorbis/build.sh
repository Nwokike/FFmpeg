#!/usr/bin/env bash
# libvorbis: static, PIC, no examples/tests — installed into INSTALL_DIR.
cd "$SOURCE_DIR"
./configure \
    --prefix="${INSTALL_DIR}" \
    --host="${TARGET}" \
    --sysroot="${SYSROOT_PATH}" \
    --with-ogg="${INSTALL_DIR}" \
    --disable-shared \
    --enable-static \
    --disable-examples \
    --disable-docs
make -j"${HOST_NPROC}"
make install
