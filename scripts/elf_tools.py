"""Minimal ELF32/ELF64 inspection for Android native payload validation."""

from __future__ import annotations

import struct

# ── minimal ELF reader (what Android native payloads must satisfy) ──────────
# align  — minimum PT_LOAD p_align (16 KiB = 0x4000 is the Play requirement
#          for 64-bit ABIs on 16 KiB pages; 32-bit ABIs are 4 KiB).
# needed — DT_NEEDED names the linker must find at load time.
# soname — DT_SONAME (jniLibs names must be lib*.so, so SONAMEs are
#          re-materialised at app runtime, not at packaging time).
# bits   — 32 or 64, from EI_CLASS (armeabi-v7a is ELF32, arm64 is ELF64).

DT_NEEDED, DT_STRTAB, DT_SONAME, DT_TEXTREL = 1, 5, 14, 22
ALIGN_16K = 0x4000
ALIGN_4K = 0x1000

# bionic/system libraries provided by the platform — never shipped by us.
SYSTEM_SONAMES = {
    "libc.so",
    "libdl.so",
    "libm.so",
    "liblog.so",
    "libandroid.so",
    "libz.so",
}


class ElfError(SystemExit):
    """Raised when a blob is not a readable ELF payload."""


def _cstr(blob: bytes, off: int) -> str:
    end = blob.find(b"\0", off)
    return blob[off : end if end != -1 else len(blob)].decode("utf-8", "replace")


def elf_info(blob: bytes, label: str) -> dict:
    """Return {needed, soname, align, textrel, bits} for an ELF32/ELF64 blob."""
    if blob[:4] != b"\x7fELF":
        raise ElfError(f"{label}: not an ELF file")
    bits = {1: 32, 2: 64}.get(blob[4])
    if bits is None:
        raise ElfError(f"{label}: unknown ELF class {blob[4]}")
    if bits == 64:
        e_phoff = struct.unpack_from("<Q", blob, 0x20)[0]
        e_phentsize = struct.unpack_from("<H", blob, 0x36)[0]
        e_phnum = struct.unpack_from("<H", blob, 0x38)[0]
    else:
        e_phoff = struct.unpack_from("<I", blob, 0x1C)[0]
        e_phentsize = struct.unpack_from("<H", blob, 0x2A)[0]
        e_phnum = struct.unpack_from("<H", blob, 0x2C)[0]

    loads: list[tuple[int, int, int, int]] = []
    dyn_off = dyn_size = None
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        p_type = struct.unpack_from("<I", blob, o)[0]
        if bits == 64:
            p_offset, p_vaddr = struct.unpack_from("<QQ", blob, o + 0x08)
            p_filesz = struct.unpack_from("<Q", blob, o + 0x20)[0]
            p_align = struct.unpack_from("<Q", blob, o + 0x30)[0]
        else:
            p_offset, p_vaddr = struct.unpack_from("<II", blob, o + 0x04)
            p_filesz = struct.unpack_from("<I", blob, o + 0x10)[0]
            p_align = struct.unpack_from("<I", blob, o + 0x1C)[0]
        if p_type == 1:  # PT_LOAD
            if p_align and (p_vaddr % p_align) != (p_offset % p_align):
                raise ElfError(
                    f"{label}: PT_LOAD segment congruence failure: "
                    f"vaddr {p_vaddr:#x} % {p_align:#x} != offset {p_offset:#x} % {p_align:#x}"
                )
            loads.append((p_offset, p_vaddr, p_filesz, p_align))
        elif p_type == 2:  # PT_DYNAMIC
            dyn_off, dyn_size = p_offset, p_filesz
    align = min((seg[3] for seg in loads), default=None)
    if dyn_off is None:
        return {"needed": [], "soname": None, "align": align, "textrel": False, "bits": bits}

    def vaddr_to_off(v: int) -> int | None:
        for p_offset, p_vaddr, p_filesz, _ in loads:
            if p_vaddr <= v < p_vaddr + p_filesz:
                return p_offset + (v - p_vaddr)
        return None

    entry_size = 16 if bits == 64 else 8
    entry_fmt = "<QQ" if bits == 64 else "<II"
    entries: list[tuple[int, int]] = []
    for i in range(dyn_size // entry_size):
        d_tag, d_val = struct.unpack_from(entry_fmt, blob, dyn_off + i * entry_size)
        if d_tag == 0:
            break
        entries.append((d_tag, d_val))
    strtab_v = next((v for t, v in entries if t == DT_STRTAB), None)
    strtab_off = vaddr_to_off(strtab_v) if strtab_v is not None else None
    needed = (
        [_cstr(blob, strtab_off + v) for t, v in entries if t == DT_NEEDED]
        if strtab_off is not None
        else []
    )
    soname = (
        next((_cstr(blob, strtab_off + v) for t, v in entries if t == DT_SONAME), None)
        if strtab_off is not None
        else None
    )
    textrel = any(t == DT_TEXTREL for t, _ in entries)
    return {
        "needed": needed,
        "soname": soname,
        "align": align,
        "textrel": textrel,
        "bits": bits,
    }


def unmet_needed(info: dict, shipped_sonames: set[str]) -> list[str]:
    """DT_NEEDED entries not satisfied by the shipped payloads or the platform."""
    return [
        n
        for n in info["needed"]
        if n not in shipped_sonames
        and not n.startswith(("libc.", "libdl.", "libm."))
        and n not in SYSTEM_SONAMES
    ]
