#!/usr/bin/env python3
"""Package ffmpeg-android-maker's per-ABI prefixes into flet-libffmpeg wheels.

The mobile wrap's packaging stage. Input is one `make install` prefix per ABI
(lib/*.so + include/ + lib/pkgconfig/*.pc) as produced by
scripts/build_ffmpeg_android.sh; output is one
`flet_libffmpeg-<version>-<tag>-py3-none-android_24_<abi>.whl` per ABI with the
exact layout the `av` wheel's extension modules link against (unversioned
libav*.so in opt/lib, relocatable pkg-config files in opt/lib/pkgconfig).

Every payload is verified before it ships:
- ELF64, 16 KiB PT_LOAD alignment, no text relocations;
- DT_SONAME == filename for the seven libav* libraries;
- DT_NEEDED satisfied by the shipped set or the platform (external codec
  libraries must be statically folded in, not shipped loose);
- the embedded FFmpeg configure string names every pinned external encoder and
  `--enable-gpl`.

Stdlib only; pins come from scripts/wrap_pins.py.
"""

from __future__ import annotations

import argparse
import hashlib
import runpy
import zipfile
from pathlib import Path

from elf_tools import ALIGN_16K, ElfError, elf_info

REPO_ROOT = Path(__file__).resolve().parent.parent
PINS = runpy.run_path(REPO_ROOT / "scripts" / "wrap_pins.py")

FFMPEG_VERSION = PINS["FFMPEG_VERSION"]
BUILD_TAG = PINS["WHEEL_BUILD_TAG"]
ABIS = PINS["ABIS"]
REQUIRED_TOKENS = PINS["REQUIRED_CONFIGURE_TOKENS"]
COMPONENTS = PINS["PAYLOAD_COMPONENTS"]

DIST_NAME = "flet_libffmpeg"
# The seven shared libraries the `av` extension modules link by basename.
EXPECTED_LIBS = (
    "libavcodec.so",
    "libavdevice.so",
    "libavfilter.so",
    "libavformat.so",
    "libavutil.so",
    "libswresample.so",
    "libswscale.so",
)
LICENSE_FILES = (
    "GPL-3.0.txt",
    "GPL-2.0.txt",
    "LGPL-2.1.txt",
    "IJG.txt",
    "BSD-3-Clause.txt",
    "MIT.txt",
    "ISC.txt",
    "Apache-2.0.txt",
)

ARCH_TAGS = {
    "arm64-v8a": "arm64_v8a",
    "armeabi-v7a": "armeabi_v7a",
    "x86_64": "x86_64",
}


def fail(msg: str) -> None:
    raise SystemExit(f"refusing to ship: {msg}")


