"""Version drift guard: pyproject ↔ version.json ↔ changelog ↔ runtime constants.

Ported from the CollabShell pattern — these four must never disagree at release.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from core.changelog import CHANGELOG, notes_for
from core.constants import APP_VERSION, BUILD_NUMBER

ROOT = Path(__file__).resolve().parents[1]


def _load_pyproject() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)


def _load_version_json() -> dict:
    with open(ROOT / "version.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_pyproject_matches_version_json():
    proj = _load_pyproject()
    vjson = _load_version_json()
    assert proj["project"]["version"] == vjson["version"]
    assert proj["tool"]["flet"]["build_number"] == vjson["build_number"]


def test_runtime_constants_match_pyproject():
    proj = _load_pyproject()
    assert APP_VERSION == proj["project"]["version"]
    assert BUILD_NUMBER == proj["tool"]["flet"]["build_number"]


def test_changelog_has_entry_for_current_version():
    assert APP_VERSION in CHANGELOG
    notes = notes_for(APP_VERSION)
    assert notes and "unavailable" not in notes


def test_version_json_release_notes_are_real():
    vjson = _load_version_json()
    # Regression guard: the M0 scaffold note must never ship again
    assert "M0" not in vjson["release_notes"]
    assert "scaffold" not in vjson["release_notes"].lower()
    assert len(vjson["release_notes"]) > 80
