#!/usr/bin/env bash
# libvorbis 1.3.7 — Vorbis encoder for FFmpeg (--enable-libvorbis).
VORBIS_VERSION=1.3.7
VORBIS_SHA256=b33cc4934322bcbf6efcbacf49e3ca01aadbea4114ec9589d1b1e9d20f72954b
downloadTarArchive \
  "libvorbis" \
  "https://downloads.xiph.org/releases/vorbis/libvorbis-${VORBIS_VERSION}.tar.xz" \
  "$VORBIS_SHA256"
