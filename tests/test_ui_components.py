"""Studio component kit: construct without a page, honor selection + facts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import flet as ft  # noqa: E402

from components.studio import chip_group, media_summary_card, screen_header  # noqa: E402


def test_chip_group_marks_only_the_selected_option():
    picked: list = []
    row = chip_group(["MP4", "MKV", "WEBM"], value="MKV", on_change=picked.append)
    chips = [c for c in row.controls if isinstance(c, ft.Chip)]
    assert [c.selected for c in chips] == [False, True, False]
    chips[2].on_select(None)
    assert picked == ["WEBM"]


def test_chip_group_accepts_label_value_pairs():
    row = chip_group([("High", 1080), ("Low", 480)], value=480, on_change=lambda _v: None)
    chips = [c for c in row.controls if isinstance(c, ft.Chip)]
    assert chips[1].selected is True


def test_screen_header_has_back_only_when_asked():
    assert any(
        isinstance(c, ft.IconButton)
        for c in screen_header("Title", on_back=lambda: None).content.controls
    )
    assert not any(isinstance(c, ft.IconButton) for c in screen_header("Title").content.controls)


def test_media_summary_card_without_media_renders_a_placeholder():
    card = media_summary_card(None)
    row = card.content
    text = next(t for t in row.controls if isinstance(t, ft.Column)).controls[0]
    assert text.value == "No media selected"
