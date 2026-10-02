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


class _Saver:
    """FilePicker stub that cancels the save dialog (returns None)."""

    def __init__(self):
        self.calls = 0

    async def pick_files(self, **kwargs):
        return []

    async def save_file(self, **kwargs):
        self.calls += 1
        return None


def test_save_cancel_does_not_fall_through_to_downloads(tmp_path, monkeypatch):
    import services.media_io as mio

    src = tmp_path / "result.mp4"
    src.write_bytes(b"video")
    service = MediaIOService(_Page())
    service.file_picker = _Saver()
    # Point Downloads at an empty dir: any fallback write would land here.
    fake_home = tmp_path / "home"
    (fake_home / "Downloads").mkdir(parents=True)
    monkeypatch.setattr(mio.Path, "home", classmethod(lambda cls: fake_home))

    result = asyncio.run(service.save_media_file(str(src)))

    assert result is None, "user-cancel must not write anything"
    assert service.file_picker.calls == 1
    assert list((fake_home / "Downloads").iterdir()) == [], "no fallback copy on cancel"


def test_pick_retries_with_data_for_mobile_uris():
    virtual = SimpleNamespace(path=None, name="content.mp4", bytes=None)
    with_bytes = SimpleNamespace(path=None, name="content.mp4", bytes=b"data")

    class _RetryPicker:
        def __init__(self):
            self.calls = []

        async def pick_files(self, **kwargs):
            self.calls.append(kwargs.get("with_data"))
            return [with_bytes] if kwargs.get("with_data") else [virtual]

    service = MediaIOService(_Page())
    service.file_picker = _RetryPicker()

    result = asyncio.run(service.pick_media_file())

    assert service.file_picker.calls == [False, True]
    assert result is not None and result.endswith(".mp4")


class _Share:
    def __init__(self, status):
        import flet as ft

        self._status = status
        self.ft = ft

    async def share_files(self, items, text=None):
        return SimpleNamespace(status=self._status)


def test_share_reports_dismissed_as_not_shared(tmp_path):
    import flet as ft

    media = tmp_path / "clip.mp4"
    media.write_bytes(b"video")
    service = MediaIOService(_Page())
    service.share = _Share(ft.ShareResultStatus.DISMISSED)
    assert asyncio.run(service.share_file(str(media))) is False

    service.share = _Share(ft.ShareResultStatus.SUCCESS)
    assert asyncio.run(service.share_file(str(media))) is True
