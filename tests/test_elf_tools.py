"""ELF reader contract: ELF32 (armeabi-v7a) and ELF64 (arm64/x86_64).

The packager refused the v2.0.0 ARM32 wheel with "only ELF64 supported
(ei_class=1)" — these fixtures pin both classes and the congruence check so
the regression cannot come back.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import elf_tools  # noqa: E402 - scripts/ is not a package

STRTAB = b"\0libfoo.so\0libbar.so\0"
NEEDED_OFF, SONAME_OFF = 1, 11


def _elf32(load_align: int = 0x4000, load_offset: int = 0x1000) -> bytes:
    ident = b"\x7fELF" + bytes([1, 1, 1]) + b"\0" * 9  # 32-bit, little-endian
    ehsize, phentsize, phnum = 52, 32, 2
    strtab_off, dyn_off = 0x1000, 0x1200
    dyn = b"".join(
        struct.pack("<II", tag, val)
        for tag, val in (
            (elf_tools.DT_NEEDED, NEEDED_OFF),
            (elf_tools.DT_SONAME, SONAME_OFF),
            (elf_tools.DT_STRTAB, strtab_off),
            (0, 0),
        )
    )
    buf = bytearray(dyn_off + len(dyn))
    buf[0:16] = ident
    struct.pack_into(
        "<HHIIIIIHHHHHH", buf, 16, 3, 40, 1, 0, ehsize, 0, 0, ehsize, phentsize, phnum, 0, 0, 0
    )
    struct.pack_into(
        "<IIIIIIII", buf, ehsize, 1, load_offset, 0x1000, 0x1000, 0x200, 0x200, 6, load_align
    )
    struct.pack_into(
        "<IIIIIIII", buf, ehsize + phentsize, 2, dyn_off, dyn_off, dyn_off, len(dyn), len(dyn), 6, 4
    )
    buf[0x1000 : 0x1000 + len(STRTAB)] = STRTAB
    buf[dyn_off : dyn_off + len(dyn)] = dyn
    return bytes(buf)


def _elf64(load_align: int = 0x4000) -> bytes:
    ident = b"\x7fELF" + bytes([2, 1, 1]) + b"\0" * 9  # 64-bit, little-endian
    ehsize, phentsize, phnum = 64, 56, 2
    strtab_off, dyn_off = 0x1000, 0x1200
    dyn = b"".join(
        struct.pack("<QQ", tag, val)
        for tag, val in (
            (elf_tools.DT_NEEDED, NEEDED_OFF),
            (elf_tools.DT_SONAME, SONAME_OFF),
            (elf_tools.DT_STRTAB, strtab_off),
            (0, 0),
        )
    )
    buf = bytearray(dyn_off + len(dyn))
    buf[0:16] = ident
    struct.pack_into(
        "<HHIQQQIHHHHHH", buf, 16, 3, 183, 1, 0, ehsize, 0, 0, ehsize, phentsize, phnum, 0, 0, 0
    )
    struct.pack_into(
        "<IIQQQQQQ", buf, ehsize, 1, 6, 0x1000, 0x1000, 0x1000, 0x200, 0x200, load_align
    )
    struct.pack_into(
        "<IIQQQQQQ",
        buf,
        ehsize + phentsize,
        2,
        6,
        dyn_off,
        dyn_off,
        dyn_off,
        len(dyn),
        len(dyn),
        8,
    )
    buf[0x1000 : 0x1000 + len(STRTAB)] = STRTAB
    buf[dyn_off : dyn_off + len(dyn)] = dyn
    return bytes(buf)


def test_elf32_parses_needed_soname_and_alignment():
    info = elf_tools.elf_info(_elf32(), "arm32/libfoo.so")
    assert info["bits"] == 32
    assert info["needed"] == ["libfoo.so"]
    assert info["soname"] == "libbar.so"
    assert info["align"] == 0x4000
    assert info["textrel"] is False


def test_elf64_parses_the_same_contract():
    info = elf_tools.elf_info(_elf64(), "arm64/libfoo.so")
    assert info["bits"] == 64
    assert info["needed"] == ["libfoo.so"]
    assert info["soname"] == "libbar.so"
    assert info["align"] == 0x4000


def test_elf32_misaligned_pt_load_is_refused():
    with pytest.raises(elf_tools.ElfError):
        elf_tools.elf_info(_elf32(load_offset=0x1010), "arm32/bad.so")


def test_non_elf_is_refused():
    with pytest.raises(elf_tools.ElfError):
        elf_tools.elf_info(b"not an elf", "junk")
