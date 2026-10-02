"""Video compressor screen for target-size limits and platform presets."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from components.tool_job_status import tool_job_row
from core.notify import ERROR, show_snack
from core.state import Job, use_app_state
from core.storage_paths import format_bytes, get_temp_dir, unique_temp_name
from core.styles import card_container, section_header
from core.theme import ACCENT_BLUE, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, FONT_XS, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


@ft.component
def CompressScreen() -> ft.Control:
    """Target-size constraint view with messaging presets (WhatsApp, Discord, Email)."""
    page = ft.context.page
    ctrl = use_controller()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    media_path = app_state.current_media_path
    info = app_state.current_media_info
    file_name = Path(media_path).name if media_path else "No file selected"
    orig_bytes = Path(media_path).stat().st_size if media_path and Path(media_path).exists() else 0
    orig_size_str = format_bytes(orig_bytes)
    # Compress is a VIDEO op (bitrate ladder + H.264/AAC encode): images and
    # audio-only files are refused with an explanation, not a confusing .mp4.
    media_kind = info.kind if info is not None else "video"
    kind_ok = media_kind == "video"
    duration_s = info.duration_s if info and info.duration_s > 0 else 10.0

    target_mb, set_target_mb = ft.use_state(16.0)  # Default 16MB (WhatsApp)

    # Encoder-empty guard mirrors Convert: without verified video encoders
    # Start would fail late in _pick_video_encoder instead of refusing here.
    probing = app_state.probe_info is None
    available_video = (
        list(app_state.probe_info.video_encoder_picks or []) if app_state.probe_info else []
    )

    # Live pipeline: derived from the queue, never a stuck local flag.
    running_job = (
        app_state.active_job if (app_state.active_job and app_state.active_job.is_running) else None
    )
    busy = running_job is not None

    # Preset sizes (MB)
    presets = [
        ("whatsapp", "WhatsApp (16 MB)", 16.0),
        ("discord", "Discord (25 MB)", 25.0),
        ("email", "Email (10 MB)", 10.0),
        ("small", "Ultra Small (5 MB)", 5.0),
    ]

    # Estimated split mirrors the engine (total minus audio headroom):
    # the old readout showed the TOTAL as video kbps (15-20% high at 5MB/60s).
    est_bits = target_mb * 8 * 1024 * 1024 * 0.92
    est_total = int(est_bits / duration_s)
    est_audio = min(128000, max(64000, int(est_total * 0.15)))
    est_video_kbps = max(0, (est_total - est_audio) // 1000)

    def _start_compression(_):
        if not media_path or busy:
            return
        if probing or not available_video:
            show_snack(
                page,
                "Still probing engine capabilities — try again in a moment.",
                bgcolor=ERROR,
            )
            return
        if not kind_ok:
            return

        out_name = unique_temp_name(f"{Path(media_path).stem}_compressed_{target_mb:.1f}MB", ".mp4")
        out_path = str(get_temp_dir() / out_name)

        job = Job(
            op="compress",
            input_path=media_path,
            output_path=out_path,
            params={"target_size_mb": float(target_mb)},
            original_size_bytes=orig_bytes,
        )
        ctrl.start_job(job)

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
                    ft.Text("Video Compressor", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Input file overview
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.COMPRESS_ROUNDED, size=32, color=ACCENT_BLUE),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    file_name,
                                    size=FONT_MD,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    (
                                        f"Current Size: {orig_size_str} • {duration_s:.1f}s"
                                        if info
                                        else f"Current Size: {orig_size_str}"
                                    ),
                                    size=FONT_SM,
                                    color=muted,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.OutlinedButton(
                            "Change", on_click=lambda _: ctrl.pick_media_for("compress")
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Live pipeline status (derived, never stuck)
            *([tool_job_row(running_job, ctrl, is_dark=is_dark)] if running_job else []),
            # Kind gate: compress needs a video timeline.
            *(
                [
                    card_container(
                        content=ft.Text(
                            "Compression needs a video file — images and audio-only "
                            "files have no video timeline to squeeze. Use Convert "
                            "for stills or Audio Studio for sound.",
                            size=FONT_SM,
                            color=muted,
                        ),
                        padding=SPACE_MD,
                        border_radius=RADIUS_LG,
                        is_dark=is_dark,
                    )
                ]
                if media_path and not kind_ok
                else []
            ),
            # Target Presets
            section_header("Destination Presets", "Quick target size limits", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(label),
                        selected=abs(target_mb - val) < 0.1,
                        on_click=lambda _, v=val: set_target_mb(v),
                    )
                    for _, label, val in presets
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Target Size Slider (0.1 MB steps — the old 78 divisions made the
            # round(…,1) a lie at exactly 1.0 MB granularity).
            section_header(
                "Custom Target Size",
                f"Maximum file size: {target_mb:.1f} MB (≈ {est_video_kbps} kbps video + audio)",
                is_dark=is_dark,
            ),
            ft.Slider(
                value=float(target_mb),
                min=2.0,
                max=80.0,
                divisions=780,
                on_change=lambda e: set_target_mb(round(float(e.control.value), 1)),
            ),
            # Efficiency readout card
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=18, color=ACCENT_BLUE),
                                ft.Text(
                                    "Estimated Reduction", size=FONT_SM, weight=ft.FontWeight.W_600
                                ),
                            ],
                            spacing=SPACE_SM,
                        ),
                        ft.Text(
                            f"Original: {orig_size_str} → Target: ≤ {target_mb:.1f} MB "
                            "(decimal MB vs platform quotas).\n"
                            "Below ~1 Mbps the engine downscales to 720p, below "
                            "~400 kbps to 480p; always H.264/AAC, preset fast, "
                            "~8% container headroom.",
                            size=FONT_XS,
                            color=muted,
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
                padding=SPACE_MD,
                is_dark=is_dark,
            ),
            # Action button — gated on probe + encoder-empty + kind (Convert parity).
            *(
                [
                    ft.Row(
                        controls=[
                            ft.ProgressRing(width=22, height=22),
                            ft.Text(
                                "Probing engine capabilities…",
                                size=FONT_XS,
                                color=muted,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=SPACE_SM,
                    )
                ]
                if probing
                else []
            ),
            ft.FilledButton(
                f"Compress to ≤ {target_mb:.1f} MB",
                icon=ft.Icons.CHECK_ROUNDED,
                height=48,
                disabled=not media_path or busy or probing or not available_video or not kind_ok,
                on_click=_start_compression,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
