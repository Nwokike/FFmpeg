"""Update check service fetching remote version.json manifest."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from core.constants import BUILD_NUMBER, UPDATE_CONFIG_URL

logger = logging.getLogger("UpdateService")


class UpdateService:
    """Checks repository version.json for updates silently in the background."""

    @staticmethod
    async def check_for_updates() -> dict[str, Any] | None:
        """Fetch remote version.json and return data if a newer build exists."""
        try:
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                resp = await client.get(UPDATE_CONFIG_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    remote_build = int(data.get("build_number", 0))
                    if remote_build > BUILD_NUMBER:
                        logger.info(
                            "New update discovered: build %s > %s", remote_build, BUILD_NUMBER
                        )
                        return data
        except Exception as exc:
            logger.debug("Silent update check skipped: %s", exc)
        return None
