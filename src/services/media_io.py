"""Media I/O service — file picking, system save, and native share sheet."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import flet as ft

from core.storage_paths import get_data_dir

logger = logging.getLogger("MediaIOService")


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
        """Open system file picker to select a video or audio file. Returns local path."""
        try:
            res = await self.file_picker.pick_files(
                dialog_title="Select Media File",
                file_type=ft.FilePickerFileType.MEDIA,
                allow_multiple=False,
            )
            if res and res.files:
                selected = res.files[0]
                # If native local path is available (desktop / android scoped)
                if selected.path and os.path.exists(selected.path):
                    return selected.path

                # If bytes are returned (e.g. mobile virtual content URI)
                if selected.bytes:
                    cache_dest = get_data_dir() / selected.name
                    cache_dest.write_bytes(selected.bytes)
                    return str(cache_dest)
        except Exception as exc:
            logger.error("Failed to pick media file: %s", exc)
        return None

    async def save_media_file(
        self, source_path: str, default_name: str | None = None
    ) -> str | None:
        """Prompt user to save an output file to Downloads or chosen location."""
        src = Path(source_path)
        if not src.exists():
            logger.warning("Save target file does not exist: %s", source_path)
            return None

        name = default_name or src.name
        try:
            data = src.read_bytes()
            dest_path = await self.file_picker.save_file(
                dialog_title="Save Converted Media",
                file_name=name,
                src_bytes=data,
            )
            if dest_path:
                logger.info("Media file saved to: %s", dest_path)
                return dest_path
        except Exception as exc:
            logger.error("Failed saving media file: %s", exc)

        # Fallback for systems where save_file dialog fails: copy to Downloads folder
        try:
            downloads = Path.home() / "Downloads"
            if downloads.exists():
                fallback = downloads / name
                shutil.copy2(source_path, str(fallback))
                logger.info("Saved to Downloads fallback: %s", fallback)
                return str(fallback)
        except Exception:
            pass

        return None

    async def share_file(self, file_path: str) -> bool:
        """Trigger native system share sheet for the specified media file."""
        p = Path(file_path)
        if not p.exists():
            return False
        try:
            share_item = ft.ShareFile.from_path(str(p.resolve()))
            await self.share.share_files([share_item], text=f"Processed with FFmpeg: {p.name}")
            return True
        except Exception as exc:
            logger.error("Native share sheet failed: %s", exc)
            return False
