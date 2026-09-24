"""AdMob ID manager — swaps test ↔ production IDs across the three files.

The three files that must always agree (CI's AdMob guard fails tag builds
while the Google test App ID is in pyproject):

  1. pyproject.toml   [tool.flet.android.meta_data] APPLICATION_ID
  2. src/core/constants.py   ADMOB_*_TEST / ADMOB_*_PROD values
  3. src/services/ad_service.py   USE_TEST_IDS flag

Usage:
  uv run python tools/admob.py check-ids
  uv run python tools/admob.py swap-ids --mode test
  uv run python tools/admob.py swap-ids --mode prod \
      --app-id ca-app-pub-XXXXXXXXXXXXXXXX~NNNNNNNNNN \
      --banner ca-app-pub-XXXXXXXXXXXXXXXX/NNNNNNNNNN \
      --interstitial ca-app-pub-XXXXXXXXXXXXXXXX/NNNNNNNNNN [--yes]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
CONSTANTS = ROOT / "src" / "core" / "constants.py"
AD_SERVICE = ROOT / "src" / "services" / "ad_service.py"

APP_ID_RE = re.compile(r"ca-app-pub-\d{16}~\d{10}")
UNIT_RE = re.compile(r"ca-app-pub-\d{16}/\d{10}")
TEST_APP_ID = "ca-app-pub-3940256099942544~3347511713"
TEST_BANNER = "ca-app-pub-3940256099942544/9214589741"
TEST_INTERSTITIAL = "ca-app-pub-3940256099942544/1033173712"


@click.group()
def cli() -> None:
    """Manage AdMob test/production IDs across the app."""


@cli.command("check-ids")
def check_ids() -> None:
    """Report which IDs are live in each of the three files."""
    proj = PYPROJECT.read_text(encoding="utf-8")
    consts = CONSTANTS.read_text(encoding="utf-8")
    svc = AD_SERVICE.read_text(encoding="utf-8")

    app_m = re.search(r'"com\.google\.android\.gms\.ads\.APPLICATION_ID"\s*=\s*"([^"]+)"', proj)
    app_id = app_m.group(1) if app_m else "(missing)"
    prod_banner = re.search(r'ADMOB_BANNER_UNIT_PROD\s*=\s*"([^"]*)"', consts)
    prod_inter = re.search(r'ADMOB_INTERSTITIAL_UNIT_PROD\s*=\s*"([^"]*)"', consts)
    flag = re.search(r"USE_TEST_IDS\s*=\s*(True|False)", svc)

    click.echo(f"pyproject APPLICATION_ID : {app_id}")
    click.echo(f"constants PROD banner   : {prod_banner.group(1) if prod_banner else '(missing)'}")
    click.echo(f"constants PROD interstitial: {prod_inter.group(1) if prod_inter else '(missing)'}")
    click.echo(f"ad_service USE_TEST_IDS : {flag.group(1) if flag else '(missing)'}")

    has_prod = bool(prod_banner and prod_banner.group(1))
    if app_id == TEST_APP_ID:
        click.secho(
            "MODE: TEST (safe for PR builds; v1.0.0 closed-test tags are allowed; later production tags fail)",
            fg="yellow",
        )
    elif has_prod and flag and flag.group(1) == "False":
        click.secho("MODE: PRODUCTION (release-ready)", fg="green")
    else:
        click.secho("MODE: INCONSISTENT — run swap-ids to align the three files", fg="red")


@cli.command("swap-ids")
@click.option("--mode", type=click.Choice(["test", "prod"]), required=True)
@click.option("--app-id", default=None, help="Production App ID (required for --mode prod)")
@click.option("--banner", default=None, help="Production banner unit (required for prod)")
@click.option(
    "--interstitial", default=None, help="Production interstitial unit (required for prod)"
)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
def swap_ids(
    mode: str, app_id: str | None, banner: str | None, interstitial: str | None, yes: bool
) -> None:
    """Write matching IDs into all three files atomically-ish (sequentially)."""
    if mode == "prod":
        for value, pattern, label in (
            (app_id, APP_ID_RE, "--app-id"),
            (banner, UNIT_RE, "--banner"),
            (interstitial, UNIT_RE, "--interstitial"),
        ):
            if not value or not pattern.fullmatch(value):
                raise click.ClickException(f"--mode prod requires a valid {label} (got {value!r})")
    else:
        app_id, banner, interstitial = TEST_APP_ID, TEST_BANNER, TEST_INTERSTITIAL

    if not yes and not click.confirm(
        f"Overwrite AdMob IDs in pyproject/constants/ad_service with {mode.upper()} IDs?"
    ):
        raise click.Abort()

    # Transform ALL three files before writing any one of them — a pattern
    # miss in file 3 must not leave pyproject/constants already swapped.

    # 1) pyproject manifest id
    proj = _sub(
        PYPROJECT.read_text(encoding="utf-8"),
        r'("com\.google\.android\.gms\.ads\.APPLICATION_ID"\s*=\s*")([^"]+)(")',
        app_id,
        "pyproject APPLICATION_ID",
    )

    # 2) constants — PROD slots always receive the given values; in test mode
    #    the TEST slots are (re)written too. VALUES only, never symbol names:
    #    a str.replace over the *_TEST/*_PROD names renames the constants and
    #    silently corrupts the file.
    consts = CONSTANTS.read_text(encoding="utf-8")
    for name, value in (
        ("ADMOB_APP_ID_PROD", app_id),
        ("ADMOB_BANNER_UNIT_PROD", banner),
        ("ADMOB_INTERSTITIAL_UNIT_PROD", interstitial),
    ):
        consts = _sub(
            consts,
            rf'({name}\s*=\s*")([^"]*)(")',
            value,
            f"constants {name}",
        )
    if mode == "test":
        for name, value in (
            ("ADMOB_APP_ID_TEST", TEST_APP_ID),
            ("ADMOB_BANNER_UNIT_TEST", TEST_BANNER),
            ("ADMOB_INTERSTITIAL_UNIT_TEST", TEST_INTERSTITIAL),
        ):
            consts = _sub(
                consts,
                rf'({name}\s*=\s*")([^"]*)(")',
                value,
                f"constants {name}",
            )

    # 3) ad_service flag
    svc = _sub_flag(
        AD_SERVICE.read_text(encoding="utf-8"),
        r"(USE_TEST_IDS\s*=\s*)(True|False)",
        "True" if mode == "test" else "False",
        "USE_TEST_IDS",
    )

    # Every transform succeeded — commit.
    PYPROJECT.write_text(proj, encoding="utf-8")
    CONSTANTS.write_text(consts, encoding="utf-8")
    AD_SERVICE.write_text(svc, encoding="utf-8")

    click.secho(f"Swapped to {mode.upper()} IDs in:", fg="green")
    for p in (PYPROJECT, CONSTANTS, AD_SERVICE):
        click.echo(f"  - {p.relative_to(ROOT)}")


def _sub(text: str, pattern: str, replacement: str, label: str) -> str:
    """Rewrite the value inside the FIRST match of a quoted-value pattern.

    The pattern must expose group(1)=prefix through the opening quote,
    group(2)=the value, group(3)=the closing quote. Older versions of this
    helper re-emitted group(2) AFTER the replacement (``False`` + ``True``
    → ``FalseTrue``), which wrote a file that failed to import with a
    NameError the next time the app started.
    """
    new, n = re.subn(
        pattern,
        lambda m: f"{m.group(1)}{replacement}{m.group(3)}",
        text,
        count=1,
    )
    if n != 1:
        raise click.ClickException(f"Could not locate {label} for replacement")
    return new


def _sub_flag(text: str, pattern: str, replacement: str, label: str) -> str:
    """Rewrite a bare (unquoted) value in the first match: group(1)=prefix."""
    new, n = re.subn(pattern, rf"\g<1>{replacement}", text, count=1)
    if n != 1:
        raise click.ClickException(f"Could not locate {label} for replacement")
    return new


if __name__ == "__main__":
    sys.exit(cli())
