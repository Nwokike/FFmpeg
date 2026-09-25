"""Application state and reactive models for FFmpeg."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import flet as ft

from core.engine_probe import EngineProbe


@dataclass
class ChapterInfo:
    """One container chapter (times in seconds)."""

    id: int
    title: str
    start_s: float
    end_s: float


@dataclass
class MediaStreamInfo:
    """Detailed stream parameters extracted from media containers."""

    index: int
    stream_type: str  # "video", "audio", "subtitle", "data"
    codec_name: str
    codec_long_name: str = ""
    profile: str | None = None
    bitrate: int | None = None
    duration_s: float | None = None
    # Video
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    pix_fmt: str | None = None
    rotation: int | None = None  # display-matrix degrees (from first frame)
    # Audio
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str | None = None
    # General
    language: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    disposition: dict[str, bool] = field(default_factory=dict)  # default/forced/…

    @property
    def has_subtitle_like_type(self) -> bool:
        return self.stream_type in ("subtitle", "text")


@dataclass
class MediaInfo:
    """Full container overview and probed streams for a media file."""

    file_path: str
    file_name: str
    file_size_bytes: int
    duration_s: float
    bitrate: int
    format_name: str
    format_long_name: str
    streams: list[MediaStreamInfo] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    chapters: list[ChapterInfo] = field(default_factory=list)
    raw_dump: str = ""

    @property
    def video_stream(self) -> MediaStreamInfo | None:
        for s in self.streams:
            if s.stream_type == "video":
                return s
        return None

    @property
    def audio_stream(self) -> MediaStreamInfo | None:
        for s in self.streams:
            if s.stream_type == "audio":
                return s
        return None


@ft.observable
@dataclass
class Job:
    """A single queued or executing media transformation job."""

    op: str  # "convert", "compress", "cut", "extract_audio", "extract_frames", "create_gif", "filters", "audio_studio"
    input_path: str
    output_path: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "pending"  # "pending", "running", "completed", "failed", "cancelled"
    progress: float = 0.0  # 0.0 to 1.0
    status_message: str = "Queued"
    error_message: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    original_size_bytes: int = 0
    output_size_bytes: int = 0

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @property
    def is_finished(self) -> bool:
        return self.status in ("completed", "failed", "cancelled")


@ft.observable
class AppState:
    """Global observable application state for Flet 1.0."""

    def __init__(self) -> None:
        self.has_accepted_terms: bool = False
        # Navigation
        self.selected_tab: int = 0  # 0: Home, 1: Jobs & History, 2: Settings
        self.active_view: str = "dashboard"  # "dashboard", "convert", "compress", "cut", "extract", "filters", "audio", "probe", "result", "engine_info"

        # Current loaded media for processing
        self.current_media_path: str | None = None
        self.current_media_info: MediaInfo | None = None

        # Job queues and history (whole-value assignment pattern)
        self.jobs: list[Job] = []
        self.active_job: Job | None = None
        self.last_completed_job: Job | None = None
        self.history: list[Job] = []

        # System & network
        self.is_online: bool = True
        # Ad consent settled (and banner slots may render). AdService state is
        # invisible to Flet's reactivity, so without this observable banners
        # stayed collapsed until an unrelated page update.
        self.ads_ready: bool = False
        self.update_available: bool = False
        self.update_data: dict[str, Any] | None = None
        self.probe_info: EngineProbe | None = None

        # Theme — whole-value observable writes ONLY (dict-item mutation of
        # settings["theme_mode"] never published, so headers/tints stayed stale
        # until an unrelated re-render — the "must change screen to finish the
        # switch" bug). theme_revision bumps on toggle AND platform-brightness
        # change so SYSTEM mode re-themes instantly (CollabShell pattern).
        self.theme_mode: ft.ThemeMode = ft.ThemeMode.SYSTEM
        self.theme_revision: int = 0

        # Settings
        self.settings: dict[str, Any] = {
            "theme_mode": "system",  # "system", "dark", "light"
            "default_video_preset": "medium",  # "fast", "medium", "slow"
            "default_audio_format": "mp3",  # "mp3", "aac", "flac", "opus"
            "default_crf": 23,
            "save_to_downloads": True,
            "http_proxy": "",
            "hardware_accel": True,
        }

    def set_setting(self, key: str, value: Any) -> None:
        """Write one settings key as a WHOLE-VALUE assignment.

        A dict-item write (``self.settings[key] = v``) mutates in place and
        never reaches the observable's ``__setattr__`` hook — subscribers kept
        rendering the old value until an unrelated re-render.
        """
        self.settings = {**self.settings, key: value}


state = AppState()

# Flet components must receive observables through a context (or component
# argument) to subscribe to changes.  Reading the module-level singleton
# directly still returns the new value, but leaves the rendered component
# stale -- which is how tab, banner, and theme controls appeared inert.
AppStateCtx = ft.create_context(state)


def use_app_state() -> AppState:
    """Return the app state and subscribe the current Flet component to it."""
    return ft.use_context(AppStateCtx)


__all__ = [
    "AppState",
    "AppStateCtx",
    "Job",
    "MediaInfo",
    "MediaStreamInfo",
    "state",
    "use_app_state",
]
