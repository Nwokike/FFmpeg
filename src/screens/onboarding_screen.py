"""Onboarding intro deck with terms acceptance and quick-start actions."""

from __future__ import annotations

import flet as ft

from core.assets import app_icon_svg
from core.state import use_app_state
from core.theme import PRIMARY, PRIMARY_DARK, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import (
    FONT_2XL,
    FONT_MD,
    FONT_SM,
    ICON_HERO,
    RADIUS_FULL,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
)
from state.controller_ctx import use_controller

_SLIDES = [
    (
        "icon.svg",
        True,
        "Welcome to FFmpeg",
        "The complete, uncompromised power of FFmpeg 8 running directly on your phone. Ultra-fast, on-device processing.",
    ),
    (
        ft.Icons.AUTO_AWESOME_ROUNDED,
        False,
        "Every Tool You Need",
        "Convert any video or audio, compress for messaging apps, trim with frame-accuracy, extract tracks & GIFs, and normalize audio.",
    ),
    (
        ft.Icons.SHIELD_ROUNDED,
        False,
        "Private & Sovereign",
        "Your media files and processed outputs never leave your device — all conversion and editing happens on-device.",
    ),
]


@ft.component
def OnboardingScreen() -> ft.Control:
    """Three-step onboarding slide presentation."""
    page = ft.context.page
    ctrl = use_controller()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    slide_idx, set_slide_idx = ft.use_state(0)
    accepted_terms, set_accepted_terms = ft.use_state(False)

    icon_src, is_image, title, description = _SLIDES[slide_idx]

    def _next(_=None):
        if slide_idx < len(_SLIDES) - 1:
            set_slide_idx(slide_idx + 1)
        else:
            ctrl.finish_onboarding()

    def _on_drag(e: ft.DragEndEvent):
        if e.primary_velocity is not None:
            if e.primary_velocity < -200 and slide_idx < len(_SLIDES) - 1:
                set_slide_idx(slide_idx + 1)
            elif e.primary_velocity > 200 and slide_idx > 0:
                set_slide_idx(slide_idx - 1)

    dots = [
        ft.Container(
            width=24 if i == slide_idx else 8,
            height=8,
            border_radius=RADIUS_FULL,
            bgcolor=PRIMARY if i == slide_idx else ("#2A2E35" if is_dark else "#D1D5DB"),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        for i in range(len(_SLIDES))
    ]

    is_last = slide_idx == len(_SLIDES) - 1

    # Hero: first slide shows your real FFmpeg icon.svg, others show themed icons
    if is_image:
        hero_content = ft.Image(
            src=app_icon_svg(),
            width=ICON_HERO * 2.2,
            height=ICON_HERO * 2.2,
            fit=ft.BoxFit.CONTAIN,
            color=ft.Colors.WHITE if is_dark else PRIMARY_DARK,
            color_blend_mode=ft.BlendMode.SRC_IN,
        )
    else:
        hero_content = ft.Icon(icon_src, size=ICON_HERO * 1.5, color=PRIMARY)

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(),
                        *(
                            [ft.TextButton("Skip", on_click=lambda _: ctrl.finish_onboarding())]
                            if not is_last
                            else []
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.GestureDetector(
                    on_horizontal_drag_end=_on_drag,
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Container(
                                    content=hero_content,
                                    padding=SPACE_XL,
                                    border_radius=RADIUS_FULL,
                                    bgcolor="#1E3E1C" if is_dark else "#E2F4E0",
                                ),
                                ft.Text(
                                    title,
                                    size=FONT_2XL,
                                    weight=ft.FontWeight.BOLD,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    description,
                                    size=FONT_MD,
                                    color=muted,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=SPACE_LG,
                        ),
                        alignment=ft.Alignment.CENTER,
                        padding=ft.Padding.symmetric(vertical=SPACE_XL),
                    ),
                    expand=True,
                ),
                ft.Row(controls=dots, alignment=ft.MainAxisAlignment.CENTER, spacing=SPACE_SM),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            *(
                                [
                                    ft.Row(
                                        controls=[
                                            ft.Checkbox(
                                                value=accepted_terms,
                                                on_change=lambda e: set_accepted_terms(
                                                    e.control.value
                                                ),
                                            ),
                                            ft.Text(
                                                "I agree to local processing terms", size=FONT_SM
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        spacing=SPACE_SM,
                                    )
                                ]
                                if is_last
                                else []
                            ),
                            ft.FilledButton(
                                "Get Started" if is_last else "Continue",
                                on_click=_next,
                                disabled=is_last and not accepted_terms,
                                height=48,
                                width=320,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=SPACE_MD,
                    ),
                    padding=ft.Padding.only(bottom=SPACE_LG),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            expand=True,
        ),
        padding=SPACE_LG,
        expand=True,
    )
