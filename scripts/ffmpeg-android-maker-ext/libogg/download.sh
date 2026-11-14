#!/usr/bin/env bash
# libogg 1.3.5 — dependency of libvorbis (built first; no --enable flag).
# Self-contained download: upstream's downloadTarArchive helper takes no
# digest, and the wrap owns its checksums (pins live in wrap scripts).
OGG_VERSION=1.3.5
OGG_SHA256=c4d91be36fc8e54deae7575241e03f4211eb102afb3fc0775fbbc1b740016705
OGG_DIR="libogg-${OGG_VERSION}"
OGG_TARBALL="${OGG_DIR}.tar.xz"

if [ ! -d "$OGG_DIR" ]; then
  curl -fLO "https://downloads.xiph.org/releases/ogg/${OGG_TARBALL}"
  echo "${OGG_SHA256}  ${OGG_TARBALL}" | sha256sum -c -
  tar xf "${OGG_TARBALL}"
  rm -f "${OGG_TARBALL}"
fi
export SOURCES_DIR_libogg="$(pwd)/${OGG_DIR}"