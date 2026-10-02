"""Honesty pins: words in src/ must match behavior.

M4 removed cross-repo attributions, unmeasured speed claims, stale version
pins, and hardcoded palette dupes. These tests fail the build if any of
those classes creep back. Docs (swarm-audit archive) and changelog history
are allow-listed: they record what WAS, not what IS.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _src_text() -> dict[str, str]:
    return {
        str(p.relative_to(ROOT)): p.read_text(encoding="utf-8")
        for p in SRC.rglob("*.py")
        if "__pycache__" not in p.parts
    }


def test_no_sherlock_attributions_in_src():
    offenders = [f for f, t in _src_text().items() if "sherlock" in t.lower()]
    assert offenders == [], f"cross-repo attributions crept back: {offenders}"


def test_no_stale_flet_version_pins_in_src():
    offenders = [f for f, t in _src_text().items() if "1.0.1" in t]
    assert offenders == [], f"stale version pins: {offenders}"


def test_no_unmeasured_speed_claims_in_src():
    offenders = []
    for f, t in _src_text().items():
        low = t.lower()
        if "ultra-fast" in low or "ultra fast" in low or "uncompromised" in low:
            offenders.append(f)
        for m in re.finditer(r"\binstant\b", low):
            # "instant Share sheet" (OS sheet speed) and code identifiers are
            # out of scope; product-speed claims ("instant lossless/cut") are not.
            line = low[max(0, m.start() - 60) : m.end() + 40]
            if "share sheet" not in line and "instantly" not in line:
                offenders.append(f"{f}: ...{line.strip()}...")
                break
    assert offenders == [], f"unmeasured speed claims: {offenders}"


def test_version_helpers_return_live_strings():
    from core.versions import ffmpeg_version, pyav_major, pyav_version

    assert pyav_version() and ffmpeg_version() and pyav_major()
    assert pyav_major().isdigit(), "short label must be a bare major number"


def test_no_hardcoded_engine_numerals_in_screens():
    # Changelog history + versions.py fallbacks/docstrings are allow-listed:
    # history is literal by design, fallbacks name the last-known-good wheel.
    allowed = {"changelog.py", "versions.py"}
    offenders = []
    for f, t in _src_text().items():
        if Path(f).name in allowed:
            continue
        if "PyAV 18" in t or "FFmpeg 8" in t:
            offenders.append(f)
    assert offenders == [], f"use core.versions helpers instead: {offenders}"


def test_no_raw_brand_hex_outside_constants_and_theme():
    offenders = []
    for f, t in _src_text().items():
        norm = f.replace("\\", "/")
        if norm.endswith("core/constants.py") or norm.endswith("core/theme.py"):
            continue
        offenders.extend(
            f"{f}: {m.group(0)}"
            for m in re.finditer(
                r"#(?:3[Cc]8038|0[Ff]1114|1[Ee]3[Ee]1[Cc]|E2F4E0|242930|E5E7EB)\b", t
            )
        )
    assert offenders == [], f"import palette from constants/theme: {offenders}"


def test_op_titles_stay_single_sourced():
    from core.constants import OP_LABELS, op_title

    for op, label in OP_LABELS.items():
        assert op_title(op) == label
    # Drift guards: the pairs that diverged before M3.
    assert op_title("concat") == op_title("join") == "Join"
    assert op_title("record") == "Recording"
