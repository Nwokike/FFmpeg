"""Flet 1.0 FilePicker return-shape and virtual-file regressions."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from services.media_io import MediaIOService, _copy_with_progress, picker_files


class _Page:
    def __init__(self):
        self.services = []


class _Picker:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    async def pick_files(self, **kwargs):
        self.kwargs = kwargs
        return self.result


def _service(result):
    service = MediaIOService(_Page())
    service.file_picker = _Picker(result)
    return service


def test_picker_files_accepts_flet_list_and_legacy_event():
    item = object()
    assert picker_files([item]) == [item]
    assert picker_files(SimpleNamespace(files=[item])) == [item]
    assert picker_files([]) == []


def test_pick_media_file_accepts_flet_list_result(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"video")
    service = _service([SimpleNamespace(path=str(media), name=media.name, bytes=None)])

    result = asyncio.run(service.pick_media_file())

    assert result == str(media)
    assert service.file_picker.kwargs["with_data"] is False


def test_pick_media_files_accepts_flet_list_result(tmp_path):
    first = tmp_path / "one.mp4"
    second = tmp_path / "two.mp4"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    service = _service(
        [
            SimpleNamespace(path=str(first), name=first.name, bytes=None),
            SimpleNamespace(path=str(second), name=second.name, bytes=None),
        ]
    )

    assert asyncio.run(service.pick_media_files()) == [str(first), str(second)]


def test_copy_reports_progress_and_preserves_bytes(tmp_path):
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    source.write_bytes(b"a" * (64 * 1024 + 7))
    progress = []

    asyncio.run(
        _copy_with_progress(
            source, destination, lambda value, message: progress.append((value, message))
        )
    )

    assert destination.read_bytes() == source.read_bytes()
    assert progress
    assert progress[-1][0] == 1.0
