"""Media I/O service — file picking, system save, and native share sheet."""

from __future__ import annotations

import asyncio
import errno
import logging
import os
import shutil
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

import flet as ft

from core.storage_paths import cache_bytes

logger = logging.getLogger("MediaIOService")

# Files above this size skip the read-into-RAM save dialog (mobile save_file
# requires src_bytes) and use the streaming Downloads copy instead.
MAX_SAF_BYTES = 100 * 1024 * 1024

_COPY_CHUNK_BYTES = 1024 * 1024


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


def _has_local_path(selected) -> bool:
    # Trivial exists check, kept sync so all three picker call sites share it.
    return bool(selected.path) and Path(selected.path).exists()


def _fd_copy_sync(src: Path, tmp: Path, total: int, report: Callable[[int], None]) -> None:
    """Blocking chunk copy (runs in a worker thread); reports bytes copied."""
    with src.open("rb") as fsrc, tmp.open("wb") as fdst:
        while True:
            chunk = fsrc.read(_COPY_CHUNK_BYTES)
            if not chunk:
                break
            fdst.write(chunk)
            report(len(chunk))
        fdst.flush()
        os.fsync(fdst.fileno())


async def _copy_with_progress(
    source: Path,
    destination: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> None:
    """Copy a file in bounded chunks; temp + atomic rename, no residue.

    The whole loop runs in ONE worker thread (not a thread-hop per chunk).
    A partial destination is cleaned up on any failure.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = max(1, (await asyncio.to_thread(source.stat)).st_size)
    copied = 0

    def report(n: int) -> None:
        nonlocal copied
        copied += n

    tmp = destination.with_name(destination.name + ".part")
    try:
        if on_progress:
            on_progress(0.0, f"Saving {destination.name}…")
        await asyncio.to_thread(_fd_copy_sync, source, tmp, total, report)
        # Progress callbacks stay on the loop; report coarsely to avoid a
        # callback storm on big files.
        if on_progress:
            on_progress(1.0, f"Saving {destination.name}…")
        await asyncio.to_thread(os.replace, tmp, destination)
    except BaseException:
        await asyncio.to_thread(_drop_quietly, tmp)
        raise


def _drop_quietly(path: Path) -> None:
    with suppress(OSError):
        path.unlink(missing_ok=True)


class MediaIOService:
    """Coordinates FilePicker and Share services across mobile and desktop."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.file_picker = ft.FilePicker()
        self.share = ft.Share()
        # Service controls self-register with the client on construction
        # (Service.__post_init__ → ServiceRegistry.register_service, which
        # pushes the update). Manual page.services.append bypasses that
        # channel — the mounted tree would never learn about them — so the
        # only job here is keeping strong refs so GC can't collect them.
        # Identity (``is``) is the right check — dataclass equality can
        # claim a fresh picker is "already in" services when a value-equal
        # twin is there, while the real instance is still unmounted.
        _ = (self.file_picker, self.share)

    async def _pick_once(self, allow_multiple: bool):
        """One picker round; on mobile content URIs retry with data attached."""
        res = await self.file_picker.pick_files(
            dialog_title="Select Media Files to Join" if allow_multiple else "Select Media File",
            file_type=ft.FilePickerFileType.MEDIA,
            allow_multiple=allow_multiple,
            with_data=False,
        )
        files = picker_files(res)
        return files

    def _local_or_cached(self, selected, picked: list[str], *, single: bool) -> None:
        # Native local path first (desktop / android scoped storage).
        if _has_local_path(selected):
            picked.append(selected.path)
            return
        # Bytes fallback (mobile virtual content URI): request data on retry.
        if selected.bytes:
            picked.append(str(cache_bytes(selected.name, selected.bytes)))
            return
        if single:
            logger.warning("Picker returned no local media path; choose a local copy")
        else:
            logger.warning("Picker skipped %s: no local path", selected.name)

    async def pick_media_file(self) -> str | None:
        """Open the media picker without copying a 500 MB file into Python RAM."""
        try:
            files = await self._pick_once(allow_multiple=False)
            if files:
                out: list[str] = []
                self._local_or_cached(files[0], out, single=True)
                if out:
                    return out[0]
                # No path and no bytes: retry once with data attached so
                # mobile content URIs resolve instead of dead-ending.
                res = await self.file_picker.pick_files(
                    dialog_title="Select Media File",
                    file_type=ft.FilePickerFileType.MEDIA,
                    allow_multiple=False,
                    with_data=True,
                )
                files = picker_files(res)
                if files:
                    self._local_or_cached(files[0], out, single=True)
                    if out:
                        return out[0]
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
            files = await self._pick_once(allow_multiple=True)
            if not files:
                return picked
            missing_data = [f for f in files if not _has_local_path(f) and not f.bytes]
            if missing_data:
                # One retry with data for the mobile-URI entries only.
                res = await self.file_picker.pick_files(
                    dialog_title="Select Media Files to Join",
                    file_type=ft.FilePickerFileType.MEDIA,
                    allow_multiple=True,
                    with_data=True,
                )
                retry = {f.name: f for f in picker_files(res)}
                files = [retry.get(f.name, f) for f in files]
            for f in files:
                self._local_or_cached(f, picked, single=False)
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
        is the OOM this guard exists to prevent). Returns None on user-cancel
        WITHOUT falling through to Downloads; the fallback runs only after a
        dialog error or the size guard.
        """
        src = Path(source_path)
        if not src.exists():  # noqa: ASYNC240 — trivial stat/exists check
            logger.warning("Save target file does not exist: %s", source_path)
            return None

        if src.is_dir():  # noqa: ASYNC240 — trivial stat/exists check
            # Frame exports are directories; SAF deals in files. Zip into the
            # temp tier (dirs live there, so the archive is regenerable).
            # make_archive appends .zip to the full base name — safe for stems
            # that themselves contain dots. Orphan archives from earlier saves
            # are reclaimed by the temp age-prune.
            try:
                src = Path(
                    await asyncio.to_thread(shutil.make_archive, str(src), "zip", root_dir=str(src))
                )
            except OSError:
                logger.exception("Failed zipping frame export")
                return None

        name = default_name or src.name
        try:
            size = (await asyncio.to_thread(src.stat)).st_size
        except OSError:
            logger.exception("Save target vanished: %s", src)
            return None
        if on_progress:
            on_progress(0.0, f"Preparing {name}…")
        dialog_failed = False
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
                # None = the user cancelled. Respect it: no fallback copy.
                logger.info("Save dialog cancelled by user; no file written")
                return None
            except Exception as exc:
                dialog_failed = True
                if _is_out_of_space(exc):
                    logger.exception("Out of storage space while saving the media file")
                else:
                    logger.exception("Failed saving media file")
        else:
            dialog_failed = True
            logger.info("Save dialog skipped for large file (%d bytes): %s", size, name)

        # Fallback: streaming copy to Downloads (dialog error or size guard —
        # never user-cancel, which returns above). Desktop/dev only: mobile
        # has no ~/Downloads; there the failure is reported, not silent.
        if not dialog_failed:
            return None
        if on_progress:
            on_progress(0.05, "Saving directly to Downloads…")
        try:
            downloads = Path.home() / "Downloads"
            fallback = downloads / name
            if not downloads.exists():
                logger.warning(
                    "Downloads fallback unavailable (no %s); save the file from the result screen instead",
                    downloads,
                )
                return None
            # Collision-safe: never silently overwrite an existing download.
            if fallback.exists():
                stem, suffix = fallback.stem, fallback.suffix
                for i in range(2, 1000):
                    candidate = downloads / f"{stem} ({i}){suffix}"
                    if not candidate.exists():
                        fallback = candidate
                        break
                else:
                    logger.warning("Downloads fallback crowded; not overwriting %s", fallback)
                    return None
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
        """Trigger native system share sheet. True only on actual share."""
        p = Path(file_path)
        if not p.exists():  # noqa: ASYNC240 — trivial stat/exists check
            logger.warning("Share target missing: %s", file_path)
            return False
        if p.is_dir():  # noqa: ASYNC240 — trivial stat/exists check
            try:
                p = Path(
                    await asyncio.to_thread(shutil.make_archive, str(p), "zip", root_dir=str(p))
                )
            except OSError:
                logger.exception("Failed zipping directory for share")
                return False
        try:
            if on_progress:
                on_progress(0.25, f"Preparing {p.name} for sharing…")
            share_item = ft.ShareFile.from_path(str(p.resolve()))
            if on_progress:
                on_progress(0.6, "Opening the system share sheet…")
            result = await self.share.share_files(
                [share_item], text=f"Processed with FFmpeg: {p.name}"
            )
            status = getattr(result, "status", None)
            if status is not None and status != ft.ShareResultStatus.SUCCESS:
                # DISMISSED / UNAVAILABLE: the sheet never shared anything.
                logger.info("Share sheet ended without sharing (%s)", status)
                return False
            if on_progress:
                on_progress(1.0, "Share sheet opened")
            return True
        except Exception as exc:
            if _is_out_of_space(exc):
                logger.exception("Out of storage space preparing the share")
            else:
                logger.exception("Native share sheet failed")
            return False