def _urlsafe_b64(digest: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _record_line(name: str, blob: bytes) -> str:
    return f"{name},sha256={_urlsafe_b64(hashlib.sha256(blob).digest())},{len(blob)}"


def _find_configure_string(blobs: dict[str, bytes]) -> str:
    """FFmpeg embeds its configure line in libavutil (avutil_configuration)."""
    for blob in blobs.values():
        idx = blob.find(b"--enable-cross-compile")
        if idx != -1:
            start = blob.rfind(b"--prefix=", 0, idx)
            end = blob.find(b"\x00", idx)
            return blob[start:end].decode("utf-8", "replace")
    return ""


def verify_prefix(prefix: Path, abi: str) -> tuple[dict[str, bytes], str]:
    """Verify one ABI prefix; return {filename: bytes} and the configure line."""
    lib_dir = prefix / "lib"
    blobs: dict[str, bytes] = {}
    for name in EXPECTED_LIBS:
        path = lib_dir / name
        if not path.is_file():
            fail(f"{abi}: {name} missing from {lib_dir}")
        blob = path.read_bytes()
        try:
            info = elf_info(blob, f"{abi}/{name}")
        except ElfError as exc:
            fail(str(exc))
        if not info["align"] or info["align"] < ALIGN_16K:
            fail(f"{abi}/{name}: PT_LOAD align {info['align']:#x} < 0x{ALIGN_16K:x} (16 KiB)")
        if info["textrel"]:
            fail(f"{abi}/{name}: DT_TEXTREL present (unrelocatable on modern Android)")
        if info["soname"] and info["soname"] != name:
            fail(f"{abi}/{name}: DT_SONAME {info['soname']!r} != filename")
        unmet = [
            n
            for n in info["needed"]
            if n not in blobs
            and not n.startswith(("libav", "libsw", "libc.", "libdl.", "libm."))
            and n not in {"libz.so", "liblog.so", "libandroid.so", "libc++_shared.so"}
        ]
        if unmet:
            fail(
                f"{abi}/{name}: loose DT_NEEDED on {', '.join(unmet)} — external codec libraries must be statically folded in"
            )
        blobs[name] = blob

    configure = _find_configure_string(blobs)
    if not configure:
        fail(f"{abi}: embedded FFmpeg configure string not found")
    if f"ffmpeg-{FFMPEG_VERSION}" not in configure and f"/{FFMPEG_VERSION}/" not in configure:
        fail(f"{abi}: configure string is not FFmpeg {FFMPEG_VERSION}: {configure[:120]}")
    if "--enable-gpl" not in configure:
        fail(f"{abi}: configure string lacks --enable-gpl")
    missing = [t for t in REQUIRED_TOKENS if f"--enable-{t}" not in configure]
    if missing:
        fail(f"{abi}: configure string lacks pinned encoders: {', '.join(missing)}")
    return blobs, configure


def collect_prefix(prefix: Path, abi: str) -> dict[str, bytes]:
    """Headers + relocatable pkg-config files from the prefix."""
    entries: dict[str, bytes] = {}
    inc = prefix / "include"
    if not inc.is_dir():
        fail(f"{abi}: include/ missing under {prefix}")
    for path in sorted(inc.rglob("*")):
        if path.is_file():
            entries[f"opt/include/{path.relative_to(inc)}"] = path.read_bytes()
    pc_dir = prefix / "lib" / "pkgconfig"
    if pc_dir.is_dir():
        for path in sorted(pc_dir.glob("*.pc")):
            text = path.read_text(encoding="utf-8")
            # Relocate to the pkg-config ${pcfiledir} form the mobile-forge
            # flet-libffmpeg recipe ships (consumers get opt/lib/pkgconfig on
            # PKG_CONFIG_LIBDIR when the host wheel is unpacked).
            lines = [
                "prefix=${pcfiledir}/../.." if line.startswith("prefix=") else line
                for line in text.splitlines()
            ]
            entries[f"opt/lib/pkgconfig/{path.name}"] = ("\n".join(lines) + "\n").encode()
    return entries


def third_party_table() -> str:
    lines = [
        "",
        "## Third-party components of the native payload",
        "",
        "This wheel repackages FFmpeg and its statically-linked codec libraries,",
        "cross-built for Android from the pinned upstream sources listed in",
        "scripts/wrap_pins.py. The app-level source offer lives in the companion",
        "repository's THIRD-PARTY-SOURCES.md and under Settings → Open-Source",
        "Licenses.",
        "",
        "| Component | License | Upstream |",
        "|---|---|---|",
    ]
    for name, (lic, url) in COMPONENTS.items():
        lines.append(f"| {name} | {lic} | {url} |")
    lines.append("")
    return "\n".join(lines)


def build_wheel(out_dir: Path, prefix: Path, abi: str) -> Path:
    blobs, configure = verify_prefix(prefix, abi)
    entries = collect_prefix(prefix, abi)
    for name, blob in blobs.items():
        entries[f"opt/lib/{name}"] = blob

    tag = f"py3-none-android_{PINS['ANDROID_API_LEVEL']}_{ARCH_TAGS[abi]}"
    dist_info = f"{DIST_NAME}-{FFMPEG_VERSION}.dist-info"

    licenses = {}
    for fname in LICENSE_FILES:
        path = REPO_ROOT / "LICENSES" / fname
        if not path.is_file():
            fail(f"missing vendored license text: {path}")
        licenses[f"{dist_info}/licenses/{fname.replace('.txt', '')}"] = path.read_bytes()

    metadata = "\n".join(
        [
            "Metadata-Version: 2.4",
            "Name: flet-libffmpeg",
            f"Version: {FFMPEG_VERSION}",
            "Summary: FFmpeg's seven libav* shared libraries for the av (PyAV) Android wheel",
            "License-Expression: GPL-3.0-or-later AND IJG",
            *[f"License-File: {f.replace('.txt', '')}" for f in LICENSE_FILES],
            "",
            "FFmpeg and its statically-linked external codec libraries, cross-built",
            f"for Android at API level {PINS['ANDROID_API_LEVEL']} with 16 KiB page alignment.",
            third_party_table(),
        ]
    ).encode()
    entries[f"{dist_info}/METADATA"] = metadata
    entries[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        "Root-Is-Purelib: false\n"
        "Generator: ffmpeg-av-wrap (build_flet_libffmpeg_wheel.py)\n"
        f"Build: {BUILD_TAG}\n"
        f"Tag: {tag}\n"
    ).encode()
    for name, blob in licenses.items():
        entries[name] = blob

    record_name = f"{dist_info}/RECORD"
    record_lines = [_record_line(n, b) for n, b in entries.items()]
    record_lines.append(f"{record_name},,")
    entries[record_name] = "\n".join(record_lines).encode()

    out_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = out_dir / f"{DIST_NAME}-{FFMPEG_VERSION}-{BUILD_TAG}-{tag}.whl"
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(entries):
            zf.writestr(name, entries[name])

    total = sum(len(b) for b in blobs.values())
    print(
        f">> {wheel_path.name} ({wheel_path.stat().st_size / 1e6:.1f} MB; "
        f"payload {total / 1e6:.1f} MB) configure: {configure[:100]}..."
    )
    return wheel_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ffmpeg-prefix",
        required=True,
        type=Path,
        help="Directory holding one `make install` prefix per ABI (lib/ include/ lib/pkgconfig/)",
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "wheels")
    parser.add_argument("--abis", default=",".join(ABIS))
    args = parser.parse_args()

    abis = [a.strip() for a in args.abis.split(",") if a.strip()]
    unknown = [a for a in abis if a not in ARCH_TAGS]
    if unknown:
        fail(f"unknown ABIs: {', '.join(unknown)}")

    wheels = []
    for abi in abis:
        prefix = args.ffmpeg_prefix / abi
        if not prefix.is_dir():
            fail(f"prefix not found: {prefix}")
        wheels.append(build_wheel(args.out, prefix, abi))
    print(f">> wrote {len(wheels)} wheel(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
