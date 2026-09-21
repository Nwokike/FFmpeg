"""Video compressor screen for target-size limits and platform presets."""

from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from core.state import Job, state
from core.storage_paths import format_bytes, get_temp_dir
from core.styles import card_container, section_header
from core.theme import ACCENT_BLUE, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, FONT_XS, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


@ft.component
def CompressScreen() -> ft.Control:
    """Target-size constraint view with messaging presets (WhatsApp, Discord, Email)."""
    page = ft.context.page
    ctrl = use_controller()
    is_dark = is_dark_mode(page)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    media_path = state.current_media_path
    info = state.current_media_info
    file_name = Path(media_path).name if media_path else "No file selected"
    orig_bytes = Path(media_path).stat().st_size if media_path and os.path.exists(media_path) else 0
    orig_size_str = format_bytes(orig_bytes)
    duration_s = info.duration_s if info and info.duration_s > 0 else 10.0

    target_mb, set_target_mb = ft.use_state(16.0)  # Default 16MB (WhatsApp)
    is_processing, set_is_processing = ft.use_state(False)

    # Preset sizes (MB)
    presets = [
        ("whatsapp", "WhatsApp (16 MB)", 16.0),
        ("discord", "Discord (25 MB)", 25.0),
        ("email", "Email (10 MB)", 10.0),
        ("small", "Ultra Small (5 MB)", 5.0),
    ]

    # Calculate estimated bitrate
    est_bits = target_mb * 8 * 1024 * 1024 * 0.92
    est_kbps = int((est_bits / duration_s) / 1000)

    def _start_compression(_):
        if not media_path:
            return
        set_is_processing(True)

        out_name = f"{Path(media_path).stem}_compressed_{int(target_mb)}MB.mp4"
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
                                    f"Current Size: {orig_size_str} • {duration_s:.1f}s",
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
            # Target Presets
            section_header("Destination Presets", "Quick target size limits", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(label),
                        selected=abs(target_mb - val) < 0.1,
                        on_select=lambda _, v=val: set_target_mb(v),
                    )
                    for _, label, val in presets
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Target Size Slider
            section_header(
                "Custom Target Size",
                f"Maximum file size: {target_mb:.1f} MB (≈ {est_kbps} kbps)",
                is_dark=is_dark,
            ),
            ft.Slider(
                value=float(target_mb),
                min=2.0,
                max=80.0,
                divisions=78,
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
                            f"Original: {orig_size_str} → Target: ≤ {target_mb:.1f} MB.\n"
                            f"Resolution will be dynamically scaled if necessary to maintain sharp visual clarity.",
                            size=FONT_XS,
                            color=muted,
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
                padding=SPACE_MD,
                is_dark=is_dark,
            ),
            # Action button
            ft.FilledButton(
                f"Compress to ≤ {target_mb:.1f} MB",
                icon=ft.Icons.CHECK_ROUNDED,
                height=48,
                disabled=not media_path or is_processing,
                on_click=_start_compression,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
