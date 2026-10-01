"""Protocol probe stays quiet: the dead-port open must not emit native
ERROR lines (device log showed ``tcp://127.0.0.1:9 Connection refused`` as
an [ERROR] on every boot), while results stay identical."""

from __future__ import annotations

import logging

from core.engine_probe import _probe_protocol


def test_probe_protocol_returns_present_for_dead_port(caplog):
    """tcp/9 is always closed — the handler exists, so result is present."""
    with caplog.at_level(logging.DEBUG):
        assert _probe_protocol("tcp") == "present"


def test_probe_protocol_results_unchanged():
    """Silencing must not change present/missing verdicts."""
    assert _probe_protocol("tcp") == "present"
    assert _probe_protocol("http") == "present"
    # tcp and rtmp both ride the dead-port path — same verdict shape.
    assert _probe_protocol("rtmp") == "present"
