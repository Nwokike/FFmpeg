"""M0 device-spike CLI: `uv run python spike.py`.

Prints the full engine capability report + runs the synthetic transcode
self-test. Run on the dev machine AND on-device (from the packaged app's
Engine Info screen logic) to answer every [UNVERIFIED-DEVICE] flag.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.engine_probe import run

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    probe_result, transcode_result = run()
    print("\n════════ M0 SPIKE REPORT ════════")
    print(probe_result.to_text())
    print("\n── synthetic transcode self-test ──")
    for key, value in transcode_result.items():
        print(f"{key}: {value}")
    sys.exit(0 if transcode_result.get("ok") else 1)
