"""Update-dialog launch allowlist — remote markdown must not open arbitrary URLs."""

from __future__ import annotations

import pytest

from components.update_dialog import is_allowed_launch_url
from core.constants import GITHUB_RELEASE_URL, PLAYSTORE_URL


@pytest.mark.parametrize(
    "url",
    [
        GITHUB_RELEASE_URL,
        PLAYSTORE_URL,
        "https://github.com/Nwokike/FFmpeg/issues",
        "https://raw.githubusercontent.com/Nwokike/FFmpeg/main/version.json",
        "https://api.github.com/repos/Nwokike/FFmpeg",
    ],
)
def test_project_domains_are_allowed(url: str) -> None:
    assert is_allowed_launch_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/Nwokike/FFmpeg",  # plaintext downgrade
        "https://evil.example.com/github.com",  # suffix in path, different host
        "https://github.com.evil.example/",  # prefix-lookalike host
        "market://details?id=evil",  # Android market scheme
        "intent://scan/#Intent;scheme=zxing;end",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "ffmpeg://app/evil",
        "",
        "not a url",
    ],
)
def test_everything_else_is_blocked(url: str) -> None:
    assert is_allowed_launch_url(url) is False
