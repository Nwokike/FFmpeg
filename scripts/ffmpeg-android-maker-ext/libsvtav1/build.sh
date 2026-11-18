#!/usr/bin/env bash
# SVT-AV1: static lib only (no app, no tests), installed into INSTALL_DIR.
# House cmake pattern (libaom's recipe): per-ABI build dir at the sources
# root, ${CMAKE_EXECUTABLE}, the shared libaom/android.cmake toolchain, and
# ${MAKE_EXECUTABLE} targets. || exit 1 so a failed stage aborts the build
# loop instead of being swallowed by the source-ed script.
CMAKE_BUILD_DIR=libsvtav1_build_${ANDROID_ABI}
rm -rf ${CMAKE_BUILD_DIR}
mkdir ${CMAKE_BUILD_DIR}
cd ${CMAKE_BUILD_DIR}

${CMAKE_EXECUTABLE} .. \
    -DANDROID_PLATFORM=${ANDROID_PLATFORM} \
    -DCMAKE_TOOLCHAIN_FILE=${SCRIPTS_DIR}/libaom/android.cmake \
    -DCMAKE_INSTALL_PREFIX=${INSTALL_DIR} \
    -DBUILD_SHARED_LIBS=0 \
    -DSVT_AV1_LTO=OFF \
    -DBUILD_APPS=OFF \
    -DBUILD_TESTING=OFF || exit 1

${MAKE_EXECUTABLE} -j${HOST_NPROC} || exit 1
${MAKE_EXECUTABLE} install