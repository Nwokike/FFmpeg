"""Media I/O service — file picking, system save, and native share sheet."""

from __future__ import annotations

import asyncio
import errno
import logging
import shutil
from collections.abc import Callable
from pathlib import Path

import flet as ft

from core.storage_paths import cache_bytes

logger = logging.getLogger("MediaIOService")

# Files above this size skip the read-into-RAM save dialog (mobile save_file
# requires src_bytes) and use the streaming Downloads copy instead.
MAX_SAF_BYTES = 100 * 1024 * 1024


def _is_out_of_space(exc: BaseException) -> bool:
    """True for ENOSPC/EDQUOT — the one failure users hit mid-save, logged
    distinctly so a full disk is never mistaken for a picker bug."""
    return isinstance(exc, OSError) and exc.errno in (errno.ENOSPC, errno.EDQUOT)


def picker_files(result) -> list:
    """Normalize Flet 1.0's list return and legacy event-shaped results."""
    if not result:
        return []
    if isinstance(result, list):
        return result
    return list(getattr(result, "files", None) or [])


async def _copy_with_progress(
    source: Path,
    destination: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> None:
    """Copy a file in bounded chunks while keeping UI callbacks on the event loop."""
    total = max(1, (await asyncio.to_thread(source.stat)).st_size)
    copied = 0
    src = await asyncio.to_thread(source.open, "rb")
    dst = await asyncio.to_thread(destination.open, "wb")
    try:
        while chunk := await asyncio.to_thread(src.read, 64 * 1024):
            await asyncio.to_thread(dst.write, chunk)
            copied += len(chunk)
            if on_progress:
                on_progress(min(1.0, copied / total), f"Saving {destination.name}…")
    finally:
        await asyncio.to_thread(src.close)
        await asyncio.to_thread(dst.close)


class MediaIOService:
    """Coordinates FilePicker and Share services across mobile and desktop."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.file_picker = ft.FilePicker()
        self.share = ft.Share()

        # Retain strong refs and register in page.services for Flet 1.0 GC
        if self.file_picker not in self.page.services:
            self.page.services.append(self.file_picker)
        if self.share not in self.page.services:
            self.page.services.append(self.share)

    async def pick_media_file(self) -> str | None:
        """Open the media picker without copying a 500 MB file into Python RAM."""
        try:
            res = await self.file_picker.pick_files(
                dialog_title="Select Media File",
                file_type=ft.FilePickerFileType.MEDIA,
                allow_multiple=False,
                with_data=False,
            )
            files = picker_files(res)
            if files:
                selected = files[0]
                # If native local path is available (desktop / android scoped)
                if selected.path and Path(selected.path).exists():  # noqa: ASYNC240 — trivial stat/exists check
                    return selected.path

                # If bytes are returned (e.g. mobile virtual content URI)
                if selected.bytes:
                    return str(cache_bytes(selected.name, selected.bytes))
                logger.warning("Picker returned no local media path; choose a local copy")
        except Exception as exc:
            if _is_out_of_space(exc):
                logger.exception("Out of storage space while caching the picked file")
            else:
                logger.exception("Failed to pick media file")
        return None

    async def pick_media_files(self) -> list[str]:
        """Multi-select media picker; never buffers large files in RAM."""
        picked: list[str] = []
        try:
            res = await self.file_picker.pick_files(
                dialog_title="Select Media Files to Join",
                file_type=ft.FilePickerFileType.MEDIA,
                allow_multiple=True,
                with_data=False,
            )
            files = picker_files(res)
            if not files:
                return picked
            for f in files:
                if f.path and Path(f.path).exists():  # noqa: ASYNC240 — trivial stat/exists check
                    picked.append(f.path)
                elif f.bytes:
                    picked.append(str(cache_bytes(f.name, f.bytes)))
                else:
                    logger.warning("Picker skipped %s: no local path", f.name)
        except Exception as exc:
            if _is_out_of_space(exc):
                logger.exception("Out of storage space while caching picked files")
            else:
                logger.exception("Failed to pick media files")
        return picked

    async def save_media_file(
        self,
        source_path: str,
        default_name: str | None = None,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> str | None:
        """Prompt user to save an output file to Downloads or chosen location.

        Directories (frame exports) are zipped first; files above the SAF byte
        budget skip the full-read dialog and go straight to the Downloads copy
        (save_file requires src_bytes on mobile — reading a huge file into RAM
        is the OOM this guard exists to prevent).
        """
        src = Path(source_path)
        if not src.exists():  # noqa: ASYNC240 — trivial stat/exists check
            logger.warning("Save target file does not exist: %s", source_path)
            return None

        if src.is_dir():  # noqa: ASYNC240 — trivial stat/exists check
            # Frame exports are directories; SAF deals in files. Zip in place
            # (dirs live in the temp tier, so the archive is regenerable).
            # make_archive appends .zip to the full base name — safe for stems
            # that themselves contain dots.
            try:
                src = Path(shutil.make_archive(str(src), "zip", root_dir=str(src)))
            except OSError:
                logger.exception("Failed zipping frame export")
                return None

        name = default_name or src.name
        size = src.stat().st_size
        if on_progress:
            on_progress(0.0, f"Preparing {name}…")
        if size <= MAX_SAF_BYTES:
            try:
                data = await asyncio.to_thread(src.read_bytes)
                if on_progress:
                    on_progress(0.35, "Waiting for a save destination…")
                dest_path = await self.file_picker.save_file(
                    dialog_title="Save Converted Media",
                    file_name=name,
                    src_bytes=data,
                )
                if dest_path:
                    logger.info("Media file saved to: %s", dest_path)
                    if on_progress:
                        on_progress(1.0, f"Saved {name}")
                    return dest_path
            except Exception as exc:
                if _is_out_of_space(exc):
                    logger.exception("Out of storage space while saving the media file")
                else:
                    logger.exception("Failed saving media file")
        else:
            logger.info("Save dialog skipped for large file (%d bytes): %s", size, name)

        # Fallback: copy to Downloads (covers dialog failure AND the size guard)
        if on_progress:
            on_progress(0.05, "Saving directly to Downloads…")
        try:
            downloads = Path.home() / "Downloads"
            if downloads.exists():
                fallback = downloads / name
                await _copy_with_progress(src, fallback, on_progress)
                logger.info("Saved to Downloads fallback: %s", fallback)
                if on_progress:
                    on_progress(1.0, f"Saved {name}")
                return str(fallback)
        except Exception as e:
            if _is_out_of_space(e):
                logger.exception("Out of storage space copying to Downloads")
            else:
                logger.warning("Downloads fallback failed: %s", e)

        return None

    async def share_file(
        self,
        file_path: str,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> bool:
        """Trigger native system share sheet for the specified media file."""
        p = Path(file_path)
        if not p.exists():  # noqa: ASYNC240 — trivial stat/exists check
            logger.warning("Share target missing: %s", file_path)
            return False
        if p.is_dir():  # noqa: ASYNC240 — trivial stat/exists check
            try:
                p = Path(shutil.make_archive(str(p), "zip", root_dir=str(p)))
            except OSError:
                logger.exception("Failed zipping directory for share")
                return False
        try:
            if on_progress:
                on_progress(0.25, f"Preparing {p.name} for sharing…")
            share_item = ft.ShareFile.from_path(str(p.resolve()))
            if on_progress:
                on_progress(0.6, "Opening the system share sheet…")
            await self.share.share_files([share_item], text=f"Processed with FFmpeg: {p.name}")
            if on_progress:
                on_progress(1.0, "Share sheet opened")
            return True
        except Exception as exc:
            if _is_out_of_space(exc):
                logger.exception("Out of storage space preparing the share")
            else:
                logger.exception("Native share sheet failed")
            return False
