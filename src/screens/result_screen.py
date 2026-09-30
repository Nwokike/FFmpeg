"""Job completion and export view featuring media playback, metrics, and sharing."""

from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from core.state import use_app_state
from core.storage_paths import format_bytes
from core.styles import card_container, status_badge
from core.theme import PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import (
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    RADIUS_LG,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from state.controller_ctx import use_controller

logger = logging.getLogger(__name__)

_VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".webm", ".avi", ".ts")
_AUDIO_EXTS = (".mp3", ".aac", ".m4a", ".flac", ".opus", ".wav")

try:
    import flet_video as ftv

    _HAS_VIDEO = True
except ImportError:
    _HAS_VIDEO = False

try:
    from flet_audio import Audio, AudioState, ReleaseMode

    _HAS_AUDIO_PLAYER = True
except ImportError:  # pragma: no cover — package is in the dev tree
    _HAS_AUDIO_PLAYER = False


def _fmt_ms(ms: int) -> str:
    """Millisecond timestamp → mm:ss."""
    total_s = max(0, int(ms)) // 1000
    return f"{total_s // 60:02d}:{total_s % 60:02d}"


@ft.component
def ResultScreen() -> ft.Control:
    """Finished job presentation with hardware-accelerated preview player and export actions."""
    page = ft.context.page
    ctrl = use_controller()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    job = app_state.last_completed_job or app_state.active_job

    # ── Preview lifecycles — hooks run on EVERY render (incl. the no-job
    # early return below), and controls are built ONCE per job mount so
    # re-renders never re-create the player underneath the user. ──────────
    compare, set_compare = ft.use_state("output")  # "output" | "original"
    playing, set_playing = ft.use_state(False)
    pos_ms, set_pos_ms = ft.use_state(0)
    dur_ms, set_dur_ms = ft.use_state(0)
    players_ready, set_players_ready = ft.use_state(False)
    video_ref = ft.use_ref(None)
    audio_ref = ft.use_ref(None)
    dragging_ref = ft.use_ref(False)  # slider drag in flight — ignore position events
    audio_state_ref = ft.use_ref(AudioState.STOPPED)

    def _is_mounted(ctrl) -> bool:
        """True once Flet attached the control to the page.

        The preview Video is constructed during a render pass and attached on
        the next one; calling stop/pause in that window raised
        ``Control must be added to the page first`` in the log.

        ``Control.page`` raises RuntimeError (not AttributeError) when
        unmounted, so a bare ``getattr(ctrl, "page")`` check crashes the
        guard itself — catch both.
        """
        if ctrl is None:
            return False
        try:
            _ = ctrl.page  # type: ignore[attr-defined]
            return True
        except (RuntimeError, AttributeError):
            return False

    def _set_compare(target: str) -> None:
        if target == compare:
            return
        # Re-tapping the already-selected segment yields an empty `selected`
        # set on the Dart side — bail rather than raising StopIteration here
        # and surfacing as an Unhandled Flet error.
        if not target:
            return
        set_compare(target)
        v = video_ref.current
        if not _is_mounted(v):
            return
        idx = 1 if target == "original" else 0

        async def _jump():
            try:
                await v.jump_to(idx)
            except IndexError as exc:
                logger.debug("jump_to(%s) out of range: %s", idx, exc)
            except Exception as exc:
                logger.warning("A/B preview switch failed: %s", exc)

        page.run_task(_jump)

    def _stop_video_player() -> None:
        v = video_ref.current
        video_ref.current = None  # job change must rebuild — a stopped stale
        # player kept in the ref made the next job show the previous output
        if not _is_mounted(v):
            return

        async def _stop():
            try:
                await v.stop()
            except Exception as exc:
                logger.warning("Preview stop failed: %s", exc)

        page.run_task(_stop)

    def _release_audio() -> None:
        a = audio_ref.current
        if a is None:
            return
        audio_ref.current = None

        async def _release():
            try:
                await a.release()
            except Exception as exc:
                logger.warning("Audio release failed: %s", exc)
            finally:
                if a in page.services:
                    page.services.remove(a)

        page.run_task(_release)

    def _on_audio_state(e) -> None:
        next_state = getattr(e, "state", AudioState.STOPPED)
        audio_state_ref.current = next_state
        set_playing(next_state == AudioState.PLAYING)
        if next_state == AudioState.COMPLETED:
            # Keep the slider truthful when the native player reaches its end;
            # the next tap must start a fresh take rather than call resume().
            set_pos_ms(dur_ms)

    def _mount_players():
        # Job changed: clear the previous job's preview flags first so a stale
        # A/B choice, playing state or position can't leak into the new result.
        set_compare("output")
        set_playing(False)
        audio_state_ref.current = AudioState.STOPPED
        set_pos_ms(0)
        set_dur_ms(0)
        # Back to False first: True→True is a no-op for the render scheduler,
        # which left the new player hidden behind the "Preparing preview" spinner.
        set_players_ready(False)
        if job is None or not job.output_path:
            return None
        out_p = Path(job.output_path)
        if not out_p.is_file():
            return None
        suffix = out_p.suffix.lower()

        if suffix in _VIDEO_EXTS and _HAS_VIDEO and video_ref.current is None:
            try:
                playlist = [ftv.VideoMedia(str(out_p))]
                if job.input_path and Path(job.input_path).exists():
                    playlist.append(ftv.VideoMedia(job.input_path))
                # A/B compare only makes sense with two items; the
                # SegmentedButton guards jump_to(1), but don't crash if
                # the playlist ever lands here as length 1 anyway.
                if len(playlist) > 1:
                    video_ref.current = ftv.Video(
                        playlist=playlist,
                        autoplay=False,
                        filter_quality=ft.FilterQuality.MEDIUM,
                        on_error=lambda e: logger.warning(
                            "Preview error: %s", getattr(e, "data", e)
                        ),
                    )
                else:
                    video_ref.current = ftv.Video(
                        playlist=playlist,
                        autoplay=False,
                        filter_quality=ft.FilterQuality.MEDIUM,
                        on_error=lambda e: logger.warning(
                            "Preview error: %s", getattr(e, "data", e)
                        ),
                    )
            except Exception as exc:
                logger.warning("Preview construction failed: %s", exc)

        if suffix in _AUDIO_EXTS and _HAS_AUDIO_PLAYER and audio_ref.current is None:
            try:
                player = Audio(
                    src=str(out_p),
                    release_mode=ReleaseMode.STOP,
                    # e.state is an AudioState ENUM — compare the enum and keep
                    # the terminal COMPLETED state for replay decisions.
                    on_state_change=_on_audio_state,
                    on_position_change=lambda e: (
                        set_pos_ms(int(getattr(e, "position", 0) or 0))
                        if not dragging_ref.current
                        else None
                    ),
                    on_duration_change=lambda e: (
                        set_dur_ms(int(e.duration.in_milliseconds))
                        if getattr(e, "duration", None) is not None
                        else None
                    ),
                )
                page.services.append(player)
                audio_ref.current = player
            except Exception as exc:
                logger.warning("Audio player construction failed: %s", exc)

        set_players_ready(True)
        return None

    ft.use_effect(
        _mount_players,
        [job.id if job else ""],
        cleanup=lambda: (_stop_video_player(), _release_audio()),
    )

    # Guard order matters: Path("") resolves to the CWD (which exists) and
    # Path(None) raises — an empty/None output path must bail before either.
    if not job or not job.output_path or not Path(job.output_path).exists():
        return ft.ListView(
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            on_click=lambda _: ctrl.navigate("dashboard"),
                        ),
                        ft.Text("Job Results", size=FONT_LG, weight=ft.FontWeight.BOLD),
                    ],
                ),
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=48, color=muted),
                            ft.Text(
                                "No Completed Job Active", size=FONT_MD, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text(
                                "Run any conversion or export to view processed media output.",
                                size=FONT_SM,
                                color=muted,
                            ),
                            ft.FilledButton(
                                "Go to Home", on_click=lambda _: ctrl.navigate("dashboard")
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=SPACE_MD,
                    ),
                    padding=SPACE_LG,
                    is_dark=is_dark,
                ),
            ],
            spacing=SPACE_MD,
            expand=True,
        )

    out_path = job.output_path
    out_name = Path(out_path).name

    orig_size = job.original_size_bytes
    out_size = Path(out_path).stat().st_size if Path(out_path).exists() else job.output_size_bytes

    size_saved_str = ""
    if orig_size > 0 and out_size > 0:
        delta = orig_size - out_size
        pct = (delta / orig_size) * 100
        if delta > 0:
            size_saved_str = f"Reduced by {format_bytes(delta)} ({pct:.1f}% smaller)"
        elif delta < 0:
            size_saved_str = f"Increased by {format_bytes(abs(delta))}"

    # Determine preview player based on extension
    is_video = out_path.lower().endswith(_VIDEO_EXTS)
    is_image = out_path.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))
    # Same condition _mount_players uses to append the Original to the playlist
    has_orig = bool(job.input_path and Path(job.input_path).exists())

    preview_control: ft.Control
    export_titles = {
        "extract_audio": "Audio Export Complete",
        "extract_subtitles": "Subtitles Extracted",
        "record": "Recording Ready",
    }
    export_title = export_titles.get(job.op, "Export Complete")
    export_icon = (
        ft.Icons.SUBTITLES_ROUNDED if job.op == "extract_subtitles" else ft.Icons.AUDIOTRACK_ROUNDED
    )
    if is_video and _HAS_VIDEO:
        video_control = video_ref.current
        preview_control = ft.Container(
            content=ft.Column(
                controls=[
                    *(
                        [video_control]
                        if video_control is not None
                        else [
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.ProgressRing(width=22, height=22),
                                        ft.Text(
                                            "Preparing preview…",
                                            size=FONT_SM,
                                            color=muted,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=SPACE_SM,
                                ),
                                alignment=ft.Alignment.CENTER,
                                height=200,
                            )
                        ]
                    ),
                    *(
                        [
                            ft.SegmentedButton(
                                selected=[compare],
                                segments=[
                                    ft.Segment(value="output", label=ft.Text("Output")),
                                    ft.Segment(value="original", label=ft.Text("Original")),
                                ],
                                on_change=lambda e: (
                                    _set_compare(next(iter(e.control.selected), compare))
                                    if getattr(e.control, "selected", None)
                                    else None
                                ),
                            )
                        ]
                        if has_orig  # single-item playlist: Original would doom jump_to(1)
                        else []
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=SPACE_SM,
            ),
            padding=SPACE_SM,
            border_radius=RADIUS_LG,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor="#000000",
        )
    elif is_image:
        preview_control = ft.Container(
            content=ft.Image(
                src=out_path,
                fit=ft.BoxFit.CONTAIN,
                height=240,
            ),
            alignment=ft.Alignment.CENTER,
            padding=SPACE_SM,
        )
    else:
        title_row = ft.Row(
            controls=[
                ft.Icon(export_icon, size=40, color=PRIMARY),
                ft.Column(
                    controls=[
                        ft.Text(export_title, size=FONT_MD, weight=ft.FontWeight.BOLD),
                        ft.Text(out_name, size=FONT_SM, color=muted),
                    ],
                    spacing=2,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=SPACE_MD,
        )

        audio_player: list[ft.Control] = []
        player = audio_ref.current
        if player is not None and players_ready:

            def _toggle_play(_e):
                async def _t():
                    try:
                        if playing:
                            await player.pause()
                        elif audio_state_ref.current == AudioState.COMPLETED:
                            await player.play()
                        elif pos_ms > 0:
                            await player.resume()
                        else:
                            await player.play()
                    except Exception as exc:
                        logger.warning("Playback control failed: %s", exc)

                page.run_task(_t)

            def _drag(e):
                dragging_ref.current = True
                set_pos_ms(int(e.control.value))

            def _seek_player(e):
                # Always release the drag guard here — a cancelled drag that
                # never fires on_change_end would mute position events forever.
                dragging_ref.current = False
                target = int(e.control.value)
                set_pos_ms(target)

                async def _seek():
                    try:
                        await player.seek(ft.Duration(milliseconds=target))
                    except Exception as exc:
                        logger.warning("Seek failed: %s", exc)

                page.run_task(_seek)

            audio_player = [
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.PAUSE_ROUNDED if playing else ft.Icons.PLAY_ARROW_ROUNDED,
                            icon_size=32,
                            on_click=_toggle_play,
                            tooltip="Play" if not playing else "Pause",
                        ),
                        # Until duration arrives, a 0..1 slider mis-seeks to 0
                        (
                            ft.Slider(
                                min=0.0,
                                max=float(dur_ms),
                                value=float(min(pos_ms, dur_ms)),
                                expand=True,
                                on_change=_drag,
                                on_change_end=_seek_player,
                            )
                            if dur_ms > 0
                            else ft.Container(expand=True)
                        ),
                    ],
                    spacing=SPACE_SM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        ft.Text(_fmt_ms(pos_ms), size=FONT_XS, color=muted),
                        ft.Text(_fmt_ms(dur_ms), size=FONT_XS, color=muted),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ]

        preview_control = ft.Container(
            content=ft.Column(
                controls=[title_row, *audio_player],
                spacing=SPACE_MD,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=SPACE_LG,
            bgcolor="#1E3E1C" if is_dark else "#E2F4E0",
            border_radius=RADIUS_LG,
        )

    return ft.ListView(
        controls=[
            # Header
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Processing Complete", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Preview Player Card
            preview_control,
            # Result Stats Card
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(
                                    "Output File",
                                    size=FONT_XS,
                                    color=muted,
                                    weight=ft.FontWeight.W_600,
                                ),
                                status_badge("COMPLETED", text_color=PRIMARY),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(
                            out_name,
                            size=FONT_MD,
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Divider(),
                        ft.Row(
                            controls=[
                                ft.Column(
                                    [
                                        ft.Text("ORIGINAL", size=FONT_XS, color=muted),
                                        ft.Text(
                                            format_bytes(orig_size),
                                            size=FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                    ]
                                ),
                                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=muted),
                                ft.Column(
                                    [
                                        ft.Text("FINAL SIZE", size=FONT_XS, color=PRIMARY),
                                        ft.Text(
                                            format_bytes(out_size),
                                            size=FONT_SM,
                                            weight=ft.FontWeight.BOLD,
                                            color=PRIMARY,
                                        ),
                                    ]
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_AROUND,
                        ),
                        *(
                            [
                                ft.Text(
                                    size_saved_str,
                                    size=FONT_SM,
                                    color=PRIMARY,
                                    text_align=ft.TextAlign.CENTER,
                                    weight=ft.FontWeight.W_500,
                                )
                            ]
                            if size_saved_str
                            else []
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
                padding=SPACE_LG,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Actions Row
            ft.Row(
                controls=[
                    ft.FilledButton(
                        "Save to Device",
                        icon=ft.Icons.DOWNLOAD_ROUNDED,
                        height=48,
                        expand=True,
                        on_click=lambda _: ctrl.save_result(job),
                    ),
                    ft.OutlinedButton(
                        "Share",
                        icon=ft.Icons.SHARE_ROUNDED,
                        height=48,
                        expand=True,
                        on_click=lambda _: ctrl.share_result(job),
                    ),
                ],
                spacing=SPACE_MD,
            ),
            ft.TextButton(
                "Return to Dashboard",
                icon=ft.Icons.HOME_ROUNDED,
                on_click=lambda _: ctrl.navigate("dashboard"),
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
