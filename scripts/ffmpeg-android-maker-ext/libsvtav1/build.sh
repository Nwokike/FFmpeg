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

# SVT-AV1 sets CMAKE_ARCHIVE_OUTPUT_DIRECTORY to <source>/Bin/<config>/ but
# never creates it — cmake then fails at archive time with "Error running
# link command: no such file or directory". Create the declared output dir.
mkdir -p ../Bin/Release

# Pin the archiver explicitly: NDK r27's toolchain can resolve CMAKE_AR to a
# target-prefixed wrapper that does not exist ("Error running link command:
# no such file or directory" at archive time). FAM_AR/FAM_RANLIB are the
# llvm-ar/llvm-ranlib every autotools recipe here already uses.
${CMAKE_EXECUTABLE} .. \
    -DANDROID_PLATFORM=${ANDROID_PLATFORM} \
    -DANDROID_ABI=${ANDROID_ABI} \
    -DCMAKE_TOOLCHAIN_FILE=${SCRIPTS_DIR}/libaom/android.cmake \
    -DCMAKE_INSTALL_PREFIX=${INSTALL_DIR} \
    -DCMAKE_AR=${FAM_AR} \
    -DCMAKE_RANLIB=${FAM_RANLIB} \
    -DCMAKE_C_COMPILER_AR=${FAM_AR} \
    -DCMAKE_C_COMPILER_RANLIB=${FAM_RANLIB} \
    -DBUILD_SHARED_LIBS=0 \
    -DSVT_AV1_LTO=OFF \
    -DBUILD_APPS=OFF \
    -DBUILD_TESTING=OFF || exit 1

# Make the resolved binutils visible in the build log for the next failure.
${CMAKE_EXECUTABLE} -LA -N . | grep -E '^CMAKE_(AR|RANLIB|C_COMPILER_AR|C_COMPILER_RANLIB):' || true

${MAKE_EXECUTABLE} -j${HOST_NPROC} || exit 1
${MAKE_EXECUTABLE} install