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
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _load_version_json() -> dict:
    with (ROOT / "version.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def test_pyproject_matches_version_json():
    proj = _load_pyproject()
    vjson = _load_version_json()
    assert proj["project"]["version"] == vjson["version"]
    assert proj["tool"]["flet"]["build_number"] == vjson["build_number"]


def test_runtime_constants_match_pyproject():
    proj = _load_pyproject()
    assert proj["project"]["version"] == APP_VERSION
    assert proj["tool"]["flet"]["build_number"] == BUILD_NUMBER


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


def test_admob_prod_live_agreement():
    """The 'prod-live?' question answered by pytest, not eyeballs.

    Mirrors the CI AdMob guard locally: tag builds must never serve test
    IDs, so the three PROD units + manifest App ID + USE_TEST_IDS=False
    must agree here first.
    """
    import services.ad_service as ad_module
    from core.constants import (
        ADMOB_APP_ID_PROD,
        ADMOB_BANNER_UNIT_PROD,
        ADMOB_INTERSTITIAL_UNIT_PROD,
    )

    assert ad_module.AdService.USE_TEST_IDS is False
    assert ADMOB_APP_ID_PROD and "3940256099942544" not in ADMOB_APP_ID_PROD
    assert ADMOB_BANNER_UNIT_PROD and "3940256099942544" not in ADMOB_BANNER_UNIT_PROD
    assert ADMOB_INTERSTITIAL_UNIT_PROD and "3940256099942544" not in ADMOB_INTERSTITIAL_UNIT_PROD
    assert ADMOB_BANNER_UNIT_PROD.startswith(ADMOB_APP_ID_PROD.split("~")[0])
    assert ADMOB_INTERSTITIAL_UNIT_PROD.startswith(ADMOB_APP_ID_PROD.split("~")[0])

    proj = _load_pyproject()
    manifest_app_id = proj["tool"]["flet"]["android"]["meta_data"][
        "com.google.android.gms.ads.APPLICATION_ID"
    ]
    assert manifest_app_id == ADMOB_APP_ID_PROD
    manifest_block = (
        (ROOT / "pyproject.toml")
        .read_text(encoding="utf-8")
        .split("meta_data")[1]
        .split("[tool.flet.android.permission]")[0]
    )
    assert "3940256099942544" not in manifest_block, "manifest meta_data block is prod-only"


def test_version_helpers_have_live_fallbacks():
    from core.versions import ffmpeg_version, pyav_major, pyav_version

    assert pyav_version() and ffmpeg_version() and pyav_major()
