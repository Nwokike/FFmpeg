#!/usr/bin/env bash
# libvorbis: static, PIC; ogg comes from the INSTALL_DIR libogg build via the
# flags this configure actually defines (--with-ogg-includes/--with-ogg-libraries)
# plus the verified --disable-oggtest. House autotools pattern (see
# libogg/build.sh).
./configure \
    --prefix=${INSTALL_DIR} \
    --host=${TARGET} \
    --with-sysroot=${SYSROOT_PATH} \
    --disable-shared \
    --enable-static \
    --with-pic \
    --disable-oggtest \
    --with-ogg-includes=${INSTALL_DIR}/include \
    --with-ogg-libraries=${INSTALL_DIR}/lib \
    CC=${FAM_CC} \
    AR=${FAM_AR} \
    RANLIB=${FAM_RANLIB} || exit 1

${MAKE_EXECUTABLE} clean
${MAKE_EXECUTABLE} -j${HOST_NPROC}
${MAKE_EXECUTABLE} install