"""Validate release version/build identity across pyproject, constants, and OTA manifest."""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def main() -> int:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "src"))
    from core.constants import APP_VERSION, BUILD_NUMBER

    project_version = str(pyproject["project"]["version"])
    project_build = str(pyproject["tool"]["flet"]["build_number"])
    build_version = os.environ.get("BUILD_VERSION", project_version)
    build_number = os.environ.get("BUILD_NUMBER", project_build)
    errors: list[str] = []

    if build_version != project_version:
        errors.append(f"BUILD_VERSION {build_version!r} != pyproject {project_version!r}")
    if project_version != APP_VERSION:
        errors.append(
            f"core.constants.APP_VERSION {APP_VERSION!r} != pyproject {project_version!r}"
        )
    if str(BUILD_NUMBER) != build_number:
        errors.append(f"core.constants.BUILD_NUMBER {BUILD_NUMBER} != BUILD_NUMBER {build_number}")
    if project_build != build_number:
        errors.append(f"tool.flet.build_number {project_build} != BUILD_NUMBER {build_number}")

    manifest_version = str(manifest["version"])
    if manifest_version == project_version:
        if str(manifest["build_number"]) != build_number:
            errors.append(
                f"version.json is synced to {manifest_version} but its build number "
                f"{manifest['build_number']} != {build_number}"
            )
    elif _version_tuple(manifest_version) < _version_tuple(project_version):
        print(
            f"NOTICE: version.json held back at {manifest_version} "
            f"(build {manifest['build_number']}) while app is {project_version}; "
            "this is allowed until the Play upload.",
            file=sys.stderr,
        )
    else:
        errors.append(f"version.json {manifest_version} is ahead of pyproject {project_version}")

    if errors:
        print("Release version drift:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Release identity consistent: {project_version} (build {build_number})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
