#!/usr/bin/env bash
# libvorbis 1.3.7 — Vorbis encoder for FFmpeg (--enable-libvorbis).
# Self-contained download with checksum verification (see libogg/download.sh).
VORBIS_VERSION=1.3.7
VORBIS_SHA256=b33cc4934322bcbf6efcbacf49e3ca01aadbea4114ec9589d1b1e9d20f72954b
VORBIS_DIR="libvorbis-${VORBIS_VERSION}"
VORBIS_TARBALL="${VORBIS_DIR}.tar.xz"

if [ ! -d "$VORBIS_DIR" ]; then
  curl -fLO "https://downloads.xiph.org/releases/vorbis/${VORBIS_TARBALL}"
  echo "${VORBIS_SHA256}  ${VORBIS_TARBALL}" | sha256sum -c -
  tar xf "${VORBIS_TARBALL}"
  rm -f "${VORBIS_TARBALL}"
fi
export SOURCES_DIR_libvorbis="$(pwd)/${VORBIS_DIR}"