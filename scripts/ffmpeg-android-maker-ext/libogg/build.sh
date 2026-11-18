#!/usr/bin/env bash
# libogg: static, PIC — installed into INSTALL_DIR so libvorbis's configure
# (--with-ogg-includes/--with-ogg-libraries) and FFmpeg's pkg-config probe
# find it. House autotools pattern (libmp3lame/libwebp): no cd — the build
# loop already runs in the sources root; --with-sysroot (configure rejects
# bare --sysroot); explicit compiler and binutils from export-build-variables.
./configure \
    --prefix=${INSTALL_DIR} \
    --host=${TARGET} \
    --with-sysroot=${SYSROOT_PATH} \
    --disable-shared \
    --enable-static \
    --with-pic \
    CC=${FAM_CC} \
    AR=${FAM_AR} \
    RANLIB=${FAM_RANLIB} || exit 1

${MAKE_EXECUTABLE} clean
${MAKE_EXECUTABLE} -j${HOST_NPROC}
${MAKE_EXECUTABLE} install