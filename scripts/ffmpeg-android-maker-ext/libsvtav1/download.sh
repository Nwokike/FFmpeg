#!/usr/bin/env bash
# SVT-AV1 v4.0.1 — AV1 encoder (--enable-libsvtav1).
# Self-contained download with checksum verification (see libogg/download.sh).
SVTAV1_VERSION=v4.0.1
SVTAV1_SHA256=9c0f9a4327334c40a76d2f39940d8a1b2dd8b1358375a11c4715d516b90a65cb
SVTAV1_DIR="SVT-AV1-${SVTAV1_VERSION}"
SVTAV1_TARBALL="${SVTAV1_DIR}.tar.gz"

if [ ! -d "$SVTAV1_DIR" ]; then
  curl -fLO "https://gitlab.com/AOMediaCodec/SVT-AV1/-/archive/${SVTAV1_VERSION}/${SVTAV1_TARBALL}"
  echo "${SVTAV1_SHA256}  ${SVTAV1_TARBALL}" | sha256sum -c -
  tar xf "${SVTAV1_TARBALL}"
  rm -f "${SVTAV1_TARBALL}"
fi
export SOURCES_DIR_libsvtav1="$(pwd)/${SVTAV1_DIR}"