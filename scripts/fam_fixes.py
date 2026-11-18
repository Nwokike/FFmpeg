"""Deterministic repairs for the pinned ffmpeg-android-maker clone.

Only bugs that make the pinned upstream unusable are repaired here — no
feature patching, and every fix is idempotent.

1. mbedtls: at the pinned commit ``download.sh`` clones the tag into
   ``${MBEDTLS_VERSION}`` (= v3.6.3) while ``build.sh`` cd's into
   ``mbedtls-${MBEDTLS_VERSION}`` — a directory that never exists. The build
   scripts are sourced without ``set -e``, so the failed cd is swallowed and
   mbedtls is silently skipped (FFmpeg then lacks a TLS backend). The cd is
   made layout-agnostic.

Usage: python3 scripts/fam_fixes.py <path-to-ffmpeg-android-maker-clone>
"""

from __future__ import annotations

import sys
from pathlib import Path

OLD = "cd mbedtls-${MBEDTLS_VERSION}\n"
NEW = 'cd "$(ls -d "mbedtls-${MBEDTLS_VERSION}" "${MBEDTLS_VERSION}" 2>/dev/null | head -1)"\n'


def fix_mbedtls(forge: Path) -> bool:
    build = forge / "scripts" / "mbedtls" / "build.sh"
    text = build.read_text()
    if OLD not in text:
        return False
    build.write_text(text.replace(OLD, NEW, 1))
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    forge = Path(sys.argv[1])
    changed = [name for name, fn in (("mbedtls cd", fix_mbedtls),) if fn(forge)]
    print("fam fixes applied:", ", ".join(changed) if changed else "none (already applied)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
