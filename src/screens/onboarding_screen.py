"""Onboarding intro deck with terms acceptance and quick-start actions.

Terms consent is explicit: the ONLY path into the app is the checked
"Get Started" button on the last slide. There is deliberately no Skip —
a skipped consent is not a consent, and persisting terms_accepted for a
user who never saw the checkbox would be a legal defect, not UX.
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from core.assets import app_icon_svg
from core.state import use_app_state
from core.theme import (
    PRIMARY,
    PRIMARY_CONTAINER_DARK,
    PRIMARY_CONTAINER_LIGHT,
    PRIMARY_DARK,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
    is_dark_mode,
)
from core.tokens import (
    FONT_2XL,
    FONT_MD,
    ICON_HERO,
    RADIUS_FULL,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
)
from state.controller_ctx import use_controller


@dataclass(frozen=True)
class _Slide:
    """One deck card: brand art on the first slide, themed icon after."""

    title: str
    description: str
    icon: ft.IconData | None = None  # None → render the app icon SVG


_SLIDES = (
    _Slide(
        title="Welcome to FFmpeg",
        description=(
            "FFmpeg running on-device: convert, compress, trim, extract, "
            "and normalize without uploading anything."
        ),
        icon=None,
    ),
    _Slide(
        title="Every Tool You Need",
        description="Convert any video or audio, compress for messaging apps, trim with frame-accuracy, extract tracks & GIFs, and normalize audio.",
        icon=ft.Icons.AUTO_AWESOME_ROUNDED,
    ),
    _Slide(
        title="Private & Sovereign",
        description="Your media files and processed outputs never leave your device — all conversion and editing happens on-device.",
        icon=ft.Icons.SHIELD_ROUNDED,
    ),
)

# Slow drags still turn the page: 60 px/s is a deliberate swipe, not noise.
_SWIPE_VELOCITY_PX_S = 60.0


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

    slide = _SLIDES[slide_idx]

    def _next(_=None):
        if slide_idx < len(_SLIDES) - 1:
            set_slide_idx(slide_idx + 1)
        else:
            ctrl.finish_onboarding()

    def _back(_=None):
        if slide_idx > 0:
            set_slide_idx(slide_idx - 1)

    def _on_drag(e: ft.DragEndEvent):
        if e.primary_velocity is not None:
            if e.primary_velocity < -_SWIPE_VELOCITY_PX_S and slide_idx < len(_SLIDES) - 1:
                set_slide_idx(slide_idx + 1)
            elif e.primary_velocity > _SWIPE_VELOCITY_PX_S and slide_idx > 0:
                set_slide_idx(slide_idx - 1)

    dots = [
        ft.Container(
            key=f"onboarding-dot-{i}",
            width=24 if i == slide_idx else 8,
            height=8,
            border_radius=RADIUS_FULL,
            bgcolor=PRIMARY if i == slide_idx else ("#2A2E35" if is_dark else "#D1D5DB"),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            on_click=lambda _, i=i: set_slide_idx(i),
        )
        for i in range(len(_SLIDES))
    ]

    is_last = slide_idx == len(_SLIDES) - 1

    if slide.icon is None:
        hero_content = ft.Image(
            src=app_icon_svg(),
            width=ICON_HERO * 2.2,
            height=ICON_HERO * 2.2,
            fit=ft.BoxFit.CONTAIN,
            color=ft.Colors.WHITE if is_dark else PRIMARY_DARK,
            color_blend_mode=ft.BlendMode.SRC_IN,
            semantics_label="FFmpeg app icon",
        )
    else:
        hero_content = ft.Icon(
            slide.icon, size=ICON_HERO * 1.5, color=PRIMARY, semantics_label=slide.title
        )

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.GestureDetector(
                    on_horizontal_drag_end=_on_drag,
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Container(
                                    content=hero_content,
                                    padding=SPACE_XL,
                                    border_radius=RADIUS_FULL,
                                    bgcolor=PRIMARY_CONTAINER_DARK
                                    if is_dark
                                    else PRIMARY_CONTAINER_LIGHT,
                                ),
                                ft.Text(
                                    slide.title,
                                    size=FONT_2XL,
                                    weight=ft.FontWeight.BOLD,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    slide.description,
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
                ft.Row(
                    controls=[
                        *(
                            [
                                ft.TextButton(
                                    "Back",
                                    on_click=_back,
                                    visible=slide_idx > 0,
                                )
                            ]
                            if not is_last
                            else []
                        ),
                        ft.Row(
                            controls=dots,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=SPACE_SM,
                            expand=True,
                        ),
                        ft.Container(width=64, visible=slide_idx > 0 and not is_last),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            *(
                                [
                                    ft.Checkbox(
                                        label="I agree to local processing terms",
                                        value=accepted_terms,
                                        on_change=lambda e: set_accepted_terms(e.control.value),
                                    )
                                ]
                                if is_last
                                else []
                            ),
                            ft.Container(
                                content=ft.FilledButton(
                                    "Get Started" if is_last else "Continue",
                                    on_click=_next,
                                    disabled=is_last and not accepted_terms,
                                    height=48,
                                    expand=True,
                                ),
                                width=420,
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
            # The deck must scroll, not overflow: large fonts, short heights,
            # and landscape would otherwise throw a render overflow on the
            # very first screen a user ever sees.
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=SPACE_LG,
        expand=True,
    )
