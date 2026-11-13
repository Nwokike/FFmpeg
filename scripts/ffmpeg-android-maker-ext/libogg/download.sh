#!/usr/bin/env bash
# libogg 1.3.5 — dependency of libvorbis (built first; no --enable flag).
OGG_VERSION=1.3.5
OGG_SHA256=c4d91be36fc8e54deae7575241e03f4211eb102afb3fc0775fbbc1b740016705
downloadTarArchive \
  "libogg" \
  "https://downloads.xiph.org/releases/ogg/libogg-${OGG_VERSION}.tar.xz" \
  "$OGG_SHA256"
