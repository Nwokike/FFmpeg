#!/usr/bin/env bash
# SVT-AV1 v4.0.1 — AV1 encoder (--enable-libsvtav1).
SVTAV1_VERSION=v4.0.1
SVTAV1_SHA256=9c0f9a4327334c40a76d2f39940d8a1b2dd8b1358375a11c4715d516b90a65cb
downloadTarArchive \
  "libsvtav1" \
  "https://gitlab.com/AOMediaCodec/SVT-AV1/-/archive/${SVTAV1_VERSION}/SVT-AV1-${SVTAV1_VERSION}.tar.gz" \
  "$SVTAV1_SHA256"
