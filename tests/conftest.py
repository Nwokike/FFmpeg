"""Shared fixtures: synthetic media builder (session-scoped) + FakePage harness."""

from __future__ import annotations

import array
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

_SECONDS = 2.0
_FPS = 30
_WIDTH = 96
_HEIGHT = 64
_RATE = 44100


def _build_synthetic(path: str) -> None:
    """2s clip: 96x64 h264 + 440Hz stereo AAC — fast, deterministic, no assets."""
    import av

    out = av.open(path, "w")
    vs = out.add_stream("libx264", rate=_FPS)
    vs.width, vs.height, vs.pix_fmt = _WIDTH, _HEIGHT, "yuv420p"
    # keyint=10 gives regular keyframes — exercises keyframe snap + tick chips
    vs.options = {"crf": "30", "preset": "ultrafast", "keyint": "10", "min-keyint": "10"}
    asr = out.add_stream("aac", rate=_RATE)
    asr.layout = "stereo"

    n_samples = 0
    for i in range(int(_SECONDS * _FPS)):
        vt = av.VideoFrame(_WIDTH, _HEIGHT, "yuv420p")
        for idx, plane in enumerate(vt.planes):
            plane.update(bytes([100 + (i % 50) + idx]) * plane.buffer_size)
        vt.pts = i
        for pkt in vs.encode(vt):
            out.mux(pkt)
    for _ in range(86):  # ~2s of audio at 1024 samples/frame
        af = av.AudioFrame("s16", "stereo", 1024)
        af.sample_rate = _RATE
        samples = array.array(
            "h",
            (
                v
                for k in range(1024)
                for v in (int(12000 * math.sin(2 * math.pi * 440 * (n_samples + k) / _RATE)),) * 2
            ),
        )
        n_samples += 1024
        af.planes[0].update(samples.tobytes())
        for pkt in asr.encode(af):
            out.mux(pkt)
    for pkt in vs.encode(None):
        out.mux(pkt)
    for pkt in asr.encode(None):
        out.mux(pkt)
    out.close()


@pytest.fixture(scope="session")
def synthetic_media(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    """Session-wide synthetic source clip + scratch dir for outputs."""
    import av  # noqa: F401 — fail fast if the engine wheel is broken

    workdir = tmp_path_factory.mktemp("engine_media")
    src = workdir / "source.mp4"
    _build_synthetic(str(src))
    assert src.exists() and src.stat().st_size > 0
    return SimpleNamespace(path=str(src), dir=Path(workdir), frames=_SECONDS * _FPS)


class FakePage:
    """Minimal Page stand-in for component/controller tests (Sherlock pattern)."""

    def __init__(self) -> None:
        self.route = "/"
        self.dialogs: list = []
        self.updates = 0
        self.tasks: list = []
        self.services: list = []

    def show_dialog(self, dialog) -> None:
        if self.dialogs:
            raise RuntimeError("Dialog is already opened")
        self.dialogs.append(dialog)

    def pop_dialog(self):
        return self.dialogs.pop() if self.dialogs else None

    def update(self, *args) -> None:
        self.updates += 1

    def run_task(self, fn, *args, **kwargs):
        self.tasks.append((fn, args))


@pytest.fixture
def fake_page() -> FakePage:
    return FakePage()
