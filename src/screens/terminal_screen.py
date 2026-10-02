"""Expert Terminal — typed ffmpeg command lines → validated plan → queued job.

Two-step confirm (parse → review plan + notes → Run) because command mode must
never silently approximate: every approximation note lands in the pane before
the job enqueues. The AI-mode chip is VISIBLE but LOCKED per the owner's
credits model — it unlocks with the Kiri Router credit rollout (premium x10),
never dead-ends silently.
"""

from __future__ import annotations

import logging

import flet as ft

from core.notify import ERROR, SUCCESS, show_snack
from core.state import Job, use_app_state
from core.styles import card_container, section_header
from core.theme import ACCENT_AMBER, PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, RADIUS_MD, SPACE_LG, SPACE_MD, SPACE_SM
from services.command_parser import CommandError, OpPlan, help_text, parse_command, tokenize
from state.controller_ctx import use_controller
from state.service_ctx import use_services

logger = logging.getLogger("TerminalScreen")

_LEVEL_COLORS = {
    "err": ERROR,
    "note": ACCENT_AMBER,
    "plan": PRIMARY,
    "ok": SUCCESS,
    "in": "#9CA3AF",
    "info": "#9CA3AF",
}


@ft.component
def TerminalScreen() -> ft.Control:
    """Command line for the engine's supported ffmpeg subset + plan confirm."""
    page = ft.context.page
    ctrl = use_controller()
    services = use_services()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    command, set_command = ft.use_state("")
    lines, set_lines = ft.use_state(())
    history, set_history = ft.use_state(())
    pending, set_pending = ft.use_state(None)  # OpPlan awaiting confirmation

    def _help(_=None) -> None:
        set_lines((*lines, ("info", help_text())))

    def _ai_locked(_=None) -> None:
        show_snack(
            page,
            "AI mode unlocks with Kiri Router credits — premium multiplies "
            "them x10. Arriving with the credits rollout (Settings → About).",
            bgcolor=ACCENT_AMBER,
            duration_ms=5000,
        )

    def _use_history(cmd: str) -> None:
        set_command(cmd)

    def _submit(_=None) -> None:
        cmd = command.strip()
        if not cmd:
            show_snack(page, "Type a command first — ? shows the accepted flags", bgcolor=ERROR)
            return
        if pending is not None:
            show_snack(page, "Confirm or discard the pending plan first", bgcolor=ACCENT_AMBER)
            return

        entry: list[tuple[str, str]] = [("in", f"$ {cmd}")]

        # Pre-probe only when a trim needs an end boundary (parser refuses
        # without it) — one header read, engine-side failures stay loud.
        # Tokenizer-based (not substring): a filename containing "-ss" must
        # not trigger a probe, and single-quoted / multi-input commands must
        # resolve every input. tokenize() refuses bad quoting loudly already.
        duration: float | None = None
        try:
            probe_tokens = tokenize(cmd)
        except CommandError:
            probe_tokens = []
        probe_inputs = [
            probe_tokens[k + 1] for k in range(len(probe_tokens) - 1) if probe_tokens[k] == "-i"
        ]
        has_ss = "-ss" in probe_tokens
        has_end = "-t" in probe_tokens or "-to" in probe_tokens
        if probe_inputs and has_ss and not has_end:
            src = probe_inputs[0]
            try:
                duration = float(services.engine.probe(src).duration_s)
            except Exception as exc:  # engine raises loud; keep parsing honest
                logger.warning("Terminal pre-probe failed for %s: %s", src, exc)
                entry.append(("err", f"probe failed: {exc}"))

        try:
            plan = parse_command(cmd, duration_s=duration)
        except CommandError as exc:
            # _refuse already logged at WARNING — surface the same text here.
            entry.append(("err", str(exc)))
            set_lines(lines + tuple(entry))
            return

        entry.append(("plan", f"plan → {plan.summary()}"))
        entry.extend(("note", f"note: {note}") for note in plan.notes)
        entry.append(("info", "Review the plan, then Run or Discard below."))
        set_lines(lines + tuple(entry))
        set_pending(plan)
        history_cmd = cmd
        set_history((history_cmd, *tuple(h for h in history if h != history_cmd))[:8])

    def _confirm(_=None) -> None:
        plan: OpPlan = pending
        ctrl.start_job(
            Job(
                op=plan.op,
                input_path=plan.input_path,
                output_path=plan.output_path,
                params=dict(plan.params),
            )
        )
        set_lines((*lines, ("ok", f"queued: {plan.op} → {plan.output_path}")))
        set_pending(None)
        set_command("")

    def _discard(_=None) -> None:
        set_lines((*lines, ("note", "plan discarded")))
        set_pending(None)

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            # Back row (upgraded to the unified header in the header sweep)
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Expert Terminal", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Engine truth banner + mode switch + help
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=24, color=PRIMARY),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "ffmpeg (subset)",
                                            size=FONT_MD,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                        ft.Text(
                                            "pyav-18.1.0 — FFmpeg libraries, no binary",
                                            size=FONT_SM,
                                            color=muted,
                                        ),
                                    ],
                                    spacing=0,
                                ),
                                ft.Container(expand=True),
                                ft.IconButton(
                                    icon=ft.Icons.HELP_OUTLINE_ROUNDED,
                                    tooltip="Accepted flags (ffmpeg -h)",
                                    on_click=_help,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            controls=[
                                ft.TextButton(
                                    "Expert",
                                    icon=ft.Icons.TERMINAL_ROUNDED,
                                    style=ft.ButtonStyle(
                                        bgcolor=ft.Colors.with_opacity(0.15, PRIMARY),
                                        # Positional binds to `side`, not `radius`
                                        shape=ft.RoundedRectangleBorder(radius=RADIUS_MD),
                                    ),
                                ),
                                ft.TextButton(
                                    "AI — locked",
                                    icon=ft.Icons.LOCK_ROUNDED,
                                    tooltip="Credits rollout (Kiri Router)",
                                    on_click=_ai_locked,
                                ),
                            ],
                            spacing=SPACE_SM,
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
            ),
            section_header(
                "Command", "classic ffmpeg syntax, engine-verified subset", is_dark=is_dark
            ),
            ft.Row(
                controls=[
                    ft.TextField(
                        value=command,
                        on_change=lambda e: set_command(e.control.value or ""),
                        hint_text="ffmpeg -i in.mp4 -c:v libx264 -crf 23 out.mp4",
                        dense=True,
                        expand=True,
                    ),
                    ft.FilledButton("Run", icon=ft.Icons.PLAY_ARROW_ROUNDED, on_click=_submit),
                ],
                spacing=SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            *(
                [
                    card_container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.RULE_ROUNDED, color=ACCENT_AMBER, size=20),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "Plan ready — review before running",
                                            size=FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                        ft.Text(
                                            pending.summary(),
                                            size=FONT_SM,
                                            color=muted,
                                        ),
                                    ],
                                    spacing=0,
                                    expand=True,
                                ),
                                ft.FilledButton("Run plan", on_click=_confirm),
                                ft.TextButton("Discard", on_click=_discard),
                            ],
                            spacing=SPACE_SM,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        )
                    )
                ]
                if pending is not None
                else []
            ),
            section_header("Output", "engine stdout/stderr + plan notes", is_dark=is_dark),
            ft.Container(
                height=280,
                border_radius=RADIUS_MD,
                bgcolor="#0D0D0D" if is_dark else "#101418",
                padding=ft.Padding(SPACE_MD, SPACE_MD, SPACE_MD, SPACE_MD),
                content=ft.ListView(
                    controls=[
                        ft.Text(
                            text,
                            size=FONT_SM - 1,
                            font_family="Roboto Mono",
                            color=_LEVEL_COLORS.get(level, muted),
                            selectable=True,
                        )
                        for level, text in lines
                    ],
                    spacing=2,
                    auto_scroll=True,
                ),
            ),
            *(
                [
                    section_header("Recent", "tap to reload a command", is_dark=is_dark),
                    *[
                        ft.TextButton(
                            cmd,
                            icon=ft.Icons.HISTORY_ROUNDED,
                            on_click=lambda _, c=cmd: _use_history(c),
                        )
                        for cmd in history
                    ],
                ]
                if history
                else []
            ),
        ],
        spacing=SPACE_LG,
        expand=True,
    )


__all__ = ["TerminalScreen"]
