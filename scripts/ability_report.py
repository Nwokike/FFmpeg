#!/usr/bin/env python3
"""Run the ability matrix and render ``docs/ability-matrix.md`` from the results.

    uv run python scripts/ability_report.py            # full matrix, then report
    uv run python scripts/ability_report.py --no-run   # re-render from a saved XML

The matrix is ``tests/test_ability_matrix.py`` (marker ``live``): one test id per
ability, each verified by probing its own output. The report is the gate you read
before the phone pass — anything not green here is not green on a phone either.

Exit code: 0 when every ability passed, 1 when anything failed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "ability-matrix.md"
MARKER = "ability-matrix"

# Group tests by their matrix section for readable tables.
SECTIONS = [
    ("Video encoders", "test_video_encoder"),
    ("Audio encoders", "test_audio_encoder"),
    ("Muxers", "test_muxer"),
    ("Containers", "test_container"),
    ("Filters", "test_filter"),
    ("Extract targets", "test_extract"),
    ("Tools", "test_tool_"),
    ("Probe truth", "test_probe"),
    ("Options reach encoders", "test_video_encoder_option_applies"),
    ("Self-test & job shape", "test_engine_self_test"),
]


def run_matrix(xml_path: Path) -> int:
    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "-m",
            "live",
            "tests/test_ability_matrix.py",
            "--junit-xml",
            str(xml_path),
            "--tb=no",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
    )
    return result.returncode


def parse(xml_path: Path) -> list[dict]:
    tree = ET.parse(xml_path)
    cases: list[dict] = []
    for suite in tree.getroot().iter("testsuite"):
        for case in suite.iter("testcase"):
            entry = {
                "name": str(case.get("name")),
                "class": str(case.get("classname")),
                "status": "passed",
                "message": "",
            }
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            if failure is not None:
                entry["status"] = "failed"
                entry["message"] = (failure.get("message") or failure.text or "").strip()
            elif error is not None:
                entry["status"] = "failed"
                entry["message"] = (error.get("message") or error.text or "").strip()
            elif skipped is not None:
                entry["status"] = "skipped"
                entry["message"] = (skipped.get("message") or skipped.text or "").strip()
            cases.append(entry)
    return cases


def wheel_identity() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    import av

    from core.engine_probe import _ffmpeg_build_identity

    return f"av {av.__version__} · FFmpeg {getattr(av, 'ffmpeg_version_info', '?')} · build {_ffmpeg_build_identity()}"


def render(cases: list[dict]) -> str:
    total = len(cases)
    passed = sum(1 for c in cases if c["status"] == "passed")
    failed = [c for c in cases if c["status"] == "failed"]
    skipped = [c for c in cases if c["status"] == "skipped"]

    lines = [
        "# Ability matrix",
        "",
        f"_Wheel: {wheel_identity()} · generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC} · "
        f"{passed}/{total} abilities green, {len(failed)} failed, {len(skipped)} skipped_",
        "",
        "One row per ability; the test id is the ability. Run `uv run python "
        "scripts/ability_report.py` to regenerate.",
        "",
    ]
    if failed:
        lines += ["## Failures", ""]
        causes: dict[str, list[str]] = defaultdict(list)
        for case in failed:
            first_line = (case["message"] or "no message").splitlines()[0][:160]
            causes[first_line].append(case["name"])
        for cause, names in sorted(causes.items(), key=lambda kv: -len(kv[1])):
            lines += [
                f"- **{cause}** — {len(names)} ability(ies): "
                + ", ".join(f"`{n}`" for n in names[:8])
                + (" …" if len(names) > 8 else "")
            ]
        lines += ["", "| Ability | Error |", "|---|---|"]
        for case in failed:
            message = (case["message"] or "").splitlines()[0][:120]
            lines.append(f"| `{case['name']}` | {message} |")
        lines.append("")

    if skipped:
        lines += ["## Skips", "", "| Ability | Why |", "|---|---|"]
        for case in skipped:
            lines.append(
                f"| `{case['name']}` | {(case['message'] or 'n/a').splitlines()[0][:110]} |"
            )
        lines.append("")

    lines += ["## Sections", "", "| Section | Green | Failed | Skipped |", "|---|---|---|---|"]
    for title, prefix in SECTIONS:
        members = [c for c in cases if c["name"].startswith(prefix) or prefix in c["class"]]
        ok = sum(1 for c in members if c["status"] == "passed")
        bad = sum(1 for c in members if c["status"] == "failed")
        skip = sum(1 for c in members if c["status"] == "skipped")
        if members:
            lines.append(f"| {title} | {ok} | {bad} | {skip} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", default=f"/tmp/{MARKER}.xml", help="JUnit XML to (re)use")
    parser.add_argument("--no-run", action="store_true", help="render from an existing XML")
    args = parser.parse_args()
    xml_path = Path(args.xml)
    if not args.no_run:
        run_matrix(xml_path)
    cases = parse(xml_path)
    REPORT.write_text(render(cases), encoding="utf-8")
    print(f"wrote {REPORT} ({len(cases)} abilities)")
    return 1 if any(c["status"] == "failed" for c in cases) else 0


if __name__ == "__main__":
    sys.exit(main())
